"""Re-audit: k4 mapping alignment, primitive mapping, L_eq pair semantics, params."""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
H = Path(__file__).resolve().parent
P2 = ROOT / '_p0pilot/round32_20261029'
MAPD = H.parent / 'label_expand_20261031' / 'p2_mapping'
FOLD = ROOT / 'generate_trans/folds/hosts_bt31'
TAB = ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables'
K4P = FOLD / 'data/processed/satrel_k4_node_feats.npy'

rep = {}

# 1) k4 global order vs per-view real.npy (two views)
k4 = np.load(K4P, mmap_mode='r')
for split, view in (('val', 's38417t100__ctldup_d1_s42__ys_abc'), ('test', 's38584t100__ctldup_d1_s42__ys_abc')):
    vd = TAB / f'sat_k4_{"validation" if split == "val" else "test"}_round29/views' / view
    base = vd / 'base_inputs_normalized.npz'
    if not base.exists():
        base = vd / 'base_inputs.npz'
    with np.load(base) as z:
        gid = z['global_ids']
    real = np.load(vd / 'real.npy')
    d = np.abs(np.asarray(k4[gid], dtype=np.float32) - real)
    rep[f'k4_check_{split}'] = dict(view=view, nodes=int(len(gid)),
                                    max_abs_diff=float(d.max()), equal=bool(np.allclose(k4[gid], real)))

# 2) primitive matrix sanity: rows sum to 1, present gate mapping
prim = np.load(P2 / 'primitive_matrix.npy')
rep['prim'] = dict(shape=list(prim.shape), row_sums=[round(float(x), 4) for x in prim.sum(1)[:8]],
                   nonzero_per_row=[int((prim[i] > 0).sum()) for i in range(25)])

# 3) L_eq pairs: same host/instance, different view?
z = np.load(FOLD / 'data/processed/satrel_node_pairs.npz')
a, b, k = z['a'], z['b'], z['kind']
vi = np.load(ROOT / '_p0pilot/round29_20261029/frozen/view_index_all.npy')
names = json.loads((FOLD / 'views.json').read_text(encoding='utf-8'))
order = names['train_views'] + names['val_views'] + names['test_views']
m = k == 0
idx = np.flatnonzero(m)[:6]
ex = []
for i in idx:
    va, vb = int(vi[a[i]]), int(vi[b[i]])
    ex.append(dict(a_node=int(a[i]), b_node=int(b[i]), a_view=order[va] if va >= 0 else None,
                   b_view=order[vb] if vb >= 0 else None, different_view=bool(va != vb)))
rep['eq_pairs_sample'] = ex
rep['eq_pairs_counts'] = dict(total=int((k == 0).sum()), cross_view=int(sum(
    1 for i in np.flatnonzero(m)[:200000] if vi[a[i]] != vi[b[i]])))

# 4) parameter counts
rep['params'] = {'single4': 32322, 'dual_gate_2+2': 36612, 'dual_post(2+2+1)': 36612 + 64 * 64 * 2 + 128,
                 'dual_mix_post_cat(dim=39)': 36612 + 39 * 39 + 39 + 64 * 64 * 2 + 128}
print(json.dumps(rep, indent=1, ensure_ascii=False))
(H / 'reaudit.json').write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding='utf-8')
