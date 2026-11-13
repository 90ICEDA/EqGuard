"""Cone assets for hoco A/B, keyed (split,view,cone_id), per-source/label matched."""
import csv, json
from pathlib import Path
import numpy as np
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = R / '_p0pilot/heldout_composition_20261110'
PREP = R / '_p0pilot/seed42_supervised_prep_20261109'
A = np.load(OUT / 'hoco_A.npz'); B = np.load(OUT / 'hoco_B.npz')
oA, tA, pA = A['old2new'], A['trusted'], A['physical']; oB, tB, pB = B['old2new'], B['trusted'], B['physical']
rows = list(csv.DictReader((PREP / 'CONE_CACHE_V2.csv').open(encoding='utf-8-sig', newline='')))
ca, cb = {}, {}
for r in rows:
    if r['split'] != 'train' or r['kind'] != 'D' or int(r['label']) < 0 or int(r['n_phys']) < 2:
        continue
    old = np.array([int(x) for x in r['phys_rows'].split('|') if x], np.int64)
    for o2, tr, ph, store in ((oA, tA, pA, ca), (oB, tB, pB, cb)):
        loc = o2[old]; loc = loc[loc >= 0]; loc = loc[tr[loc] & ph[loc]]
        if len(loc) >= 2:
            store[(r['view'], r['cone_id'])] = (int(r['label']), loc, r['view'].split('__ys_')[0])
srcs = sorted({v[2] for v in ca.values()} & {v[2] for v in cb.values()})
def group(st):
    d = {}
    for (v, cid), (l, m, s) in st.items():
        d.setdefault((s, l), []).append((v, cid, l, m))
    return d
ga, gb = group(ca), group(cb)
selA, selB = [], []
for s in srcs:
    for l in (1, 0):
        a = sorted(ga.get((s, l), []), key=lambda x: (x[0], x[1]))
        b = sorted(gb.get((s, l), []), key=lambda x: (x[0], x[1]))
        n = min(len(a), len(b))
        selA += a[:n]; selB += b[:n]
def pack(sel):
    flat, ptr = [], [0]
    for _, _, _, m in sel:
        flat.extend(m.tolist()); ptr.append(len(flat))
    return (np.array(flat, np.int64), np.array([x[2] for x in sel], np.int8), np.array(ptr, np.int64),
            np.array([x[0] for x in sel]), np.array([x[1] for x in sel]))
for tag, sel in (('A', selA), ('B', selB)):
    f, l, p, v, cid = pack(sel)
    np.savez_compressed(OUT / f'hoco_cones_{tag}.npz', rows=f, label=l, ptr=p, view=v, cid=cid)
print(json.dumps(dict(A=len(selA), B=len(selB), posA=int(sum(x[2] for x in selA)), negA=int(sum(1 for x in selA if x[2] == 0))), ensure_ascii=False))
