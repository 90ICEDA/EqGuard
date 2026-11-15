"""Label-blind circuit scores from saved task-one margins and physical cones."""
import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean

import numpy as np

OUT = Path(__file__).resolve().parent
P = OUT.parent
RUN = P / 'seed42_nc_ablation_20261109'


def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        yield from csv.DictReader(f)


def write(name, items):
    with (OUT / name).open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(items[0]))
        writer.writeheader()
        writer.writerows(items)


def pools():
    layout = {k: {} for k in ('val', 'test')}
    for r in rows(P / 'control_loader_po_20261105/view_dictionary.csv'):
        if r['key'] in ('trans_val', 'trans_test'):
            layout[r['key'].split('_')[1]][r['view']] = r
    pools = {k: defaultdict(dict) for k in layout}
    for split, file in [
            ('val', P / 'seed42_supervised_prep_20261109/CONE_CACHE_V2.csv'),
            ('test', RUN / 'CONE_CACHE_TEST.csv')]:
        physical = np.load(P / f'control_boundary_v3_20261104/inputs/trans_{split}/physical.npy')
        for r in rows(file):
            if r['split'] != split or r['kind'] not in ('D', 'PO') or int(r['n_phys']) == 0:
                continue
            view, cid = r['view'], r['cone_id']
            lo, hi = (int(layout[split][view][k]) for k in ('start', 'physical_stop'))
            a = np.fromstring(r['phys_rows'], dtype=np.int64, sep='|')
            assert len(a) == int(r['n_phys']) and np.all(np.diff(a) > 0)
            assert ((a >= lo) & (a < hi)).all() and physical[a].all()
            assert cid not in pools[split][view]
            pools[split][view][cid] = a
        assert set(pools[split]) == set(layout[split])
        for view, r in layout[split].items():
            lo, hi, stop = (int(r[k]) for k in ('start', 'physical_stop', 'stop'))
            assert physical[lo:hi].all() and not physical[hi:stop].any()
    return layout, pools


def score_view(score, group, lo, hi):
    winners = []
    ties = 0
    for a in group.values():
        local = score[a]
        top = a[local == local.max()]
        winners.append(int(top.min()))
        ties += len(top) > 1
    unique = sorted(set(winners))
    k = 5
    assert len(unique) >= k
    raw = np.sort(score[winners].astype(np.float64))
    dedup = np.sort(score[unique].astype(np.float64))
    node = np.sort(score[lo:hi].astype(np.float64))
    assert raw[-1] == dedup[-1]
    assert (dedup[-k:] <= raw[-k:]).all()
    return dict(node_max=node[-1], node_top5=node[-k:].mean(),
                endpoint_top5=raw[-k:].mean(), group_top5=dedup[-k:].mean(),
                endpoints=len(winners), groups=len(unique), tied_endpoint_max=ties)


def macro(rows, fn):
    sources = defaultdict(list)
    for row in rows:
        sources[row['source']].append(int(fn(row)))
    return mean(mean(x) for x in sources.values())


def main():
    layout, pool = pools()
    raw, summary, by_recipe = [], [], []
    for seed in (42, 1, 2):
        suffix = '' if seed == 42 else f'_s{seed}'
        for arm in ('N', 'NC'):
            with np.load(RUN / f'{arm}{suffix}_scores.npz') as z:
                for point in ('best', 'last'):
                    scored = {}
                    for split in layout:
                        m = z[f'{split}_{point}']
                        assert m.shape == (max(int(v['stop']) for v in layout[split].values()),)
                        assert np.isfinite(m).all()
                        scored[split] = [dict(seed=seed, arm=arm, point=point, split=split,
                                              view=view, source=v['source'], kind=v['kind'],
                                              recipe=v['recipe'], **score_view(
                                                  m, pool[split][view], int(v['start']),
                                                  int(v['physical_stop'])))
                                         for view, v in layout[split].items()]
                    for rule in ('node_max', 'node_top5', 'endpoint_top5', 'group_top5'):
                        val_pos = [r for r in scored['val'] if r['kind'] == 'trojan']
                        val_neg = [r for r in scored['val'] if r['kind'] == 'control']
                        candidates = sorted({r[rule] for r in val_pos}, reverse=True)
                        for target in ('recall90', 'zero_val_fpr'):
                            if target == 'recall90':
                                index = next(i for i, t in enumerate(candidates)
                                             if macro(val_pos, lambda r: r[rule] >= t) >= .90)
                                cut = candidates[index]
                                assert index == 0 or macro(val_pos, lambda r: r[rule] >= candidates[index-1]) < .90
                            else:
                                cut = np.nextafter(max(r[rule] for r in val_neg), np.inf)
                            result = dict(seed=seed, arm=arm, point=point, rule=rule,
                                          calibration=target, threshold=cut)
                            for split, views in scored.items():
                                for kind, metric in [('trojan', 'tpr'), ('control', 'fpr')]:
                                    sub = [r for r in views if r['kind'] == kind]
                                    for rec in ('all', *sorted({r['recipe'] for r in sub})):
                                        rr = sub if rec == 'all' else [r for r in sub if r['recipe'] == rec]
                                        alarms = sum(r[rule] >= cut for r in rr)
                                        rate = macro(rr, lambda r: r[rule] >= cut)
                                        if rec == 'all':
                                            result.update({f'{split}_{metric}': rate,
                                                           f'{split}_{metric}_count': alarms,
                                                           f'{split}_{metric}_den': len(rr)})
                                        by_recipe.append(dict(seed=seed, arm=arm, point=point, rule=rule,
                                                              calibration=target, split=split, recipe=rec,
                                                              kind=kind, count=alarms, views=len(rr), rate=rate))
                            raw.extend(dict(**r, rule=rule, calibration=target,
                                            threshold=cut, alarm=int(r[rule] >= cut))
                                       for views in scored.values() for r in views)
                            summary.append(result)
    write('ALARM.csv', summary)
    write('ALARM_BY_RECIPE.csv', by_recipe)
    write('ALARM_BY_VIEW.csv', raw)
    for arm in ('N', 'NC'):
        for point in ('best', 'last'):
            for rule in ('node_max', 'node_top5', 'endpoint_top5', 'group_top5'):
                for calibration in ('recall90', 'zero_val_fpr'):
                    rr = [r for r in summary if (r['arm'], r['point'], r['rule'], r['calibration'])
                          == (arm, point, rule, calibration)]
                    print(arm, point, rule, calibration,
                          [round(100 * mean(r[k] for r in rr), 2)
                           for k in ('val_tpr', 'val_fpr', 'test_tpr', 'test_fpr')])
    unique = [r for r in raw if r['rule'] == 'group_top5' and r['calibration'] == 'recall90']
    summary_grouping = {s: {k: {m: mean(r[m] for r in unique if r['split'] == s and r['kind'] == k)
                               for m in ('endpoints', 'groups', 'tied_endpoint_max')}
                            for k in ('control', 'trojan')} for s in layout}
    (OUT / 'GROUPING.json').write_text(json.dumps(summary_grouping, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
