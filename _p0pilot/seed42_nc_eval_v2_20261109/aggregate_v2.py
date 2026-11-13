"""Aggregate v2: A (val->test transfer) and B (test diagnostic) separated, paired mean/SD,
source-level and contributor analysis from saved margins."""
import csv
import json
from pathlib import Path

import numpy as np
from sklearn.metrics import average_precision_score

R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OLD = R / '_p0pilot/seed42_nc_ablation_20261109'
OUT = R / '_p0pilot/seed42_nc_eval_v2_20261109'
BOUND = json.loads((R / '_p0pilot/control_boundary_v3_20261104/input_contract.json').read_text(encoding='utf-8'))
SEEDS = [(42, ''), (1, '_s1'), (2, '_s2')]


def views_of(split):
    return {v['view']: v for v in BOUND['shared_inputs'][f'trans_{split}']['views']}


def view_aps(s, y, t, views):
    out = {}
    for v, lay in views.items():
        lo = lay['start']; hi = lo + (lay['old_stop'] - lay['old_start'])
        m = t[lo:hi]
        if m.sum() >= 2 and len(np.unique(y[lo:hi][m])) > 1:
            out[v] = float(average_precision_score(y[lo:hi][m], s[lo:hi][m]))
    return out


def main():
    d = json.loads((OUT / 'EVAL_V2_ALL.json').read_text(encoding='utf-8'))
    rows, per_seed = [], {}
    for seed, tag in SEEDS:
        pair = {}
        for point in ('best', 'last'):
            n = d[f'N_s{seed}_{point}']; c = d[f'NC_s{seed}_{point}']
            for key, getter in [
                ('trans_val_ap', lambda x: x['val']['ap_view']),
                ('trans_test_ap', lambda x: x['test']['ap_view']),
                ('trans_val_top1', lambda x: x['val']['top1']),
                ('trans_test_top1', lambda x: x['test']['top1']),
                ('trans_val_top5', lambda x: x['val']['top5']),
                ('trans_test_top5', lambda x: x['test']['top5']),
                ('normal_val_alarm', lambda x: x['normal_val']['alarm_fpr']),
                ('normal_test_alarm', lambda x: x['normal_test']['alarm_fpr']),
                ('normal_val_node_fpr', lambda x: x['normal_val']['trusted_normal_fpr']),
                ('normal_test_node_fpr', lambda x: x['normal_test']['trusted_normal_fpr']),
                ('coneD_test_fpr', lambda x: x['cones_test']['D']['fpr_at_thr']),
                ('conePO_test_fpr', lambda x: x['cones_test']['PO']['fpr_at_thr']),
            ]:
                a, b = getter(n), getter(c)
                if a is None or b is None:
                    continue
                pair.setdefault(f'{point}|{key}', []).append(b - a)
                rows.append(dict(seed=seed, point=point, metric=key, N=a, NC=b, delta=b - a))
            for k in ('0.8', '0.9', '0.95'):
                a = n['equal_recall']['A_val_transfer'][k]['test_fpr']
                b = c['equal_recall']['A_val_transfer'][k]['test_fpr']
                rows.append(dict(seed=seed, point=point, metric=f'A_test_fpr@{k}', N=a, NC=b, delta=b - a))
                a = n['equal_recall']['B_test_diagnostic'][k]['test_fpr']
                b = c['equal_recall']['B_test_diagnostic'][k]['test_fpr']
                rows.append(dict(seed=seed, point=point, metric=f'B_test_fpr@{k}', N=a, NC=b, delta=b - a))
        per_seed[seed] = pair
    agg = {}
    for r in rows:
        agg.setdefault(f"{r['point']}|{r['metric']}", []).append(r)
    summary = {}
    for k, rr in agg.items():
        ds = [x['delta'] for x in rr]; ns = [x['N'] for x in rr]; cs = [x['NC'] for x in rr]
        summary[k] = dict(n=len(ds), N=float(np.mean(ns)), NC=float(np.mean(cs)),
                          delta=float(np.mean(ds)), sd=float(np.std(ds, ddof=1)) if len(ds) > 1 else None)
    # contributor analysis (seed42 best, per view / source / role)
    zN = np.load(OLD / 'N_scores.npz'); zC = np.load(OLD / 'NC_scores.npz')
    yv, tv = zN['y_val'], zN['trust_val']
    apsN = view_aps(zN['val_best'], yv, tv, views_of('val'))
    apsC = view_aps(zC['val_best'], yv, tv, views_of('val'))
    contrib = [dict(view=v, N=apsN[v], NC=apsC[v], delta=apsC[v] - apsN[v],
                    source=v.split('__')[0]) for v in apsN if v in apsC]
    contrib.sort(key=lambda x: x['delta'], reverse=True)
    by_source = {}
    for c in contrib:
        by_source.setdefault(c['source'], []).append(c['delta'])
    src = [dict(source=s, views=len(v), mean_delta=float(np.mean(v))) for s, v in by_source.items()]
    (OUT / 'AGG_V2.json').write_text(json.dumps(dict(summary=summary, per_seed=per_seed), indent=2), encoding='utf-8')
    (OUT / 'CONTRIB_V2.json').write_text(json.dumps(dict(top_gain=contrib[:8], top_loss=contrib[-8:],
                                                          by_source=src), indent=2), encoding='utf-8')
    with (OUT / 'AGG_V2.csv').open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['metric', 'N', 'NC', 'delta', 'sd', 'n'])
        w.writeheader()
        for k, v in summary.items():
            w.writerow(dict(metric=k, **v))
    print('done', len(rows), 'rows', len(summary), 'summary')


if __name__ == '__main__':
    main()
