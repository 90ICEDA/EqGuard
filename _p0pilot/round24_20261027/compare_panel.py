"""Compare k=4, k=6, k=8 on the same four-view panel (descriptive, no training)."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[2]
T = ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables'
OUT = T / 'sat_k8_rs232_round24' / 'panel_diff'
OUT.mkdir(exist_ok=True)
MERGED = {
    'k4': T / 'sat_k4_rs232_round23' / 'merged_rs232_k4.csv',
    'k6': T / 'sat_k6_rs232_round23' / 'merged_rs232_k6.csv',
    'k8': T / 'sat_k8_rs232_round24' / 'merged_rs232_k8.csv',
}
PANEL = json.loads((T / 'sat_k8_rs232_round24' / 'panel.json').read_text(encoding='utf-8'))['panel']
FEATURES = ['change_on_comparable', 'max_input_influence', 'infeasible_fraction',
            'complete_restricted_domain', 'comparable_pair_fraction',
            'ones_on_forced', 'determinism_on_feasible']


def auc(y, x):
    y = np.asarray(y, int); x = np.asarray(x, float)
    return None if len(np.unique(y)) < 2 else float(roc_auc_score(y, x))


def matched(d, keys, feat):
    vals = []
    for _, m in d.groupby(keys):
        p = m.loc[m.label.eq(1), feat].to_numpy(float)
        n = m.loc[m.label.eq(0), feat].to_numpy(float)
        if len(p) == 0 or len(n) < 5:
            continue
        vals.append(float((p[:, None] > n[None, :]).mean()))
    return float(np.median(vals)) if vals else None


def main():
    frames = {}
    for k, p in MERGED.items():
        d = pd.read_csv(p)
        d = d[d.covered & d.status.eq('eligible') & d.view.isin(PANEL)].copy()
        d['variant'] = k
        d['k_over'] = d['k_over_4'] if k == 'k4' else d['k_over_8']
        frames[k] = d

    # Fair comparison: only nodes covered by all three variants.
    keys = ['view', 'global_node']
    common = None
    for d in frames.values():
        s = set(map(tuple, d[keys].to_numpy()))
        common = s if common is None else common & s
    common = common or set()
    for k, d in frames.items():
        d = d.copy()
        d['in_common'] = [tuple(x) in common for x in d[keys].to_numpy()]
        frames[k] = d[d.in_common].copy()

    overall, by_view = [], []
    for k, d in frames.items():
        counts = dict(variant=k, view_count=int(d.view.nunique()), rows=int(len(d)),
                      positives=int(d.label.sum()), covered=int(d.covered.sum()),
                      change_zero_pos=int(((d.label == 1) & (d.change_on_comparable == 0)).sum()),
                      change_nonzero_pos=int(((d.label == 1) & (d.change_on_comparable > 0)).sum()),
                      mean_k=float(d.k.mean()))
        for feat in FEATURES + ['k_over']:
            overall.append(dict(**counts, feature=feat, auc=auc(d.label, d[feat]),
                                median_matched_view_driver=matched(d, ['view', 'driver_type'], feat),
                                median_matched_view_driver_k=matched(d, ['view', 'driver_type', 'k'], feat)))
        for v, m in d.groupby('view'):
            by_view.append(dict(variant=k, view=v, family=m.family.iloc[0], rows=len(m),
                                positives=int(m.label.sum()),
                                auc_change=auc(m.label, m.change_on_comparable),
                                auc_max=auc(m.label, m.max_input_influence),
                                auc_infeasible=auc(m.label, m.infeasible_fraction),
                                mean_k=float(m.k.mean())))
    overall = pd.DataFrame(overall)
    by_view = pd.DataFrame(by_view)
    overall.to_csv(OUT / 'panel_overall.csv', index=False, encoding='utf-8-sig')
    by_view.to_csv(OUT / 'panel_by_view.csv', index=False, encoding='utf-8-sig')
    summary = dict(
        status='descriptive_panel_k4_k6_k8_no_training',
        panel=PANEL, common_nodes=len(common),
        comparison='only nodes covered by all k variants; same view/global_node',
        overall=overall.to_dict(orient='records'),
        by_view=by_view.to_dict(orient='records'),
        notes=['No training, no threshold tuning, no test labels.',
               'All four views are train views.',
               'k_over is k_over_4 for k4 and k_over_8 for k6/k8; it is not directly comparable across k4 and k6/k8.',
               'Panel is a small pre-registered subset; AUCs are descriptive.'])
    (OUT / 'panel_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    print(overall.pivot(index='feature', columns='variant', values='auc').round(4).to_string())
    print('\nmatched view+driver median win rate')
    print(overall.pivot(index='feature', columns='variant', values='median_matched_view_driver').round(4).to_string())
    print('\ncommon', len(common))
    for k, d in frames.items():
        print(k, len(d), int(d.label.sum()), int(((d.label == 1) & (d.change_on_comparable == 0)).sum()))


if __name__ == '__main__':
    main()
