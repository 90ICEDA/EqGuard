"""Four-group executable assets: A/B subgraphs, quota sampling, cone budget, shared normalization,
shared interface + real step0 precheck. No training."""
import os
for k in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
    os.environ[k] = '1'
os.environ['P2B_MASK'] = 'old'
import csv, hashlib, json, sys
from pathlib import Path
import numpy as np, torch

R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = R / '_p0pilot/four_group_contract_20261109'
V5 = R / '_p0pilot/heldout_recipe_v5_20261109'
V4 = R / '_p0pilot/heldout_recipe_v4_20261109'
B = R / '_p0pilot/control_boundary_v3_20261104'
PREP = R / '_p0pilot/seed42_supervised_prep_20261109'
L = R / '_p0pilot/control_loader_po_20261105'
sys.path.insert(0, str(V5)); sys.path.insert(0, str(L)); sys.path.insert(0, str(R / '_p0pilot/control_best200_20261104'))
sys.path.insert(0, str(R / '_p0pilot/seed42_nc_ablation_20261109'))
import fold_io as F
from supervision_loader import FiveGroupLoader
from evaluate import Model, T
import cone_loss as CL
from sklearn.metrics import average_precision_score

BASE = ('ys_abc', 'ys_id', 'ys_opt')
ADD = ('ys_aig', 'ys_nand')


def sha(a): return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()


def contract(): return json.loads((B / 'input_contract.json').read_text(encoding='utf-8'))


def subgraph(arr, views, keep):
    rows, aux = [], 0
    for v, lay in views.items():
        if v not in keep: continue
        rows.extend(range(lay['start'], lay['stop'])); aux += lay['stop'] - lay['physical_stop']
    rows = np.array(rows, np.int64)
    o2n = np.full(len(arr['y']), -1, np.int64); o2n[rows] = np.arange(len(rows))
    src, dst = arr['edge_index'][0], arr['edge_index'][1]
    m = (o2n[src] >= 0) & (o2n[dst] >= 0)
    return dict(rows=rows, old2new=o2n, new2old=rows,
                x=arr['x39'][rows], y=arr['y'][rows], trusted=arr['trusted'][rows], physical=arr['physical'][rows],
                edge=np.stack([o2n[src[m]], o2n[dst[m]]]), aux=aux)


def main():
    c = contract(); vs = {v['view']: v for v in c['shared_inputs']['trans_train']['views']}
    files = {k: np.load(B / 'inputs' / f'trans_train/{k}.npy') for k in ('x39', 'edge_index', 'y', 'trusted', 'physical')}
    A_keep = {v for v in vs if v.split('__')[-1] in BASE}
    B_keep = {v for v in vs if v.split('__')[-1] in BASE + ADD}
    A = subgraph(files, vs, A_keep); Bg = subgraph(files, vs, B_keep)
    srcA = {v.split('__ys_')[0] for v in A_keep}; srcB = {v.split('__ys_')[0] for v in B_keep}
    assert srcA == srcB and len(srcA) == 66
    # per-source positive quota and 502 positive ids
    def pos_by_src(g, keep):
        out = {}
        for v in keep:
            lay = vs[v]; a, b = lay['start'], lay['stop']
            s = v.split('__ys_')[0]
            e = (files['y'][a:b] == 1) & files['trusted'][a:b] & files['physical'][a:b]
            idx = np.arange(a, b)[e]
            out.setdefault(s, []).extend(g['old2new'][idx].tolist())
        return {k: sorted(v) for k, v in out.items()}
    pa, pb = pos_by_src(A, A_keep), pos_by_src(Bg, B_keep)
    quota = {s: min(len(pa[s]), len(pb[s])) for s in pa}
    assert sum(quota.values()) == 502, sum(quota.values())
    posA = np.array([x for s in sorted(quota) for x in pa[s][:quota[s]]], np.int64)
    posB = np.array([x for s in sorted(quota) for x in pb[s][:quota[s]]], np.int64)
    # pools: eligible negatives
    def pools(g):
        elig = (g['y'] == 0) & g['trusted'] & g['physical']
        return np.where(elig)[0].astype(np.int64)
    poolA, poolB = pools(A), pools(Bg)
    rng = np.random.default_rng(42)
    stepsA, stepsB = [], []
    for step in range(200):
        r = np.random.default_rng(42 + step)
        cA = r.choice(poolA, 8192, replace=False)
        restA = np.setdiff1d(poolA, cA, assume_unique=False)
        eA = r.choice(restA, 144, replace=False)
        r2 = np.random.default_rng(42 + step)
        cB = r2.choice(poolB, 8192, replace=False)
        restB = np.setdiff1d(poolB, cB, assume_unique=False)
        eB = r2.choice(restB, 144, replace=False)
        stepsA.append(np.concatenate([posA, cA, eA]).astype(np.int64))
        stepsB.append(np.concatenate([posB, cB, eB]).astype(np.int64))
        assert len(np.unique(stepsA[-1])) == len(stepsA[-1]) and len(np.unique(stepsB[-1])) == len(stepsB[-1])
    # normalization on A orig+trans train
    orig = np.load(B / 'inputs/orig_train/x39.npy')
    cat = np.concatenate([orig[:, 25:], A['x'][:, 25:]], 0)
    mean = cat.mean(0).astype(np.float32); std = cat.std(0).astype(np.float32); std[std < 1e-6] = 1.0
    # cone budget: D cones trusted>=2, per source min pos/neg, 1:1
    coneA, coneB = {}, {}
    with (PREP / 'CONE_CACHE_V2.csv').open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    for g, keep, store in ((A, A_keep, coneA), (Bg, B_keep, coneB)):
        for r in rows:
            if r['split'] != 'train' or r['kind'] != 'D' or int(r['label']) < 0 or int(r['n_phys']) < 2:
                continue
            if r['view'] not in keep: continue
            mem = [int(g['old2new'][int(x)]) for x in r['phys_rows'].split('|') if x and g['old2new'][int(x)] >= 0]
            mem = [x for x in mem if bool(g['trusted'][x]) and bool(g['physical'][x])]
            if len(mem) < 2: continue
            s = r['view'].split('__ys_')[0]
            store.setdefault(s, {})[r['cone_id']] = (int(r['label']), mem)
    def budget(store):
        sel = []
        for s in sorted(quota):
            pos = [k for k, v in store.get(s, {}).items() if v[0] == 1]
            neg = [k for k, v in store.get(s, {}).items() if v[0] == 0]
            n = min(len(pos), len(neg))
            if n == 0: continue
            rr = np.random.default_rng(7)
            sel += [(k, store[s][k]) for k in pos[:n]]
            sel += [(k, store[s][k]) for k in rr.choice(neg, n, replace=False).tolist()] if False else [(k, store[s][k]) for k in neg[:n]]
        return sel
    selA, selB = budget(coneA), budget(coneB)
    def _cnt(sel, lab): return sum(1 for _, (l, _) in sel if l == lab)
    npos = min(_cnt(selA, 1), _cnt(selB, 1)); nneg = min(_cnt(selA, 0), _cnt(selB, 0))
    def bal(sel):
        return ([x for x in sel if x[1][0] == 1][:npos] + [x for x in sel if x[1][0] == 0][:nneg])
    selA, selB = bal(selA), bal(selB)
    def pack(sel):
        flat, ptr = [], [0]
        for _, (lab, mem) in sel:
            flat.extend(mem); ptr.append(len(flat))
        return np.array(flat, np.int64), np.array([lab for _, (lab, _) in sel], np.int8), np.array(ptr, np.int64)
    # save assets
    OUT.mkdir(exist_ok=True)
    for tag, g, steps, sel in (('A', A, stepsA, selA), ('B', Bg, stepsB, selB)):
        flat, lab, ptr = pack(sel)
        np.savez_compressed(OUT / f'group_{tag}.npz',
                            **{k: g[k] for k in ('x', 'y', 'trusted', 'physical', 'rows', 'edge', 'old2new', 'new2old')},
                            mean=mean, std=std, pos=(posA if tag == 'A' else posB),
                            steps=np.array([sha(x) for x in steps]),
                            cone_rows=flat, cone_label=lab, cone_ptr=ptr)
    rep = dict(A_views=len(A_keep), B_views=len(B_keep), sources=len(srcA), aux_A=A['aux'], aux_B=Bg['aux'],
               nodes_A=len(A['y']), nodes_B=len(Bg['y']), quota_total=int(sum(quota.values())),
               poolA=len(poolA), poolB=len(poolB), cone_A=len(selA), cone_B=len(selB),
               cone_pos_A=sum(1 for _, (l, _) in selA if l == 1), cone_pos_B=sum(1 for _, (l, _) in selB if l == 1),
               norm_sha=sha(np.concatenate([mean, std])), step0_A=sha(stepsA[0]), step0_B=sha(stepsB[0]))
    (OUT / 'ASSETS.json').write_text(json.dumps(rep, indent=2), encoding='utf-8')
    print(json.dumps(rep, ensure_ascii=False))


if __name__ == '__main__':
    main()
