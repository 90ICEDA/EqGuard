"""Validate the four-view k=8 panel and cross-check against k4/k6."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
T = ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables'
T8 = T / 'sat_k8_rs232_round24'
PANEL = json.loads((T8 / 'panel.json').read_text(encoding='utf-8'))['panel']
PLAN = json.loads((T8 / 'plan.json').read_text(encoding='utf-8'))
OUT = {}


def merged(k):
    p = T / f'sat_k{k}_rs232_round23' / f'merged_rs232_k{k}.csv' if k in (4, 6) else T8 / 'merged_rs232_k8.csv'
    return pd.read_csv(p)


def main():
    rows = []
    for item in PLAN['views']:
        d = T8 / 'views' / item['view']
        rec = json.loads((d / (item['view'] + '.records.json')).read_text(encoding='utf-8'))
        real = np.load(d / 'real.npy')
        base = np.load(d / 'base_inputs.npz')
        cov = json.loads((d / 'coverage.json').read_text(encoding='utf-8'))
        assert len(rec) == len(real) == len(base['global_ids'])
        assert real.shape[1] == 19
        assert cov['test_labels_read'] is False
        rows.append(dict(view=item['view'], records=len(rec), covered=int((real[:, 18] > 0).sum()),
                         sat_queries=int(cov['actual_sat_queries']),
                         gate_passed=bool(cov['gate_passed'])))
    df = merged(8)
    feat = [c for c in df.columns if c not in
            {'global_node', 'local_node', 'view', 'family', 'split', 'cell', 'driver_type',
             'target_role', 'k', 'status', 'nonlocal_cut', 'covered', 'label'}]
    nan = {c: int(pd.isna(df[c]).sum()) for c in feat}
    assert not any(nan.values()), nan
    assert df.global_node.is_unique
    assert int(df.label.sum()) == 37
    assert int((df.label.eq(1) & df.covered).sum()) == 37
    assert df.loc[df.status.eq('eligible'), 'k'].between(1, 8).all()
    # Cross-variant panel comparison: same global nodes, labels, covered.
    common = None
    frames = {}
    for k in (4, 6, 8):
        d = merged(k)
        d = d[d.covered & d.status.eq('eligible') & d.view.isin(PANEL)]
        frames[k] = d.set_index(['view', 'global_node'])
        common = set(frames[k].index) if common is None else common & set(frames[k].index)
    common = common or set()
    labels = []
    covered = []
    for k in (4, 6, 8):
        q = frames[k].loc[sorted(common)]
        labels.append(q.label.to_numpy())
        covered.append(q.covered.to_numpy())
    OUT['views'] = rows
    OUT['merged'] = dict(rows=len(df), covered=int(df.covered.sum()), positives=int(df.label.sum()),
                         positives_covered=int((df.label.eq(1) & df.covered).sum()),
                         sat_queries=int(sum(x['sat_queries'] for x in rows)),
                         coverage=float(df.covered.mean()), feature_nan=nan)
    OUT['cross_variant'] = dict(common_nodes=len(common), same_labels=all(np.array_equal(labels[0], x) for x in labels[1:]),
                               same_covered=all(np.array_equal(covered[0], x) for x in covered[1:]),
                               k4_rows=len(frames[4]), k6_rows=len(frames[6]), k8_rows=len(frames[8]))
    OUT['notes'] = ['No training, no threshold tuning, no test labels.',
                    'k8 panel has 4 train views; all labels are posthoc.',
                    'k8 gate_passed is false only because there is no val split.']
    (T8 / 'validation.json').write_text(json.dumps(OUT, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(OUT, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
