"""Seed42 held-out fold training through the shared fold_io interface (6 runs)."""
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


def ap_val(model, rec, xv, ev, yv, tv, rows):
    model.eval()
    with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
        s = (model(xv, ev).float()[:, 1] - model(xv, ev).float()[:, 0]).cpu().numpy()
    aps = []
    for v, lay in F.views('val').items():
        a, b = np.searchsorted(rows, [lay['start'], lay['stop']])
        if b - a < 2:
            continue
        yy, tt, ss = yv[a:b], tv[a:b], s[a:b]
        if len(np.unique(yy[tt])) > 1:
            aps.append(average_precision_score(yy[tt], ss[tt]))
    return float(np.mean(aps)) if aps else None


def run(loader, rec, arm):
    mean, std = F.fold_stats(rec)
    dtr = F.load_trans(rec, 'train'); dv = F.load_trans(rec, 'val'); dt = F.load_trans(rec, 'test')
    do = F.load_orig('train', mean, std)
    x = torch.as_tensor(dtr['x'], device='cuda'); e = torch.as_tensor(dtr['edge'], device='cuda'); y = torch.as_tensor(dtr['y'], device='cuda')
    xo = torch.as_tensor(do['x'], device='cuda'); eo = torch.as_tensor(do['edge'], device='cuda'); yo = torch.as_tensor(do['y'], device='cuda')
    xv = torch.as_tensor(dv['x'], device='cuda'); ev = torch.as_tensor(dv['edge'], device='cuda')
    cones = dict(rows=list(range(len(dtr['cone_label']))), idx=torch.as_tensor(dtr['cone_rows'], device='cuda'),
                 seg=torch.repeat_interleave(torch.arange(len(dtr['cone_label']), device='cuda'), torch.as_tensor(np.diff(dtr['cone_ptr']), device='cuda')),
                 lab=torch.as_tensor(dtr['cone_label'], dtype=torch.float32, device='cuda'))
    T.seed(42)
    model = Model().cuda(); model.load_state_dict(torch.load(R / '_p0pilot/control_v3_eligible_20261104/init_s42.pt', map_location='cuda', weights_only=True))
    opt = torch.optim.Adam(model.parameters(), lr=2e-4, weight_decay=1e-3)
    best = dict(score=-1, step=-1, state=None); logs = []
    for step in range(200):
        T.seed(42 + step); model.train(); opt.zero_grad(set_to_none=True)
        q = loader.step('orig', 'G0', step)
        ids_o = np.array(q.indices, copy=True)
        ids_t, comp = F.step_indices(rec, step)
        it = torch.as_tensor(ids_t, device='cuda'); io = torch.as_tensor(ids_o, device='cuda')
        with torch.autocast('cuda', dtype=torch.bfloat16):
            lo = model(xo, eo); l_o = T.domain_loss(lo, yo, io)
        l_o.backward()
        with torch.autocast('cuda', dtype=torch.bfloat16):
            lt = model(x, e); l_t = T.domain_loss(lt, y, it)
            if arm == 'NC':
                l_t = l_t + CL.cone_loss(lt, cones)
        l_t.backward()
        gn = float(torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)); opt.step()
        logs.append(dict(step=step + 1, orig=float(l_o.detach()), trans=float(l_t.detach()),
                         orig_sha=F.sha_ids(ids_o), trans_sha=F.sha_ids(ids_t), grad_norm=gn,
                         finite=bool(np.isfinite(float(l_o)) and np.isfinite(float(l_t)) and np.isfinite(gn))))
        if (step + 1) % 5 == 0 or step == 199:
            ap = ap_val(model, rec, xv, ev, np.asarray(dv['y']), np.asarray(dv['trusted']), dv['rows'])
            logs[-1]['val_ap'] = ap
            if ap is not None and ap > best['score']:
                best = dict(score=ap, step=step + 1, state={k: v.detach().cpu().clone() for k, v in model.state_dict().items()})
    last = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
    outdir = OUT / rec / arm; outdir.mkdir(parents=True, exist_ok=True)
    torch.save(best['state'], outdir / 'best.pt'); torch.save(last, outdir / 'last.pt')
    (outdir / 'LOG.json').write_text(json.dumps(dict(rec=rec, arm=arm, best_step=best['step'], best_score=best['score'],
                                                     comp=comp, logs=logs), indent=2), encoding='utf-8')
    res = {}
    for tag, st in (('best', best['state']), ('last', last)):
        model.load_state_dict(st); model.eval()
        with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
            sv = (model(xv, ev).float()[:, 1] - model(xv, ev).float()[:, 0]).cpu().numpy()
            xt = torch.as_tensor(dt['x'], device='cuda'); et = torch.as_tensor(dt['edge'], device='cuda')
            stg = (model(xt, et).float()[:, 1] - model(xt, et).float()[:, 0]).cpu().numpy()
        res[tag] = dict(val_ap=ap_val(model, rec, xv, ev, np.asarray(dv['y']), np.asarray(dv['trusted']), dv['rows']))
        np.savez_compressed(outdir / f'{tag}_pred.npz', val=sv, test=stg, val_rows=dv['rows'], test_rows=dt['rows'])
    return dict(rec=rec, arm=arm, best_step=best['step'], best_score=best['score'], res=res, seconds=time.perf_counter())


def main():
    loader = FiveGroupLoader()
    T.CONTRACT = loader.feature_contract; T.NORM = loader.normalization; T.arrays = loader.arrays
    assert T.MASK_MODE == 'old' and not T.EXTRA and T.EQ == 0
    out = {}
    for rec in F.RECIPES:
        for arm in ('N', 'NC'):
            t = time.perf_counter(); out[f'{rec}_{arm}'] = run(loader, rec, arm); out[f'{rec}_{arm}']['wall'] = time.perf_counter() - t
            print('DONE', rec, arm, out[f'{rec}_{arm}']['best_step'], out[f'{rec}_{arm}']['best_score'], flush=True)
            (OUT / 'RESULTS_V5.json').write_text(json.dumps(out, indent=2), encoding='utf-8')
    print('ALL_DONE')


if __name__ == '__main__':
    main()
