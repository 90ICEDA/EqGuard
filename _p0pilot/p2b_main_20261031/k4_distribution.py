"""Distribution report for the k4 SAT functional features (18 content dims + covered)."""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
X = ROOT / '_p0pilot/round29_20261029/all_split_exports/export_00000/all_splits_real_k4.npy'
S = ROOT / '_p0pilot/round29_20261029/all_split_exports/export_00000/split_index.npy'

COLS = ['k_over_4', 'feasibility_known_fraction', 'feasible_fraction', 'forced_fraction',
        'undecided_fraction', 'infeasible_fraction', 'determinism_on_feasible', 'determinism_valid',
        'ones_on_forced', 'ones_valid', 'comparable_pair_fraction', 'change_on_comparable',
        'influence_valid', 'max_input_influence', 'complete_full_domain',
        'complete_restricted_domain', 'partial_forcing', 'has_unknown']


def auc(y, p):
    from sklearn.metrics import roc_auc_score
    return float(roc_auc_score(y, p)) if y.sum() and (~y).sum() else None


def main():
    x = np.load(X, mmap_mode='r'); s = np.load(S)
    lab = json.loads((ROOT / 'generate_trans/folds/hosts_bt31/data/for_train/label_transport.json').read_text(encoding='utf-8'))['trans_labels_from_orig']
    y = np.full(len(s), -1, np.int8)
    for k, v in lab.items():
        y[int(k)] = v
    trust = np.zeros(len(s), bool)
    trust[:3220146] = np.load(ROOT / 'generate_trans/folds/hosts_bt31/data/for_train/trust_trans.npy')
    cov = np.asarray(x[:, 18])
    fam = np.load(OUT / 'view_family.npy') if (OUT / 'view_family.npy').exists() else None

    rep = {'coverage': {}, 'columns': {}, 'separation': {}}
    for sid, name in ((0, 'train'), (1, 'val'), (2, 'test')):
        m = s == sid
        rep['coverage'][name] = dict(nodes=int(m.sum()), covered=int(cov[m].sum()),
                                     rate=round(float(cov[m].mean()), 4))
    rep['coverage']['unlisted'] = dict(nodes=int((s == -1).sum()), covered=int(cov[s == -1].sum()))

    for c in range(18):
        v = np.asarray(x[:, c])
        rep['columns'][COLS[c]] = dict(
            mean=round(float(v.mean()), 4), std=round(float(v.std()), 4),
            p1=round(float(np.quantile(v, .01)), 4), p50=round(float(np.quantile(v, .50)), 4),
            p99=round(float(np.quantile(v, .99)), 4), min=float(v.min()), max=float(v.max()),
            constant_pct=round(float(np.mean(v == v[0])), 4))

    pos = (y == 1) & trust; neg = (y == 0) & trust
    tr = s == 0
    for c in range(18):
        v = np.asarray(x[:, c])
        yy = (y == 1)[tr & trust]
        vv = v[tr & trust]
        rep['separation'][COLS[c]] = dict(pos_mean=round(float(v[pos].mean()), 4),
                                          neg_mean=round(float(v[neg].mean()), 4),
                                          auc_train=round(auc(yy, vv), 4) if yy.sum() else None,
                                          pos_mean_train=round(float(vv[yy].mean()), 4),
                                          neg_mean_train=round(float(vv[~yy].mean()), 4))
    (OUT / 'k4_distribution.json').write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(rep['coverage'], ensure_ascii=False))
    print('col                    mean   std   p50   p99   const%  auc_train')
    for c in range(18):
        d = rep['columns'][COLS[c]]; a = rep['separation'][COLS[c]]['auc_train']
        print(f"{COLS[c]:22s} {d['mean']:.3f} {d['std']:.3f} {d['p50']:.3f} {d['p99']:.3f} {d['constant_pct']*100:6.1f}  {a if a is not None else float('nan'):.3f}")


if __name__ == '__main__':
    main()
