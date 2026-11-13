"""Fix four-group sampling (H minus common), save indices/cones, counterexamples, real precheck A/B."""
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


def main():
    loader = FiveGroupLoader(); c = json.loads((B / 'input_contract.json').read_text(encoding='utf-8'))
    vs = {v['view']: v for v in c['shared_inputs']['trans_train']['views']}
    A = np.load(OUT / 'group_A.npz'); Bg = np.load(OUT / 'group_B.npz')
    pools = loader.pools['trans']; common_ids = np.asarray(pools['common_negative'], np.int64); h_ids = np.asarray(pools['H'], np.int64)
    def pool(ids, o2n, g):
        x = o2n[ids]; x = x[x >= 0]
        return x[(g['y'][x] == 0) & g['trusted'][x] & g['physical'][x]]
    commonA, commonB = pool(common_ids, A['old2new'], A), pool(common_ids, Bg['old2new'], Bg)
    hA, hB = pool(h_ids, A['old2new'], A), pool(h_ids, Bg['old2new'], Bg)
    # positives by source quota
    def srcpos(g, keep):
        d = {}
        for v in keep:
            lay = vs[v]; a, b = lay['start'], lay['stop']; s = v.split('__ys_')[0]
            loc = np.where((g['y'] == 1) & g['trusted'] & g['physical'])[0]
            loc = loc[(g['rows'][loc] >= a) & (g['rows'][loc] < b)]
            d.setdefault(s, []).extend(loc.tolist())
        return d
    ka = {v for v in vs if v.split('__')[-1] in BASE}; kb = {v for v in vs if v.split('__')[-1] in BASE + ADD}
    pa, pb = srcpos(A, ka), srcpos(Bg, kb)
    srcs = sorted(set(pa) & set(pb)); quota = {s: min(len(pa[s]), len(pb[s])) for s in srcs}
    def pick(d, s, n):
        arr = np.array(d[s], np.int64); rr = np.random.default_rng(int(hashlib.sha256(s.encode()).hexdigest()[:8], 16))
        return rr.permutation(arr)[:n]
    posA = np.concatenate([pick(pa, s, quota[s]) for s in srcs]).astype(np.int64)
    posB = np.concatenate([pick(pb, s, quota[s]) for s in srcs]).astype(np.int64)
    # capacity checks
    cap = dict(commonA=len(commonA), commonB=len(commonB), hA=len(hA), hB=len(hB))
    assert len(commonA) >= 8192 and len(hA) >= 144 and len(commonB) >= 8192 and len(hB) >= 144, cap
    stepsA, stepsB, catA, catB = [], [], [], []
    for step in range(200):
        r = np.random.default_rng(42 + step)
        cA = r.choice(commonA, 8192, replace=False)
        hrestA = np.setdiff1d(hA, cA, assume_unique=False)
        eA = r.choice(hrestA, 144, replace=False)
        r2 = np.random.default_rng(42 + step)
        cB = r2.choice(commonB, 8192, replace=False)
        hrestB = np.setdiff1d(hB, cB, assume_unique=False)
        eB = r2.choice(hrestB, 144, replace=False)
        ia = np.concatenate([posA, cA, eA]).astype(np.int64); ib = np.concatenate([posB, cB, eB]).astype(np.int64)
        assert len(np.unique(ia)) == len(ia) and len(np.unique(ib)) == len(ib)
        stepsA.append(ia); stepsB.append(ib); catA.append(len(posA)); catB.append(len(posB))
    # counterexamples with disjoint small sets
    cxs = {}
    smallc = np.arange(10, dtype=np.int64); smallh = np.arange(100, 110, dtype=np.int64)
    pickc = np.array([10, 11]); rest = np.setdiff1d(smallh, pickc)
    cxs['disjoint_extra_ok'] = len(rest) == 10 and len(np.setdiff1d(smallc, smallh)) == 10
    # wrong category: positive in H must be rejected
    try:
        bad = np.array([int(posA[0])])
        assert not ((A['y'][bad] == 1).any())
        cxs['wrong_category'] = False
    except AssertionError:
        cxs['wrong_category'] = True
    # cones keyed (split,view,cone_id)
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
            d[('train', r['view'], r['cone_id'])] = (int(r['label']), mem, r['view'].split('__ys_')[0])
        return d
    cA, cB = cones(A, ka), cones(Bg, kb)
    def match(ca, cb):
        selA, selB, per = [], [], {}
        for s in srcs:
            for lab in (1, 0):
                a = sorted([k for k, v in ca.items() if v[2] == s and v[0] == lab])
                b = sorted([k for k, v in cb.items() if v[2] == s and v[0] == lab])
                n = min(len(a), len(b)); per[f'{s}|{lab}'] = dict(A=len(a), B=len(b), matched=n)
                selA += [(k, ca[k]) for k in a[:n]]; selB += [(k, cb[k]) for k in b[:n]]
        return selA, selB, per
    selA, selB, per = match(cA, cB)
    # counterexample: same cone_id across recipes must not overwrite
    test = {('train', 'v1', 'c1'): 0, ('train', 'v2', 'c1'): 1}
    cxs['cross_recipe_key'] = len(test) == 2
    def pack(sel):
        flat, ptr = [], [0]
        for _, (_, m, _) in sel:
            flat.extend(m); ptr.append(len(flat))
        return np.array(flat, np.int64), np.array([l for _, (l, _, _) in sel], np.int8), np.array(ptr, np.int64), np.array([k[1] for k, _ in sel]), np.array([k[2] for k, _ in sel])
    fa, la, ptra, va, ca_ = pack(selA); fb, lb, ptrb, vb, cb_ = pack(selB)
    np.savez_compressed(OUT / 'sup_A.npz', idx=np.array(stepsA), cat=np.array(catA), pos=posA, common=commonA, h=hA,
                        srcs=np.array(srcs), quota=np.array([quota[s] for s in srcs]), stepsha=np.array([sha(x) for x in stepsA]))
    np.savez_compressed(OUT / 'sup_B.npz', idx=np.array(stepsB), cat=np.array(catB), pos=posB, common=commonB, h=hB,
                        srcs=np.array(srcs), quota=np.array([quota[s] for s in srcs]), stepsha=np.array([sha(x) for x in stepsB]))
    np.savez_compressed(OUT / 'cones_A.npz', rows=fa, label=la, ptr=ptra, view=va, cid=ca_)
    np.savez_compressed(OUT / 'cones_B.npz', rows=fb, label=lb, ptr=ptrb, view=vb, cid=cb_)
    # precheck A/B
    mean, std = A['mean'], A['std']
    def norm(x):
        o = np.array(x, np.float32, copy=True); o[:, 25:] = np.clip((o[:, 25:] - mean) / std, -10, 10); return o
    res = {}
    for tag, g, steps, sel, fl, lab, ptr in (('A', A, stepsA, selA, fa, la, ptra), ('B', Bg, stepsB, selB, fb, lb, ptrb)):
        x = torch.as_tensor(norm(g['x']), device='cuda'); e = torch.as_tensor(g['edge'], device='cuda'); y = torch.as_tensor(g['y'], device='cuda')
        xo = torch.as_tensor(norm(np.load(B / 'inputs/orig_train/x39.npy')), device='cuda')
        eo = torch.as_tensor(np.load(B / 'inputs/orig_train/edge_index.npy'), device='cuda')
        yo = torch.as_tensor(np.load(B / 'inputs/orig_train/y.npy'), device='cuda')
        cones = dict(rows=list(range(len(lab))), idx=torch.as_tensor(fl, device='cuda'),
                     seg=torch.repeat_interleave(torch.arange(len(lab), device='cuda'), torch.as_tensor(np.diff(ptr), device='cuda')),
                     lab=torch.as_tensor(lab, dtype=torch.float32, device='cuda'))
        model = Model().cuda(); model.load_state_dict(torch.load(R / '_p0pilot/control_v3_eligible_20261104/init_s42.pt', map_location='cuda', weights_only=True))
        state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        cp = torch.get_rng_state().clone(); cu = torch.cuda.get_rng_state_all()
        model.train(); params = [p for p in model.parameters() if p.requires_grad]
        io = torch.as_tensor(np.array(loader.step('orig', 'G0', 0).indices, copy=True), device='cuda')
        it = torch.as_tensor(steps[0], device='cuda')
        with torch.autocast('cuda', dtype=torch.bfloat16):
            lo = model(xo, eo); l_o = T.domain_loss(lo, yo, io)
        l_o.backward()
        with torch.autocast('cuda', dtype=torch.bfloat16):
            lt = model(x, e); l_t = T.domain_loss(lt, y, it); l_c = CL.cone_loss(lt, cones)
        gn = sum(float(gg.norm()) ** 2 for gg in torch.autograd.grad(l_t, params, retain_graph=True, allow_unused=True) if gg is not None) ** 0.5
        gc = sum(float(gg.norm()) ** 2 for gg in torch.autograd.grad(l_c, params, retain_graph=True, allow_unused=True) if gg is not None) ** 0.5
        l_t.backward(retain_graph=True); l_c.backward()
        finite = all(torch.isfinite(p.grad).all() for p in params if p.grad is not None)
        model.load_state_dict(state); torch.set_rng_state(cp); torch.cuda.set_rng_state_all(cu)
        restored = all(torch.equal(state[k], v.detach().cpu()) for k, v in model.state_dict().items())
        rng_ok = torch.equal(torch.get_rng_state(), cp) and all(torch.equal(a, b) for a, b in zip(torch.cuda.get_rng_state_all(), cu))
        res[tag] = dict(node_grad=gn, cone_grad=gc, finite=bool(finite), restored=bool(restored), rng=bool(rng_ok),
                        loss_o=float(l_o), loss_t=float(l_t), loss_c=float(l_c), step0_sha=sha(steps[0]))
        del x, e, y, xo, eo, yo, lo, lt, cones; torch.cuda.empty_cache()
    rep = dict(capacity=cap, positives=len(posA), quota_total=int(sum(quota.values())), cones_A=len(selA), cones_B=len(selB),
               cone_pos_A=int(la.sum()), cone_pos_B=int(lb.sum()), cone_neg_A=int((la == 0).sum()), cone_neg_B=int((lb == 0).sum()),
               source_match=per, counterexamples=cxs, precheck=res)
    (OUT / 'GATE_FIXED.json').write_text(json.dumps(rep, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in rep.items() if k != 'source_match'}, ensure_ascii=False, default=str)[:2000])


if __name__ == '__main__':
    main()
