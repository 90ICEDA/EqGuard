"""Extra Round 21 feature-audit tables (no training / no SAT)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import feature_diff as fd

OUT = fd.OUT
SELECTED = ['n_forced', 'n_forced_one', 'n_forced_zero',
            'input_change_fraction_mean', 'change_on_comparable',
            'max_input_influence', 'n_inputs_change_fraction_positive',
            'ones_on_forced', 'frac_infeasible']


def main():
    X, meta = fd.build_features()
    for col in ['driver', 'role', 'k', 'family']:
        rows = []
        for value, idx in meta[meta.covered].groupby(col).groups.items():
            z = meta.loc[idx]
            pos = int(z.y.sum())
            rows.append(dict({col: value}, covered_nodes=len(z), positives=pos,
                             negatives=int((z.y == 0).sum()),
                             positive_rate=float(pos / len(z))))
        pd.DataFrame(rows).to_csv(OUT / f'class_by_{col}.csv', index=False, encoding='utf-8-sig')

    base = (meta.covered & (meta.role == 'comb_output') & (meta.k == 4)).values
    rows = []
    for feature in SELECTED:
        a = X[feature].values.astype(float)
        p, n = a[base & (meta.y.values == 1)], a[base & (meta.y.values == 0)]
        rows.append(dict(scope='comb_k4', feature=feature, n_pos=len(p), n_neg=len(n),
                         pos_mean=float(p.mean()), neg_mean=float(n.mean()),
                         auc=fd.safe_auc(np.r_[np.ones(len(p)), np.zeros(len(n))], np.r_[p, n]),
                         smd=fd.smd(p, n)))
    for gate in ['INVX0', 'XOR2X1', 'MX2X1_RS', 'AND2X2', 'OR2X1']:
        m = base & (meta.driver.values == gate)
        yy = meta.y.values[m]
        for feature in SELECTED:
            a = X[feature].values.astype(float)[m]
            p, n = a[yy == 1], a[yy == 0]
            if len(p) >= 2 and len(n) >= 10:
                rows.append(dict(scope=gate, feature=feature, n_pos=len(p), n_neg=len(n),
                                 pos_mean=float(p.mean()), neg_mean=float(n.mean()),
                                 auc=fd.safe_auc(np.r_[np.ones(len(p)), np.zeros(len(n))], np.r_[p, n]),
                                 smd=fd.smd(p, n)))
    pd.DataFrame(rows).to_csv(OUT / 'feature_gate_k4.csv', index=False, encoding='utf-8-sig')

    rows = []
    for (family, gate, k, role), idx in meta[meta.covered & (meta.role == 'comb_output')].groupby(
            ['family', 'driver', 'k', 'role']).groups.items():
        z = meta.loc[idx]
        p = z.y.values == 1
        n = z.y.values == 0
        if p.sum() < 2 or n.sum() < 10:
            continue
        for feature in SELECTED:
            a = X[feature].values.astype(float)[idx]
            pp, nn = a[p], a[n]
            rows.append(dict(family=family, driver=gate, k=int(k), feature=feature,
                             n_pos=int(p.sum()), n_neg=int(n.sum()),
                             pos_mean=float(pp.mean()), neg_mean=float(nn.mean()),
                             auc=fd.safe_auc(np.r_[np.ones(len(pp)), np.zeros(len(nn))],
                                             np.r_[pp, nn])))
    pd.DataFrame(rows).to_csv(OUT / 'feature_matched_strata.csv', index=False, encoding='utf-8-sig')
    print(dict(status='extra_outputs_written', rows_gate=len(pd.read_csv(OUT / 'feature_gate_k4.csv')),
               rows_strata=len(pd.read_csv(OUT / 'feature_matched_strata.csv'))))


if __name__ == '__main__':
    main()
