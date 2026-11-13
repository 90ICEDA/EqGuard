"""v5 gate using the shared fold_io interface."""
import os
for k in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
    os.environ[k] = '1'
os.environ['P2B_MASK'] = 'old'
import json, sys
from pathlib import Path
import numpy as np, torch

R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = R / '_p0pilot/heldout_recipe_v5_20261109'
sys.path.insert(0, str(OUT))
sys.path.insert(0, str(R / '_p0pilot/control_loader_po_20261105'))
sys.path.insert(0, str(R / '_p0pilot/control_best200_20261104'))
sys.path.insert(0, str(R / '_p0pilot/seed42_nc_ablation_20261109'))
import fold_io as F
from supervision_loader import FiveGroupLoader
from evaluate import Model, T
import cone_loss as CL
from sklearn.metrics import average_precision_score

RECIPES = F.RECIPES


def main():
    loader = FiveGroupLoader()
    T.CONTRACT = loader.feature_contract; T.NORM = loader.normalization; T.arrays = loader.arrays
    c = F.contract()
    checks = []
    for rec in RECIPES:
        for split in ('train', 'val', 'test'):
            z = np.load(F.V4 / f'{rec}_{split}_map.npz')
            n = c['shared_inputs'][f'trans_{split}']['nodes']
            o2n = z['old2new']; n2o = z['new2old']; rows = z['rows']
            tail = int(rows.max()) + 1
            ok = (len(o2n) == n and np.array_equal(n2o, rows) and np.array_equal(o2n[n2o], np.arange(len(rows)))
                  and (tail >= n or o2n[tail] == -1 if tail < n else True))
            checks.append(dict(fold=rec, split=split, name='mapping',
                               passed=bool(ok), detail=f'old2new_len={len(o2n)}/{n}, roundtrip={np.array_equal(o2n[n2o], np.arange(len(rows)))}'))
            raw = np.load(F.B / 'inputs' / f'trans_{split}/x39.npy')
            mean, std = F.fold_stats(rec)
            ind = np.array(raw, np.float32, copy=True)
            ind[:, 25:] = np.clip((ind[:, 25:] - mean) / std, -10, 10)
            here = F.norm(z['x'], mean, std)
            checks.append(dict(fold=rec, split=split, name='norm_elementwise',
                               passed=bool(np.array_equal(here, ind[rows]) and np.array_equal(here[:, :25], ind[rows][:, :25])),
                               detail='independent formula elementwise'))
        # 200-step hash vs frozen
        steps = []
        for st in range(200):
            ids, comp = F.step_indices(rec, st); steps.append(F.sha_ids(ids))
        zt = np.load(F.V4 / f'{rec}_train_map.npz')
        checks.append(dict(fold=rec, split='train', name='g0_200_steps',
                           passed=bool(steps == [str(x) for x in zt['steps']]),
                           detail=f'step0 match={steps[0]==str(zt["steps"][0])}, n={len(steps)}'))
        # rejection
        held = [v for v in F.views('train') if rec in v and v.startswith(('rs232t1000', 's15850t100', 's35932t200'))]
        rej = False
        try:
            F.load_trans(rec, 'train', extra=[held[0]])
        except ValueError as e:
            rej = 'held-out recipe view injected' in str(e)
        checks.append(dict(fold=rec, split='train', name='rejection', passed=rej, detail=held[0]))
        # margin 2D
        zv = F.load_trans(rec, 'val')
        lg = np.random.default_rng(1).normal(size=(len(zv['y']), 2))
        off = np.random.default_rng(2).normal(size=(len(zv['y']), 1))
        m = lambda a: a[:, 1] - a[:, 0]
        a1 = average_precision_score(zv['y'][zv['trusted']], m(lg)[zv['trusted']])
        a2 = average_precision_score(zv['y'][zv['trusted']], m(lg + off)[zv['trusted']])
        k = max(1, int(zv['trusted'].sum() * 0.01))
        t1 = set(np.argsort(-m(lg))[:k]); t2 = set(np.argsort(-m(lg + off))[:k])
        c1 = set(np.argsort(-(lg[:, 1] + off[:, 0]))[:k])
        checks.append(dict(fold=rec, split='val', name='margin2d',
                           passed=bool(abs(a1 - a2) < 1e-9 and t1 == t2 and c1 != t1), detail=f'AP {a1:.6f}/{a2:.6f}'))
        # precheck
        mean, std = F.fold_stats(rec)
        dtr = F.load_trans(rec, 'train'); do = F.load_orig('train', mean, std)
        ids_t, comp = F.step_indices(rec, 0)
        model = Model().cuda(); model.load_state_dict(torch.load(R / '_p0pilot/control_v3_eligible_20261104/init_s42.pt', map_location='cuda', weights_only=True))
        state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        cpu = torch.get_rng_state().clone(); cuda = torch.cuda.get_rng_state_all()
        model.train()
        x = torch.as_tensor(dtr['x'], device='cuda'); e = torch.as_tensor(dtr['edge'], device='cuda'); y = torch.as_tensor(dtr['y'], device='cuda')
        xo = torch.as_tensor(do['x'], device='cuda'); eo = torch.as_tensor(do['edge'], device='cuda'); yo = torch.as_tensor(do['y'], device='cuda')
        q = loader.step('orig', 'G0', 0); io = torch.as_tensor(np.array(q.indices, copy=True), device='cuda')
        it = torch.as_tensor(ids_t, device='cuda')
        cones = dict(rows=list(range(len(dtr['cone_label']))), idx=torch.as_tensor(dtr['cone_rows'], device='cuda'),
                     seg=torch.repeat_interleave(torch.arange(len(dtr['cone_label']), device='cuda'), torch.as_tensor(np.diff(dtr['cone_ptr']), device='cuda')),
                     lab=torch.as_tensor(dtr['cone_label'], dtype=torch.float32, device='cuda'))
        params = [p for p in model.parameters() if p.requires_grad]
        with torch.autocast('cuda', dtype=torch.bfloat16):
            lo = model(xo, eo); l_o = T.domain_loss(lo, yo, io)
        l_o.backward()
        with torch.autocast('cuda', dtype=torch.bfloat16):
            lt = model(x, e); l_t = T.domain_loss(lt, y, it); l_c = CL.cone_loss(lt, cones)
        gn = sum(float(g.norm()) ** 2 for g in torch.autograd.grad(l_t, params, retain_graph=True, allow_unused=True) if g is not None) ** 0.5
        gc = sum(float(g.norm()) ** 2 for g in torch.autograd.grad(l_c, params, retain_graph=True, allow_unused=True) if g is not None) ** 0.5
        l_t.backward(retain_graph=True); l_c.backward()
        finite = all(torch.isfinite(p.grad).all() for p in params if p.grad is not None)
        model.load_state_dict(state); torch.set_rng_state(cpu); torch.cuda.set_rng_state_all(cuda)
        restored = all(torch.equal(state[k], v.detach().cpu()) for k, v in model.state_dict().items())
        rng_ok = torch.equal(torch.get_rng_state(), cpu) and all(torch.equal(a, b) for a, b in zip(torch.cuda.get_rng_state_all(), cuda))
        checks.append(dict(fold=rec, split='train', name='precheck',
                           passed=bool(finite and gc > 0 and restored and rng_ok),
                           detail=f'node_grad={gn:.3f}, cone_grad={gc:.3f}, finite={finite}, restored={restored}, rng={rng_ok}, step=0, comp={comp}'))
        del x, e, y, xo, eo, yo, lo, lt, cones
        torch.cuda.empty_cache()
    gate = dict(passed=all(c['passed'] for c in checks), checks=checks)
    (OUT / 'GATE_V5.json').write_text(json.dumps(gate, indent=2), encoding='utf-8')
    for c in checks:
        if not c['passed']:
            print('FAIL', c['fold'], c['split'], c['name'], c['detail'])
    print('GATE', gate['passed'], len(checks))


if __name__ == '__main__':
    main()
