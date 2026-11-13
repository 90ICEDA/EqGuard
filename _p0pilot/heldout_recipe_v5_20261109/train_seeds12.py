"""Seed 1/2 held-out v5: 12 runs through fold_io; save logs/ckpt/optimizer/RNG/preds."""
import os
for k in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
    os.environ[k] = '1'
os.environ['P2B_MASK'] = 'old'
import hashlib, json, sys, time
from pathlib import Path
import numpy as np, torch

R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = R / '_p0pilot/heldout_recipe_v5_20261109'
sys.path.insert(0, str(OUT)); sys.path.insert(0, str(R / '_p0pilot/control_loader_po_20261105'))
sys.path.insert(0, str(R / '_p0pilot/control_best200_20261104')); sys.path.insert(0, str(R / '_p0pilot/seed42_nc_ablation_20261109'))
import fold_io as F
from supervision_loader import FiveGroupLoader
from evaluate import Model, T
import cone_loss as CL
from sklearn.metrics import average_precision_score

CACHE = {}


def cached(rec):
    if rec not in CACHE:
        mean, std = F.fold_stats(rec)
        CACHE[rec] = dict(mean=mean, std=std, tr=F.load_trans(rec, 'train'), va=F.load_trans(rec, 'val'),
                          te=F.load_trans(rec, 'test'), orig=F.load_orig('train', mean, std))
    return CACHE[rec]


def ap_val(model, rec, xv, ev, yv, tv, rows):
    model.eval()
    with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
        lg = model(xv, ev).float()
        s = (lg[:, 1] - lg[:, 0]).cpu().numpy()
    aps = []
    for v, lay in F.views('val').items():
        a, b = np.searchsorted(rows, [lay['start'], lay['stop']])
        if b - a < 2:
            continue
        yy, tt, ss = yv[a:b], tv[a:b], s[a:b]
        if len(np.unique(yy[tt])) > 1:
            aps.append(average_precision_score(yy[tt], ss[tt]))
    return float(np.mean(aps)) if aps else None


def run(loader, rec, arm, seed):
    z = cached(rec); dtr, dv, dt, do = z['tr'], z['va'], z['te'], z['orig']
    x = torch.as_tensor(dtr['x'], device='cuda'); e = torch.as_tensor(dtr['edge'], device='cuda'); y = torch.as_tensor(dtr['y'], device='cuda')
    xo = torch.as_tensor(do['x'], device='cuda'); eo = torch.as_tensor(do['edge'], device='cuda'); yo = torch.as_tensor(do['y'], device='cuda')
    xv = torch.as_tensor(dv['x'], device='cuda'); ev = torch.as_tensor(dv['edge'], device='cuda')
    cones = dict(rows=list(range(len(dtr['cone_label']))), idx=torch.as_tensor(dtr['cone_rows'], device='cuda'),
                 seg=torch.repeat_interleave(torch.arange(len(dtr['cone_label']), device='cuda'), torch.as_tensor(np.diff(dtr['cone_ptr']), device='cuda')),
                 lab=torch.as_tensor(dtr['cone_label'], dtype=torch.float32, device='cuda'))
    T.seed(seed)
    model = Model().cuda(); init = R / f'_p0pilot/control_v3_eligible_20261104/init_s{seed}.pt'
    model.load_state_dict(torch.load(init, map_location='cuda', weights_only=True))
    opt = torch.optim.Adam(model.parameters(), lr=2e-4, weight_decay=1e-3)
    outdir = OUT / rec / arm / f'seed{seed}'; outdir.mkdir(parents=True, exist_ok=True)
    logs = []
    for step in range(200):
        T.seed(seed + step); model.train(); opt.zero_grad(set_to_none=True)
        q = loader.step('orig', 'G0', step)
        io = np.array(q.indices, copy=True); it, comp = F.step_indices(rec, step)
        with torch.autocast('cuda', dtype=torch.bfloat16):
            lo = model(xo, eo); l_o = T.domain_loss(lo, yo, torch.as_tensor(io, device='cuda'))
        l_o.backward()
        with torch.autocast('cuda', dtype=torch.bfloat16):
            lt = model(x, e); l_t = T.domain_loss(lt, y, torch.as_tensor(it, device='cuda'))
            if arm == 'NC':
                l_t = l_t + CL.cone_loss(lt, cones)
        l_t.backward()
        gn = float(torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)); opt.step()
        rec_step = dict(step=step + 1, orig=float(l_o.detach()), trans=float(l_t.detach()),
                        orig_sha=F.sha_ids(io), trans_sha=F.sha_ids(it), grad_norm=gn,
                        finite=bool(np.isfinite(float(l_o)) and np.isfinite(float(l_t)) and np.isfinite(gn)))
        if step == 0:
            assert rec_step['finite'] and gn > 0
        logs.append(rec_step)
        if (step + 1) % 5 == 0 or step == 199:
            ap = ap_val(model, rec, xv, ev, np.asarray(dv['y']), np.asarray(dv['trusted']), dv['rows'])
            logs[-1]['val_ap'] = ap
            if 'best' not in locals() or (ap is not None and ap > best['score']):
                best = dict(score=ap, step=step + 1, state={k: v.detach().cpu().clone() for k, v in model.state_dict().items()})
    last = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
    for tag, st in (('best', best['state']), ('last', last)):
        model.load_state_dict(st); model.eval()
        with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
            lgv = model(xv, ev).float(); sv = (lgv[:, 1] - lgv[:, 0]).cpu().numpy()
            xt = torch.as_tensor(dt['x'], device='cuda'); et = torch.as_tensor(dt['edge'], device='cuda')
            lgt = model(xt, et).float(); stg = (lgt[:, 1] - lgt[:, 0]).cpu().numpy()
        torch.save(dict(model=st, optimizer=opt.state_dict(), completed=200, rng_cpu=torch.get_rng_state(),
                        rng_cuda=torch.cuda.get_rng_state_all(), seed=seed), outdir / f'{tag}_resume.pt')
        np.savez_compressed(outdir / f'{tag}_pred.npz', val=sv, test=stg, val_rows=dv['rows'], test_rows=dt['rows'])
    (outdir / 'LOG.json').write_text(json.dumps(dict(rec=rec, arm=arm, seed=seed, init_sha=hashlib.sha256(init.read_bytes()).hexdigest(),
                                                     best_step=best['step'], best_score=best['score'], comp=comp, logs=logs), indent=2), encoding='utf-8')
    return dict(rec=rec, arm=arm, seed=seed, best_step=best['step'], best_score=best['score'])


def main():
    loader = FiveGroupLoader()
    T.CONTRACT = loader.feature_contract; T.NORM = loader.normalization; T.arrays = loader.arrays
    assert T.MASK_MODE == 'old' and not T.EXTRA and T.EQ == 0
    out = {}
    for seed in (1, 2):
        for rec in F.RECIPES:
            for arm in ('N', 'NC'):
                out[f'{rec}_{arm}_s{seed}'] = run(loader, rec, arm, seed)
                print('DONE', rec, arm, seed, out[f'{rec}_{arm}_s{seed}']['best_score'], flush=True)
                (OUT / 'RESULTS_SEEDS12.json').write_text(json.dumps(out, indent=2), encoding='utf-8')
    print('ALL_DONE')


if __name__ == '__main__':
    main()
