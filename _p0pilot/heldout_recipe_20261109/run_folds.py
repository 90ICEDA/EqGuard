"""Gate + seed42 N/NC training on three held-out-recipe folds (trans side fold graphs; orig unchanged)."""
import os
for k in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
    os.environ[k] = '1'
os.environ['P2B_MASK'] = 'old'
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = R / '_p0pilot/heldout_recipe_20261109'
L = R / '_p0pilot/control_loader_po_20261105'
V = R / '_p0pilot/control_v3_eligible_20261104'
sys.path.insert(0, str(L)); sys.path.insert(0, str(R / '_p0pilot/control_best200_20261104'))
sys.path.insert(0, str(R / '_p0pilot/seed42_nc_ablation_20261109'))
from supervision_loader import FiveGroupLoader  # noqa: E402
from evaluate import Model, T  # noqa: E402
import cone_loss as CL  # noqa: E402
from sklearn.metrics import average_precision_score  # noqa: E402

BOUND = json.loads((R / '_p0pilot/control_boundary_v3_20261104/input_contract.json').read_text(encoding='utf-8'))
RECIPES = ('ys_abc', 'ys_aig', 'ys_nand')


def view_ranges(split):
    return {v['view']: v for v in BOUND['shared_inputs'][f'trans_{split}']['views']}


def per_view_ap(s, old_rows, y, trust, split):
    aps, top1 = [], []
    for v, lay in view_ranges(split).items():
        lo = lay['start']; hi = lo + (lay['old_stop'] - lay['old_start'])
        a, b = np.searchsorted(old_rows, [lo, hi])
        if b - a < 2:
            continue
        yy = y[a:b]; tt = trust[a:b]; ss = s[a:b]
        if len(np.unique(yy[tt])) > 1:
            aps.append(average_precision_score(yy[tt], ss[tt]))
        order = np.lexsort((np.arange(b - a)[tt], -ss[tt]))
        pos = (yy[tt] == 1)[order]
        k = max(1, int(tt.sum() * 0.01))
        if pos.sum():
            top1.append(float(pos[:k].sum() / pos.sum()))
    return float(np.mean(aps)) if aps else None, float(np.mean(top1)) if top1 else None


def fold_ids(z, trust):
    pos = np.where((z['y'] == 1) & z['trusted'] & z['physical'])[0]
    neg = np.where((z['y'] == 0) & z['trusted'] & z['physical'])[0]
    rng = np.random.default_rng(42)
    picks = []
    for step in range(200):
        pick = rng.choice(neg, size=8336, replace=len(neg) < 8336)
        picks.append(np.concatenate([pos, pick]).astype(np.int64))
    return picks


def tensors(z):
    return (torch.as_tensor(z['x'], dtype=torch.float32, device='cuda'),
            torch.as_tensor(z['edge'], dtype=torch.long, device='cuda'),
            torch.as_tensor(z['y'], dtype=torch.long, device='cuda'),
            torch.as_tensor(z['trusted'], dtype=torch.bool, device='cuda'),
            torch.as_tensor(z['physical'], dtype=torch.bool, device='cuda'))


def cone_tensors_fold(z):
    return dict(rows=list(range(len(z['cone_label']))),
                idx=torch.as_tensor(z['cone_rows'], dtype=torch.long, device='cuda'),
                seg=torch.repeat_interleave(
                    torch.arange(len(z['cone_label']), device='cuda'),
                    torch.as_tensor(np.diff(z['cone_ptr']), dtype=torch.long, device='cuda')),
                lab=torch.as_tensor(z['cone_label'], dtype=torch.float32, device='cuda'),
                pos=int(z['cone_label'].sum()), neg=int((z['cone_label'] == 0).sum()))


def gate(loader, folds):
    """One-fold training-mode no-update gate + held-out-view rejection test."""
    z = folds['ys_abc']
    x, edge, y, tr, ph = tensors(z)
    x = (x - torch.as_tensor(z['mean'], device='cuda')) / torch.as_tensor(z['std'], device='cuda')
    cones = cone_tensors_fold(z)
    model = Model().cuda(); model.load_state_dict(torch.load(V / 'init_s42.pt', map_location='cuda', weights_only=True))
    state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
    rng = (torch.get_rng_state().clone(), torch.cuda.get_rng_state_all())
    model.train()
    d = loader.torch_graph('orig', 'train', 'cuda')
    q = loader.step('orig', 'G0', 0)
    ids = torch.as_tensor(np.array(q.indices, copy=True), dtype=torch.long, device='cuda')
    with torch.autocast('cuda', dtype=torch.bfloat16):
        lo = model(d['x'], d['edge']); loss_o = T.domain_loss(lo, d['y'], ids)
    loss_o.backward()
    with torch.autocast('cuda', dtype=torch.bfloat16):
        lt = model(x, edge); loss_t = T.domain_loss(lt, y, torch.as_tensor(fold_ids(z, tr)[0], device='cuda'))
        cl = CL.cone_loss(lt, cones)
    (loss_t + cl).backward()
    finite = all(torch.isfinite(p.grad).all() for p in model.parameters() if p.grad is not None)
    cone_grad = sum(float(p.grad.norm()) for p in model.parameters() if p.grad is not None)
    model.load_state_dict(state); torch.set_rng_state(rng[0]); torch.cuda.set_rng_state_all(rng[1])
    restored = all(torch.equal(state[k], v.detach().cpu()) for k, v in model.state_dict().items())
    # rejection: held-out view id must not be allowed in training rows
    keep_tr = {v for v in view_ranges('train') if 'ys_abc' not in v}
    held = {v for v in view_ranges('test') if 'ys_abc' in v}
    leaked = sorted(keep_tr & held)
    assert len(keep_tr) == 194, len(keep_tr)
    mean_chk = z['x'].mean(0).astype(np.float32)
    assert np.allclose(mean_chk, z['mean'], atol=1e-5)
    out = dict(passed=bool(finite and cone_grad > 0 and restored and not leaked),
               loss_orig=float(loss_o.detach()), loss_trans=float(loss_t.detach()), loss_cone=float(cl.detach()),
               grads_finite=bool(finite), cone_grad_sum=cone_grad, restored=bool(restored),
               heldout_views=len(held), leaked=leaked, cones=len(z['cone_label']), members=len(z['cone_rows']))
    (OUT / 'GATE.json').write_text(json.dumps(out, indent=2), encoding='utf-8')
    return out


def run_fold(loader, rec, folds, arm, seed=42):
    z = folds[rec]
    x, edge, y, tr, ph = tensors(z)
    x = (x - torch.as_tensor(z['mean'], device='cuda')) / torch.as_tensor(z['std'], device='cuda')
    cones = cone_tensors_fold(z)
    ids_list = fold_ids(z, tr)
    zv = folds[rec + '_val']; zt = folds[rec + '_test']
    xv, ev, yv, tv, pv = tensors(zv); xv = (xv - torch.as_tensor(z['mean'], device='cuda')) / torch.as_tensor(z['std'], device='cuda')
    xt, et, yt, tt, pt = tensors(zt); xt = (xt - torch.as_tensor(z['mean'], device='cuda')) / torch.as_tensor(z['std'], device='cuda')
    T.seed(seed)
    model = Model().cuda(); model.load_state_dict(torch.load(V / 'init_s42.pt', map_location='cuda', weights_only=True))
    opt = torch.optim.Adam(model.parameters(), lr=2e-4, weight_decay=1e-3)
    d_o = loader.torch_graph('orig', 'train', 'cuda')
    best = dict(score=-1, step=-1, state=None); hist = []
    for step in range(200):
        T.seed(seed + step); model.train(); opt.zero_grad(set_to_none=True)
        q = loader.step('orig', 'G0', step)
        ids_o = torch.as_tensor(np.array(q.indices, copy=True), dtype=torch.long, device='cuda')
        with torch.autocast('cuda', dtype=torch.bfloat16):
            lo = model(d_o['x'], d_o['edge']); l_o = T.domain_loss(lo, d_o['y'], ids_o)
        l_o.backward()
        ids_t = torch.as_tensor(ids_list[step], dtype=torch.long, device='cuda')
        with torch.autocast('cuda', dtype=torch.bfloat16):
            lt = model(x, edge); l_t = T.domain_loss(lt, y, ids_t)
            if arm == 'NC':
                l_t = l_t + CL.cone_loss(lt, cones)
        l_t.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0); opt.step()
        if (step + 1) % 5 == 0 or step == 199:
            model.eval()
            with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
                sv = model(xv, ev).float()[:, 1].cpu().numpy()
            ap, top1 = per_view_ap(sv, zv['old_rows'], np.asarray(zv['y']), np.asarray(zv['trusted']), 'val')
            hist.append(dict(step=step + 1, orig=float(l_o), trans=float(l_t), val_ap=ap))
            if ap is not None and ap > best['score']:
                best = dict(score=ap, step=step + 1, state={k: v.detach().cpu().clone() for k, v in model.state_dict().items()})
    last = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
    res = {}
    for tag, st in (('best', best['state']), ('last', last)):
        model.load_state_dict(st); model.eval()
        with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
            sv = model(xv, ev).float()[:, 1].cpu().numpy(); stg = model(xt, et).float()[:, 1].cpu().numpy()
        res[tag] = dict(val=per_view_ap(sv, zv['old_rows'], np.asarray(zv['y']), np.asarray(zv['trusted']), 'val'),
                        test=per_view_ap(stg, zt['old_rows'], np.asarray(zt['y']), np.asarray(zt['trusted']), 'test'))
    return dict(arm=arm, fold=rec, seed=seed, best_step=best['step'], best_score=best['score'],
                history=hist, results=res)


def main():
    loader = FiveGroupLoader()
    T.CONTRACT = loader.feature_contract; T.NORM = loader.normalization; T.arrays = loader.arrays
    assert T.MASK_MODE == 'old' and not T.EXTRA and T.EQ == 0
    folds = {rec: np.load(OUT / f'{rec}_trans.npz') for rec in RECIPES}
    for rec in RECIPES:
        folds[rec + '_val'] = np.load(OUT / f'{rec}_val.npz')
        folds[rec + '_test'] = np.load(OUT / f'{rec}_test.npz')
    g = gate(loader, folds)
    print('GATE', g['passed'], flush=True)
    if not g['passed']:
        return
    out = {}
    for rec in RECIPES:
        for arm in ('N', 'NC'):
            key = f'{rec}_{arm}'
            out[key] = run_fold(loader, rec, folds, arm)
            print('DONE', key, out[key]['best_step'], out[key]['best_score'], flush=True)
    (OUT / 'RESULTS_FOLDS.json').write_text(json.dumps(out, indent=2), encoding='utf-8')
    print('ALL_DONE')


if __name__ == '__main__':
    main()
