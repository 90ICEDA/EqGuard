"""Seed42 four-group training (A/B x N/NC) with shared val pool and prechecked interface."""
import os
for k in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
    os.environ[k] = '1'
os.environ['P2B_MASK'] = 'old'
import hashlib, json, sys, time
from pathlib import Path
import numpy as np, torch

R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = R / '_p0pilot/four_group_contract_20261109'
B = R / '_p0pilot/control_boundary_v3_20261104'
L = R / '_p0pilot/control_loader_po_20261105'
sys.path.insert(0, str(L)); sys.path.insert(0, str(R / '_p0pilot/control_best200_20261104'))
sys.path.insert(0, str(R / '_p0pilot/seed42_nc_ablation_20261109'))
from supervision_loader import FiveGroupLoader
from evaluate import Model, T
import cone_loss as CL
from sklearn.metrics import average_precision_score


def main():
    tag = sys.argv[1]; arm = sys.argv[2]; seed = int(sys.argv[3]) if len(sys.argv) > 3 else 42
    g = np.load(OUT / f'group_{tag}.npz'); sup = np.load(OUT / f'sup_{tag}.npz'); cone = np.load(OUT / f'cones_{tag}.npz')
    val = np.load(OUT / 'val_common.npz'); mean, std = g['mean'], g['std']
    gx = np.array(g['x'], np.float32, copy=True); gx[:, 25:] = np.clip((gx[:, 25:] - mean) / std, -10, 10)
    x = torch.as_tensor(gx, device='cuda'); e = torch.as_tensor(g['edge'], device='cuda'); y = torch.as_tensor(g['y'], device='cuda')
    xv = torch.as_tensor(val['x'], device='cuda'); ev = torch.as_tensor(val['edge'], device='cuda')
    xo = torch.as_tensor(np.load(B / 'inputs/orig_train/x39.npy'), device='cuda'); eo = torch.as_tensor(np.load(B / 'inputs/orig_train/edge_index.npy'), device='cuda')
    # orig normalization with A stats
    xo = torch.clip((xo - torch.as_tensor(mean, device='cuda')) / torch.as_tensor(std, device='cuda'), -10, 10) if False else xo
    o_raw = np.load(B / 'inputs/orig_train/x39.npy'); o_norm = np.array(o_raw, np.float32, copy=True); o_norm[:, 25:] = np.clip((o_norm[:, 25:] - mean) / std, -10, 10)
    xo = torch.as_tensor(o_norm, device='cuda'); yo = torch.as_tensor(np.load(B / 'inputs/orig_train/y.npy'), device='cuda')
    cones = dict(rows=list(range(len(cone['label']))), idx=torch.as_tensor(cone['rows'], device='cuda'),
                 seg=torch.repeat_interleave(torch.arange(len(cone['label']), device='cuda'), torch.as_tensor(np.diff(cone['ptr']), device='cuda')),
                 lab=torch.as_tensor(cone['label'], dtype=torch.float32, device='cuda'))
    loader = FiveGroupLoader()
    T.seed(seed); model = Model().cuda(); model.load_state_dict(torch.load(R / f'_p0pilot/control_v3_eligible_20261104/init_s{seed}.pt', map_location='cuda', weights_only=True))
    opt = torch.optim.Adam(model.parameters(), lr=2e-4, weight_decay=1e-3)
    outdir = OUT / (f'run_{tag}_{arm}' if seed == 42 else f'run_{tag}_{arm}_s{seed}'); outdir.mkdir(exist_ok=True)
    logs = []; best = dict(score=-1, step=-1, state=None)
    for step in range(200):
        T.seed(seed + step); model.train(); opt.zero_grad(set_to_none=True)
        ids_o = np.array(loader.step('orig', 'G0', step).indices, copy=True)
        with torch.autocast('cuda', dtype=torch.bfloat16):
            lo = model(xo, eo); l_o = T.domain_loss(lo, yo, torch.as_tensor(ids_o, device='cuda'))
        l_o.backward()
        ids_t = sup['idx'][step]
        with torch.autocast('cuda', dtype=torch.bfloat16):
            lt = model(x, e); l_t = T.domain_loss(lt, y, torch.as_tensor(ids_t, device='cuda'))
            if arm == 'NC':
                l_t = l_t + CL.cone_loss(lt, cones)
        l_t.backward(); gn = float(torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)); opt.step()
        rec = dict(step=step + 1, orig=float(l_o.detach()), trans=float(l_t.detach()), orig_sha=hashlib.sha256(ids_o.tobytes()).hexdigest(),
                   trans_sha=str(sup['stepsha'][step]), grad_norm=gn,
                   finite=bool(np.isfinite(float(l_o)) and np.isfinite(float(l_t)) and np.isfinite(gn)))
        assert rec['finite']
        logs.append(rec)
        if (step + 1) % 5 == 0 or step == 199:
            model.eval()
            with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
                lg = model(xv, ev).float(); s = (lg[:, 1] - lg[:, 0]).cpu().numpy()
            aps = []
            for v in val['views']:
                pass
            # per-view AP from contract val layouts mapped through val rows
            c = json.loads((B / 'input_contract.json').read_text(encoding='utf-8'))
            vs = {x['view']: x for x in c['shared_inputs']['trans_val']['views']}
            for v in val['views']:
                lay = vs[str(v)]; a, b = np.searchsorted(val['rows'], [lay['start'], lay['stop']])
                yy, tt, ss = val['y'][a:b], val['trusted'][a:b], s[a:b]
                if len(np.unique(yy[tt])) > 1:
                    aps.append(average_precision_score(yy[tt], ss[tt]))
            ap = float(np.mean(aps)) if aps else None
            logs[-1]['val_ap'] = ap
            if ap is not None and ap > best['score']:
                best = dict(score=ap, step=step + 1, state={k: v.detach().cpu().clone() for k, v in model.state_dict().items()})
    last = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
    for t, st in (('best', best['state']), ('last', last)):
        torch.save(dict(model=st, optimizer=opt.state_dict(), completed=200, rng_cpu=torch.get_rng_state(),
                        rng_cuda=torch.cuda.get_rng_state_all(), tag=tag, arm=arm, seed=seed), outdir / f'{t}_resume.pt')
        model.load_state_dict(st); model.eval()
        with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
            lgv = model(xv, ev).float(); sv = (lgv[:, 1] - lgv[:, 0]).cpu().numpy()
        np.savez_compressed(outdir / f'{t}_pred.npz', val=sv, val_rows=val['rows'])
    (outdir / 'LOG.json').write_text(json.dumps(dict(tag=tag, arm=arm, best_step=best['step'], best_score=best['score'], logs=logs), indent=2), encoding='utf-8')
    print('DONE', tag, arm, best['step'], best['score'], flush=True)


if __name__ == '__main__':
    main()
