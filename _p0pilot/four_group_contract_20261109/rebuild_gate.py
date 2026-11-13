"""Rebuild four-group supervision from contract pools + real model precheck (no training)."""
import os
for k in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
    os.environ[k] = '1'
os.environ['P2B_MASK'] = 'old'
import csv, hashlib, json, sys
from pathlib import Path
import numpy as np, torch

R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = R / '_p0pilot/four_group_contract_20261109'
B = R / '_p0pilot/control_boundary_v3_20261104'
PREP = R / '_p0pilot/seed42_supervised_prep_20261109'
L = R / '_p0pilot/control_loader_po_20261105'
sys.path.insert(0, str(L)); sys.path.insert(0, str(R / '_p0pilot/control_best200_20261104'))
sys.path.insert(0, str(R / '_p0pilot/seed42_nc_ablation_20261109'))
from supervision_loader import FiveGroupLoader
from evaluate import Model, T
import cone_loss as CL
from sklearn.metrics import average_precision_score

BASE = ('ys_abc', 'ys_id', 'ys_opt'); ADD = ('ys_aig', 'ys_nand')


def sha(a): return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()


def contract(): return json.loads((B / 'input_contract.json').read_text(encoding='utf-8'))


def main():
    loader = FiveGroupLoader()
    c = contract(); vs = {v['view']: v for v in c['shared_inputs']['trans_train']['views']}
    pools = loader.pools['trans']
    common_ids = np.asarray(pools['common_negative'], np.int64)
    h_ids = np.asarray(pools['H'], np.int64)
    rowsA = np.load(OUT / 'group_A.npz')['rows']; rowsB = np.load(OUT / 'group_B.npz')['rows']
    o2a = np.load(OUT / 'group_A.npz')['old2new']; o2b = np.load(OUT / 'group_B.npz')['old2new']
    A = np.load(OUT / 'group_A.npz'); Bg = np.load(OUT / 'group_B.npz')
    def filt(ids, o2n):
        m = (o2n[ids] >= 0)
        return o2n[ids[m]]
    commonA, commonB = filt(common_ids, o2a), filt(common_ids, o2b)
    hA, hB = filt(h_ids, o2a), filt(h_ids, o2b)
    # eligibility: negatives trusted physical y=0 and not positives
    def elig(pool, g):
        return pool[(g['y'][pool] == 0) & g['trusted'][pool] & g['physical'][pool]]
    commonA, commonB = elig(commonA, A), elig(commonB, Bg)
    hA, hB = elig(hA, A), elig(hB, Bg)
    posA_all = np.where((A['y'] == 1) & A['trusted'] & A['physical'])[0]
    # per-source positives and recipe identity
    def pos_src(g, rows, views):
        out = {}
        for v in views:
            lay = vs[v]; a, b = lay['start'], lay['stop']
            e = (g['y'] == 1) & g['trusted'] & g['physical']
            # local ids whose rows in [a,b)
            loc = np.where(e)[0]
            loc = loc[(g['rows'][loc] >= a) & (g['rows'][loc] < b)]
            out.setdefault(v, []).append((v.split('__ys_')[0], v.split('__')[-1], loc))
        return out
    srcpos = {}
    for g, views, tag in ((A, [v for v in vs if v.split('__')[-1] in BASE], 'A'),
                          (Bg, [v for v in vs if v.split('__')[-1] in BASE + ADD], 'B')):
        d = {}
        for v in views:
            lay = vs[v]; a, b = lay['start'], lay['stop']
            loc = np.where((g['y'] == 1) & g['trusted'] & g['physical'])[0]
            loc = loc[(g['rows'][loc] >= a) & (g['rows'][loc] < b)]
            s = v.split('__ys_')[0]
            d.setdefault(s, []).extend(loc.tolist())
        srcpos[tag] = d
    common_src = sorted(set(srcpos['A']) & set(srcpos['B']))
    quota = {s: min(len(srcpos['A'][s]), len(srcpos['B'][s])) for s in common_src}
    def pick(d, s, n):
        arr = np.array(sorted(d[s]), np.int64)
        rr = np.random.default_rng(int(hashlib.sha256(s.encode()).hexdigest()[:8], 16))
        return rr.permutation(arr)[:n]
    posA = np.concatenate([pick(srcpos['A'], s, quota[s]) for s in common_src]).astype(np.int64)
    posB = np.concatenate([pick(srcpos['B'], s, quota[s]) for s in common_src]).astype(np.int64)
    stepsA, stepsB = [], []
    for step in range(200):
        r = np.random.default_rng(42 + step)
        cA = r.choice(commonA, 8192, replace=False); restA = np.setdiff1d(commonA, cA)
        eA = r.choice(np.intersect1d(restA, hA), 144, replace=False)
        r2 = np.random.default_rng(42 + step)
        cB = r2.choice(commonB, 8192, replace=False); restB = np.setdiff1d(commonB, cB)
        eB = r2.choice(np.intersect1d(restB, hB), 144, replace=False)
        stepsA.append(np.concatenate([posA, cA, eA]).astype(np.int64))
        stepsB.append(np.concatenate([posB, cB, eB]).astype(np.int64))
        assert len(np.unique(stepsA[-1])) == len(stepsA[-1]) == len(posA) + 8336
        assert len(np.unique(stepsB[-1])) == len(stepsB[-1]) == len(posB) + 8336
    # cones keyed (view,cone_id); per-source pos/neg quotas matched across groups
    rows = list(csv.DictReader((PREP / 'CONE_CACHE_V2.csv').open(encoding='utf-8-sig', newline='')))
    def cones(g, keep):
        d = {}
        for r in rows:
            if r['split'] != 'train' or r['kind'] != 'D' or int(r['label']) < 0 or int(r['n_phys']) < 2:
                continue
            if r['view'] not in keep: continue
            mem = [int(g['old2new'][int(x)]) for x in r['phys_rows'].split('|') if x and g['old2new'][int(x)] >= 0]
            mem = [x for x in mem if bool(g['trusted'][x]) and bool(g['physical'][x])]
            if len(mem) < 2: continue
            d[(r['view'], r['cone_id'])] = (int(r['label']), mem, r['view'].split('__ys_')[0])
        return d
    cA = cones(A, {v for v in vs if v.split('__')[-1] in BASE})
    cB = cones(Bg, {v for v in vs if v.split('__')[-1] in BASE + ADD})
    def match(ca, cb):
        selA, selB = [], []
        for s in common_src:
            pa = sorted([k for k, v in ca.items() if v[2] == s and v[0] == 1])
            pb = sorted([k for k, v in cb.items() if v[2] == s and v[0] == 1])
            na = sorted([k for k, v in ca.items() if v[2] == s and v[0] == 0])
            nb = sorted([k for k, v in cb.items() if v[2] == s and v[0] == 0])
            npos = min(len(pa), len(pb)); nneg = min(len(na), len(nb))
            selA += [(k, ca[k]) for k in pa[:npos]] + [(k, ca[k]) for k in na[:nneg]]
            selB += [(k, cb[k]) for k in pb[:npos]] + [(k, cb[k]) for k in nb[:nneg]]
        return selA, selB
    selA, selB = match(cA, cB)
    rep = dict(A_views=len([v for v in vs if v.split('__')[-1] in BASE]), B_views=len([v for v in vs if v.split('__')[-1] in BASE + ADD]),
               sources=len(common_src), quota_total=int(len(posA)), commonA=len(commonA), commonB=len(commonB),
               hA=len(hA), hB=len(hB), conesA=len(selA), conesB=len(selB),
               cone_posA=sum(1 for _, (l, _, _) in selA if l == 1), cone_posB=sum(1 for _, (l, _, _) in selB if l == 1),
               cone_negA=sum(1 for _, (l, _, _) in selA if l == 0), cone_negB=sum(1 for _, (l, _, _) in selB if l == 0),
               pos_total_A=int(len(posA)), pos_total_B=int(len(posB)))
    # counterexamples
    keyed = {(v['view'], 'c1'): 0 for v in [vs[list(vs)[0]]]}; keyed[(list(vs)[1], 'c1')] = 1
    cx1 = len(keyed) == 2
    def accept_neg(ids, g):
        if bool((g['y'][ids] == 1).any()): raise ValueError('positive in negative pool')
        if not bool(g['trusted'][ids].all() and g['physical'][ids].all()): raise ValueError('ineligible')
        return True
    try:
        accept_neg(np.array([int(posA[0])]), A); cx2 = False
    except ValueError:
        cx2 = True
    # save indices
    np.savez_compressed(OUT / 'sup_A.npz', steps=np.array([sha(x) for x in stepsA]), pos=posA,
                        common=commonA, extra=hA, quota=np.array(list(quota.values())), srcs=np.array(common_src))
    np.savez_compressed(OUT / 'sup_B.npz', steps=np.array([sha(x) for x in stepsB]), pos=posB,
                        common=commonB, extra=hB, quota=np.array(list(quota.values())), srcs=np.array(common_src))
    ptrA = np.array([0] + list(np.cumsum([len(m) for _, (_, m, _) in selA])), np.int64)
    ptrB = np.array([0] + list(np.cumsum([len(m) for _, (_, m, _) in selB])), np.int64)
    np.savez_compressed(OUT / 'cones_A.npz', ptr=ptrA, rows=np.array([x for _, (_, m, _) in selA for x in m], np.int64),
                        label=np.array([l for _, (l, _, _) in selA], np.int8),
                        view=np.array([k[0] for k, _ in selA]), cid=np.array([k[1] for k, _ in selA]))
    np.savez_compressed(OUT / 'cones_B.npz', ptr=ptrB, rows=np.array([x for _, (_, m, _) in selB for x in m], np.int64),
                        label=np.array([l for _, (l, _, _) in selB], np.int8),
                        view=np.array([k[0] for k, _ in selB]), cid=np.array([k[1] for k, _ in selB]))
    # precheck
    def normal(x, mean, std):
        o = np.array(x, np.float32, copy=True); o[:, 25:] = np.clip((o[:, 25:] - mean) / std, -10, 10); return o
    mean, std = A['mean'], A['std']
    xa = torch.as_tensor(normal(A['x'], mean, std), device='cuda'); ea = torch.as_tensor(A['edge'], device='cuda'); ya = torch.as_tensor(A['y'], device='cuda')
    xo = torch.as_tensor(normal(np.load(B / 'inputs/orig_train/x39.npy'), mean, std), device='cuda')
    eo = torch.as_tensor(np.load(B / 'inputs/orig_train/edge_index.npy'), device='cuda')
    yo = torch.as_tensor(np.load(B / 'inputs/orig_train/y.npy'), device='cuda')
    cones_t = dict(rows=list(range(len(selA))), idx=torch.as_tensor([x for _, (_, m, _) in selA for x in m], device='cuda'),
                   seg=torch.repeat_interleave(torch.arange(len(selA), device='cuda'), torch.as_tensor(np.diff(ptrA), device='cuda')),
                   lab=torch.as_tensor([l for _, (l, _, _) in selA], dtype=torch.float32, device='cuda'))
    model = Model().cuda(); model.load_state_dict(torch.load(R / '_p0pilot/control_v3_eligible_20261104/init_s42.pt', map_location='cuda', weights_only=True))
    state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
    cp = torch.get_rng_state().clone(); cu = torch.cuda.get_rng_state_all()
    model.train()
    params = [p for p in model.parameters() if p.requires_grad]
    ids_o = torch.as_tensor(np.array(loader.step('orig', 'G0', 0).indices, copy=True), device='cuda')
    it = torch.as_tensor(stepsA[0], device='cuda')
    with torch.autocast('cuda', dtype=torch.bfloat16):
        lo = model(xo, eo); l_o = T.domain_loss(lo, yo, ids_o)
    l_o.backward()
    with torch.autocast('cuda', dtype=torch.bfloat16):
        lt = model(xa, ea); l_t = T.domain_loss(lt, ya, it); l_c = CL.cone_loss(lt, cones_t)
    gn = sum(float(g.norm()) ** 2 for g in torch.autograd.grad(l_t, params, retain_graph=True, allow_unused=True) if g is not None) ** 0.5
    gc = sum(float(g.norm()) ** 2 for g in torch.autograd.grad(l_c, params, retain_graph=True, allow_unused=True) if g is not None) ** 0.5
    l_t.backward(retain_graph=True); l_c.backward()
    finite = all(torch.isfinite(p.grad).all() for p in params if p.grad is not None)
    model.load_state_dict(state); torch.set_rng_state(cp); torch.cuda.set_rng_state_all(cu)
    restored = all(torch.equal(state[k], v.detach().cpu()) for k, v in model.state_dict().items())
    rng_ok = torch.equal(torch.get_rng_state(), cp)
    rep.update(precheck=dict(node_grad=gn, cone_grad=gc, finite=bool(finite), restored=bool(restored), rng=bool(rng_ok),
                             loss_o=float(l_o), loss_t=float(l_t), loss_c=float(l_c),
                             counterexample_cone_key=cx1, counterexample_wrong_neg=cx2))
    (OUT / 'SUP_REPORT.json').write_text(json.dumps(rep, indent=2), encoding='utf-8')
    print(json.dumps(rep, ensure_ascii=False))


if __name__ == '__main__':
    main()
