"""Validate the four-view s15850 k=6 full panel and cross-check against k4."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
T = ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables'
T4 = T / 'sat_s15850_round22'
T6 = T / 'sat_k6_s15850_round26'
PANEL = json.loads((T6 / 'panel.json').read_text(encoding='utf-8'))['panel']
PLAN = json.loads((T6 / 'plan.json').read_text(encoding='utf-8'))


def main():
    views = []
    for item in PLAN['views']:
        d = T6 / 'views' / item['view']
        rec = json.loads((d / (item['view'] + '.records.json')).read_text(encoding='utf-8'))
        real = np.load(d / 'real.npy')
        base = np.load(d / 'base_inputs.npz')
        cov = json.loads((d / 'coverage.json').read_text(encoding='utf-8'))
        assert len(rec) == len(real) == len(base['global_ids'])
        assert real.shape[1] == 19
        assert cov['test_labels_read'] is False
        views.append(dict(view=item['view'], records=len(rec),
                          covered=int((real[:, 18] > 0).sum()),
                          sat_queries=int(cov['actual_sat_queries']),
                          gate_passed=bool(cov['gate_passed'])))

    d4 = pd.read_csv(T4 / 'merged_s15850.csv')
    d6 = pd.read_csv(T6 / 'merged_s15850_k6.csv')
    feat = [c for c in d6.columns if c not in
            {'global_node', 'local_node', 'view', 'family', 'split', 'cell', 'driver_type',
             'target_role', 'k', 'status', 'nonlocal_cut', 'covered', 'label'}]
    nan = {c: int(pd.isna(d6[c]).sum()) for c in feat}
    assert not any(nan.values()), nan
    assert d6.global_node.is_unique
    assert int(d6.label.sum()) == int(d4[d4.view.isin(PANEL)].label.sum())
    assert int((d6.label.eq(1) & d6.covered).sum()) == int(d6.label.sum())
    assert d6.loc[d6.status.eq('eligible'), 'k'].between(1, 6).all()

    common = None
    frames = {}
    for k, d in (('k4', d4), ('k6', d6)):
        q = d[d.covered & d.status.eq('eligible') & d.view.isin(PANEL)]
        frames[k] = q.set_index(['view', 'global_node'])
        common = set(frames[k].index) if common is None else common & set(frames[k].index)
    common = common or set()
    a = frames['k4'].loc[sorted(common)]
    b = frames['k6'].loc[sorted(common)]
    out = dict(
        views=views,
        k6=dict(rows=len(d6), covered=int(d6.covered.sum()),
                positives=int(d6.label.sum()),
                positives_covered=int((d6.label.eq(1) & d6.covered).sum()),
                sat_queries=int(sum(x['sat_queries'] for x in views)),
                coverage=float(d6.covered.mean()), feature_nan=nan),
        cross_variant=dict(common_nodes=len(common),
                           same_labels=bool(np.array_equal(a.label.to_numpy(), b.label.to_numpy())),
                           same_covered=bool(np.array_equal(a.covered.to_numpy(), b.covered.to_numpy())),
                           k4_rows=len(frames['k4']), k6_rows=len(frames['k6'])),
        notes=['No training, no threshold tuning, no test labels.',
               'Full k6 on four s15850 injection views; no negative sampling.',
               'Four s15850 injection views: alpha/delta/epsilon/gamma.',
               'k6 gate_passed is false only because there is no val split.'])
    (T6 / 'validation.json').write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
