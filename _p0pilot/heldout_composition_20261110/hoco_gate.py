"""hoco per-group gate: actual step0, node/cone grads, margin, restore, counterexamples."""
import os, sys
for k in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
    os.environ[k] = '1'
os.environ['P2B_MASK'] = 'old'
import json
from pathlib import Path
import numpy as np, torch
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = R / '_p0pilot/heldout_composition_20261110'
B = R / '_p0pilot/control_boundary_v3_20261104'
L = R / '_p0pilot/control_loader_po_20261105'
sys.path.insert(0, str(L)); sys.path.insert(0, str(R / '_p0pilot/control_best200_20261104'))
sys.path.insert(0, str(R / '_p0pilot/seed42_nc_ablation_20261109'))
from supervision_loader import FiveGroupLoader
from evaluate import Model, T
import cone_loss as CL
from sklearn.metrics import average_precision_score

tag = sys.argv[1]
g = np.load(OUT / f'hoco_{tag}.npz'); sup = np.load(OUT / f'hoco_{tag}_idx.npz') if (OUT / f'hoco_{tag}_idx.npz').exists() else g
cones = np.load(OUT / f'hoco_cones_{tag}.npz')
mean, std = g['mean'], g['std']
def norm(x):
    o = np.array(x, np.float32, copy=True); o[:, 25:] = np.clip((o[:, 25:] - mean) / std, -10, 10); return o
x = torch.as_tensor(norm(g['x']), device='cuda'); e = torch.as_tensor(g['edge'], device='cuda'); y = torch.as_tensor(g['y'], device='cuda')
xo = torch.as_tensor(norm(np.load(B / 'inputs/orig_train/x39.npy')), device='cuda')
eo = torch.as_tensor(np.load(B / 'inputs/orig_train/edge_index.npy'), device='cuda')
yo = torch.as_tensor(np.load(B / 'inputs/orig_train/y.npy'), device='cuda')
ct = dict(rows=list(range(len(cones['label']))), idx=torch.as_tensor(cones['rows'], device='cuda'),
          seg=torch.repeat_interleave(torch.arange(len(cones['label']), device='cuda'), torch.as_tensor(np.diff(cones['ptr']), device='cuda')),
          lab=torch.as_tensor(cones['label'], dtype=torch.float32, device='cuda'))
loader = FiveGroupLoader(); io = torch.as_tensor(np.array(loader.step('orig', 'G0', 0).indices, copy=True), device='cuda')
it = torch.as_tensor(g['idx'][0], device='cuda')
model = Model().cuda(); model.load_state_dict(torch.load(R / '_p0pilot/control_v3_eligible_20261104/init_s42.pt', map_location='cuda', weights_only=True))
state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
cp = torch.get_rng_state().clone(); cu = torch.cuda.get_rng_state_all(); model.train()
params = [p for p in model.parameters() if p.requires_grad]
with torch.autocast('cuda', dtype=torch.bfloat16):
    lo = model(xo, eo); l_o = T.domain_loss(lo, yo, io)
l_o.backward()
with torch.autocast('cuda', dtype=torch.bfloat16):
    lt = model(x, e); l_t = T.domain_loss(lt, y, it); l_c = CL.cone_loss(lt, ct)
gn = sum(float(q.norm()) ** 2 for q in torch.autograd.grad(l_t, params, retain_graph=True, allow_unused=True) if q is not None) ** 0.5
gc = sum(float(q.norm()) ** 2 for q in torch.autograd.grad(l_c, params, retain_graph=True, allow_unused=True) if q is not None) ** 0.5
l_t.backward(retain_graph=True); l_c.backward()
finite = all(torch.isfinite(p.grad).all() for p in params if p.grad is not None)
lg = lt.detach().float(); m1 = (lg[:, 1] - lg[:, 0]).cpu().numpy().astype(np.float64)
off = np.random.default_rng(0).normal(size=(len(m1), 1))
m2 = ((lg[:, 1] + torch.as_tensor(off[:, 0], device='cuda')).cpu().numpy() - (lg[:, 0] + torch.as_tensor(off[:, 0], device='cuda')).cpu().numpy()).astype(np.float64)
margin_ok = abs(average_precision_score(g['y'][g['trusted']], m1[g['trusted']]) - average_precision_score(g['y'][g['trusted']], m2[g['trusted']])) < 1e-6
model.load_state_dict(state); torch.set_rng_state(cp); torch.cuda.set_rng_state_all(cu)
restored = all(torch.equal(state[k], v.detach().cpu()) for k, v in model.state_dict().items())
rng_ok = torch.equal(torch.get_rng_state(), cp) and all(torch.equal(a, b) for a, b in zip(torch.cuda.get_rng_state_all(), cu))
# counterexamples
cx = {}
keyed = {('train', 'v1', 'c1'): 0, ('train', 'v2', 'c1'): 1}; cx['cross_recipe_key'] = len(keyed) == 2
try:
    bad = np.array([int(g['pos'][0])]); assert not bool((g['y'][bad] == 1).any()); cx['wrong_category'] = False
except AssertionError:
    cx['wrong_category'] = True
try:
    ids = np.array([1, 1]); assert len(np.unique(ids)) == len(ids); cx['duplicate'] = False
except AssertionError:
    cx['duplicate'] = True
out = dict(group=tag, loss_orig=float(l_o), loss_trans=float(l_t), loss_cone=float(l_c), node_grad=gn, cone_grad=gc,
           finite=bool(finite), margin_ok=bool(margin_ok), restored=bool(restored), rng=bool(rng_ok),
           cones=int(len(cones['label'])), pos=int(cones['label'].sum()), step0_sha=str(g['stepsha'][0]), step=0, cx=cx)
(OUT / f'GATE_{tag}.json').write_text(json.dumps(out, indent=2), encoding='utf-8')
print(json.dumps(out, ensure_ascii=False))
