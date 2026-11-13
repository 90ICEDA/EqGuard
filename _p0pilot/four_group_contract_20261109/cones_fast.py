"""Fast cone asset build: preload arrays, single cache scan, per-source/label matching."""
import csv, hashlib, json, sys, time
from pathlib import Path
import numpy as np

R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = R / '_p0pilot/four_group_contract_20261109'
B = R / '_p0pilot/control_boundary_v3_20261104'
PREP = R / '_p0pilot/seed42_supervised_prep_20261109'


def sha(a): return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()


def main():
    t0 = time.time()
    A = np.load(OUT / 'group_A.npz'); Bg = np.load(OUT / 'group_B.npz')
    supA = np.load(OUT / 'sup_A.npz'); supB = np.load(OUT / 'sup_B.npz')
    o2A, tA, pA, yA = A['old2new'], A['trusted'], A['physical'], A['y']
    o2B, tB, pB, yB = Bg['old2new'], Bg['trusted'], Bg['physical'], Bg['y']
    print('loaded', round(time.time() - t0, 1), flush=True)
    rows = list(csv.DictReader((PREP / 'CONE_CACHE_V2.csv').open(encoding='utf-8-sig', newline='')))
    print('rows', len(rows), round(time.time() - t0, 1), flush=True)
    coneA, coneB = {}, {}
    for i, r in enumerate(rows):
        if r['split'] != 'train' or r['kind'] != 'D' or int(r['label']) < 0 or int(r['n_phys']) < 2:
            continue
        view = r['view']; src = view.split('__ys_')[0]; lab = int(r['label'])
        old = np.array([int(x) for x in r['phys_rows'].split('|') if x], np.int64)
        for o2, tr, ph, store in ((o2A, tA, pA, coneA), (o2B, tB, pB, coneB)):
            loc = o2[old]
            loc = loc[loc >= 0]
            loc = loc[tr[loc] & ph[loc]]
            if len(loc) < 2:
                continue
            store[(view, r['cone_id'])] = (lab, loc, src)
        if i % 5000 == 0:
            print('scan', i, round(time.time() - t0, 1), flush=True)
    print('cones A/B', len(coneA), len(coneB), round(time.time() - t0, 1), flush=True)
    srcs = sorted({v[2] for v in coneA.values()} & {v[2] for v in coneB.values()})
    def group(store):
        d = {}
        for (v, cid), (lab, mem, src) in store.items():
            d.setdefault((src, lab), []).append((v, cid, lab, mem))
        return d
    ga, gb = group(coneA), group(coneB)
    selA, selB, per = [], [], {}
    for s in srcs:
        for lab in (1, 0):
            a = sorted(ga.get((s, lab), []), key=lambda x: (x[0], x[1]))
            b = sorted(gb.get((s, lab), []), key=lambda x: (x[0], x[1]))
            n = min(len(a), len(b))
            per[f'{s}|{lab}'] = dict(A=len(a), B=len(b), matched=n)
            selA += a[:n]; selB += b[:n]
    print('matched', len(selA), len(selB), round(time.time() - t0, 1), flush=True)
    def pack(sel):
        flat, ptr = [], [0]
        for _, _, _, mem in sel:
            flat.extend(mem.tolist()); ptr.append(len(flat))
        return (np.array(flat, np.int64), np.array([x[2] for x in sel], np.int8),
                np.array(ptr, np.int64), np.array([x[0] for x in sel]), np.array([x[1] for x in sel]),
                np.array([x[3] for x in sel], dtype=object) if False else np.array([sha(x[3]) for x in sel]))
    fa, la, pa_, va, ca, ma = pack(selA); fb, lb, pb_, vb, cb, mb = pack(selB)
    np.savez_compressed(OUT / 'cones_A.npz', rows=fa, label=la, ptr=pa_, view=va, cid=ca, memsha=ma,
                        sup_sha=sha(supA['idx']), used=len(selA))
    np.savez_compressed(OUT / 'cones_B.npz', rows=fb, label=lb, ptr=pb_, view=vb, cid=cb, memsha=mb,
                        sup_sha=sha(supB['idx']), used=len(selB))
    rep = dict(cones_A=len(selA), cones_B=len(selB), pos_A=int(la.sum()), pos_B=int(lb.sum()),
               neg_A=int((la == 0).sum()), neg_B=int((lb == 0).sum()),
               matched=per, seconds=round(time.time() - t0, 1))
    (OUT / 'CONES_REPORT.json').write_text(json.dumps(rep, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in rep.items() if k != 'matched'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
