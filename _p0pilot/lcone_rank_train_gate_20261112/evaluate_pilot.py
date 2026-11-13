"""Replay all six trained pilot arms on the same frozen v5 held-out panel."""
import argparse
import itertools
import statistics

import numpy as np
import torch
from sklearn.metrics import average_precision_score

from audit import BOUNDARY, OUT, P, V5, load_module, read, sha, write_csv, write_json
from capped_backward import CAP_RATIO
from replay import FIELDS, endpoint_metrics
from run_pilot import ARMS, CAPPED_ARM, CONTRACT, FOLDS, INIT, RUNS


def verify_run(log, folder, fold, arm, plan):
    assert (log['fold'], log['arm'], log['seed']) == (fold, arm, 42)
    assert log['contract_sha256'] == sha(CONTRACT) and log['init_sha256'] == sha(INIT)
    steps = log['logs']
    assert [r['step'] for r in steps] == list(range(1, 201))
    expected = [[i for i in plan['schedule'].get(str(k), [])] if arm != 'N' else [] for k in range(200)]
    assert [r['pairs'] for r in steps] == expected
    assert all((r['aux_loss'] is not None) == bool(ids) for r, ids in zip(steps, expected))
    key = {'NC-BCE': 'bce', 'NC-Rank': 'rank', CAPPED_ARM: 'bce'}.get(arm)
    assert log['aux_weight'] == (plan['initial_gradient_matched_weights'][key] if key else 0.0)
    if arm == CAPPED_ARM:
        assert log['cap_ratio'] == CAP_RATIO
        assert all(('gradient_cap' in r) == bool(ids) for r, ids in zip(steps, expected))
        assert all(0 <= r['gradient_cap']['aux_to_node'] <= CAP_RATIO for r in steps if 'gradient_cap' in r)
    assert all(sha(folder / p) == h for p, h in log['checkpoints'].items())
    best = max((r for r in steps if 'val_ap' in r), key=lambda r: r['val_ap'])
    assert (best['step'], best['val_ap']) == (log['best_step'], log['best_val_ap'])
    return [r['sample_sha256'] for r in steps]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--capped', action='store_true')
    parser.add_argument('--frozen-baselines', action='store_true')
    args = parser.parse_args()
    if args.frozen_baselines and not args.capped:
        parser.error('--frozen-baselines requires --capped')
    arms = ('N', 'NC-BCE', CAPPED_ARM) if args.capped else ARMS
    tag = 'Cap' if args.capped else 'Rank'
    prefix = 'PILOT_CAPPED_FROZEN' if args.frozen_baselines else ('PILOT_CAPPED' if args.capped else 'PILOT')
    frozen_paths = {'baseline': OUT / 'PILOT_TEST_MARGINS.npz', 'candidate': OUT / 'PILOT_CAPPED_TEST_MARGINS.npz'}
    stored = {}
    if args.frozen_baselines:
        for key, path in frozen_paths.items():
            with np.load(path) as data:
                stored[key] = {name: data[name] for name in data.files}
    contract = read(CONTRACT)
    panel = load_module('endpoint_panel', P / 'lcone_endpoint_overlap_20261112/audit.py')
    prior = load_module('endpoint_v5', P / 'heldout_v5_endpoint_replay_20261112/evaluate.py')
    io = load_module('pilot_io', V5 / 'fold_io.py')
    layouts, truth = panel.load()
    original = {k: np.load(BOUNDARY / f'inputs/trans_test/{k}.npy', mmap_mode='r')
                for k in ('y', 'trusted', 'physical')}
    model = None
    if not stored:
        model_type = load_module('pilot_model', P / 'control_best200_20261104/evaluate.py').Model
        model = model_type().cuda().eval().requires_grad_(False)
    endpoint_rows, node_rows, scores, meta = [], [], {}, {}
    for fold in FOLDS:
        test = io.load_trans(fold, 'test')
        cases, slices = prior.bind(fold.removeprefix('ys_'), layouts, truth, test, original)
        if model is not None:
            x, edge = (torch.as_tensor(test[k], device='cuda') for k in ('x', 'edge'))
        sample = {}
        for arm in arms:
            folder = RUNS / fold / arm
            log = read(folder / 'LOG.json')
            sample[arm] = verify_run(log, folder, fold, arm, contract['folds'][fold])
            meta[f'{fold}/{arm}'] = {k: log[k] for k in ('best_step', 'best_val_ap', 'aux_weight', 'seconds', 'checkpoints')}
            for point in ('best', 'last'):
                key = f'{fold}_{arm}_{point}'
                if stored:
                    margin = stored['candidate' if arm == CAPPED_ARM else 'baseline'][key]
                else:
                    weights = torch.load(folder / f'{point}.pt', map_location='cpu', weights_only=True)
                    model.load_state_dict(weights, strict=True)
                    with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
                        logits = model(x, edge).float()
                        margin = (logits[:, 1] - logits[:, 0]).cpu().numpy()
                    assert all(torch.equal(v.cpu(), weights[k]) for k, v in model.state_dict().items())
                assert margin.shape == test['rows'].shape and np.isfinite(margin).all()
                scores[key] = margin
                step = log['best_step'] if point == 'best' else 200
                for view, sl in slices.items():
                    mask = test['trusted'][sl]
                    y = test['y'][sl][mask]
                    assert np.unique(y).size == 2
                    node_rows.append(dict(fold=fold, arm=arm, point=point, step=step, view=view,
                                          node_ap=average_precision_score(y, margin[sl][mask])))
                for (view, kind), group in sorted(cases.items()):
                    endpoint_rows.append(dict(fold=fold, arm=arm, point=point, step=step, view=view, kind=kind,
                                              **endpoint_metrics(group, margin)))
        assert sample[arms[0]] == sample[arms[1]] == sample[arms[2]]
        print(f'{fold}: all three arms and sample hashes verified', flush=True)
    keyed = {(r['fold'], r['point'], r['kind'], r['view'], r['arm']): r for r in endpoint_rows}
    paired, macro = [], []
    for fold, point, kind in itertools.product(FOLDS, ('best', 'last'), ('D', 'PO')):
        subset = [r for r in endpoint_rows if (r['fold'], r['point'], r['kind'], r['arm']) == (fold, point, kind, 'N') and r['positive']]
        assert len(subset) == (4 if kind == 'D' else 5)
        source_pairs = []
        for baseline in subset:
            view = baseline['view']
            items = [keyed[fold, point, kind, view, arm] for arm in arms]
            assert all(tuple(r[k] for k in ('positive', 'negative', 'unknown')) ==
                       tuple(baseline[k] for k in ('positive', 'negative', 'unknown')) for r in items)
            row = dict(fold=fold, point=point, kind=kind, view=view, positive=baseline['positive'])
            for m in FIELDS:
                n, bce, candidate = [r[m] for r in items]
                row.update({f'N_{m}': n, f'BCE_{m}': bce, f'{tag}_{m}': candidate,
                            f'{tag}_minus_N_{m}': candidate-n, f'{tag}_minus_BCE_{m}': candidate-bce})
            source_pairs.append(row)
        paired.extend(source_pairs)
        tags = ('N', 'BCE', tag, f'{tag}_minus_N', f'{tag}_minus_BCE')
        summary = {m: {k: statistics.mean(r[f'{k}_{m}'] for r in source_pairs) for k in tags} for m in FIELDS}
        macro.append(dict(fold=fold, point=point, kind=kind, sources=len(source_pairs), metrics=summary))
    node = [dict(fold=f, point=p, metrics={a: statistics.mean(r['node_ap'] for r in node_rows
                        if (r['fold'], r['point'], r['arm']) == (f, p, a)) for a in arms})
            for f, p in itertools.product(FOLDS, ('best', 'last'))]
    assert len(endpoint_rows) == 120 and len(paired) == 36 and len(node_rows) == 60
    write_csv(OUT / f'{prefix}_ENDPOINTS.csv', endpoint_rows)
    write_csv(OUT / f'{prefix}_SOURCE_PAIRS.csv', paired)
    write_csv(OUT / f'{prefix}_NODE_AP_BY_SOURCE.csv', node_rows)
    if not stored:
        with (OUT / f'{prefix}_TEST_MARGINS.npz').open('xb') as f:
            np.savez_compressed(f, **scores)
    write_json(OUT / f'{prefix}_RESULTS.json', dict(runs=meta, endpoint_macro=macro, node_macro=node,
               panel_sha256=sha(panel.FROZEN / 'EVIDENCE.json'), contract_sha256=sha(CONTRACT),
               optimizer_steps=1200, new_optimizer_steps=400 if args.capped else 1200,
               frozen_score_hashes={k: sha(v) for k, v in frozen_paths.items()} if stored else None,
               sat_cec_calls=0, labels_modified=False))


if __name__ == '__main__':
    main()
