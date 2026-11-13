"""Check the per-batch auxiliary cap and independent validation directions."""
import csv
import itertools
import math
import sys
from collections import defaultdict

import numpy as np
import torch

from audit import BOUNDARY, CACHE, OUT, P, V5, load_module, read, sha, write_csv, write_json
from pilot_preflight import ACTIVE_STEPS, cone_terms, grad_vector
from run_pilot import CONTRACT, FOLDS, RUNS, cuda_graph

RATIO = 0.1
LOSS_KEYS = {'NC-BCE': 'bce', 'NC-Rank': 'rank'}


def capped_weight(weight, node_norm, auxiliary_norm):
    """Detached auxiliary coefficient before the common global clip."""
    if not all(math.isfinite(v) and v >= 0 for v in (weight, node_norm, auxiliary_norm)):
        raise ValueError('invalid gradient norm or coefficient')
    return min(weight, RATIO * node_norm / auxiliary_norm) if auxiliary_norm else weight


def validation_evidence():
    path = P / 'lcone_endpoint_frozen_20261112/EVIDENCE.json'
    labels = {(r['view'], r['cone_id']): r['status'] for r in read(path)['endpoints']
              if r['split'] == 'val' and r['kind'] == 'D' and r['status'] in ('positive', 'negative')}
    layouts = {r['view']: r for r in read(BOUNDARY / 'input_contract.json')['shared_inputs']['trans_val']['views']}
    by_view = defaultdict(lambda: defaultdict(list))
    with CACHE.open(encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            key = r['view'], r['cone_id']
            if r['split'] != 'val' or key not in labels:
                continue
            members = np.fromstring(r['phys_rows'], sep='|', dtype=np.int64)
            assert len(members) == int(r['n_phys']) and len(members)
            v = layouts[r['view']]
            assert np.all((members >= v['start']) & (members < v['physical_stop']))
            by_view[r['view']][labels.pop(key)].append(members)
    assert not labels
    return layouts, by_view, sha(path)


def bind_validation(fold, val, layouts, by_view):
    sources = defaultdict(list)
    for view, labels in sorted(by_view.items()):
        if view.endswith('__' + fold) or not (labels['positive'] and labels['negative']):
            continue
        v = layouts[view]
        assert np.all(val['old2new'][v['start']:v['stop']] >= 0)
        neg = val['old2new'][np.unique(np.concatenate(labels['negative']))]
        pos = [val['old2new'][x] for x in labels['positive']]
        assert all(np.all(r >= 0) and val['physical'][r].all() for r in (*pos, neg))
        sources[view.rsplit('__ys_', 1)[0]].append((view, pos, neg))
    assert sources
    return sources


def probe(model, T, state, orig, train, val, ids_o, ids_t, pairs, sources, loss_key, old_weight, step):
    params = tuple(model.parameters())
    model.load_state_dict(state, strict=True)
    model.train()
    T.seed(42+step)
    with torch.autocast('cuda', dtype=torch.bfloat16):
        lo = T.domain_loss(model(orig[0], orig[1]), orig[2], ids_o)
    og = grad_vector(lo, params)
    with torch.autocast('cuda', dtype=torch.bfloat16):
        logits = model(train[0], train[1])
        lt = T.domain_loss(logits, train[2], ids_t)
    score = logits.float()[:, 1] - logits.float()[:, 0]
    terms = dict(zip(('bce', 'rank'), cone_terms(score, pairs)))
    raw = grad_vector(terms[loss_key], params, retain=True)
    node = og + grad_vector(lt, params, retain=True)
    nr, ar = node.norm().item(), raw.norm().item()
    weight = capped_weight(old_weight, nr, ar)
    capped = grad_vector(weight*terms[loss_key], params)
    measured_ratio = capped.norm().item()/nr
    assert measured_ratio <= RATIO + .002 and nr > 0 and ar > 0
    # The mathematical limit uses the raw gradient norm. AMP may introduce rounding.
    ideal_cap = weight * raw
    assert ideal_cap.norm().item()/nr <= RATIO + 1e-7
    model.load_state_dict(state, strict=True)
    model.eval()
    with torch.autocast('cuda', dtype=torch.bfloat16):
        lg = model(val[0], val[1]).float()
        margin = lg[:, 1] - lg[:, 0]
    effects = []
    for i, (source, groups) in enumerate(sources.items()):
        gaps = [torch.stack([margin[p].amax() for p in pos]).mean() - margin[neg].amax()
                for _, pos, neg in groups]
        gap = torch.stack(gaps).mean()
        dv = grad_vector(gap, params, retain=(i+1 < len(sources)))
        effects.append(dict(source=source, views=len(groups), positive_endpoints=sum(len(p) for _, p, _ in groups),
                            gap=gap.detach().item(), node_projection=-torch.dot(dv, node).item(),
                            fixed_aux_projection=-torch.dot(dv, raw*old_weight).item(),
                            ideal_capped_aux_projection=-torch.dot(dv, ideal_cap).item(),
                            measured_capped_aux_projection=-torch.dot(dv, capped).item()))
    assert all(torch.equal(v.cpu(), state[k]) for k, v in model.state_dict().items())
    assert all(p.grad is None for p in params)
    return dict(old_weight=old_weight, capped_weight=weight, original_aux_to_node=old_weight*ar/nr,
                mathematical_aux_to_node=weight*ar/nr, measured_aux_to_node=measured_ratio,
                cap_active=weight < old_weight, effects=effects)


def main():
    assert capped_weight(.3, 2., 4.) == .05 and capped_weight(.3, 2., 0.) == .3
    assert torch.cuda.is_bf16_supported()
    io = load_module('v5_io', V5 / 'fold_io.py')
    module = load_module('v5_model', P / 'control_best200_20261104/evaluate.py')
    sys.path.insert(0, str(P / 'control_loader_po_20261105'))
    from supervision_loader import FiveGroupLoader
    loader = FiveGroupLoader()
    model = module.Model().cuda()
    contract = read(CONTRACT)
    layouts, by_view, truth_sha = validation_evidence()
    step = ACTIVE_STEPS[-1]
    diagnostics, rows, support = [], [], {}
    for fold in FOLDS:
        train, val = io.load_trans(fold), io.load_trans(fold, 'val')
        sources = bind_validation(fold, val, layouts, by_view)
        support[fold] = {s: [v for v, _, _ in entries] for s, entries in sources.items()}
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
            r = probe(model, module.T, state, *graphs, ids_o, ids_t, [plan['pool'][i] for i in pair_ids],
                      sources, key, plan['initial_gradient_matched_weights'][key], step)
            base = dict(fold=fold, arm=arm, point=point)
            rows.extend(dict(base, **e) for e in r.pop('effects'))
            diagnostics.append(dict(base, **r, checkpoint_sha256=sha(path)))
            print(base, r, flush=True)
        del graphs
    write_csv(OUT / 'CAP_VALIDATION_BY_SOURCE.csv', rows)
    write_json(OUT / 'CAP_VALIDATION.json', dict(diagnostics=diagnostics, validation_support=support,
               validation_evidence_sha256=truth_sha, train_step=step+1, gradient_cap=RATIO,
               optimizer_steps=0, sat_cec_calls=0, labels_modified=False, test_predictions_read=False))


if __name__ == '__main__':
    main()
