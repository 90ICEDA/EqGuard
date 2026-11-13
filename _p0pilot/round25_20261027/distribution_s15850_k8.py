"""Feature-distribution audit for the four-view s15850 k=8 panel (no training)."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

ROOT = Path(__file__).resolve().parents[2]
T4 = ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables/sat_s15850_round22'
T8 = ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables/sat_k8_s15850_round25'
PANEL = json.loads((T8 / 'panel.json').read_text(encoding='utf-8'))['panel']
OUT = T8 / 'distribution'
OUT.mkdir(exist_ok=True)
COMMON = ['feasibility_known_fraction', 'feasible_fraction', 'forced_fraction',
          'undecided_fraction', 'infeasible_fraction', 'determinism_on_feasible',
          'determinism_valid', 'ones_on_forced', 'ones_valid',
          'comparable_pair_fraction', 'change_on_comparable', 'influence_valid',
          'max_input_influence', 'complete_full_domain',
          'complete_restricted_domain', 'partial_forcing', 'has_unknown']


def safe_auc(y, x):
    y = np.asarray(y, int); x = np.asarray(x, float)
    return None if len(np.unique(y)) < 2 else float(roc_auc_score(y, x))


def safe_ap(y, x):
    y = np.asarray(y, int); x = np.asarray(x, float)
    return None if len(np.unique(y)) < 2 else float(average_precision_score(y, x))


def stats(y, x):
    x = np.asarray(x, float); y = np.asarray(y, int)
    if len(x) == 0:
        return dict(n=0)
    return dict(n=int(len(x)), mean=float(x.mean()), std=float(x.std()),
                min=float(x.min()), q05=float(np.quantile(x, .05)),
                q25=float(np.quantile(x, .25)), median=float(np.median(x)),
                q75=float(np.quantile(x, .75)), q95=float(np.quantile(x, .95)),
                max=float(x.max()), zero=int((x == 0).sum()),
                nonzero=int((x != 0).sum()), auc=safe_auc(y, x), ap=safe_ap(y, x))


def load4():
    d = pd.read_csv(T4 / 'merged_s15850.csv')
    return d[d.covered & d.status.eq('eligible') & d.view.isin(PANEL)].copy()


def load8():
    d = pd.read_csv(T8 / 'merged_s15850_k8.csv')
    return d[d.covered & d.status.eq('eligible') & d.view.isin(PANEL)].copy()


def main():
    d4, d8 = load4(), load8()
    d4['k_over'] = d4['k_over_4']
    d8['k_over'] = d8['k_over_8']
    rows = []
    for variant, d in (('k4', d4), ('k8', d8)):
        for feat in COMMON + ['k_over']:
            for label_name, m in (('all', d), ('positive', d[d.label == 1]),
                                  ('negative', d[d.label == 0])):
                s = stats(m.label, m[feat]); s.update(variant=variant, feature=feat,
                                                      label=label_name)
                rows.append(s)
    overall = pd.DataFrame(rows)
    overall.to_csv(OUT / 'distribution_overall.csv', index=False, encoding='utf-8-sig')

    fam = []
    for variant, d in (('k4', d4), ('k8', d8)):
        for family, m in d.groupby('family'):
            for feat in COMMON + ['k_over']:
                p = m[m.label == 1]; n = m[m.label == 0]
                fam.append(dict(
                    variant=variant, family=family, feature=feat,
                    positives=len(p), negatives=len(n),
                    pos_mean=float(p[feat].mean()) if len(p) else None,
                    neg_mean=float(n[feat].mean()) if len(n) else None,
                    pos_median=float(p[feat].median()) if len(p) else None,
                    neg_median=float(n[feat].median()) if len(n) else None,
                    pos_zero=int((p[feat] == 0).sum()),
                    neg_zero=int((n[feat] == 0).sum()),
                    auc=safe_auc(m.label, m[feat]), ap=safe_ap(m.label, m[feat])))
    pd.DataFrame(fam).to_csv(OUT / 'distribution_by_family.csv', index=False, encoding='utf-8-sig')

    drv = []
    for variant, d in (('k4', d4), ('k8', d8)):
        for (family, driver), m in d.groupby(['family', 'driver_type']):
            p = m[m.label == 1]; n = m[m.label == 0]
            if len(p) == 0 or len(n) < 5:
                continue
            for feat in COMMON + ['k_over']:
                drv.append(dict(variant=variant, family=family, driver_type=driver,
                                feature=feat, positives=len(p), negatives=len(n),
                                pos_mean=float(p[feat].mean()),
                                neg_mean=float(n[feat].mean()),
                                auc=safe_auc(m.label, m[feat])))
    pd.DataFrame(drv).to_csv(OUT / 'distribution_by_driver.csv', index=False, encoding='utf-8-sig')

    # Same-node k4/k8 comparison.
    keys = ['view', 'global_node']
    common = set(map(tuple, d4[keys].to_numpy())) & set(map(tuple, d8[keys].to_numpy()))
    c4 = d4.set_index(keys).loc[sorted(common)].reset_index()
    c8 = d8.set_index(keys).loc[sorted(common)].reset_index()
    assert np.array_equal(c4.label.to_numpy(), c8.label.to_numpy())
    diff = []
    for feat in COMMON:
        diff.append(dict(feature=feat, nodes=len(c4), positives=int(c4.label.sum()),
                         k4_pos_mean=float(c4.loc[c4.label == 1, feat].mean()),
                         k8_pos_mean=float(c8.loc[c8.label == 1, feat].mean()),
                         k4_neg_mean=float(c4.loc[c4.label == 0, feat].mean()),
                         k8_neg_mean=float(c8.loc[c8.label == 0, feat].mean()),
                         k4_auc=safe_auc(c4.label, c4[feat]),
                         k8_auc=safe_auc(c8.label, c8[feat]),
                         k4_positive_nonzero=int((c4.loc[c4.label == 1, feat] != 0).sum()),
                         k8_positive_nonzero=int((c8.loc[c8.label == 1, feat] != 0).sum())))
    pd.DataFrame(diff).to_csv(OUT / 'k4_vs_k8.csv', index=False, encoding='utf-8-sig')

    def queries(variant):
        if variant == 'k4':
            total = 0
            for v in PANEL:
                c = json.loads((T4 / 'views' / v / 'coverage.json').read_text(encoding='utf-8'))
                total += int(c['actual_sat_queries'])
            return total
        s = json.loads((T8 / 'merged_summary.json').read_text(encoding='utf-8'))
        return int(sum(x['sat_queries'] for x in s['views'] if x['view'] in PANEL))

    summary = dict(
        status='descriptive_s15850_k8_distribution_no_training',
        panel=PANEL, views=len(PANEL),
        k4=dict(rows=len(d4), positives=int(d4.label.sum()),
                covered=int(d4.covered.sum()), sat_queries=queries('k4')),
        k8=dict(rows=len(d8), positives=int(d8.label.sum()),
                covered=int(d8.covered.sum()), sat_queries=queries('k8')),
        common_nodes=len(common), same_labels=True,
        notes=['No training, no threshold tuning, no test labels.',
               'Bounded sample: all positives + 300 stratified negatives per view.',
               'Only four s15850 injection views; zeta is not included.',
               'k4 has k_over_4; k8 has k_over_8; do not compare that column across variants.',
               'AUC/AP are descriptive; positives are few and view-node repeated.'])
    (OUT / 'distribution_summary.json').write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print('\nK8 overall key features:')
    print(overall[(overall.variant == 'k8') & (overall.feature.isin(
        ['change_on_comparable', 'max_input_influence', 'infeasible_fraction',
         'complete_restricted_domain', 'comparable_pair_fraction', 'ones_on_forced']))]
          .pivot(index='feature', columns='label', values='median').round(3).to_string())


if __name__ == '__main__':
    main()
