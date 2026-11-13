"""Compare hard and normalized smooth training pooling with no parameter updates."""
import argparse
import itertools
import math
import sys
from collections import Counter

import numpy as np
import torch
import torch.nn.functional as F

from audit import OUT, P, V5, load_module, read, sha, write_csv, write_json
from pilot_preflight import ACTIVE_STEPS, PAIR_MARGIN, cone_terms, grad_vector
from probe_gradient_cap import LOSS_KEYS, RATIO, bind_validation, capped_weight, validation_evidence
from run_pilot import CONTRACT, FOLDS, RUNS, cuda_graph

TAU = 1.0


def smooth_max(scores):
    return TAU * (torch.logsumexp(scores / TAU, dim=0) - math.log(scores.numel()))


def pooled_loss(scores, members, pair_count, key, pooling):
    pos, neg = torch.stack([pooling(scores[rows]) for rows in members]).split(pair_count)
    if key == 'rank':
        return F.softplus(PAIR_MARGIN + neg - pos).mean()
    return F.binary_cross_entropy_with_logits(torch.cat((pos, neg)),
                    torch.cat((torch.ones_like(pos), torch.zeros_like(neg))), pos_weight=scores.new_tensor(10.0))


def distribution(grad, members, score, soft):
    detached = score.detach()
    mass = grad.detach().abs()
    total = mass.sum().item()
    assert total > 0
    winner = [r[detached[r] == detached[r].max()] for r in members]
    counts = Counter(i for r in members for i in r.tolist())
    top_counts = Counter(i for r in winner for i in r.tolist())
    shared_high = sorted(i for i in top_counts if counts[i] > 1)
    common_winner = sorted(i for i in top_counts if top_counts[i] > 1)
    effective = []
    for r in members:
        v = detached[r]
        w = torch.softmax(v/TAU, dim=0) if soft else (v == v.max()).float()/(v == v.max()).sum()
        effective.append(1/w.square().sum().item())
    return dict(nonzero_members=int((mass > 0).sum()), effective_members_mean=float(np.mean(effective)),
                largest_node_fraction=mass.max().item()/total,
                all_hard_max_fraction=mass[sorted(top_counts)].sum().item()/total,
                shared_high_fraction=mass[shared_high].sum().item()/total,
                common_winner_fraction=mass[common_winner].sum().item()/total,
                shared_high_count=len(shared_high), common_winner_count=len(common_winner))


def probe(model, T, state, graphs, ids_o, ids_t, pairs, sources, loss_key, weight, step):
    orig, train, val = graphs
    params = tuple(model.parameters())
    model.load_state_dict(state, strict=True)
    model.train()
    T.seed(42+step)
    with torch.autocast('cuda', dtype=torch.bfloat16):
        lo = T.domain_loss(model(orig[0], orig[1]), orig[2], ids_o)
    go = grad_vector(lo, params)
    with torch.autocast('cuda', dtype=torch.bfloat16):
        logits = model(train[0], train[1])
        lt = T.domain_loss(logits, train[2], ids_t)
    node = go + grad_vector(lt, params, retain=True)
    node_norm = node.norm().item()
    score = logits.float()[:, 1] - logits.float()[:, 0]
    members = [torch.as_tensor(p[k], device='cuda') for k in ('pos_rows', 'neg_rows') for p in pairs]
    assert all(r.unique().numel() == r.numel() > 0 for r in members)
    g, stats = {}, {}
    for mode, pooling in (('hard', torch.amax), ('smooth', smooth_max)):
        loss = pooled_loss(score, members, len(pairs), loss_key, pooling)
        if mode == 'hard':
            expected = cone_terms(score, pairs)[0 if loss_key == 'bce' else 1]
            torch.testing.assert_close(loss, expected, rtol=0, atol=0)
        ds = torch.autograd.grad(loss, score, retain_graph=True)[0]
        info = distribution(ds, members, score, mode == 'smooth')
        raw = grad_vector(loss, params, retain=(mode == 'hard'))
        raw_norm = raw.norm().item()
        assert node_norm > 0 and raw_norm > 0
        coef = capped_weight(weight, node_norm, raw_norm)
        g[mode] = coef * raw
        ratio = g[mode].norm().item()/node_norm
        assert torch.isfinite(g[mode]).all() and ratio <= RATIO+1e-7
        stats[mode] = dict(**info, loss=loss.detach().item(), raw_norm=raw_norm, coefficient=coef,
                           aux_to_node=ratio)
    model.load_state_dict(state, strict=True)
    model.eval()
    with torch.autocast('cuda', dtype=torch.bfloat16):
        lg = model(val[0], val[1]).float()
        margin = lg[:, 1] - lg[:, 0]
    projections = []
    for i, (source, entries) in enumerate(sources.items()):
        gap = torch.stack([torch.stack([margin[p].amax() for p in pos]).mean() - margin[neg].amax()
                           for _, pos, neg in entries]).mean()
        dv = grad_vector(gap, params, retain=(i+1 < len(sources)))
        effects = {k: -torch.dot(dv, vec).item() for k, vec in g.items()}
        projections.append(dict(source=source, views=len(entries), gap=gap.detach().item(), **effects,
                                smooth_minus_hard=effects['smooth']-effects['hard']))
    assert all(torch.equal(v.cpu(), state[k]) for k, v in model.state_dict().items())
    assert all(p.grad is None for p in params)
    return stats, F.cosine_similarity(g['hard'], g['smooth'], dim=0).item(), projections


def sharing_sweep(model, T, io, contract):
    """Check all nand scheduled batches for the shared-winner premise."""
    fold = 'ys_nand'
    train = io.load_trans(fold)
    origin = io.load_orig('train', train['mean'], train['std'])
    x, e, _ = cuda_graph(train)
    ox, oe, _ = cuda_graph(origin)
    plan = contract['folds'][fold]
    rows = []
    for arm, point in itertools.product(LOSS_KEYS, ('best', 'last')):
        run = RUNS / fold / arm
        log = read(run / 'LOG.json')
        path = run / f'{point}.pt'
        assert log['checkpoints'][path.name] == sha(path)
        state = torch.load(path, map_location='cpu', weights_only=True)
        for step in ACTIVE_STEPS:
            ids = plan['schedule'][str(step)]
            assert log['logs'][step]['pairs'] == ids
            pairs = [plan['pool'][i] for i in ids]
            members = [torch.as_tensor(p[k], device='cuda') for k in ('pos_rows', 'neg_rows') for p in pairs]
            model.load_state_dict(state, strict=True)
            model.train()
            T.seed(42+step)
            with torch.no_grad(), torch.autocast('cuda', dtype=torch.bfloat16):
                model(ox, oe)
                logits = model(x, e).float()
                score = logits[:, 1] - logits[:, 0]
            score.requires_grad_(True)
            measures = {}
            for mode, fn in (('hard', torch.amax), ('smooth', smooth_max)):
                loss = pooled_loss(score, members, len(pairs), LOSS_KEYS[arm], fn)
                ds = torch.autograd.grad(loss, score)[0]
                measures[mode] = distribution(ds, members, score, mode == 'smooth')
            rows.append(dict(arm=arm, point=point, step=step+1, **{
                f'{mode}_{k}': v for mode, stats in measures.items() for k, v in stats.items()}))
        model.load_state_dict(state, strict=True)
        model.eval()
        assert all(torch.equal(v.cpu(), state[k]) for k, v in model.state_dict().items())
    assert len(rows) == 48 and all(p.grad is None for p in model.parameters())
    write_csv(OUT / 'SMOOTH_POOL_NAND_SHARING.csv', rows)
    print('nand batches', len(rows), 'with shared high', sum(bool(r['hard_shared_high_count']) for r in rows),
          'with common winner', sum(bool(r['hard_common_winner_count']) for r in rows), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sharing', action='store_true')
    args = parser.parse_args()
    same = torch.tensor([2., 2., 2.], requires_grad=True)
    torch.testing.assert_close(smooth_max(same), same.max())
    torch.testing.assert_close(torch.autograd.grad(smooth_max(same), same)[0], torch.ones(3)/3)
    assert torch.cuda.is_bf16_supported()
    io = load_module('v5_io', V5 / 'fold_io.py')
    module = load_module('v5_model', P / 'control_best200_20261104/evaluate.py')
    sys.path.insert(0, str(P / 'control_loader_po_20261105'))
    from supervision_loader import FiveGroupLoader
    loader = FiveGroupLoader()
    model = module.Model().cuda()
    contract = read(CONTRACT)
    if args.sharing:
        sharing_sweep(model, module.T, io, contract)
        return
    layouts, by_view, truth_sha = validation_evidence()
    step = ACTIVE_STEPS[-1]
    diagnostics, rows = [], []
    for fold in FOLDS:
        train, val = io.load_trans(fold), io.load_trans(fold, 'val')
        sources = bind_validation(fold, val, layouts, by_view)
        graphs = tuple(cuda_graph(d) for d in (io.load_orig('train', train['mean'], train['std']), train, val))
        o = np.array(loader.step('orig', 'G0', step).indices, copy=True)
        t, _ = io.step_indices(fold, step)
        ids_o, ids_t = (torch.as_tensor(x, device='cuda') for x in (o, t))
        plan = contract['folds'][fold]
        pair_ids = plan['schedule'][str(step)]
        for arm, point in itertools.product(LOSS_KEYS, ('best', 'last')):
            key = LOSS_KEYS[arm]
            run = RUNS / fold / arm
            path = run / f'{point}.pt'
            log = read(run / 'LOG.json')
            assert sha(path) == log['checkpoints'][path.name]
            assert log['logs'][step]['sample_sha256'] == [io.sha_ids(o), io.sha_ids(t)]
            assert log['logs'][step]['pairs'] == pair_ids
            state = torch.load(path, map_location='cpu', weights_only=True)
            stats, cosine, effects = probe(model, module.T, state, graphs, ids_o, ids_t,
                      [plan['pool'][i] for i in pair_ids], sources, key,
                      plan['initial_gradient_matched_weights'][key], step)
            base = dict(fold=fold, arm=arm, point=point)
            rows.extend(dict(base, **e) for e in effects)
            diagnostics.append(dict(base, **stats, gradient_cosine=cosine, checkpoint_sha256=sha(path)))
            print(base, stats, flush=True)
        del graphs
    write_csv(OUT / 'SMOOTH_POOL_BY_SOURCE.csv', rows)
    write_json(OUT / 'SMOOTH_POOL_PREFLIGHT.json', dict(diagnostics=diagnostics, tau=TAU,
               validation_evidence_sha256=truth_sha, train_step=step+1, gradient_cap=RATIO,
               optimizer_steps=0, sat_cec_calls=0, labels_modified=False, test_predictions_read=False))


if __name__ == '__main__':
    main()
