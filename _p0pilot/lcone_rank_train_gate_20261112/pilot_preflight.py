"""Freeze and check a shared-pool D loss pilot. No optimizer or holdout reads."""
import csv
import sys
from collections import Counter, defaultdict

import numpy as np
import torch
import torch.nn.functional as F

from audit import OUT, P, V5, load_module, read, read_panel, sha, write_json

FOLDS = ('ys_abc', 'ys_nand')
ACTIVE_STEPS = tuple(range(0, 192, 16))
PAIR_MARGIN = 0.5
GRADIENT_FRACTION = 0.1


def get_margin(model, data):
    with torch.autocast('cuda', dtype=torch.bfloat16):
        logits = model(torch.as_tensor(data['x'], device='cuda'), torch.as_tensor(data['edge'], device='cuda'))
    return logits, logits.float()[:, 1] - logits.float()[:, 0]


def maximum_rows(margin, ids):
    values = margin[ids]
    return tuple(int(i) for i in ids[values == values.max()])


def freeze_pool(candidates, panel, old_to_new, reference):
    buckets = defaultdict(list)
    duplicates = []
    signatures = set()
    for r in candidates:
        view, p, n = (r[k] for k in ('view', 'positive', 'negative'))
        pos, neg = (panel[view][k] for k in (p, n))
        assert (pos[0], neg[0]) == ('positive', 'negative')
        pglob, nglob = pos[1], neg[1]
        pids, nids = (old_to_new[a] for a in (pglob, nglob))
        assert np.all(pids >= 0) and np.all(nids >= 0)
        pp, nn = (maximum_rows(reference, a) for a in (pids, nids))
        assert abs(float(reference[pids].max()) - float(r['positive_score'])) < 0.03
        assert abs(float(reference[nids].max()) - float(r['negative_score'])) < 0.03
        assert reference[pids].max() < reference[nids].max() and not set(pp).intersection(nn)
        signature = (r['source'], tuple(sorted(pp)), tuple(sorted(nn)))
        info = dict(r, pos_rows=pids.tolist(), neg_rows=nids.tolist(),
                    reference_pos_argmax=list(pp), reference_neg_argmax=list(nn))
        if signature in signatures:
            duplicates.append({k: r[k] for k in ('view', 'positive', 'negative')})
            continue
        signatures.add(signature)
        buckets[r['source']].append(info)
    assert len(buckets) == 2 and all(buckets.values())
    pool = []
    schedule_by_source = []
    for source, pairs in sorted(buckets.items()):
        ids = list(range(len(pool), len(pool)+len(pairs)))
        pool.extend(pairs)
        schedule_by_source.append(ids)
    schedule = {step: [ids[i % len(ids)] for ids in schedule_by_source] for i, step in enumerate(ACTIVE_STEPS)}
    return pool, schedule, duplicates


def grad_vector(loss, params, retain=False):
    grads = torch.autograd.grad(loss, params, allow_unused=True, retain_graph=retain)
    return torch.cat([(torch.zeros_like(p) if g is None else g).detach().float().reshape(-1)
                      for p, g in zip(params, grads)])


def cone_terms(margin, pairs):
    pos = torch.stack([margin[r['pos_rows']].amax() for r in pairs])
    neg = torch.stack([margin[r['neg_rows']].amax() for r in pairs])
    bce = F.binary_cross_entropy_with_logits(torch.cat((pos, neg)),
                    torch.cat((torch.ones_like(pos), torch.zeros_like(neg))), pos_weight=margin.new_tensor(10.0))
    rank = F.softplus(PAIR_MARGIN + neg - pos).mean()
    return bce, rank


def probe(model, T, io, loader, init, fold, train, orig, step, pairs, history):
    model.load_state_dict(init, strict=True)
    model.train()
    T.seed(42 + step)
    ids_o = np.array(loader.step('orig', 'G0', step).indices, copy=True)
    ids_t, comp = io.step_indices(fold, step)
    for name, ids in (('orig', ids_o), ('trans', ids_t)):
        assert io.sha_ids(ids) == history[step][name + '_sha']
    params = tuple(model.parameters())
    original_logits, _ = get_margin(model, orig)
    lo = T.domain_loss(original_logits, torch.as_tensor(orig['y'], device='cuda'), torch.as_tensor(ids_o, device='cuda'))
    og = grad_vector(lo, params)
    logits, margin = get_margin(model, train)
    lt = T.domain_loss(logits, torch.as_tensor(train['y'], device='cuda'), torch.as_tensor(ids_t, device='cuda'))
    bce, rank = cone_terms(margin, pairs)
    node_grad = og + grad_vector(lt, params, retain=True)
    bce_gradient = grad_vector(bce, params, retain=True)
    rank_gradient = grad_vector(rank, params)
    assert all(torch.isfinite(g).all() and g.norm().item() > 0 for g in (node_grad, bce_gradient, rank_gradient))
    actual = margin.detach().cpu().numpy()
    shared = [len(set(maximum_rows(actual, np.array(r['pos_rows']))) & set(maximum_rows(actual, np.array(r['neg_rows']))))
              for r in pairs]
    assert all(p.grad is None for p in params)
    assert all(torch.equal(v.detach().cpu(), init[k]) for k, v in model.named_parameters())
    model.load_state_dict(init, strict=True)
    model.eval()
    assert all(torch.equal(v.cpu(), init[k]) for k, v in model.state_dict().items())
    norms = dict(node=node_grad.norm().item(), bce=bce_gradient.norm().item(), rank=rank_gradient.norm().item())
    return dict(step=step+1, node_loss=float(lo.detach()+lt.detach()), bce=float(bce.detach()), rank=float(rank.detach()),
                norms=norms, bce_rank_gradient_cosine=F.cosine_similarity(bce_gradient, rank_gradient, dim=0).item(),
                shared_positive_negative_max=shared, node_sample_counts=[len(ids_o), *comp],
                node_sample_sha256=[io.sha_ids(ids_o), io.sha_ids(ids_t)])


def main():
    assert 'ginvenv_gpu' in sys.executable and torch.cuda.is_bf16_supported()
    _, panel = read_panel(verified=True)
    model_source = load_module('v5_model', P / 'control_best200_20261104/evaluate.py')
    io = load_module('v5_io', V5 / 'fold_io.py')
    sys.path.insert(0, str(P / 'control_loader_po_20261105'))
    from supervision_loader import FiveGroupLoader

    loader = FiveGroupLoader()
    model = model_source.Model().cuda().eval()
    candidates = OUT / 'VERIFIED_HARD_PAIR_CANDIDATES.csv'
    with candidates.open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    init_path = P / 'control_v3_eligible_20261104/init_s42.pt'
    init = torch.load(init_path, map_location='cpu', weights_only=True)
    results = {}
    for fold in FOLDS:
        train = io.load_trans(fold)
        orig = io.load_orig('train', train['mean'], train['std'])
        checkpoint = V5 / fold / 'N/best.pt'
        model.load_state_dict(torch.load(checkpoint, map_location='cpu', weights_only=True), strict=True)
        with torch.inference_mode():
            _, ref = get_margin(model, train)
        pool, schedule, duplicates = freeze_pool([r for r in rows if r['fold'] == fold], panel, train['old2new'], ref.cpu().numpy())
        history = read(checkpoint.parent / 'LOG.json')['logs']
        probes = [probe(model, model_source.T, io, loader, init, fold, train, orig, step,
                        [pool[i] for i in schedule[step]], history) for step in ACTIVE_STEPS[:2]]
        norms = probes[0]['norms']
        weights = {k: GRADIENT_FRACTION*norms['node']/norms[k] for k in ('bce', 'rank')}
        results[fold] = dict(pool=pool, schedule=schedule, duplicate_reference_argmax_pairs=duplicates,
                             exposures=dict(Counter(i for ids in schedule.values() for i in ids)), probes=probes,
                             initial_gradient_matched_weights=weights, reference_checkpoint_sha256=sha(checkpoint),
                             train_map_sha256=sha(io.V4 / f'{fold}_train_map.npz'))
        print(fold, 'retained', len(pool), 'argmax duplicates', len(duplicates), 'weights', weights,
              'probes', probes, flush=True)
    write_json(OUT / 'PILOT_PREFLIGHT.json', dict(folds=results, init_sha256=sha(init_path),
              candidate_sha256=sha(candidates), active_steps_zero_based=ACTIVE_STEPS, pair_margin=PAIR_MARGIN,
              gradient_fraction=GRADIENT_FRACTION, node_steps=200, optimizer_steps=0, sat_cec_calls=0,
              labels_modified=False, holdout_predictions_read=False))


if __name__ == '__main__':
    main()
