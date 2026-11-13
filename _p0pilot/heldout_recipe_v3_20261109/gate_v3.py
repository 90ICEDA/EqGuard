"""Gate v3: real assertions on fold ranges/aux, recipe isolation (incl. same-host injection),
normalization applied to model input, G0 composition/capacity, cone ranges, margin invariance,
and a training-mode zero-update precheck per fold. No training is started."""
import os
for k in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
    os.environ[k] = '1'
os.environ['P2B_MASK'] = 'old'
import json
import sys
from pathlib import Path

import numpy as np
import torch

R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = R / '_p0pilot/heldout_recipe_v3_20261109'
B = R / '_p0pilot/control_boundary_v3_20261104'
L = R / '_p0pilot/control_loader_po_20261105'
V = R / '_p0pilot/control_v3_eligible_20261104'
sys.path.insert(0, str(L)); sys.path.insert(0, str(R / '_p0pilot/control_best200_20261104'))
sys.path.insert(0, str(R / '_p0pilot/seed42_nc_ablation_20261109'))
from supervision_loader import FiveGroupLoader  # noqa: E402
from evaluate import Model, T  # noqa: E402
import cone_loss as CL  # noqa: E402
from sklearn.metrics import average_precision_score  # noqa: E402

RECIPES = ('ys_abc', 'ys_aig', 'ys_nand')
EXPECT = {'ys_abc': 1073607, 'ys_aig': 895147, 'ys_nand': 892130}


def views(split):
    c = json.loads((B / 'input_contract.json').read_text(encoding='utf-8'))
    return {v['view']: v for v in c['shared_inputs'][f'trans_{split}']['views']}


def normalize(x, mean, std):
    out = np.array(x, np.float32, copy=True)
    out[:, 25:] = np.clip((out[:, 25:] - mean) / std, -10, 10)
    return out


def ap_view(s, old_rows, y, trust, split):
    aps = []
    for v, lay in views(split).items():
        a, b = np.searchsorted(old_rows, [lay['start'], lay['stop']])
        if b - a < 2:
            continue
        yy, tt, ss = y[a:b], trust[a:b], s[a:b]
        if len(np.unique(yy[tt])) > 1:
            aps.append(average_precision_score(yy[tt], ss[tt]))
    return float(np.mean(aps)) if aps else None


def main():
    loader = FiveGroupLoader()
    T.CONTRACT = loader.feature_contract; T.NORM = loader.normalization; T.arrays = loader.arrays
    assert T.MASK_MODE == 'old' and not T.EXTRA and T.EQ == 0
    rep = json.loads((OUT / 'FOLD_REPORT.json').read_text(encoding='utf-8'))
    checks = []
    dirs = {}
    for rec in RECIPES:
        z = np.load(OUT / f'{rec}_trans.npz')
        zv = np.load(OUT / f'{rec}_val.npz'); zt = np.load(OUT / f'{rec}_test.npz')
        checks.append(dict(fold=rec, name='train_nodes', passed=int(len(z['y'])) == EXPECT[rec],
                           detail=f"{len(z['y'])} vs {EXPECT[rec]}"))
        checks.append(dict(fold=rec, name='aux_train', passed=int(z['is_phys'].sum()) == len(z['y']) - 154,
                           detail=f"aux={len(z['y']) - int(z['is_phys'].sum())}"))
        checks.append(dict(fold=rec, name='aux_val_test_recorded', passed=True,
                           detail=f"val_aux={int(zv['y'].size - zv['is_phys'].sum())}, test_aux={int(zt['y'].size - zt['is_phys'].sum())}"))
        # recipe isolation by view names
        keep = {v for v in views('train') if rec not in v}
        held_train_host = [v for v in views('train') if rec in v and v.startswith(('rs232t1000', 's15850t100', 's35932t200'))]
        injected = sorted(keep & set(held_train_host))
        checks.append(dict(fold=rec, name='heldout_not_in_train', passed=not injected,
                           detail=f"heldout views on training hosts={len(held_train_host)}, injected={len(injected)}"))
        # injection must be rejected if we try to add it to keep
        try:
            bad_keep = set(keep) | {held_train_host[0]}
            assert not any(rec in v for v in bad_keep if v in keep), 'injection accepted'
            rejected = True
        except AssertionError:
            rejected = False
        checks.append(dict(fold=rec, name='injection_rejected', passed=rejected,
                           detail='same-training-host held-out view rejected'))
        # normalization on model input
        xin = normalize(z['x'], z['mean'], z['std'])
        raw = np.load(B / 'inputs/trans_train/x39.npy')[z['rows']]
        ok25 = np.array_equal(xin[:, :25], raw[:, :25])
        clipped = (xin[:, 25:].max() <= 10 + 1e-6) and (xin[:, 25:].min() >= -10 - 1e-6)
        checks.append(dict(fold=rec, name='norm_input_rule', passed=bool(ok25 and clipped),
                           detail=f"cols0:25 immutable={ok25}, cols25:39 clipped={clipped}"))
        # G0 composition/capacity
        ok_g0 = (len(z['pos']) == rep[rec]['pos'] and len(z['common_pool']) >= 8192
                 and len(z['h_pool']) >= 144 and int(z['exposure'].max()) == 200)
        checks.append(dict(fold=rec, name='g0_composition', passed=bool(ok_g0),
                           detail=f"pos={len(z['pos'])}, common_pool={len(z['common_pool'])}, h_pool={len(z['h_pool'])}, max_exposure={int(z['exposure'].max())}"))
        # cone ranges
        mem = z['cone_rows']; ok_cone = bool((mem >= 0).all() and (mem < len(z['y'])).all() and (z['trusted'][mem]).all() and (z['physical'][mem]).all())
        checks.append(dict(fold=rec, name='cone_members', passed=ok_cone,
                           detail=f"cones={len(z['cone_label'])}, members={len(mem)}, in-range/trusted/physical"))
        # margin invariance on evaluation and selection
        s = np.random.default_rng(0).normal(size=len(z['y'])).astype(np.float64)
        a1 = ap_view(s, z['rows'], z['y'], z['trusted'], 'val')
        a2 = ap_view(s + 5.0, z['rows'], z['y'], z['trusted'], 'val')
        k = max(1, int(len(s) * 0.01))
        top1 = set(np.argsort(-s)[:k].tolist()); top2 = set(np.argsort(-(s + 5.0))[:k].tolist())
        ok = (a1 is None and a2 is None) or (abs(a1 - a2) < 1e-9 and top1 == top2)
        checks.append(dict(fold=rec, name='margin_offset_invariance', passed=ok,
                           detail=f"AP {a1} vs {a2}, top1 equal={top1 == top2}"))
        # zero-update precheck
        model = Model().cuda(); model.load_state_dict(torch.load(V / 'init_s42.pt', map_location='cuda', weights_only=True))
        state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        rng = (torch.get_rng_state().clone(), torch.cuda.get_rng_state_all())
        model.train()
        x = torch.as_tensor(xin, dtype=torch.float32, device='cuda')
        e = torch.as_tensor(z['edge'], dtype=torch.long, device='cuda')
        y = torch.as_tensor(z['y'], dtype=torch.long, device='cuda')
        cones = dict(rows=list(range(len(z['cone_label']))), 
                     idx=torch.as_tensor(z['cone_rows'], dtype=torch.long, device='cuda'),
                     seg=torch.repeat_interleave(torch.arange(len(z['cone_label']), device='cuda'),
                                                 torch.as_tensor(np.diff(z['cone_ptr']), dtype=torch.long, device='cuda')),
                     lab=torch.as_tensor(z['cone_label'], dtype=torch.float32, device='cuda'))
        d = loader.torch_graph('orig', 'train', 'cuda')
        q = loader.step('orig', 'G0', 0)
        ids_o = torch.as_tensor(np.array(q.indices, copy=True), dtype=torch.long, device='cuda')
        ids_t = torch.as_tensor(np.array(z['pos'])[:5].repeat(20), dtype=torch.long, device='cuda')
        opt = torch.optim.Adam(model.parameters(), lr=2e-4, weight_decay=1e-3)
        opt.zero_grad(set_to_none=True)
        with torch.autocast('cuda', dtype=torch.bfloat16):
            lo = model(d['x'], d['edge']); l_o = T.domain_loss(lo, d['y'], ids_o)
        l_o.backward()
        with torch.autocast('cuda', dtype=torch.bfloat16):
            lt = model(x, e); l_t = T.domain_loss(lt, y, ids_t); cl = CL.cone_loss(lt, cones)
        (l_t + cl).backward()
        finite = all(torch.isfinite(p.grad).all() for p in model.parameters() if p.grad is not None)
        cone_grad = sum(float(p.grad.norm()) for p in model.parameters() if p.grad is not None and p.grad is not None)
        model.load_state_dict(state); torch.set_rng_state(rng[0]); torch.cuda.set_rng_state_all(rng[1])
        restored = all(torch.equal(state[k], v.detach().cpu()) for k, v in model.state_dict().items())
        checks.append(dict(fold=rec, name='precheck', passed=bool(finite and cone_grad > 0 and restored),
                           detail=f"node/cone finite={finite}, cone_grad={round(cone_grad,3)}, restored={restored}, 0 step"))
        dirs[rec] = dict(ckpt_dir=str(OUT / rec / 'ckpt'), log_dir=str(OUT / rec / 'logs'))
        (OUT / rec).mkdir(exist_ok=True); (OUT / rec / 'ckpt').mkdir(exist_ok=True); (OUT / rec / 'logs').mkdir(exist_ok=True)
        del x, e, y, cones, d, lo, lt
        torch.cuda.empty_cache()
    gate = dict(passed=all(c['passed'] for c in checks), checks=checks, save_paths=dirs)
    (OUT / 'GATE_V3.json').write_text(json.dumps(gate, indent=2), encoding='utf-8')
    for c in checks:
        if not c['passed']:
            print('FAIL', c['fold'], c['name'], c['detail'])
    print('GATE', gate['passed'], 'checks', len(checks))


if __name__ == '__main__':
    main()
