"""L_cone v2b training: group_B + base/all cone sets, 3 seeds, 200 updates."""
import os, sys
for k in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
    os.environ[k] = '1'
os.environ['P2B_MASK'] = 'old'
import hashlib, json
from pathlib import Path
import numpy as np, torch
import torch.nn.functional as F
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FG = R / '_p0pilot/four_group_contract_20261109'
OUT = R / '_p0pilot/lcone_trainctl_20261110'
CONE_DIR = R / '_p0pilot/lcone_v2c_20261110'; B = R / '_p0pilot/control_boundary_v3_20261104'
L = R / '_p0pilot/control_loader_po_20261105'
sys.path.insert(0, str(L)); sys.path.insert(0, str(R / '_p0pilot/control_best200_20261104')); sys.path.insert(0, str(R / '_p0pilot/seed42_nc_ablation_20261109'))
from supervision_loader import FiveGroupLoader
from evaluate import Model, T
import cone_loss as CL
from sklearn.metrics import average_precision_score

arm = sys.argv[1]; seed = int(sys.argv[2]); lam = float(sys.argv[3])
c = np.load(OUT / 'cones_ctrlall_D.npz'); g = np.load(FG / 'group_B.npz'); sup = np.load(FG / 'sup_B.npz'); val = np.load(FG / 'val_common.npz')
mean, std = g['mean'], g['std']
def norm(x):
    o = np.array(x, np.float32, copy=True); o[:, 25:] = np.clip((o[:, 25:] - mean) / std, -10, 10); return o
x = torch.as_tensor(norm(g['x']), device='cuda'); e = torch.as_tensor(g['edge'], device='cuda'); y = torch.as_tensor(g['y'], device='cuda')
vx = torch.as_tensor(val['x'], device='cuda'); ve = torch.as_tensor(val['edge'], device='cuda')
xo = torch.as_tensor(norm(np.load(B / 'inputs/orig_train/x39.npy')), device='cuda')
eo = torch.as_tensor(np.load(B / 'inputs/orig_train/edge_index.npy'), device='cuda')
yo = torch.as_tensor(np.load(B / 'inputs/orig_train/y.npy'), device='cuda')
ct = dict(rows=list(range(len(c['label']))), idx=torch.as_tensor(c['rows'], device='cuda'),
          seg=torch.repeat_interleave(torch.arange(len(c['label']), device='cuda'), torch.as_tensor(np.diff(c['ptr']), device='cuda')),
          lab=torch.as_tensor(c['label'], dtype=torch.float32, device='cuda'))
loader = FiveGroupLoader(); T.seed(seed)
model = Model().cuda(); model.load_state_dict(torch.load(R / f'_p0pilot/control_v3_eligible_20261104/init_s{seed}.pt', map_location='cuda', weights_only=True))
opt = torch.optim.Adam(model.parameters(), lr=2e-4, weight_decay=1e-3)
outdir = OUT / f'run_ctrlgn_s{seed}_lam{lam}'; outdir.mkdir(parents=True, exist_ok=True)
logs = []; best = dict(score=-1, step=-1, state=None, opt=None)
for step in range(200):
    T.seed(seed + step); model.train(); opt.zero_grad(set_to_none=True)
    io = np.array(loader.step('orig', 'G0', step).indices, copy=True)
    with torch.autocast('cuda', dtype=torch.bfloat16):
        lo = model(xo, eo); l_o = T.domain_loss(lo, yo, torch.as_tensor(io, device='cuda'))
    with torch.autocast('cuda', dtype=torch.bfloat16):
        lt = model(x, e); l_t = T.domain_loss(lt, y, torch.as_tensor(sup['idx'][step], device='cuda'))
        mar = lt.float()[:, 1] - lt.float()[:, 0]
        ncone = len(c['label'])
        cmax = torch.full((ncone,), -1e9, device=mar.device)
        cmax.scatter_reduce_(0, ct['seg'], mar.index_select(0, ct['idx']), reduce='amax', include_self=True)
        pos = ct['lab'] == 1; neg = ~pos
        l_pos = F.binary_cross_entropy_with_logits(cmax[pos], torch.ones_like(cmax[pos]), pos_weight=torch.tensor(10.0, device=mar.device))
        l_neg = F.binary_cross_entropy_with_logits(cmax[neg], torch.zeros_like(cmax[neg]))
        l_c = l_pos + l_neg
    l_node = l_o + l_t
    params = [p for p in model.parameters() if p.requires_grad]
    gnode = torch.autograd.grad(l_node, params, retain_graph=True, allow_unused=True)
    gp = torch.autograd.grad(l_pos, params, retain_graph=True, allow_unused=True)
    gn = torch.autograd.grad(l_neg, params, retain_graph=True, allow_unused=True)
    def scale(g, target):
        if g is None: return None
        n = g.norm()
        return g * (target / (n + 1e-12))
    node_scaled=[scale(g, 1.0) for g in gnode]
    pos_scaled=[scale(g,0.5) for g in gp]
    neg_scaled=[scale(g,1.0) for g in gn]
    def norm_of(xs): return float(torch.sqrt(sum((x.norm()**2) for x in xs if x is not None)))
    node_norm,pos_norm,neg_norm = norm_of(node_scaled),norm_of(pos_scaled),norm_of(neg_scaled)
    for idx,p in enumerate(params):
        parts=[x for x in (node_scaled[idx],pos_scaled[idx],neg_scaled[idx]) if x is not None]
        p.grad = sum(parts) if parts else None
    gn_total = float(torch.nn.utils.clip_grad_norm_(params, 5.0)); opt.step()
    rec = dict(step=step + 1, node_orig=float(l_o), node_trans=float(l_t), cone=float(l_c),
               grad_node=node_norm, grad_pos=pos_norm, grad_neg=neg_norm, grad_norm=gn_total,
               orig_sha=hashlib.sha256(io.tobytes()).hexdigest(), trans_sha=str(sup['stepsha'][step]),
               finite=bool(np.isfinite(float(l_o)) and np.isfinite(float(l_t)) and np.isfinite(float(l_c)) and np.isfinite(gn_total)))
    assert rec['finite']; logs.append(rec)
    if (step + 1) % 20 == 0:
        print('STEP', step + 1, 'gn', round(gn_total, 3), 'gp', round(pos_norm, 3), 'gn_neg', round(neg_norm, 3), flush=True)
    if (step + 1) % 5 == 0 or step == 199:
        model.eval()
        with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
            lg = model(vx, ve).float(); s = (lg[:, 1] - lg[:, 0]).cpu().numpy()
        # val_common views are 39 across base recipes; per-view AP
        import json as J
        c2 = J.loads((B / 'input_contract.json').read_text(encoding='utf-8'))
        vv = {z['view']: z for z in c2['shared_inputs']['trans_val']['views']}
        aps = []
        for v in val['views']:
            lay = vv[str(v)]; a, b = np.searchsorted(val['rows'], [lay['start'], lay['stop']])
            yy, tt, ss = val['y'][a:b], val['trusted'][a:b], s[a:b]
            if len(np.unique(yy[tt])) > 1: aps.append(average_precision_score(yy[tt], ss[tt]))
        ap = float(np.mean(aps)) if aps else None
        logs[-1]['val_ap'] = ap
        if ap is not None and ap > best['score']:
            best = dict(score=ap, step=step + 1, state={k: v.detach().cpu().clone() for k, v in model.state_dict().items()},
                        opt={k: (v.detach().cpu().clone() if torch.is_tensor(v) else v) for k, v in opt.state_dict().items()})
last = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
for point, st, op in (('best', best['state'], best['opt']), ('last', last, opt.state_dict())):
    torch.save(dict(model=st, optimizer=op, completed=200, rng_cpu=torch.get_rng_state(), rng_cuda=torch.cuda.get_rng_state_all(),
                    arm=arm, seed=seed, best_step=best['step']), outdir / f'{point}_resume.pt')
(outdir / 'LOG.json').write_text(json.dumps(dict(arm='weak', seed=seed, lambda_=lam, pos_weight=10.0, best_step=best['step'], best_score=best['score'], logs=logs), indent=2), encoding='utf-8')
print('DONE', arm, seed, best['step'], best['score'], flush=True)
