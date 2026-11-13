"""Replay saved held-out v5 N/NC scores against frozen independent endpoints."""
import itertools
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import average_precision_score

OUT = Path(__file__).resolve().parent
P = OUT.parent
sys.path.insert(0, str(P / 'c2_endpoint_replay_20261112'))
from replay import BOUNDARY, endpoint_metrics, load_module, read, sha, summarize, write_csv, write_json

V5 = P / 'heldout_recipe_v5_20261109'
V4 = P / 'heldout_recipe_v4_20261109'
SEEDS = (42, 1, 2)


def bind(recipe, layouts, truth, test, original):
    rows = test['rows']
    assert np.all(np.diff(rows) > 0)
    assert np.array_equal(test['new2old'], rows)
    assert np.array_equal(test['old2new'][rows], np.arange(len(rows)))
    assert np.array_equal(np.flatnonzero(test['old2new'] >= 0), rows)
    for k in original:
        assert np.array_equal(test[k], original[k][rows]), k
    cases, slices = {}, {}
    for (view, kind), group in sorted(truth.items()):
        if not view.endswith('__ys_' + recipe):
            continue
        layout = layouts[view]
        start, stop = np.searchsorted(rows, [layout['start'], layout['stop']])
        assert np.array_equal(rows[start:stop], np.arange(layout['start'], layout['stop']))
        slices[view] = slice(start, stop)
        bound = {}
        for name, (label, members) in group.items():
            local = test['old2new'][members]
            assert np.all((local >= start) & (local < stop)) and test['physical'][local].all()
            assert np.array_equal(rows[local], members)
            bound[name] = (label, local)
        cases[view, kind] = bound
    assert len(slices) == 5 and len(cases) == 10
    return cases, slices


def main():
    panel = load_module('frozen_panel', P / 'lcone_endpoint_overlap_20261112/audit.py')
    layouts, truth = panel.load()
    original = {k: np.load(BOUNDARY / f'inputs/trans_test/{k}.npy', mmap_mode='r')
                for k in ('y', 'trusted', 'physical')}
    old_eval = P / 'heldout_recipe_v5_eval2_20261109/SEEDS3.json'
    reference = read(old_eval)
    outputs, records, audits, sensitivity = [], [], {}, []
    for recipe in ('abc', 'aig', 'nand'):
        fold = 'ys_' + recipe
        test_map = V4 / f'{fold}_test_map.npz'
        with np.load(test_map) as data:
            test = {k: data[k] for k in ('rows', 'old2new', 'new2old', 'y', 'trusted', 'physical')}
        cases, slices = bind(recipe, layouts, truth, test, original)
        audits[recipe] = dict(test_map_sha256=sha(test_map), heldout_views=sorted(slices), runs=[])
        for seed in SEEDS:
            sample_hashes = {}
            for arm in ('N', 'NC'):
                run = V5 / fold / arm
                if seed != 42:
                    run /= f'seed{seed}'
                log = read(run / 'LOG.json')
                assert (log['rec'], log['arm'], log.get('seed', 42)) == (fold, arm, seed)
                steps = log['logs']
                assert [r['step'] for r in steps] == list(range(1, 201)) and all(r['finite'] for r in steps)
                best = max((r for r in steps if 'val_ap' in r), key=lambda r: r['val_ap'])
                assert (best['step'], best['val_ap']) == (log['best_step'], log['best_score'])
                sample_hashes[arm] = [(r['orig_sha'], r['trans_sha']) for r in steps]
                for point in ('best', 'last'):
                    pred = run / f'{point}_pred.npz'
                    checkpoint = run / f'{point}{".pt" if seed == 42 else "_resume.pt"}'
                    with np.load(pred) as data:
                        assert np.array_equal(data['test_rows'], test['rows'])
                        native = data['test']
                    margin = native
                    scored_pred = pred
                    if seed == 42:
                        # SEEDS3 references the saved checkpoint replay on the full test graph.
                        scored_pred = old_eval.parent / f'{fold}_{arm}_{point}_testpred.npz'
                        with np.load(scored_pred) as data:
                            full_rows = data['rows']
                            assert np.all(np.diff(full_rows) > 0)
                            inds = np.searchsorted(full_rows, test['rows'])
                            assert np.array_equal(full_rows[inds], test['rows'])
                            assert all(np.array_equal(data[k][inds], test[k]) for k in original)
                            margin = data['scores'][inds]
                    assert margin.shape == test['rows'].shape and np.isfinite(margin).all()
                    source_ap = {}
                    ref = reference[f'{fold}_{arm}_{seed}_{point}']
                    for view, sl in slices.items():
                        source = view.rsplit('__ys_', 1)[0]
                        trusted = test['trusted'][sl]
                        ap = average_precision_score(test['y'][sl][trusted], margin[sl][trusted])
                        assert abs(ap - ref['heldout_src'][source]) < 1e-12, (fold, seed, arm, point, source, ap)
                        source_ap[source] = ap
                    assert abs(np.mean(list(source_ap.values())) - ref['heldout_macro']) < 1e-12
                    point_step = log['best_step'] if point == 'best' else 200
                    records.append(dict(fold=recipe, seed=seed, arm=arm, point=point,
                                        step=point_step, node_ap=ref['heldout_macro'], source_ap=source_ap))
                    audits[recipe]['runs'].append(dict(seed=seed, arm=arm, point=point,
                                                      native_prediction_sha256=sha(pred),
                                                      scored_prediction_sha256=sha(scored_pred),
                                                      checkpoint_sha256=sha(checkpoint)))
                    for (view, kind), group in cases.items():
                        metrics = endpoint_metrics(group, margin)
                        outputs.append(dict(variant='v5', fold=recipe, view=view, source=view.rsplit('__ys_', 1)[0],
                                            kind=kind, arm=arm, seed=seed, point=point, step=point_step,
                                            **metrics))
                        if seed == 42:
                            same = endpoint_metrics(group, native)
                            keys = ('top_5', 'recall_512', 'allpos_fp', 'allpos_gates')
                            changed = {k: [same[k], metrics[k]] for k in keys if same[k] != metrics[k]}
                            if changed:
                                sensitivity.append(dict(fold=recipe, arm=arm, point=point, view=view,
                                                        kind=kind, native_to_full=changed))
            assert sample_hashes['N'] == sample_hashes['NC']
        print(recipe, '12 predictions verified', flush=True)
    paired, aggregate = summarize(outputs)
    assert len(outputs) == 360 and len(paired) == 162 and len(aggregate) == 12
    by_ap = {(r['fold'], r['seed'], r['point'], r['arm']): r['node_ap'] for r in records}
    ap_pairs = []
    for fold, seed, point in itertools.product(('abc', 'aig', 'nand'), SEEDS, ('best', 'last')):
        n, nc = (by_ap[fold, seed, point, arm] for arm in ('N', 'NC'))
        ap_pairs.append(dict(fold=fold, seed=seed, point=point, N=n, NC=nc, delta=nc-n))
    write_csv(OUT / 'BY_VIEW.csv', outputs)
    write_csv(OUT / 'PAIRED_BY_SOURCE.csv', paired)
    write_json(OUT / 'SUMMARY.json', dict(aggregate=aggregate, node_ap_pairs=ap_pairs, audits=audits,
               seed42_native_vs_full_changes=sensitivity,
               original_node_eval_sha256=sha(old_eval), truth_sha256=sha(panel.FROZEN / 'EVIDENCE.json'),
               verified_sample_pairs=9, optimizer_steps=0, forward_passes=0, sat_cec_calls=0, labels_modified=False))


if __name__ == '__main__':
    main()
