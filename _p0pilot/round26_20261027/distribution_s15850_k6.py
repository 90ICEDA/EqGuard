"""Feature-distribution audit for the four-view s15850 k=6 full panel (no training)."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

ROOT = Path(__file__).resolve().parents[2]
T4 = ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables/sat_s15850_round22'
T6 = ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables/sat_k6_s15850_round26'
PANEL = json.loads((T6 / 'panel.json').read_text(encoding='utf-8'))['panel']
OUT = T6 / 'distribution'
OUT.mkdir(exist_ok=True)
COMMON = ['feasibility_known_fraction', 'feasible_fraction', 'forced_fraction',
          'undecided_fraction', 'infeasible_fraction', 'determinism_on_feasible',
          'determinism_valid', 'ones_on_forced', 'ones_valid',
          'comparable_pair_fraction', 'change_on_comparable', 'influence_valid',
          'max_input_influence', 'complete_full_domain',
          'complete_restricted_domain', 'partial_forcing', 'has_unknown']


def auc(y, x):
    y = np.asarray(y, int); x = np.asarray(x, float)
    return None if len(np.unique(y)) < 2 else float(roc_auc_score(y, x))


def ap(y, x):
    y = np.asarray(y, int); x = np.asarray(x, float)
    return None if len(np.unique(y)) < 2 else float(average_precision_score(y, x))


def stats(y, x):
    x = np.asarray(x, float); y = np.asarray(y, int)
    return dict(n=int(len(x)), mean=float(x.mean()), std=float(x.std()),
                min=float(x.min()), q05=float(np.quantile(x, .05)),
                q25=float(np.quantile(x, .25)), median=float(np.median(x)),
                q75=float(np.quantile(x, .75)), q95=float(np.quantile(x, .95)),
                max=float(x.max()), zero=int((x == 0).sum()),
                nonzero=int((x != 0).sum()), auc=auc(y, x), ap=ap(y, x))


def load(path):
    d = pd.read_csv(path)
    return d[d.covered & d.status.eq('eligible') & d.view.isin(PANEL)].copy()


def main():
    d4 = load(T4 / 'merged_s15850.csv')
    d6 = load(T6 / 'merged_s15850_k6.csv')
    d4['k_over'] = d4['k_over_4']; d6['k_over'] = d6['k_over_8']
    rows = []
    for variant, d in (('k4', d4), ('k6', d6)):
        for feat in COMMON + ['k_over']:
            for label_name, m in (('all', d), ('positive', d[d.label == 1]),
                                  ('negative', d[d.label == 0])):
                s = stats(m.label, m[feat]); s.update(variant=variant, feature=feat,
                                                      label=label_name); rows.append(s)
    overall = pd.DataFrame(rows)
    overall.to_csv(OUT / 'distribution_overall.csv', index=False, encoding='utf-8-sig')

    fam = []
    for variant, d in (('k4', d4), ('k6', d6)):
        for family, m in d.groupby('family'):
            for feat in COMMON + ['k_over']:
                p = m[m.label == 1]; n = m[m.label == 0]
                fam.append(dict(variant=variant, family=family, feature=feat,
                                positives=len(p), negatives=len(n),
                                pos_mean=float(p[feat].mean()) if len(p) else None,
                                neg_mean=float(n[feat].mean()) if len(n) else None,
                                pos_median=float(p[feat].median()) if len(p) else None,
                                neg_median=float(n[feat].median()) if len(n) else None,
                                pos_zero=int((p[feat] == 0).sum()),
                                neg_zero=int((n[feat] == 0).sum()),
                                auc=auc(m.label, m[feat]), ap=ap(m.label, m[feat])))
    pd.DataFrame(fam).to_csv(OUT / 'distribution_by_family.csv', index=False, encoding='utf-8-sig')

    keys = ['view', 'global_node']
    common = set(map(tuple, d4[keys].to_numpy())) & set(map(tuple, d6[keys].to_numpy()))
    c4 = d4.set_index(keys).loc[sorted(common)].reset_index()
    c6 = d6.set_index(keys).loc[sorted(common)].reset_index()
    assert np.array_equal(c4.label.to_numpy(), c6.label.to_numpy())
    diff = []
    for feat in COMMON:
        diff.append(dict(feature=feat, nodes=len(c4), positives=int(c4.label.sum()),
                         k4_pos_mean=float(c4.loc[c4.label == 1, feat].mean()),
                         k6_pos_mean=float(c6.loc[c6.label == 1, feat].mean()),
                         k4_neg_mean=float(c4.loc[c4.label == 0, feat].mean()),
                         k6_neg_mean=float(c6.loc[c6.label == 0, feat].mean()),
                         k4_auc=auc(c4.label, c4[feat]), k6_auc=auc(c6.label, c6[feat]),
                         k4_positive_nonzero=int((c4.loc[c4.label == 1, feat] != 0).sum()),
                         k6_positive_nonzero=int((c6.loc[c6.label == 1, feat] != 0).sum())))
    pd.DataFrame(diff).to_csv(OUT / 'k4_vs_k6.csv', index=False, encoding='utf-8-sig')

    def queries(variant):
        if variant == 'k4':
            return int(sum(json.loads((T4 / 'views' / v / 'coverage.json').read_text(
                encoding='utf-8'))['actual_sat_queries'] for v in PANEL))
        s = json.loads((T6 / 'merged_summary.json').read_text(encoding='utf-8'))
        return int(s['sat_queries'])

    summary = dict(status='descriptive_s15850_k6_full_distribution_no_training',
                   panel=PANEL, views=len(PANEL),
                   k4=dict(rows=len(d4), positives=int(d4.label.sum()),
                           covered=int(d4.covered.sum()), sat_queries=queries('k4')),
                   k6=dict(rows=len(d6), positives=int(d6.label.sum()),
                           covered=int(d6.covered.sum()), sat_queries=queries('k6')),
                   common_nodes=len(common), same_labels=True,
                   notes=['No training, no threshold tuning, no test labels.',
                          'Full k6 on four s15850 injection views; no negative sampling.',
                          'k4 has k_over_4; k6 has k_over_8; do not compare that column.',
                          'AUC/AP are descriptive; positives are few and view-node repeated.'])
    (OUT / 'distribution_summary.json').write_text(json.dumps(summary, ensure_ascii=False,
                                                              indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print('\nK6 key features:')
    print(overall[(overall.variant == 'k6') & (overall.label == 'all') &
                  overall.feature.isin(['change_on_comparable', 'max_input_influence',
                                        'infeasible_fraction', 'complete_restricted_domain',
                                        'comparable_pair_fraction', 'ones_on_forced', 'k_over'])]
          [['feature', 'mean', 'median', 'auc', 'ap']].round(4).to_string(index=False))


if __name__ == '__main__':
    main()
