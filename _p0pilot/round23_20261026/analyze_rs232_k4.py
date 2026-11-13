"""Descriptive k=6 positive/negative audit on all rs232 training views.

No training, no threshold tuning, no use of validation/test labels.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

ROOT = Path(__file__).resolve().parents[2]
T = ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables/sat_k4_rs232_round23'
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(ROOT / 'phase2/ys'))
from sat_boundary_semantics import COLS  # noqa: E402

OUT = T / 'feature_diff'
OUT.mkdir(exist_ok=True)


def safe_auc(y, x):
    y = np.asarray(y, int); x = np.asarray(x, float)
    if len(np.unique(y)) < 2:
        return None
    return float(roc_auc_score(y, x))


def safe_ap(y, x):
    y = np.asarray(y, int); x = np.asarray(x, float)
    if len(np.unique(y)) < 2:
        return None
    return float(average_precision_score(y, x))


def describe(y, x):
    y = np.asarray(y, int); x = np.asarray(x, float)
    p = x[y == 1]; n = x[y == 0]
    return dict(positives=int(len(p)), negatives=int(len(n)),
                positive_mean=(float(p.mean()) if len(p) else None),
                negative_mean=(float(n.mean()) if len(n) else None),
                mean_diff=(float(p.mean() - n.mean()) if len(p) and len(n) else None),
                auc=safe_auc(y, x), ap=safe_ap(y, x))


def main():
    df = pd.read_csv(T / 'merged_rs232_k4.csv')
    d = df[df.covered & df.status.eq('eligible')].copy()
    y = d.label.to_numpy(int)
    print('rows', len(d), 'pos', int(y.sum()), 'neg', int((y == 0).sum()), flush=True)

    overall = []
    for c in COLS:
        s = describe(y, d[c]); s['feature'] = c; overall.append(s)
    overall = pd.DataFrame(overall).sort_values('auc', ascending=False, na_position='last')
    overall.to_csv(OUT / 'feature_overall.csv', index=False, encoding='utf-8-sig')

    fam = []
    for f, m in d.groupby('family'):
        for c in COLS:
            s = describe(m.label, m[c]); s.update(feature=c, family=f); fam.append(s)
    fam = pd.DataFrame(fam)
    fam.to_csv(OUT / 'feature_by_family.csv', index=False, encoding='utf-8-sig')

    gate = []
    for g, m in d.groupby('driver_type'):
        for c in COLS:
            s = describe(m.label, m[c]); s.update(feature=c, driver_type=g); gate.append(s)
    gate = pd.DataFrame(gate)
    gate.to_csv(OUT / 'feature_by_driver.csv', index=False, encoding='utf-8-sig')

    wv = []
    for v, m in d.groupby('view'):
        if m.label.nunique() < 2 or (m.label == 0).sum() < 10:
            continue
        for c in COLS:
            s = describe(m.label, m[c]); s.update(feature=c, view=v, family=m.family.iloc[0]); wv.append(s)
    wv = pd.DataFrame(wv)
    wv.to_csv(OUT / 'feature_by_view.csv', index=False, encoding='utf-8-sig')

    matched = []
    for (v, g), m in d.groupby(['view', 'driver_type']):
        p = m[m.label == 1]; n = m[m.label == 0]
        if len(p) == 0 or len(n) < 5:
            continue
        for c in COLS:
            pv = p[c].to_numpy(float); nv = n[c].to_numpy(float)
            diff = pv - nv.mean()
            win = (pv[:, None] > nv[None, :]).mean()
            matched.append(dict(feature=c, view=v, family=m.family.iloc[0],
                                driver_type=g, positives=len(p), negatives=len(n),
                                mean_diff=float(diff.mean()), win_rate=float(win)))
    matched = pd.DataFrame(matched)
    matched.to_csv(OUT / 'matched_positive_negative.csv', index=False, encoding='utf-8-sig')

    profile = []
    for (f, g, k), m in d.groupby(['family', 'driver_type', 'k']):
        pos = m[m.label == 1]; neg = m[m.label == 0]
        if len(pos) == 0:
            continue
        row = dict(family=f, driver_type=g, k=int(k), positives=len(pos), negatives=len(neg),
                   positive_fraction=float(len(pos) / len(m)))
        for c in COLS:
            row['pos_' + c] = float(pos[c].mean())
            row['neg_' + c] = float(neg[c].mean()) if len(neg) else None
        profile.append(row)
    profile = pd.DataFrame(profile)
    profile.to_csv(OUT / 'positive_profile.csv', index=False, encoding='utf-8-sig')

    msum = []
    for c, m in matched.groupby('feature'):
        msum.append(dict(feature=c, comparisons=len(m),
                         positive_count=int(m.positives.sum()),
                         median_mean_diff=float(m.mean_diff.median()),
                         mean_mean_diff=float(m.mean_diff.mean()),
                         median_win_rate=float(m.win_rate.median()),
                         fraction_win_rate_gt_0_5=float((m.win_rate > 0.5).mean())))
    msum = pd.DataFrame(msum).sort_values('median_win_rate', ascending=False)
    msum.to_csv(OUT / 'matched_summary.csv', index=False, encoding='utf-8-sig')

    wsum = []
    for c, m in wv.groupby('feature'):
        wsum.append(dict(feature=c, views=len(m),
                         median_auc=float(m.auc.median()),
                         mean_auc=float(m.auc.mean()),
                         fraction_auc_gt_0_5=float((m.auc > 0.5).mean())))
    wsum = pd.DataFrame(wsum).sort_values('median_auc', ascending=False)
    wsum.to_csv(OUT / 'within_view_summary.csv', index=False, encoding='utf-8-sig')


    counts = dict(
        total=int(len(df)), covered=int(df.covered.sum()),
        positives=int(y.sum()), negatives=int((y == 0).sum()),
        positives_by_family=d.label[d.label == 1].groupby(d.family).size().to_dict(),
        positives_by_driver=d.label[d.label == 1].groupby(d.driver_type).size().to_dict(),
        positives_by_k=d.label[d.label == 1].groupby(d.k).size().to_dict(),
        positives_by_role=d.label[d.label == 1].groupby(d.target_role).size().to_dict(),
        positive_views=int(d[d.label == 1].view.nunique()),
        total_views=int(df.view.nunique()),
        positives_unique_global=int(df[df.label == 1].global_node.nunique()))
    summary = dict(status='descriptive_posthoc_k4_no_training', schema='18D k4/4 summary',
                   counts=counts,
                   top_overall=overall.head(10).to_dict(orient='records'),
                   top_by_family=fam[fam.positives >= 2].sort_values('auc', ascending=False).head(20).to_dict(orient='records'),
                   top_matched=msum.head(10).to_dict(orient='records'),
                   top_within_view=wsum.head(10).to_dict(orient='records'),
                   notes=['All 113 rs232 views are train views; no independent val/test.',
                          'Positive labels repeat across implementation views; AUC is descriptive, not held-out.',
                          'No SAT query, model fit, threshold tuning, or training in this audit.',
                          'Null AUC/AP is written as JSON null when only one class exists.'])
    (OUT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(dict(counts=counts, top_overall=summary['top_overall'][:6],
                          top_matched=summary['top_matched'][:6]),
                     ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    main()

