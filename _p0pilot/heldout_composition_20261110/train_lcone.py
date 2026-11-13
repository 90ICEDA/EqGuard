"""L_cone 4-arm runner (seed42) on four-group A assets: N/NC1/NC0.1/C-only."""
import os, sys
for k in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
    os.environ[k] = '1'
os.environ['P2B_MASK'] = 'old'
import hashlib, json
from pathlib import Path
import numpy as np, torch
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
FG = R / '_p0pilot/four_group_contract_20261109'; OUT = R / '_p0pilot/heldout_composition_20261110'
B = R / '_p0pilot/control_boundary_v3_20261104'
L = R / '_p0pilot/control_loader_po_20261105'
sys.path.insert(0, str(L)); sys.path.insert(0, str(R / '_p0pilot/control_best200_20261104'))
sys.path.insert(0, str(R / '_p0pilot/seed42_nc_ablation_20261109'))
from supervision_loader import FiveGroupLoader
from evaluate import Model, T
import cone_loss as CL
from sklearn.metrics import average_precision_score


def main():
    arm = sys.argv[1]
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 42
    g = np.load(FG / 'group_A.npz'); cones = np.load(FG / 'cones_A.npz'); sup = np.load(FG / 'sup_A.npz'); val = np.load(FG / 'val_common.npz')
    mean, std = g['mean'], g['std']
    def norm(x):
        o = np.array(x, np.float32, copy=True); o[:, 25:] = np.clip((o[:, 25:] - mean) / std, -10, 10); return o
    x = torch.as_tensor(norm(g['x']), device='cuda'); e = torch.as_tensor(g['edge'], device='cuda'); y = torch.as_tensor(g['y'], device='cuda')
    vx = torch.as_tensor(val['x'], device='cuda'); ve = torch.as_tensor(val['edge'], device='cuda')
    xo = torch.as_tensor(norm(np.load(B / 'inputs/orig_train/x39.npy')), device='cuda')
    eo = torch.as_tensor(np.load(B / 'inputs/orig_train/edge_index.npy'), device='cuda')
    yo = torch.as_tensor(np.load(B / 'inputs/orig_train/y.npy'), device='cuda')
    ct = dict(rows=list(range(len(cones['label']))), idx=torch.as_tensor(cones['rows'], device='cuda'),
              seg=torch.repeat_interleave(torch.arange(len(cones['label']), device='cuda'), torch.as_tensor(np.diff(cones['ptr']), device='cuda')),
              lab=torch.as_tensor(cones['label'], dtype=torch.float32, device='cuda'))
    loader = FiveGroupLoader(); T.seed(seed)
    model = Model().cuda(); model.load_state_dict(torch.load(R / f'_p0pilot/control_v3_eligible_20261104/init_s{seed}.pt', map_location='cuda', weights_only=True))
    opt = torch.optim.Adam(model.parameters(), lr=2e-4, weight_decay=1e-3)
    lam = {'N': 0.0, 'NC1': 1.0, 'NC01': 0.1, 'C': None}[arm]
    outdir = OUT / (f'lcone_{arm}' if seed == 42 else f'lcone_{arm}_s{seed}'); outdir.mkdir(exist_ok=True)
    logs = []; best = dict(score=-1, step=-1, state=None, opt=None)
    for step in range(200):
        T.seed(seed + step); model.train(); opt.zero_grad(set_to_none=True)
        io = np.array(loader.step('orig', 'G0', step).indices, copy=True)
        with torch.autocast('cuda', dtype=torch.bfloat16):
            lo = model(xo, eo); l_o = T.domain_loss(lo, yo, torch.as_tensor(io, device='cuda'))
            lt = model(x, e); l_t = T.domain_loss(lt, y, torch.as_tensor(sup['idx'][step], device='cuda'))
            l_c = CL.cone_loss(lt, ct)
        if arm == 'N':
            loss = l_o + l_t
        elif arm == 'C':
            loss = l_c
        else:
            loss = l_o + l_t + lam * l_c
        loss.backward(); gn = float(torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)); opt.step()
        rec = dict(step=step + 1, node_orig=float(l_o), node_trans=float(l_t), cone=float(l_c),
                   orig_sha=hashlib.sha256(io.tobytes()).hexdigest(), trans_sha=str(sup['stepsha'][step]),
                   grad_norm=gn, finite=bool(np.isfinite(float(l_o)) and np.isfinite(float(l_t)) and np.isfinite(float(l_c)) and np.isfinite(gn)))
        assert rec['finite']; logs.append(rec)
        if (step + 1) % 5 == 0 or step == 199:
            model.eval()
            with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
                lg = model(vx, ve).float(); s = (lg[:, 1] - lg[:, 0]).cpu().numpy()
            aps = []
            c2 = json.loads((B / 'input_contract.json').read_text(encoding='utf-8'))
            vv = {z['view']: z for z in c2['shared_inputs']['trans_val']['views']}
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
    (outdir / 'LOG.json').write_text(json.dumps(dict(arm=arm, lambda_=lam, best_step=best['step'], best_score=best['score'], logs=logs), indent=2), encoding='utf-8')
    print('DONE', arm, best['step'], best['score'], flush=True)


if __name__ == '__main__':
    main()
