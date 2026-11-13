"""Per-feature AUC for the 39 base features and the 18 SAT k4 features, plus marginal value."""
import json
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score, average_precision_score
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
H = Path(__file__).resolve().parent
P2 = ROOT / '_p0pilot/round32_20261029/inputs'
K4P = ROOT / 'generate_trans/folds/hosts_bt31/data/processed/satrel_k4_node_feats.npy'
MAPD = H.parent / 'label_expand_20261031' / 'p2_mapping'

BASE = ['gate_ANDX', 'gate_AOIX', 'gate_AOX', 'gate_BUFX', 'gate_DFFARX', 'gate_DFFNX', 'gate_DFFX',
        'gate_HADDX', 'gate_HARD_INC', 'gate_INVX', 'gate_ISOLANDX', 'gate_LSDNENX', 'gate_LSDNX',
        'gate_MUXX', 'gate_NANDX', 'gate_NORX', 'gate_OAIX', 'gate_OAX', 'gate_ORX', 'gate_SFSRX',
        'gate_SDFFX', 'gate_TOP_HARD', 'gate_TOP_RVT', 'gate_XNORX', 'gate_XORX',
        'in_ports', 'incident', 'touches_PI', 'touches_PO', 'dist_PI', 'dist_PO',
        'exact2_fanin', 'exact2_fanout', 'rst_in_dist', 'rst_out_dist', 'rst_exact2_fanin',
        'rst_exact2_fanout', 'in_SCC', 'SCC_size']
SAT = ['k_over_4', 'feasibility_known', 'feasible', 'forced', 'undecided', 'infeasible',
       'determinism_on_feasible', 'determinism_valid', 'ones_on_forced', 'ones_valid',
       'comparable_pair', 'change_on_comparable', 'influence_valid', 'max_input_influence',
       'complete_full', 'complete_restricted', 'partial_forcing', 'has_unknown']


def load_split(split):
    a = {n: np.load(P2 / f'trans_{split}' / f'{n}.npy', mmap_mode='r') for n in ('x39', 'y', 'trusted')}
    gid = np.load(MAPD / f'x39row_to_global_{split}.npy')
    K = np.load(K4P, mmap_mode='r')
    K = np.concatenate([K, np.zeros((1829, 19), np.float32)], 0)
    sat = np.asarray(K[gid])
    return np.asarray(a['x39'], np.float32), np.asarray(a['y']), np.asarray(a['trusted'], bool), sat, gid


def main():
    Xtr, ytr, mtr, Str, _ = load_split('train')
    Xva, yva, mva, Sva, _ = load_split('val')
    tr = mtr & (ytr >= 0); va = mva & (yva >= 0)
    rep = {'base_auc': {}, 'sat_auc': {}, 'corr': {}, 'linear': {}}
    for i, name in enumerate(BASE):
        v = Xtr[tr, i]
        rep['base_auc'][name] = round(float(roc_auc_score(ytr[tr], v)), 4) if v.std() > 0 else None
    for i, name in enumerate(SAT):
        v = Str[tr, i]
        rep['sat_auc'][name] = round(float(roc_auc_score(ytr[tr], v)), 4) if v.std() > 0 else None
    # correlation of each SAT dim with base dims (train trusted)
    B = Xtr[tr]; S = Str[tr]
    Bz = (B - B.mean(0)) / np.maximum(B.std(0), 1e-6)
    Sz = (S - S.mean(0)) / np.maximum(S.std(0), 1e-6)
    C = (Sz.T @ Bz) / len(B)
    for i, name in enumerate(SAT):
        j = int(np.argmax(np.abs(C[i]))); rep['corr'][name] = [BASE[j], round(float(C[i, j]), 3)]

    # marginal value: logistic regression (standardized) on train, evaluate on val
    sc = StandardScaler().fit(np.c_[B, S])
    ZB = sc.transform(np.c_[B, np.zeros_like(S)])
    ZBS = sc.transform(np.c_[B, S])
    ZS = sc.transform(np.c_[np.zeros_like(B), S])
    yv = yva[va]
    for tag, Z, Zv in (('base39', ZB, sc.transform(np.c_[Xva[va], np.zeros_like(Sva[va])])),
                       ('base39+sat', ZBS, sc.transform(np.c_[Xva[va], Sva[va]])),
                       ('sat18', ZS, sc.transform(np.c_[np.zeros_like(Xva[va]), Sva[va]]))):
        clf = LogisticRegression(max_iter=200, class_weight='balanced', solver='lbfgs')
        clf.fit(Z, ytr[tr])
        p = clf.predict_proba(Zv)[:, 1]
        rep['linear'][tag] = dict(val_auc=round(float(roc_auc_score(yv, p)), 4),
                                  val_ap=round(float(average_precision_score(yv, p)), 4))
    (H / 'feature_auc_report.json').write_text(json.dumps(rep, indent=1), encoding='utf-8')
    print('BASE feature AUC (train trusted):')
    for k, v in rep['base_auc'].items():
        print(f'  {k:22s} {v}')
    print('SAT feature AUC:')
    for k, v in rep['sat_auc'].items():
        print(f'  {k:22s} {v}  maxcorr={rep["corr"][k]}')
    print('linear probe:', json.dumps(rep['linear']))


if __name__ == '__main__':
    main()
