"""held-out composition (h=abc) assets: A=id/opt, B=+aig/nand; shared norm/val, 200-step sup, cones."""
import csv, hashlib, json, sys
from pathlib import Path
import numpy as np
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = R / '_p0pilot/heldout_composition_20261110'
B = R / '_p0pilot/control_boundary_v3_20261104'
PREP = R / '_p0pilot/seed42_supervised_prep_20261109'
L = R / '_p0pilot/control_loader_po_20261105'
sys.path.insert(0, str(L))
from supervision_loader import FiveGroupLoader

BASE = ('ys_id', 'ys_opt'); ADD = ('ys_aig', 'ys_nand')
def sha(a): return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()


def sub(arr, vs, keep):
    rows, aux = [], 0
    for v in keep:
        lay = vs[v]; rows.extend(range(lay['start'], lay['stop'])); aux += lay['stop'] - lay['physical_stop']
    rows = np.array(rows, np.int64)
    o2n = np.full(len(arr['y']), -1, np.int64); o2n[rows] = np.arange(len(rows))
    src, dst = arr['edge_index'][0], arr['edge_index'][1]
    m = (o2n[src] >= 0) & (o2n[dst] >= 0)
    return dict(rows=rows, old2new=o2n, new2old=rows, x=arr['x39'][rows], y=arr['y'][rows],
                trusted=arr['trusted'][rows], physical=arr['physical'][rows],
                edge=np.stack([o2n[src[m]], o2n[dst[m]]]), aux=int(aux))


def main():
    OUT.mkdir(exist_ok=True)
    c = json.loads((B / 'input_contract.json').read_text(encoding='utf-8'))
    vs = {v['view']: v for v in c['shared_inputs']['trans_train']['views']}
    arr = {k: np.load(B / 'inputs' / f'trans_train/{k}.npy') for k in ('x39', 'edge_index', 'y', 'trusted', 'physical')}
    ka = [v for v in vs if v.split('__')[-1] == 'ys_id' or v.split('__')[-1] == 'ys_opt']
    kb = [v for v in vs if v.split('__')[-1] in BASE + ADD]
    A = sub(arr, vs, ka); Bg = sub(arr, vs, kb)
    orig = np.load(B / 'inputs/orig_train/x39.npy')
    cat = np.concatenate([orig[:, 25:], A['x'][:, 25:]], 0)
    mean = cat.mean(0).astype(np.float32); std = cat.std(0).astype(np.float32); std[std < 1e-6] = 1
    loader = FiveGroupLoader(); pools = loader.pools['trans']
    def pool(ids, o2n, g):
        x = o2n[np.asarray(ids, np.int64)]; x = x[x >= 0]
        return x[(g['y'][x] == 0) & g['trusted'][x] & g['physical'][x]]
    cA, cB = pool(pools['common_negative'], A['old2new'], A), pool(pools['common_negative'], Bg['old2new'], Bg)
    hA, hB = pool(pools['H'], A['old2new'], A), pool(pools['H'], Bg['old2new'], Bg)
    def srcpos(g, keep):
        d = {}
        for v in keep:
            lay = vs[v]; a, b = lay['start'], lay['stop']; s = v.split('__ys_')[0]
            loc = np.where((g['y'] == 1) & g['trusted'] & g['physical'])[0]
            loc = loc[(g['rows'][loc] >= a) & (g['rows'][loc] < b)]
            d.setdefault(s, []).extend(loc.tolist())
        return d
    pa, pb = srcpos(A, ka), srcpos(Bg, kb); srcs = sorted(set(pa) & set(pb))
    quota = {s: min(len(pa[s]), len(pb[s])) for s in srcs}
    def pick(d, s, n):
        arr2 = np.array(d[s], np.int64); rr = np.random.default_rng(int(hashlib.sha256(s.encode()).hexdigest()[:8], 16))
        return rr.permutation(arr2)[:n]
    posA = np.concatenate([pick(pa, s, quota[s]) for s in srcs]).astype(np.int64)
    posB = np.concatenate([pick(pb, s, quota[s]) for s in srcs]).astype(np.int64)
    stA, stB = [], []
    for step in range(200):
        r = np.random.default_rng(42 + step); cc = r.choice(cA, 8192, replace=False); ee = r.choice(np.setdiff1d(hA, cc), 144, replace=False)
        r2 = np.random.default_rng(42 + step); dd = r2.choice(cB, 8192, replace=False); ff = r2.choice(np.setdiff1d(hB, dd), 144, replace=False)
        stA.append(np.concatenate([posA, cc, ee])); stB.append(np.concatenate([posB, dd, ff]))
        assert len(np.unique(stA[-1])) == len(stA[-1]) and len(np.unique(stB[-1])) == len(stB[-1])
    np.savez_compressed(OUT / 'hoco_A.npz', **{k: A[k] for k in A if k != 'aux'}, aux=A['aux'], mean=mean, std=std,
                        pos=posA, idx=np.array(stA), stepsha=np.array([sha(x) for x in stA]))
    np.savez_compressed(OUT / 'hoco_B.npz', **{k: Bg[k] for k in Bg if k != 'aux'}, aux=Bg['aux'], mean=mean, std=std,
                        pos=posB, idx=np.array(stB), stepsha=np.array([sha(x) for x in stB]))
    # val: id/opt
    c2 = json.loads((B / 'input_contract.json').read_text(encoding='utf-8'))
    vv = {v['view']: v for v in c2['shared_inputs']['trans_val']['views']}
    folder = B / 'inputs/trans_val'
    x = np.load(folder / 'x39.npy'); edge = np.load(folder / 'edge_index.npy')
    y = np.load(folder / 'y.npy'); tr = np.load(folder / 'trusted.npy'); ph = np.load(folder / 'physical.npy')
    kv = [v for v in vv if v.split('__')[-1] in ('ys_id', 'ys_opt')]
    rows = np.concatenate([np.arange(vv[v]['start'], vv[v]['stop']) for v in kv])
    o2n = np.full(len(y), -1, np.int64); o2n[rows] = np.arange(len(rows))
    m = (o2n[edge[0]] >= 0) & (o2n[edge[1]] >= 0)
    xx = np.array(x[rows], np.float32, copy=True); xx[:, 25:] = np.clip((xx[:, 25:] - mean) / std, -10, 10)
    np.savez_compressed(OUT / 'hoco_val.npz', x=xx, edge=np.stack([o2n[edge[0][m]], o2n[edge[1][m]]]),
                        y=y[rows], trusted=tr[rows], physical=ph[rows], rows=rows, old2new=o2n, new2old=rows,
                        views=np.array(kv), mean=mean, std=std)
    man = dict(A_views=len(ka), B_views=len(kb), A_nodes=len(A['y']), B_nodes=len(Bg['y']), aux_A=A['aux'], aux_B=Bg['aux'],
               sources=len(srcs), quota_total=int(sum(quota.values())), commonA=len(cA), commonB=len(cB), hA=len(hA), hB=len(hB),
               val_views=len(kv), val_nodes=len(rows), mean_sha=sha(np.concatenate([mean, std])),
               step0_A=sha(stA[0]), step0_B=sha(stB[0]))
    (OUT / 'INPUT_MANIFEST.json').write_text(json.dumps(man, indent=2), encoding='utf-8')
    print(json.dumps(man, ensure_ascii=False))


if __name__ == '__main__':
    main()
