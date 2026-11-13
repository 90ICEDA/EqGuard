"""Final v4 gate: corrected mappings, shared loader, rejection, 2D margin, real precheck."""
import os
for k in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
    os.environ[k] = '1'
os.environ['P2B_MASK'] = 'old'
import hashlib, json, sys
from pathlib import Path
import numpy as np, torch

R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = R / '_p0pilot/heldout_recipe_v4_20261109'
B = R / '_p0pilot/control_boundary_v3_20261104'
L = R / '_p0pilot/control_loader_po_20261105'
V = R / '_p0pilot/control_v3_eligible_20261104'
sys.path.insert(0, str(L)); sys.path.insert(0, str(R / '_p0pilot/control_best200_20261104'))
sys.path.insert(0, str(R / '_p0pilot/seed42_nc_ablation_20261109'))
from supervision_loader import FiveGroupLoader
from evaluate import Model, T
import cone_loss as CL
from sklearn.metrics import average_precision_score

RECIPES = ('ys_abc', 'ys_aig', 'ys_nand')
EXPECT = {'ys_abc': 1073607, 'ys_aig': 895147, 'ys_nand': 892130}


def views(split):
    c = json.loads((B / 'input_contract.json').read_text(encoding='utf-8'))
    return {v['view']: v for v in c['shared_inputs'][f'trans_{split}']['views']}


def norm(x, mean, std):
    o = np.array(x, np.float32, copy=True); o[:, 25:] = np.clip((o[:, 25:] - mean) / std, -10, 10); return o


def margin(lg): return lg[:, 1] - lg[:, 0]


def load(rec, split='train', extra=()):
    z = np.load(OUT / f'{rec}_{split}_map.npz')
    zt = np.load(OUT / f'{rec}_train_map.npz')
    if extra:
        bad = [v for v in extra if rec in v]
        if bad: raise ValueError(f'held-out recipe view injected: {bad[0]}')
    out = dict(x=norm(z['x'], zt['mean'], zt['std']), edge=z['edge'], y=z['y'], trusted=z['trusted'],
               physical=z['physical'], rows=z['rows'], old2new=z['old2new'], new2old=z['new2old'])
    for k in ('pos', 'common_pool', 'h_pool', 'cone_rows', 'cone_label', 'cone_ptr'):
        if k in z.files: out[k] = z[k]
    return out


def main():
    loader = FiveGroupLoader()
    T.CONTRACT = loader.feature_contract; T.NORM = loader.normalization; T.arrays = loader.arrays
    checks = []
    for rec in RECIPES:
        d = load(rec)
        z = np.load(OUT / f'{rec}_train_map.npz')
        rows = z['rows']; o2n = z['old2new']; n2o = z['new2old']
        raw = np.load(B / 'inputs/trans_train/x39.npy')
        src, dst = np.load(B / 'inputs/trans_train/edge_index.npy')
        m = (o2n[src] >= 0) & (o2n[dst] >= 0)
        ok = (np.array_equal(n2o, rows) and np.array_equal(o2n[n2o], np.arange(len(rows)))
              and np.array_equal(raw[rows], z['x']) and np.array_equal(z['edge'][0], o2n[src[m]]))
        checks.append(dict(fold=rec, name='mapping', passed=bool(ok), detail='new2old=rows, roundtrip, features, edges'))
        checks.append(dict(fold=rec, name='nodes', passed=len(d['y']) == EXPECT[rec], detail=str(len(d['y']))))
        checks.append(dict(fold=rec, name='norm', passed=bool(np.array_equal(d['x'][:, :25], raw[rows][:, :25]) and d['x'][:, 25:].max() <= 10 + 1e-6), detail='cols0:25 unchanged; 25:39 clipped'))
        held = [v for v in views('train') if rec in v and v.startswith(('rs232t1000', 's15850t100', 's35932t200'))]
        try:
            load(rec, extra=[held[0]]); rej = False
        except ValueError as e:
            rej = 'held-out recipe view injected' in str(e)
        checks.append(dict(fold=rec, name='rejection', passed=rej, detail=held[0]))
        pos = d['pos']; hh = []
        for step in range(200):
            rng = np.random.default_rng(42 + step)
            ids = np.concatenate([pos, rng.choice(d['common_pool'], 8192, replace=False), rng.choice(d['h_pool'], 144, replace=False)]).astype(np.int64)
            hh.append(hashlib.sha256(ids.tobytes()).hexdigest())
        checks.append(dict(fold=rec, name='g0', passed=(len(pos) + 8336 == len(ids)) and hh[0] == str(z['steps'][0]) and bool(d['trusted'][ids].all()), detail=f'pos={len(pos)}, total={len(ids)}'))
        # 2D margin
        zv = load(rec, 'val')
        lg = np.random.default_rng(1).normal(size=(len(zv['y']), 2)).astype(np.float64)
        c = np.random.default_rng(2).normal(size=(len(zv['y']), 1))
        a1 = average_precision_score(zv['y'][zv['trusted']], margin(lg)[zv['trusted']])
        a2 = average_precision_score(zv['y'][zv['trusted']], margin(lg + c)[zv['trusted']])
        k = max(1, int(zv['trusted'].sum() * 0.01))
        t1 = set(np.argsort(-margin(lg))[:k]); t2 = set(np.argsort(-margin(lg + c))[:k])
        c1 = set(np.argsort(-(lg[:, 1] + c[:, 0]))[:k])
        checks.append(dict(fold=rec, name='margin2d', passed=bool(abs(a1 - a2) < 1e-9 and t1 == t2 and c1 != t1), detail=f'AP {a1:.6f}/{a2:.6f}, wrong-col differs={c1!=t1}'))
        # precheck
        model = Model().cuda(); model.load_state_dict(torch.load(V / 'init_s42.pt', map_location='cuda', weights_only=True))
        state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        cpu = torch.get_rng_state().clone(); cuda = torch.cuda.get_rng_state_all()
        model.train()
        x = torch.as_tensor(d['x'], device='cuda'); e = torch.as_tensor(d['edge'], device='cuda'); y = torch.as_tensor(d['y'], device='cuda')
        ids_t = torch.as_tensor(np.concatenate([pos, np.random.default_rng(42).choice(d['common_pool'], 8192, replace=False), np.random.default_rng(43).choice(d['h_pool'], 144, replace=False)]).astype(np.int64), device='cuda')
        cones = dict(rows=list(range(len(d['cone_label']))), idx=torch.as_tensor(d['cone_rows'], device='cuda'),
                     seg=torch.repeat_interleave(torch.arange(len(d['cone_label']), device='cuda'), torch.as_tensor(np.diff(d['cone_ptr']), device='cuda')),
                     lab=torch.as_tensor(d['cone_label'], dtype=torch.float32, device='cuda'))
        do = loader.torch_graph('orig', 'train', 'cuda'); q = loader.step('orig', 'G0', 0)
        io = torch.as_tensor(np.array(q.indices, copy=True), device='cuda')
        opt = torch.optim.Adam(model.parameters(), lr=2e-4, weight_decay=1e-3); opt.zero_grad(set_to_none=True)
        params = [p for p in model.parameters() if p.requires_grad]
        with torch.autocast('cuda', dtype=torch.bfloat16):
            lo = model(do['x'], do['edge']); l_o = T.domain_loss(lo, do['y'], io)
        l_o.backward()
        with torch.autocast('cuda', dtype=torch.bfloat16):
            lt = model(x, e); l_t = T.domain_loss(lt, y, ids_t); l_c = CL.cone_loss(lt, cones)
        gnode = torch.autograd.grad(l_t, params, retain_graph=True, allow_unused=True)
        gcone = torch.autograd.grad(l_c, params, retain_graph=True, allow_unused=True)
        l_t.backward(retain_graph=True); l_c.backward()
        finite = all(torch.isfinite(p.grad).all() for p in params if p.grad is not None)
        gn = sum(float(g.norm()) ** 2 for g in gnode if g is not None) ** 0.5
        gc = sum(float(g.norm()) ** 2 for g in gcone if g is not None) ** 0.5
        model.load_state_dict(state); torch.set_rng_state(cpu); torch.cuda.set_rng_state_all(cuda)
        restored = all(torch.equal(state[k], v.detach().cpu()) for k, v in model.state_dict().items())
        checks.append(dict(fold=rec, name='precheck', passed=bool(finite and gc > 0 and restored),
                           detail=f'node_grad={gn:.3f}, cone_grad={gc:.3f}, finite={finite}, restored={restored}, 0step'))
        del x, e, y, cones, do, lo, lt; torch.cuda.empty_cache()
    gate = dict(passed=all(c['passed'] for c in checks), checks=checks)
    (OUT / 'GATE_V4.json').write_text(json.dumps(gate, indent=2), encoding='utf-8')
    for c in checks:
        if not c['passed']: print('FAIL', c['fold'], c['name'], c['detail'])
    print('GATE', gate['passed'], len(checks))


if __name__ == '__main__':
    main()
