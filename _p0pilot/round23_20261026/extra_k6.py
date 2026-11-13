
# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

T = Path(_eqguard_path('10.15/06_统一评测协议/N4_三向泛化/tables/sat_k6_rs232_round23'))
d = pd.read_csv(T / 'merged_rs232_k6.csv')
d = d[d.covered & d.status.eq('eligible')].copy()
feats = ['k_over_8', 'infeasible_fraction', 'complete_restricted_domain',
         'max_input_influence', 'change_on_comparable', 'ones_on_forced',
         'feasible_fraction', 'comparable_pair_fraction']


def auc(m, c):
    if m.label.nunique() < 2:
        return None
    return round(float(roc_auc_score(m.label, m[c])), 4)


print('=== by k ===')
for k, m in d.groupby('k'):
    row = {'k': int(k), 'n': len(m), 'pos': int(m.label.sum()), 'neg': int((m.label == 0).sum())}
    row.update({c: auc(m, c) for c in feats})
    print(row)

print('=== by family ===')
for f, m in d.groupby('family'):
    row = {'family': f, 'n': len(m), 'pos': int(m.label.sum()), 'neg': int((m.label == 0).sum())}
    row.update({c: auc(m, c) for c in feats})
    print(row)

print('=== by driver ===')
for g, m in d.groupby('driver_type'):
    row = {'driver': g, 'n': len(m), 'pos': int(m.label.sum()), 'neg': int((m.label == 0).sum())}
    row.update({c: auc(m, c) for c in feats})
    print(row)

# Match on view + driver + k, i.e. compare within identical local support.
matched = []
for (v, g, k), m in d.groupby(['view', 'driver_type', 'k']):
    p = m[m.label == 1]; n = m[m.label == 0]
    if len(p) == 0 or len(n) < 5:
        continue
    for c in feats:
        pv = p[c].to_numpy(float); nv = n[c].to_numpy(float)
        matched.append(dict(feature=c, view=v, family=m.family.iloc[0], driver=g, k=int(k),
                            positives=len(p), negatives=len(n),
                            mean_diff=float((pv - nv.mean()).mean()),
                            win_rate=float((pv[:, None] > nv[None, :]).mean())))
matched = pd.DataFrame(matched)
matched.to_csv(T / 'feature_diff' / 'matched_same_view_driver_k.csv', index=False, encoding='utf-8-sig')
print('=== matched same view+driver+k ===')
for c, m in matched.groupby('feature'):
    print(c, 'comp', len(m), 'pos', int(m.positives.sum()),
          'median_diff', round(float(m.mean_diff.median()), 4),
          'median_win', round(float(m.win_rate.median()), 4),
          'frac_win>0.5', round(float((m.win_rate > 0.5).mean()), 4))
