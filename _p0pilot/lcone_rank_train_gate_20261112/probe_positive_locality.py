"""Probe only the BCE positive membership change using existing checkpoints."""
import argparse
import sys
from collections import Counter

import torch
import torch.nn.functional as F

from audit import OUT, P, V5, load_module, read, read_panel, sha, write_csv, write_json
from pilot_preflight import ACTIVE_STEPS, cone_terms, grad_vector
from probe_gradient_cap import RATIO, bind_validation, capped_weight, validation_evidence
from run_pilot import CAPPED_ARM, CONTRACT, FOLDS, INIT, RUNS, cuda_graph, node_schedule


def membership_index(panel, pairs, globals_by_local):
    focus = {}
    for pair in pairs:
        view = pair['view']
        focus.setdefault(view, set()).update(int(globals_by_local[i]) for i in pair['pos_rows'])
    result = {}
    for view, nodes in focus.items():
        counts = {i: Counter() for i in nodes}
        for label, members in panel[view].values():
            for i in nodes.intersection(members):
                counts[i][label] += 1
        result[view] = counts
    return result


def probe(model, T, state, graphs, sample, pairs, masks, sources, weight, step, mapping, memberships):
    orig, train, val = graphs
    params = tuple(model.parameters())
    model.load_state_dict(state, strict=True)
    model.train()
    T.seed(42+step)
    ids_o, ids_t, _ = sample
    with torch.autocast('cuda', dtype=torch.bfloat16):
        lo = T.domain_loss(model(orig[0], orig[1]), orig[2], torch.as_tensor(ids_o, device='cuda'))
    go = grad_vector(lo, params)
    with torch.autocast('cuda', dtype=torch.bfloat16):
        logits = model(train[0], train[1])
        lt = T.domain_loss(logits, train[2], torch.as_tensor(ids_t, device='cuda'))
    node = go + grad_vector(lt, params, retain=True)
    nn = node.norm().item()
    margin = logits.float()[:, 1] - logits.float()[:, 0]
    negative = torch.stack([margin[p['neg_rows']].amax() for p in pairs])
    full = torch.stack([margin[p['pos_rows']].amax() for p in pairs])
    near = torch.stack([margin[m['near_positive_rows']].amax() for m in masks])
    losses = {}
    grads = {}
    stats = {}
    for key, positives in (('full', full), ('near', near)):
        labels = torch.cat((torch.ones_like(positives), torch.zeros_like(negative)))
        losses[key] = F.binary_cross_entropy_with_logits(torch.cat((positives, negative)), labels,
                                                         pos_weight=margin.new_tensor(10.))
        if key == 'full':
            torch.testing.assert_close(losses[key], cone_terms(margin, pairs)[0], atol=0, rtol=0)
        # Same negative maxima and loss normalization imply the same unweighted derivative on the negative logits.
        neg_grad = torch.autograd.grad(losses[key], negative, retain_graph=True)[0]
        raw = grad_vector(losses[key], params, retain=(key == 'full'))
        gn = raw.norm().item()
        assert nn > 0 and gn > 0
        scale = capped_weight(weight, nn, gn)
        grads[key] = scale * raw
        ratio = grads[key].norm().item()/nn
        if ratio > RATIO:
            grads[key] *= (RATIO/ratio) * (1-2*torch.finfo(torch.float32).eps)
            ratio = grads[key].norm().item()/nn
        assert torch.isfinite(grads[key]).all() and ratio <= RATIO
        stats[key] = dict(loss=losses[key].detach().item(), coefficient=scale, ratio=ratio,
                          negative_logits=negative.detach().tolist(), unweighted_negative_gradient=neg_grad.tolist())
    assert stats['full']['unweighted_negative_gradient'] == stats['near']['unweighted_negative_gradient']
    targets = []
    scores = margin.detach().cpu().numpy()
    for p, m in zip(pairs, masks):
        full_rows = p['pos_rows']
        near_rows = m['near_positive_rows']
        assert set(near_rows) <= set(full_rows)
        data = {}
        for key, ids in (('full', full_rows), ('near', near_rows)):
            mx = max(scores[i] for i in ids)
            g = [int(mapping[i]) for i in ids if scores[i] == mx]
            data[key] = dict(score=float(mx), winners=g, shares=[dict(memberships[p['view']][i]) for i in g])
        assert data['near']['score'] <= data['full']['score']
        targets.append(dict(source=p['source'], view=p['view'], endpoint=p['positive'], **data,
                            changed=set(data['full']['winners']) != set(data['near']['winners'])))
    model.load_state_dict(state, strict=True)
    model.eval()
    with torch.autocast('cuda', dtype=torch.bfloat16):
        lg = model(val[0], val[1]).float()
        score = lg[:, 1] - lg[:, 0]
    effects = []
    for i, (source, groups) in enumerate(sources.items()):
        gap = torch.stack([torch.stack([score[p].amax() for p in pos]).mean() - score[neg].amax()
                           for _, pos, neg in groups]).mean()
        dg = grad_vector(gap, params, retain=(i+1 < len(sources)))
        d = {k: -torch.dot(dg, g).item() for k, g in grads.items()}
        effects.append(dict(source=source, gap=gap.detach().item(), views=len(groups), **d,
                            near_minus_full=d['near']-d['full']))
    assert all(torch.equal(v.cpu(), state[k]) for k, v in model.state_dict().items())
    assert all(p.grad is None for p in params)
    return dict(stats=stats, targets=targets, gradient_cosine=F.cosine_similarity(grads['full'], grads['near'], dim=0).item()), effects


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cross-step', action='store_true')
    args = parser.parse_args()
    io = load_module('v5_io', V5 / 'fold_io.py')
    module = load_module('v5_model', P / 'control_best200_20261104/evaluate.py')
    sys.path.insert(0, str(P / 'control_loader_po_20261105'))
    from supervision_loader import FiveGroupLoader
    loader = FiveGroupLoader()
    model = module.Model().cuda()
    contract = read(CONTRACT)
    mask_path = OUT / 'D_LOCALITY_POSITIVE_MASK.json'
    mask = read(mask_path)
    assert mask['contract_sha256'] == sha(CONTRACT) and mask['hops'] == 2
    _, panel = read_panel(verified=True)
    layouts, val_evidence, truth_sha = validation_evidence()
    result, rows = [], []
    for fold in FOLDS:
        train, val = io.load_trans(fold), io.load_trans(fold, 'val')
        plan, near = contract['folds'][fold], mask['folds'][fold]
        assert sha(io.V4 / f'{fold}_train_map.npz') == near['train_map_sha256'] == plan['train_map_sha256']
        sources = bind_validation(fold, val, layouts, val_evidence)
        graphs = tuple(cuda_graph(g) for g in (io.load_orig('train', train['mean'], train['std']), train, val))
        schedule = node_schedule(io, loader, fold, train)
        by_pair = {r['pair_id']: r for r in near['masks']}
        memberships = membership_index(panel, plan['pool'], train['new2old'])
        run = RUNS / fold / CAPPED_ARM
        log = read(run / 'LOG.json')
        early, late = ACTIVE_STEPS[0], ACTIVE_STEPS[-1]
        steps = (('initialization', late), ('best', early), ('last', early)) if args.cross_step else (
            ('initialization', early), ('best', late), ('last', late))
        for point, step in steps:
            path = INIT if point == 'initialization' else run / f'{point}.pt'
            assert sha(path) == (contract['init_sha256'] if point == 'initialization' else log['checkpoints'][path.name])
            ids = plan['schedule'][str(step)]
            assert ids == log['logs'][step]['pairs'] and schedule[step][2] == log['logs'][step]['sample_sha256']
            state = torch.load(path, map_location='cpu', weights_only=True)
            base = dict(fold=fold, point=point, step=step+1)
            info, effects = probe(model, module.T, state, graphs, schedule[step], [plan['pool'][i] for i in ids],
                [by_pair[i] for i in ids], sources, plan['initial_gradient_matched_weights']['bce'],
                step, train['new2old'], memberships)
            rows.extend(dict(base, **r) for r in effects)
            result.append(dict(base, **info, checkpoint_sha256=sha(path)))
            print(base, 'changed', [p['changed'] for p in info['targets']], 'cosine', info['gradient_cosine'],
                  'full/near positive sources', [sum(r[k] > 0 for r in effects) for k in ('full', 'near')], flush=True)
        del graphs
    prefix = 'LOCAL_BCE_CROSS_STEP' if args.cross_step else 'LOCAL_BCE'
    write_csv(OUT / f'{prefix}_VAL_BY_SOURCE.csv', rows)
    write_json(OUT / f'{prefix}_PREFLIGHT.json', dict(diagnostics=result, mask_sha256=sha(mask_path),
               validation_evidence_sha256=truth_sha, gradient_cap=RATIO, optimizer_steps=0,
               sat_cec_calls=0, labels_modified=False, test_predictions_read=False))


if __name__ == '__main__':
    main()
