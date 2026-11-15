"""Compute independently labelled D/PO AP from the frozen experiment scores."""
import csv
from collections import defaultdict
from pathlib import Path
import statistics
import sys

import numpy as np
from sklearn.metrics import average_precision_score

OUT = Path(__file__).resolve().parent
P = OUT.parent
sys.path.insert(0, str(P / 'heldout_v5_endpoint_replay_20261112'))
from evaluate import BOUNDARY, V4, V5, bind, load_module, read

SEEDS = (42, 1, 2)


def metrics(experiment, group, scores, recipe, seed, checkpoint, arm):
    for (view, kind), cases in sorted(group.items()):
        labels = [(lab, rows) for lab, rows in cases.values() if lab in ('positive', 'negative')]
        y = [lab == 'positive' for lab, _ in labels]
        pos, neg = sum(y), len(y) - sum(y)
        if pos and neg:
            s = [float(scores[rows].max()) for _, rows in labels]
            assert np.isfinite(s).all()
            ap = average_precision_score(y, s)
        else:
            ap = None
        yield dict(experiment=experiment, recipe=recipe if recipe != 'mixed' else view.rsplit('__ys_', 1)[1],
                   view=view, source=view.rsplit('__ys_', 1)[0], kind=kind, seed=seed,
                   checkpoint=checkpoint, arm=arm, n_pos=pos, n_neg=neg,
                   n_unknown=len(cases)-pos-neg, ap=ap)


def summarize(result):
    by_source = defaultdict(list)
    for r in result:
        key = tuple(r[x] for x in ('experiment', 'recipe', 'kind', 'seed', 'checkpoint', 'arm', 'source'))
        if r['ap'] is not None:
            by_source[key].append(r['ap'])
            if r['experiment'] != 'heldout_v5':
                by_source[(key[0], 'all', *key[2:])].append(r['ap'])
    by_seed = defaultdict(dict)
    for (*key, src), values in sorted(by_source.items()):
        by_seed[tuple(key)][src] = statistics.mean(values)
    agg = defaultdict(dict)
    for (experiment, recipe, kind, seed, checkpoint, arm), values in by_seed.items():
        agg[experiment, recipe, kind, checkpoint][seed, arm] = values
    for (experiment, recipe, kind, checkpoint), stats in sorted(agg.items()):
        arms = ('H', 'H_D') if experiment == 'legacy_H' else ('N', 'NC')
        assert len(stats) == len(SEEDS)*2
        panels = [set(x) for x in stats.values()]
        assert all(s == panels[0] for s in panels)
        a, b = ([statistics.mean(stats[seed, arm].values()) for seed in SEEDS] for arm in arms)
        d = [x-y for x,y in zip(b, a)]
        yield dict(experiment=experiment, recipe=recipe, kind=kind, checkpoint=checkpoint,
                   sources=len(panels[0]), arm_a=arms[0], arm_b=arms[1],
                   ap_a=statistics.mean(a), ap_b=statistics.mean(b),
                   delta=statistics.mean(d), delta_sd=statistics.stdev(d),
                   n_improved=sum(x > 1e-12 for x in d))


def write(name, data):
    data = list(data)
    with (OUT/name).open('w', encoding='utf-8', newline='') as f:
        out = csv.DictWriter(f, fieldnames=data[0])
        out.writeheader()
        out.writerows(data)


def main():
    panel = load_module('frozen_panel', P/'lcone_endpoint_overlap_20261112/audit.py')
    layouts, truth = panel.load()
    original = {k: np.load(BOUNDARY/f'inputs/trans_test/{k}.npy', mmap_mode='r')
                for k in ('y', 'trusted', 'physical')}
    results = []
    for seed in SEEDS:
        suffix = '' if seed == 42 else f'_s{seed}'
        for arm in ('N','NC'):
            with np.load(P/f'seed42_nc_ablation_20261109/{arm}{suffix}_scores.npz') as p:
                for point in ('best','last'):
                    results.extend(metrics('unified_G0', truth, p['test_'+point], 'mixed', seed, point, arm))
        for arm in ('H','H_D'):
            for point in ('best','last'):
                with np.load(P/f'legacy_h_cone_20261115/{seed}_{arm}_{point}_margin.npz') as p:
                    results.extend(metrics('legacy_H', truth, p['test'], 'mixed', seed, point, arm))
    for recipe in ('abc','aig','nand'):
        fold = 'ys_'+recipe
        with np.load(V4/f'{fold}_test_map.npz') as packed:
            test = {k: packed[k] for k in ('rows', 'old2new', 'new2old', 'y', 'trusted', 'physical')}
            cases, views = bind(recipe, layouts, truth, test, original)
            assert len(views) == 5
            for seed in SEEDS:
                for arm in ('N','NC'):
                    run = V5/fold/arm
                    if seed != 42:
                        run /= f'seed{seed}'
                    for point in ('best','last'):
                        if seed == 42:
                            path = P/f'heldout_recipe_v5_eval2_20261109/{fold}_{arm}_{point}_testpred.npz'
                            with np.load(path) as p:
                                idx = np.searchsorted(p['rows'], test['rows'])
                                assert np.array_equal(p['rows'][idx], test['rows'])
                                assert all(np.array_equal(p[k][idx], test[k]) for k in original)
                                s = p['scores'][idx]
                        else:
                            with np.load(run/f'{point}_pred.npz') as p:
                                assert np.array_equal(p['test_rows'], test['rows'])
                                s = p['test']
                        results.extend(metrics('heldout_v5', cases, s, recipe, seed, point, arm))
    assert len(results) == 24 * len(truth) + 360
    write('BY_VIEW.csv', results)
    write('SUMMARY.csv', summarize(results))


if __name__ == '__main__':
    main()
