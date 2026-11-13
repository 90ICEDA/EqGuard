"""Aggregate v3: per-seed and mean/SD for A/B, AP, normal, cones, and source x role."""
import json
import statistics as st
from pathlib import Path

import numpy as np

OUT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train\_p0pilot\seed42_nc_eval_v3_20261109')


def main():
    d = json.loads((OUT / 'EVAL_V3_ALL.json').read_text(encoding='utf-8'))
    rows = []
    for seed in (42, 1, 2):
        for point in ('best', 'last'):
            n = d[f'N_s{seed}_{point}']; c = d[f'NC_s{seed}_{point}']
            def add(name, a, b):
                if a is None or b is None:
                    return
                rows.append(dict(seed=seed, point=point, metric=name, N=a, NC=b, delta=b - a))
            add('val_ap', n['val']['ap_view'], c['val']['ap_view'])
            add('test_ap', n['test']['ap_view'], c['test']['ap_view'])
            add('val_top1', n['val']['top1'], c['val']['top1'])
            add('test_top1', n['test']['top1'], c['test']['top1'])
            add('val_normal_node_fpr', n['normal_val']['trusted_normal_fpr'], c['normal_val']['trusted_normal_fpr'])
            add('test_normal_node_fpr', n['normal_test']['trusted_normal_fpr'], c['normal_test']['trusted_normal_fpr'])
            add('test_normal_alarm', n['normal_test']['alarm_fpr'], c['normal_test']['alarm_fpr'])
            for k in ('0.8', '0.9', '0.95'):
                add(f'A_test_fpr@{k}', n['equal_recall']['A_val_transfer'][k]['test_fpr'],
                    c['equal_recall']['A_val_transfer'][k]['test_fpr'])
                add(f'B_test_fpr@{k}', n['equal_recall']['B_test_diagnostic'][k]['test_fpr'],
                    c['equal_recall']['B_test_diagnostic'][k]['test_fpr'])
                add(f'B_test_recall@{k}', n['equal_recall']['B_test_diagnostic'][k]['test_recall'],
                    c['equal_recall']['B_test_diagnostic'][k]['test_recall'])
            for kind in ('D', 'PO'):
                add(f'cone{kind}_test_fpr', n['cones_test'][kind]['fpr_at_thr'], c['cones_test'][kind]['fpr_at_thr'])
    summary = {}
    for r in rows:
        summary.setdefault(f"{r['point']}|{r['metric']}", []).append(r)
    out = {}
    for k, rr in summary.items():
        ds = [x['delta'] for x in rr]
        out[k] = dict(n=len(ds), N=float(np.mean([x['N'] for x in rr])), NC=float(np.mean([x['NC'] for x in rr])),
                      delta=float(np.mean(ds)), sd=float(np.std(ds, ddof=1)) if len(ds) > 1 else None)
    # source x role macro over sources with support
    role_rows = {}
    for seed in (42, 1, 2):
        for point in ('best', 'last'):
            for arm in ('N', 'NC'):
                roles = d[f'{arm}_s{seed}_{point}']['val']['roles']
                for key, v in roles.items():
                    src, role = key.rsplit('|', 1)
                    role_rows.setdefault((src, role), []).append((seed, point, arm, v['recall'], v['mapped']))
    src_role = {}
    for (src, role), vals in role_rows.items():
        nN = [x[3] for x in vals if x[2] == 'N']; nC = [x[3] for x in vals if x[2] == 'NC']
        if nN and nC:
            src_role[f'{src}|{role}'] = dict(N=float(np.mean(nN)), NC=float(np.mean(nC)),
                                            delta=float(np.mean(nC) - np.mean(nN)), n=len(nN))
    (OUT / 'AGG_V3.json').write_text(json.dumps(dict(metrics=out, source_role=src_role), indent=2), encoding='utf-8')
    for k in ('best|test_ap', 'best|val_ap', 'best|A_test_fpr@0.95', 'best|B_test_fpr@0.95',
              'best|test_normal_node_fpr', 'best|test_normal_alarm', 'best|coneD_test_fpr', 'best|conePO_test_fpr'):
        print(k, {kk: (round(vv, 4) if isinstance(vv, float) else vv) for kk, vv in out[k].items()})
    print('source_role entries', len(src_role))


if __name__ == '__main__':
    main()
