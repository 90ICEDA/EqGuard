"""Evaluate exact-rank C2 NC runs on the frozen endpoint panel."""
import argparse
import csv
import itertools
import statistics
import sys
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import average_precision_score

OUT = Path(__file__).resolve().parent
P = OUT.parent
sys.path.insert(0, str(P / 'c2_endpoint_replay_20261112'))
from replay import BOUNDARY, C2, FIELDS, bind_test, endpoint_metrics, load_module, read, sha, write_csv, write_json

FOLDS = ('ys_abc', 'ys_aig', 'ys_nand')
RUNS = {'zero': ('runs_p90_exact_zero', 'legacy'),
        'view_q25': ('runs_p90_exact_view_q25', 'view-q25')}


def certified_ap(group, margin):
    labels, scores = [], []
    for label, members in group.values():
        if label != 'unknown':
            labels.append(label == 'positive')
            scores.append(float(margin[members].max()))
    return float(average_precision_score(labels, scores)) if len(set(labels)) == 2 else None


def evaluate_fold(fold, seeds, model, layouts, truth, original, old_n):
    with np.load(C2 / f'{fold}_test.npz') as data:
        test = {key: data[key] for key in data.files}
    for split in ('train', 'val'):
        with np.load(C2 / f'{fold}_{split}.npz') as data:
            assert not any(v.endswith('__' + fold) for v in data['view'])
            assert {v.split('__')[0] for v in data['view']}.isdisjoint(v.split('__')[0] for v in test['view'])
            assert all(np.array_equal(test[k], data[k]) for k in ('mean', 'std'))
    cases = bind_test(fold, test, layouts, truth, original)
    assert len(cases) == 10
    x = test['x'].copy()
    x[:, 25:] = np.clip((x[:, 25:] - test['mean']) / test['std'], -10, 10)
    x = torch.as_tensor(x, device='cuda')
    edge = torch.as_tensor(test['edge'], device='cuda')
    rows, scores, runs, sample_hashes = [], {}, {}, {}
    for seed, anchor in itertools.product(seeds, RUNS):
        directory, mode = RUNS[anchor]
        run = C2 / directory / f'{fold}_NC_s{seed}'
        log = read(run / 'LOG.json')
        ev = read(run / 'EVAL.json')
        assert (log['fold'], log['arm'], log['seed'], log['rank_mode'], log['anchor_mode']) == (fold, 'NC', seed, 'exact', mode)
        assert [r['step'] for r in log['logs']] == list(range(1, 201)) and all(r['finite'] for r in log['logs'])
        choice = max((r for r in log['logs'] if 'val_ap' in r), key=lambda r: r['val_ap'])
        assert (log['best_step'], log['best_score']) == (choice['step'], choice['val_ap'])
        if 'orig_sample_sha256' in log['logs'][0]:
            sample_hashes[seed, anchor] = [(r['orig_sample_sha256'], r['trans_sample_sha256']) for r in log['logs']]
        run_key = f'{anchor}_s{seed}'
        runs[run_key] = dict(anchor=anchor, seed=seed, log_sha256=sha(run / 'LOG.json'),
                             best_step=choice['step'], checkpoints={})
        for point in ('best', 'last'):
            path = run / f'{point}_resume.pt'
            state = torch.load(path, map_location='cpu', weights_only=True)
            assert (state['fold'], state['arm'], state['seed'], state['completed'], state['best_step']) == (fold, 'NC', seed, 200, choice['step'])
            optimizer_steps = sorted({int(v['step']) for v in state['optimizer']['state'].values()})
            if point == 'last':
                assert optimizer_steps == [200]
            elif (seed, anchor) in sample_hashes:
                assert optimizer_steps == [choice['step']]
            model.load_state_dict(state['model'], strict=True)
            with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
                logits = model(x, edge).float()
                margin = (logits[:, 1] - logits[:, 0]).cpu().numpy()
            assert np.isfinite(margin).all()
            assert all(torch.equal(v.cpu(), state['model'][k]) for k, v in model.state_dict().items())
            aps = []
            for a, b in zip(test['start'], test['stop']):
                trusted = test['trusted'][a:b]
                y = test['y'][a:b][trusted]
                if np.unique(y).size > 1:
                    aps.append(average_precision_score(y, margin[a:b][trusted]))
            ap = float(np.mean(aps))
            assert abs(ap - ev[point]['test_node_ap']) < 0.001, (point, ap, ev[point])
            runs[run_key]['checkpoints'][point] = dict(sha256=sha(path), test_node_ap=ap,
                                                       saved_test_node_ap=ev[point]['test_node_ap'], val_ap=ev[point]['val_ap'],
                                                       recall_at_fpr=ev[point]['recall_at_fpr'],
                                                       optimizer_steps=optimizer_steps,
                                                       optimizer_matches_model_step=optimizer_steps == [choice['step'] if point == 'best' else 200])
            scores[f'{fold}_{run_key}_{point}'] = margin
            for (view, kind), group in sorted(cases.items()):
                rows.append(dict(fold=fold, seed=seed, anchor=anchor, point=point, view=view, kind=kind,
                                 cone_ap=certified_ap(group, margin), **endpoint_metrics(group, margin)))

    keyed = {(r['seed'], r['anchor'], r['point'], r['view'], r['kind']): r for r in rows}
    paired, by_seed, macro, node, n_hashes = [], [], [], [], {}
    for seed, point in itertools.product(seeds, ('best', 'last')):
        old_run = C2 / 'runs_p90' / f'{fold}_N_s{seed}' / 'EVAL.json'
        n_result = read(old_run)[point]
        n_ap = n_result['test_node_ap']
        if seed not in n_hashes:
            n_hashes[seed] = sha(old_run)
        zero_ap, q25_ap = (runs[f'{a}_s{seed}']['checkpoints'][point]['test_node_ap'] for a in RUNS)
        node.append(dict(fold=fold, seed=seed, point=point, N=n_ap, zero=zero_ap, q25=q25_ap,
                         delta=q25_ap-zero_ap, q25_minus_N=q25_ap-n_ap, recall_at_fpr={
                             'N': n_result['recall_at_fpr'], **{a: runs[f'{a}_s{seed}']['checkpoints'][point]['recall_at_fpr']
                                                              for a in RUNS}}))
        for kind in ('D', 'PO'):
            group = []
            for view, typ in cases:
                if typ != kind:
                    continue
                zero, q25 = (keyed[seed, a, point, view, kind] for a in RUNS)
                n = old_n[seed, point, view, kind]
                assert all(zero[k] == q25[k] == int(n[k]) for k in ('positive', 'negative', 'unknown'))
                if zero['positive']:
                    pair = dict(fold=fold, seed=seed, point=point, kind=kind, view=view, positive=zero['positive'])
                    assert zero['cone_ap'] is not None and q25['cone_ap'] is not None
                    pair.update(zero_cone_ap=zero['cone_ap'], q25_cone_ap=q25['cone_ap'],
                                delta_cone_ap=q25['cone_ap']-zero['cone_ap'])
                    for field in FIELDS:
                        n_metric = float(n[field])
                        pair.update({f'N_{field}': n_metric, f'zero_{field}': zero[field], f'q25_{field}': q25[field],
                                     f'delta_{field}': q25[field] - zero[field],
                                     f'q25_minus_N_{field}': q25[field] - n_metric})
                    group.append(pair)
            assert len(group) == (4 if kind == 'D' else 5)
            paired.extend(group)
            tags = ('N', 'zero', 'q25', 'delta', 'q25_minus_N')
            by_seed.append(dict(fold=fold, seed=seed, point=point, kind=kind, sources=len(group),
                                cone_ap={tag: statistics.mean(r[f'{tag}_cone_ap'] for r in group)
                                         for tag in ('zero', 'q25', 'delta')}, **{
                k: {tag: statistics.mean(row[f'{tag}_{k}'] for row in group) for tag in tags} for k in FIELDS}))
    for point, kind in itertools.product(('best', 'last'), ('D', 'PO')):
        group = [r for r in by_seed if r['point'] == point and r['kind'] == kind]
        macro.append(dict(fold=fold, point=point, kind=kind, sources=group[0]['sources'],
                          cone_ap={tag: statistics.mean(r['cone_ap'][tag] for r in group)
                                   for tag in ('zero', 'q25', 'delta')}, **{
            k: {tag: statistics.mean(row[k][tag] for row in group) for tag in tags} for k in FIELDS}))
    for seed in seeds:
        if (fold, seed) == ('ys_nand', 42):
            assert not any((seed, a) in sample_hashes for a in RUNS)
        else:
            assert sample_hashes[seed, 'zero'] == sample_hashes[seed, 'view_q25']
    assert len(rows) == 40 * len(seeds) and len(paired) == 18 * len(seeds)
    assets = [C2 / f'{fold}_{k}.npz' for k in ('train', 'val', 'test', 'sup')]
    assets.append(OUT / f'{fold}_cones.npz')
    return rows, paired, scores, dict(runs=runs, macro=macro, by_seed=by_seed, node=node,
                                     audited_sample_pairs=len(sample_hashes)//2, historical_n_eval_hashes=n_hashes,
                                     asset_hashes={p.name: sha(p) for p in assets})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--all', action='store_true')
    args = parser.parse_args()
    folds, seeds = (FOLDS, (42, 1, 2)) if args.all else (('ys_nand',), (42,))
    model_type = load_module('c2_model', P / 'control_best200_20261104/evaluate.py').Model
    panel = load_module('c2_panel', P / 'lcone_endpoint_overlap_20261112/audit.py')
    layouts, truth = panel.load()
    files = dict(x='x39', y='y', physical='physical', trusted='trusted', edge='edge_index')
    original = {k: np.load(BOUNDARY / f'inputs/trans_test/{v}.npy', mmap_mode='r') for k, v in files.items()}
    model = model_type().cuda().eval().requires_grad_(False)
    old_scores = P / 'c2_endpoint_replay_20261112/BY_VIEW.csv'
    with old_scores.open(encoding='utf-8-sig', newline='') as f:
        old_n = {(int(r['seed']), r['point'], r['view'], r['kind']): r for r in csv.DictReader(f)
                 if r['variant'] == 'p90' and r['arm'] == 'N'}
    all_rows, all_paired, all_scores, summary = [], [], {}, {}
    for fold in folds:
        rows, paired, scores, result = evaluate_fold(fold, seeds, model, layouts, truth, original, old_n)
        all_rows.extend(rows)
        all_paired.extend(paired)
        all_scores.update(scores)
        summary[fold] = result
        print(f'{fold}: {len(rows)} endpoint records, {len(paired)} source pairs', flush=True)
    prefix = 'EXACT_ALL' if args.all else 'EXACT_RECHECK'
    write_csv(OUT / f'{prefix}_BY_VIEW.csv', all_rows)
    write_csv(OUT / f'{prefix}_PAIRED.csv', all_paired)
    with (OUT / f'{prefix}_MARGINS.npz').open('xb') as f:
        np.savez_compressed(f, **all_scores)
    inputs = [old_scores, P / 'lcone_endpoint_frozen_20261112/EVIDENCE.json']
    inputs += [P / f'control_v3_eligible_20261104/init_s{s}.pt' for s in seeds]
    write_json(OUT / f'{prefix}_RESULTS.json', dict(folds=summary, seeds=seeds,
               asset_hashes={p.name: sha(p) for p in inputs}, optimizer_steps_in_evaluation=0,
               sat_cec_calls=0, labels_modified=False))


if __name__ == '__main__':
    main()
