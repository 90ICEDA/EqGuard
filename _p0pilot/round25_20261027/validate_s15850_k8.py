"""Validate the four-view s15850 k=8 panel and cross-check against k4."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
T = ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables'
T4 = T / 'sat_s15850_round22'
T8 = T / 'sat_k8_s15850_round25'
PANEL = json.loads((T8 / 'panel.json').read_text(encoding='utf-8'))['panel']
PLAN = json.loads((T8 / 'plan.json').read_text(encoding='utf-8'))


def main():
    views = []
    for item in PLAN['views']:
        d = T8 / 'views' / item['view']
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
    d8 = pd.read_csv(T8 / 'merged_s15850_k8.csv')
    feat = [c for c in d8.columns if c not in
            {'global_node', 'local_node', 'view', 'family', 'split', 'cell', 'driver_type',
             'target_role', 'k', 'status', 'nonlocal_cut', 'covered', 'label'}]
    nan = {c: int(pd.isna(d8[c]).sum()) for c in feat}
    assert not any(nan.values()), nan
    assert d8.global_node.is_unique
    assert int(d8.label.sum()) == int(d4[d4.view.isin(PANEL)].label.sum())
    assert int((d8.label.eq(1) & d8.covered).sum()) == int(d8.label.sum())
    assert d8.loc[d8.status.eq('eligible'), 'k'].between(1, 8).all()

    common = None
    frames = {}
    for k, d in (('k4', d4), ('k8', d8)):
        q = d[d.covered & d.status.eq('eligible') & d.view.isin(PANEL)]
        frames[k] = q.set_index(['view', 'global_node'])
        common = set(frames[k].index) if common is None else common & set(frames[k].index)
    common = common or set()
    a = frames['k4'].loc[sorted(common)]
    b = frames['k8'].loc[sorted(common)]
    out = dict(
        views=views,
        k8=dict(rows=len(d8), covered=int(d8.covered.sum()),
                positives=int(d8.label.sum()),
                positives_covered=int((d8.label.eq(1) & d8.covered).sum()),
                sat_queries=int(sum(x['sat_queries'] for x in views)),
                coverage=float(d8.covered.mean()), feature_nan=nan),
        cross_variant=dict(common_nodes=len(common),
                           same_labels=bool(np.array_equal(a.label.to_numpy(), b.label.to_numpy())),
                           same_covered=bool(np.array_equal(a.covered.to_numpy(), b.covered.to_numpy())),
                           k4_rows=len(frames['k4']), k8_rows=len(frames['k8'])),
        notes=['No training, no threshold tuning, no test labels.',
               'Bounded sample: all 40 positives + 300 stratified negatives per view.',
               'Four s15850 injection views: alpha/delta/epsilon/gamma.',
               'k8 coverage=10.3% is the sample fraction, not an extraction failure.',
               'k8 gate_passed is false only because there is no val split.'])
    (T8 / 'validation.json').write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
