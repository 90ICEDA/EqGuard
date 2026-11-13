"""How much of each SAT k4 dimension is explained by the 14 structural features?"""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
H = Path(__file__).resolve().parent
P2 = ROOT / '_p0pilot/round32_20261029'
MAPD = H.parent / 'label_expand_20261031' / 'p2_mapping'
PROC = ROOT / 'generate_trans/folds/hosts_bt31/data/processed'
SAT = ['k_over_4', 'feasibility_known', 'feasible', 'forced', 'undecided', 'infeasible',
       'determinism_on_feasible', 'determinism_valid', 'ones_on_forced', 'ones_valid',
       'comparable_pair', 'change_on_comparable', 'influence_valid', 'max_input_influence',
       'complete_full', 'complete_restricted', 'partial_forcing', 'has_unknown']


def main():
    folder = ROOT / json.loads((P2 / 'input_contract.json').read_text(encoding='utf-8'))['shared_inputs']['trans_train']['folder']
    gid = np.load(MAPD / 'x39row_to_global_train.npy')
    k = np.load(PROC / 'satrel_k4_node_feats.npy', mmap_mode='r')
    k = np.concatenate([k, np.zeros((1829, 19), np.float32)], 0)
    x = np.load(folder / 'x39.npy', mmap_mode='r')
    tr = np.load(folder / 'trusted.npy')
    idx = np.flatnonzero(tr)[::3][:150000]
    X = np.asarray(x[idx, 25:], np.float64)
    Y = np.asarray(k[gid[idx]], np.float64)
    A = np.c_[X, np.ones(len(X))]
    out = {}
    for j, name in enumerate(SAT[:18]):
        y = Y[:, j]
        coef, *_ = np.linalg.lstsq(A, y, rcond=None)
        pred = A @ coef
        ss_res = ((y - pred) ** 2).sum(); ss_tot = ((y - y.mean()) ** 2).sum()
        out[name] = round(float(1 - ss_res / ss_tot), 3) if ss_tot > 0 else None
    print(json.dumps(out, indent=1))
    (H / 'sat_r2_from_structure.json').write_text(json.dumps(out, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
