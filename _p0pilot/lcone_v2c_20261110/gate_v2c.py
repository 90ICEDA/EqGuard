"""Gate v2c: group_B step0, base/all cones, ratio and restore."""
import json, sys
from pathlib import Path
import numpy as np, torch
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FG = R / '_p0pilot/four_group_contract_20261109'
OUT = R / '_p0pilot/lcone_v2c_20261110'; B = R / '_p0pilot/control_boundary_v3_20261104'
sys.path.insert(0, str(R / '_p0pilot/control_loader_po_20261105')); sys.path.insert(0, str(R / '_p0pilot/control_best200_20261104')); sys.path.insert(0, str(R / '_p0pilot/seed42_nc_ablation_20261109'))
from supervision_loader import FiveGroupLoader
from evaluate import Model, T
import cone_loss as CL
g = np.load(FG / 'group_B.npz'); sup = np.load(FG / 'sup_B.npz'); mean, std = g['mean'], g['std']
def norm(x):
    o = np.array(x, np.float32, copy=True); o[:, 25:] = np.clip((o[:, 25:] - mean) / std, -10, 10); return o
x = torch.as_tensor(norm(g['x']), device='cuda'); e = torch.as_tensor(g['edge'], device='cuda'); y = torch.as_tensor(g['y'], device='cuda')
xo = torch.as_tensor(norm(np.load(B / 'inputs/orig_train/x39.npy')), device='cuda')
eo = torch.as_tensor(np.load(B / 'inputs/orig_train/edge_index.npy'), device='cuda')
yo = torch.as_tensor(np.load(B / 'inputs/orig_train/y.npy'), device='cuda')
loader = FiveGroupLoader(); io = torch.as_tensor(np.array(loader.step('orig', 'G0', 0).indices, copy=True), device='cuda')
it = torch.as_tensor(sup['idx'][0], device='cuda')
res = {}
for name in ('base', 'all'):
    c = np.load(OUT / f'cones_v2c_{name}_D.npz')
    ct = dict(rows=list(range(len(c['label']))), idx=torch.as_tensor(c['rows'], device='cuda'),
              seg=torch.repeat_interleave(torch.arange(len(c['label']), device='cuda'), torch.as_tensor(np.diff(c['ptr']), device='cuda')),
              lab=torch.as_tensor(c['label'], dtype=torch.float32, device='cuda'))
    model = Model().cuda(); model.load_state_dict(torch.load(R / '_p0pilot/control_v3_eligible_20261104/init_s42.pt', map_location='cuda', weights_only=True))
    state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}; cp = torch.get_rng_state().clone(); cu = torch.cuda.get_rng_state_all()
    model.train(); ps = [p for p in model.parameters() if p.requires_grad]
    with torch.autocast('cuda', dtype=torch.bfloat16):
        lo = model(xo, eo); l_o = T.domain_loss(lo, yo, io)
    l_o.backward()
    with torch.autocast('cuda', dtype=torch.bfloat16):
        lt = model(x, e); l_t = T.domain_loss(lt, y, it); l_c = CL.cone_loss(lt, ct)
    gn = sum(float(q.norm()) ** 2 for q in torch.autograd.grad(l_t, ps, retain_graph=True, allow_unused=True) if q is not None) ** 0.5
    gc = sum(float(q.norm()) ** 2 for q in torch.autograd.grad(l_c, ps, retain_graph=True, allow_unused=True) if q is not None) ** 0.5
    l_t.backward(retain_graph=True); l_c.backward()
    finite = all(torch.isfinite(p.grad).all() for p in ps if p.grad is not None)
    model.load_state_dict(state); torch.set_rng_state(cp); torch.cuda.set_rng_state_all(cu)
    res[name] = dict(cones=int(len(c['label'])), pos=int(c['label'].sum()), node_grad=gn, cone_grad=gc,
                     ratio=gc / gn, finite=bool(finite),
                     restored=all(torch.equal(state[k], v.detach().cpu()) for k, v in model.state_dict().items()),
                     rng=torch.equal(torch.get_rng_state(), cp) and all(torch.equal(a, b) for a, b in zip(torch.cuda.get_rng_state_all(), cu)))
(OUT / 'GATE_V2C.json').write_text(json.dumps(dict(groups=res, step0_sha=str(sup['stepsha'][0]), optimizer_steps=0), indent=2), encoding='utf-8')
print(json.dumps(res, ensure_ascii=False))
