"""L_cone shared runner: arms N/NC1/NC0.1/C-only; smoke = 1 forward/backward, no step."""
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


def main():
    arm = sys.argv[1]; lam = {'N': 0.0, 'NC1': 1.0, 'NC01': 0.1, 'C': None}[arm]
    g = np.load(OUT / 'hoco_A.npz'); cones = np.load(OUT / 'hoco_cones_A.npz')
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
    model.train(); params = [p for p in model.parameters() if p.requires_grad]; opt = torch.optim.Adam(params, lr=2e-4)
    opt.zero_grad(set_to_none=True)
    with torch.autocast('cuda', dtype=torch.bfloat16):
        lo = model(xo, eo); l_o = T.domain_loss(lo, yo, io)
        lt = model(x, e); l_t = T.domain_loss(lt, y, it); l_c = CL.cone_loss(lt, ct)
    if arm == 'C':
        loss = l_c
    elif arm == 'N':
        loss = l_o + l_t
    else:
        loss = l_o + l_t + lam * l_c
    loss.backward()
    gn = torch.nn.utils.clip_grad_norm_(params, 1.0)
    finite = all(torch.isfinite(p.grad).all() for p in params if p.grad is not None)
    out = dict(arm=arm, lambda_cone=lam, loss_total=float(loss), loss_node_orig=float(l_o), loss_node_trans=float(l_t),
               loss_cone=float(l_c), grad_norm=float(gn), finite=bool(finite), optimizer_steps=0,
               cone_pos=int(cones['label'].sum()), cone_neg=int((cones['label'] == 0).sum()))
    (OUT / f'LCONE_SMOKE_{arm}.json').write_text(json.dumps(out, indent=2), encoding='utf-8')
    print(json.dumps(out))


if __name__ == '__main__':
    main()
