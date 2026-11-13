"""Compare k=4 and k=6 feature audits on the identical 113 rs232 views."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables'
K4 = BASE / 'sat_k4_rs232_round23'
K6 = BASE / 'sat_k6_rs232_round23'
FEATS = ['change_on_comparable', 'max_input_influence', 'infeasible_fraction',
         'complete_restricted_domain', 'ones_on_forced', 'comparable_pair_fraction',
         'feasible_fraction', 'forced_fraction']


def auc(y, x):
    if len(np.unique(y)) < 2:
        return None
    return float(roc_auc_score(y, x))


def load(T, name):
    d = pd.read_csv(T / name)
    return d[d.covered & d.status.eq('eligible')].set_index('global_node')


d4 = load(K4, 'merged_rs232_k4.csv')
d6 = load(K6, 'merged_rs232_k6.csv')
assert d4.index.equals(d6.index)
assert (d4.label == d6.label).all()


def within(d):
    rows = []
    for v, m in d.groupby('view'):
        if m.label.nunique() < 2 or (m.label == 0).sum() < 10:
            continue
        for c in FEATS:
            rows.append(dict(view=v, feature=c, auc=auc(m.label, m[c])))
    z = pd.DataFrame(rows)
    return z.groupby('feature').auc.median().to_dict()


def matched(d):
    rows = []
    for (v, g), m in d.groupby(['view', 'driver_type']):
        p = m[m.label == 1]; n = m[m.label == 0]
        if len(p) == 0 or len(n) < 5:
            continue
        for c in FEATS:
            pv = p[c].to_numpy(float); nv = n[c].to_numpy(float)
            rows.append(dict(feature=c, win=float((pv[:, None] > nv[None, :]).mean())))
    z = pd.DataFrame(rows)
    return z.groupby('feature').win.median().to_dict()


w4, w6 = within(d4), within(d6)
m4, m6 = matched(d4), matched(d6)
rows = []
for c in FEATS:
    rows.append(dict(feature=c,
                     k4_auc=auc(d4.label, d4[c]), k6_auc=auc(d6.label, d6[c]),
                     auc_delta=(auc(d6.label, d6[c]) - auc(d4.label, d4[c])),
                     k4_within_view_median_auc=w4.get(c), k6_within_view_median_auc=w6.get(c),
                     k4_matched_view_gate_median_win=m4.get(c),
                     k6_matched_view_gate_median_win=m6.get(c)))
out = pd.DataFrame(rows)
out.to_csv(K6 / 'feature_diff' / 'k4_vs_k6.csv', index=False, encoding='utf-8-sig')
summary = dict(status='descriptive_no_training', rows_k4=len(d4), rows_k6=len(d6),
               positives=int(d4.label.sum()), queries_k4=844620, queries_k6=1382876,
               query_ratio=round(1382876 / 844620, 3),
               features=rows,
               notes=['Same global nodes, labels and covered mask in k4 and k6.',
                      'k_over_4 and k_over_8 are not directly comparable; excluded from this table.',
                      'Matched win is computed within view x driver_type; no model is trained.'])
(K6 / 'feature_diff' / 'k4_vs_k6_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
print(out.to_string(index=False))
