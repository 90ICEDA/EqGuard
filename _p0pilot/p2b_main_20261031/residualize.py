"""Residualize SAT k4 against structural features; save per-split matrices (rows follow x39 order)."""
import json
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[2]
H = Path(__file__).resolve().parent
P2 = ROOT / '_p0pilot/round32_20261029'
MAPD = H.parent / 'label_expand_20261031' / 'p2_mapping'
PROC = ROOT / 'generate_trans/folds/hosts_bt31/data/processed'
SAT = ['k_over_4', 'feasibility_known', 'feasible', 'forced', 'undecided', 'infeasible',
       'determinism_on_feasible', 'determinism_valid', 'ones_on_forced', 'ones_valid',
       'comparable_pair', 'change_on_comparable', 'influence_valid', 'max_input_influence',
       'complete_full', 'complete_restricted', 'partial_forcing', 'has_unknown']


def rows(split):
    folder = ROOT / json.loads((P2 / 'input_contract.json').read_text(encoding='utf-8'))['shared_inputs'][f'trans_{split}']['folder']
    x = np.load(folder / 'x39.npy', mmap_mode='r')
    gid = np.load(MAPD / f'x39row_to_global_{split}.npy')
    return np.asarray(x, np.float64), gid


def main():
    k = np.load(PROC / 'satrel_k4_node_feats.npy', mmap_mode='r')
    k = np.concatenate([k, np.zeros((1829, 19), np.float32)], 0)

    Xtr, Gtr = rows('train')
    Str = Xtr[:, 25:39]
    Ytr = np.asarray(k[Gtr, :18], np.float64)
    A = np.c_[Str, np.ones(len(Str))]
    coef, *_ = np.linalg.lstsq(A, Ytr, rcond=None)
    resid_tr = Ytr - A @ coef
    mu = resid_tr.mean(0); sd = np.maximum(resid_tr.std(0), 1e-6)

    # stratified: per (gate type x in_ports tercile) mean from train
    gate = Xtr[:, :25].argmax(1); ports = Str[:, 0]
    q1, q2 = np.quantile(ports, [1 / 3, 2 / 3]); bucket = np.digitize(ports, [q1, q2])
    gmean = {}
    for g in range(25):
        for b in range(3):
            mb = (gate == g) & (bucket == b)
            if mb.any():
                gmean[(g, b)] = Ytr[mb].mean(0)
    # fallback means
    for g in range(25):
        mg = gate == g
        if mg.any():
            for b in range(3):
                gmean.setdefault((g, b), Ytr[mg].mean(0))

    rep = {'auc': {}, 'n': {}}
    for split in ('train', 'val', 'test'):
        X, G = rows(split)
        S = np.asarray(k[G, :18], np.float64)
        st = X[:, 25:39]
        A_ = np.c_[st, np.ones(len(st))]
        R = S - A_ @ coef
        Zl = np.clip((R - mu) / sd, -10, 10).astype(np.float32)
        g_ = X[:, :25].argmax(1); p_ = st[:, 0]; b_ = np.digitize(p_, [q1, q2])
        Rs = S.copy()
        for idx in range(len(S)):
            Rs[idx] = S[idx] - gmean[(int(g_[idx]), int(b_[idx]))]
        Zs = np.clip(Rs, -10, 10).astype(np.float32)   # already centered per group
        np.save(PROC / f'satrel_k4_resid_lin_{split}.npy', Zl)
        np.save(PROC / f'satrel_k4_resid_str_{split}.npy', Zs)
        rep['n'][split] = len(G)
        if split == 'train':
            tr = np.load(ROOT / json.loads((P2 / 'input_contract.json').read_text(encoding='utf-8'))['shared_inputs']['trans_train']['folder'] / 'trusted.npy')
            y = np.load(ROOT / json.loads((P2 / 'input_contract.json').read_text(encoding='utf-8'))['shared_inputs']['trans_train']['folder'] / 'y.npy')
            m = tr & (y >= 0); yy = y[m] == 1
            for j, name in enumerate(SAT):
                v = Zl[m, j]
                rep['auc'][name] = dict(lin=round(float(roc_auc_score(yy, v)), 4) if v.std() > 0 else None,
                                        str=round(float(roc_auc_score(yy, Zs[m, j])), 4) if Zs[m, j].std() > 0 else None)
    (H / 'resid_report.json').write_text(json.dumps(rep, indent=1), encoding='utf-8')
    print(f"{'dim':22s} lin_resid  str_resid")
    for name in SAT:
        a = rep['auc'][name]
        print(f"{name:22s} {a['lin']}  {a['str']}")


if __name__ == '__main__':
    main()
