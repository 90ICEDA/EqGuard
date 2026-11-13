"""Cross-host SAT feature audit: rs232 vs s15850, family and gate strata.

No model training, no threshold tuning, no new SAT queries.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import average_precision_score, roc_auc_score

ROOT = Path(__file__).resolve().parents[2]
R18 = ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables/sat_small_round18'
R22 = ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables/sat_s15850_round22'
P = ROOT / 'generate_trans/folds/hosts_bt31/data/processed'
FEATURES = json.loads((ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round15/target18_manifest.json').read_text(encoding='utf-8'))['columns']


def load_rs232():
    rec = json.loads((R18 / 'records.json').read_text(encoding='utf-8'))
    b = np.load(R18 / 'base_inputs.npz')
    real = np.load(R18 / 'real.npy')
    g = torch.load(P / 'trans_graph.pt', map_location='cpu', weights_only=False, mmap=True)
    ids = b['global_ids']
    y = g.y[torch.tensor(ids)].numpy().astype(int)
    rows = []
    for r in rec:
        i = int(r['local_node'])
        rows.append(dict(host='rs232', global_node=int(ids[i]), local_node=i,
                         view=r['view'], family=r['family'], split=r['split'],
                         cell=r['cell'], driver_type=r.get('driver_type'),
                         target_role=r.get('target_role'), k=int(r.get('k', 0)),
                         status=r.get('status'), covered=bool(real[i, 18]), label=int(y[i]),
                         **{c: float(real[i, j]) for j, c in enumerate(FEATURES) if c != 'covered'}))
    return pd.DataFrame(rows)


def load_s15850():
    d = pd.read_csv(R22 / 'merged_s15850.csv', encoding='utf-8-sig')
    d['host'] = 's15850'
    return d


def safe_auc(y, a):
    if len(np.unique(y)) < 2 or len(np.unique(a)) < 2:
        return None
    return float(roc_auc_score(y, a))


def safe_ap(y, a):
    if len(np.unique(y)) < 2:
        return None
    return float(average_precision_score(y, a))


def stats(sub, feature):
    a = sub[feature].to_numpy(float)
    y = sub['label'].to_numpy(int)
    pos = a[y == 1]
    neg = a[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return None
    return dict(n_pos=len(pos), n_neg=len(neg),
                pos_mean=float(pos.mean()), neg_mean=float(neg.mean()),
                pos_median=float(np.median(pos)), neg_median=float(np.median(neg)),
                pos_nonzero=float((pos != 0).mean()), neg_nonzero=float((neg != 0).mean()),
                mean_diff=float(pos.mean() - neg.mean()),
                auc=safe_auc(y, a), ap=safe_ap(y, a))



def main():
    r = load_rs232(); s = load_s15850()
    r = r[r.view.str.contains('__inj')]
    s = s[s.view.str.contains('__inj')]
    for d in (r, s):
        d['covered'] = d['covered'].astype(bool)

    # Fixed class and gate composition.
    counts = []
    for host, d in [('rs232', r), ('s15850', s)]:
        for (fam, role), z in d[d.covered].groupby(['family', 'target_role']):
            counts.append(dict(host=host, family=fam, target_role=role,
                               nodes=len(z), positives=int(z.label.sum()),
                               negatives=int((z.label == 0).sum()),
                               prevalence=float(z.label.mean())))
        for (fam, gate), z in d[d.covered].groupby(['family', 'driver_type']):
            counts.append(dict(host=host, family=fam, target_role='gate:' + str(gate),
                               nodes=len(z), positives=int(z.label.sum()),
                               negatives=int((z.label == 0).sum()),
                               prevalence=float(z.label.mean())))
    pd.DataFrame(counts).to_csv(R22 / 'class_composition.csv', index=False, encoding='utf-8-sig')

    host_rows = []
    for host_name, d in [('rs232', r), ('s15850', s)]:
        z = d[d.covered]
        for feat in FEATURES:
            q = stats(z, feat)
            if q:
                host_rows.append(dict(host=host_name, scope='inj_pooled', feature=feat, **q))
    host = pd.DataFrame(host_rows)
    host.to_csv(R22 / 'host_inj_feature_stats.csv', index=False, encoding='utf-8-sig')

    fam_rows = []
    for host_name, d in [('rs232', r), ('s15850', s)]:
        for fam, z in d[d.covered].groupby('family'):
            for feat in FEATURES:
                q = stats(z, feat)
                if q:
                    fam_rows.append(dict(host=host_name, family=fam, feature=feat, **q))
    fam = pd.DataFrame(fam_rows)
    fam.to_csv(R22 / 'family_feature_stats.csv', index=False, encoding='utf-8-sig')

    gate_rows = []
    for host_name, d in [('rs232', r), ('s15850', s)]:
        for gate, z in d[d.covered].groupby('driver_type'):
            for feat in FEATURES:
                q = stats(z, feat)
                if q and q['n_pos'] >= 2 and q['n_neg'] >= 10:
                    gate_rows.append(dict(host=host_name, driver_type=gate, feature=feat, **q))
    pd.DataFrame(gate_rows).to_csv(R22 / 'gate_feature_stats.csv', index=False, encoding='utf-8-sig')

    pos_rows = []
    for host_name, d in [('rs232', r), ('s15850', s)]:
        for fam, z in d[(d.covered) & (d.label == 1)].groupby('family'):
            for feat in FEATURES:
                a = z[feat].to_numpy(float)
                pos_rows.append(dict(host=host_name, family=fam, feature=feat,
                                     n=len(a), mean=float(a.mean()), median=float(np.median(a)),
                                     std=float(a.std(ddof=1)) if len(a) > 1 else 0.0,
                                     nonzero=float((a != 0).mean()),
                                     max=float(a.max()), min=float(a.min())))
    pd.DataFrame(pos_rows).to_csv(R22 / 'family_positive_profile.csv', index=False, encoding='utf-8-sig')


    # Same family across hosts: positive means and within-host AUC.
    common = sorted(set(r.family) & set(s.family))
    cross_rows = []
    for fam in common:
        for feat in FEATURES:
            qr = stats(r[(r.covered) & (r.family == fam)], feat)
            qs = stats(s[(s.covered) & (s.family == fam)], feat)
            if qr and qs:
                cross_rows.append(dict(family=fam, feature=feat,
                                       rs232_pos=qr['pos_mean'], s15850_pos=qs['pos_mean'],
                                       pos_delta=qs['pos_mean'] - qr['pos_mean'],
                                       rs232_neg=qr['neg_mean'], s15850_neg=qs['neg_mean'],
                                       rs232_auc=qr['auc'], s15850_auc=qs['auc'],
                                       rs232_npos=qr['n_pos'], s15850_npos=qs['n_pos']))
    cross = pd.DataFrame(cross_rows)
    cross.to_csv(R22 / 'same_family_cross_host.csv', index=False, encoding='utf-8-sig')

    hrows = []
    for feat in FEATURES:
        a = host[(host.host == 'rs232') & (host.feature == feat)]
        b = host[(host.host == 's15850') & (host.feature == feat)]
        if len(a) and len(b):
            hrows.append(dict(feature=feat, rs232_auc=float(a.auc.iloc[0]),
                              s15850_auc=float(b.auc.iloc[0]),
                              auc_delta=float(b.auc.iloc[0] - a.auc.iloc[0]),
                              rs232_pos=float(a.pos_mean.iloc[0]), s15850_pos=float(b.pos_mean.iloc[0]),
                              rs232_neg=float(a.neg_mean.iloc[0]), s15850_neg=float(b.neg_mean.iloc[0])))
    pd.DataFrame(hrows).to_csv(R22 / 'host_auc_compare.csv', index=False, encoding='utf-8-sig')

    summary = dict(
        status='descriptive_posthoc_no_training',
        scope='rs232 8-netlist ys_abc vs s15850 5 injection ys_abc; s15850 controls not extracted',
        positives=dict(rs232=int(r.label.sum()), s15850=int(s.label.sum())),
        covered=dict(rs232=int(r.covered.sum()), s15850=int(s.covered.sum())),
        common_families=common,
        notes=['Only injection views; no s15850 control views in this bounded pass.',
               'All features 18D summary + covered; no model/threshold tuning.',
               'Family and gate composition differ; do not read pooled AUC as host effect.'])
    (R22 / 'cross_host_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(positives=summary['positives'], covered=summary['covered'],
                          common_families=common,
                          host_top=host.sort_values('auc', ascending=False).head(8).to_dict(orient='records')),
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
