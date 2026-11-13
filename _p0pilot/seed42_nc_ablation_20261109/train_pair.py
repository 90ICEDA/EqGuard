"""seed42 N vs NC: 200 updates each, identical node indices/init/optimizer; NC adds frozen cone loss only."""
import os
for k in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
    os.environ[k] = '1'
os.environ['P2B_MASK'] = 'old'
import gc
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = R / '_p0pilot/seed42_nc_ablation_20261109'
L = R / '_p0pilot/control_loader_po_20261105'
V = R / '_p0pilot/control_v3_eligible_20261104'
sys.path.insert(0, str(L)); sys.path.insert(0, str(R / '_p0pilot/control_best200_20261104'))
from supervision_loader import FiveGroupLoader  # noqa: E402
from evaluate import Model, T  # noqa: E402
import cone_loss as CL  # noqa: E402
from sklearn.metrics import average_precision_score, roc_auc_score  # noqa: E402

BOUND = json.loads((R / '_p0pilot/control_boundary_v3_20261104/input_contract.json').read_text(encoding='utf-8'))


def view_ap(pred, y, trust, views, split):
    aps = []
    for v, lay in views.items():
        if split == 'val' and '__inj' not in v:
            continue
        if split == 'test' and '__inj' not in v:
            continue
        lo = lay['start']; hi = lo + (lay['old_stop'] - lay['old_start'])
        yy = y[lo:hi]; pp = pred[lo:hi]; tt = trust[lo:hi]
        m = tt & (yy >= 0)
        if m.sum() < 2 or yy[m].min() == yy[m].max():
            continue
        aps.append(average_precision_score(yy[m], pp[m]))
    return float(np.mean(aps)) if aps else float('nan')


def evaluate(model, loader, cones, split='val'):
    model.eval()
    res = {}
    for dm in ('trans',):
        arr = loader.arrays(dm, split)
        d = loader.torch_graph(dm, split, 'cuda')
        with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
            logits = model(d['x'], d['edge']).float()
        margin = (logits[:, 1] - logits[:, 0]).cpu().numpy()
        y = np.asarray(arr['y']); trust = np.asarray(arr['trusted'])
        pred = margin
        views = {v['view']: v for v in BOUND['shared_inputs'][f'trans_{split}']['views']}
        res['node_ap'] = view_ap(pred, y, trust, views, split)
        m = trust & (y >= 0)
        res['node_ap_pooled'] = float(average_precision_score(y[m], pred[m])) if m.sum() else float('nan')
        res['node_auc'] = float(roc_auc_score(y[m], pred[m])) if m.sum() and len(np.unique(y[m])) > 1 else float('nan')
        pos = (y == 1) & trust
        order = np.argsort(-pred)
        for frac in (1, 5):
            k = max(1, int(len(y) * frac / 100))
            top = order[:k]
            res[f'top{frac}_recall'] = float(pos[top].sum() / max(1, pos.sum()))
        hosts = {}
        for v, lay in views.items():
            h = v.split('__')[0]
            lo = lay['start']; hi = lo + (lay['old_stop'] - lay['old_start'])
            hosts.setdefault(h, []).append((lo, hi))
        rec = []
        for h, spans in hosts.items():
            idx = np.concatenate([np.arange(a, b) for a, b in spans])
            hp = idx[(y[idx] == 1) & trust[idx]]
            if not len(hp):
                continue
            k = max(1, int(len(idx) * 0.01))
            top = idx[np.argsort(-pred[idx])[:k]]
            rec.append(float(np.isin(hp, top).sum() / len(hp)))
        res['source_top1_recall'] = float(np.mean(rec)) if rec else float('nan')
        res['_margin'] = margin; res['_y'] = y; res['_trust'] = trust
        del d, logits
        gc.collect(); torch.cuda.empty_cache()
    # MIL AP on D/PO cones (unknown excluded, trusted members only)
    for kind in ('D', 'PO'):
        rows = CL.load_cones(split, kind, trust=np.asarray(loader.arrays('trans', split)['trusted']))
        if not rows:
            res[f'mil_{kind}_ap'] = float('nan'); continue
        cs = CL.cone_tensors(rows)
        arr = loader.arrays('trans', split)
        # margin over val/test nodes: recompute forward for that split
        d = loader.torch_graph('trans', split, 'cuda')
        with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
            lg = model(d['x'], d['edge']).float()
        mg = (lg[:, 1] - lg[:, 0]).cpu().numpy()
        sc = np.full(len(rows), -1e9, np.float32)
        for i, (_, _, mem) in enumerate(rows):
            sc[i] = max(mg[x] for x in mem)
        res[f'mil_{kind}_ap'] = float(average_precision_score(cs['labels'], sc))
        res[f'mil_{kind}_cones'] = len(rows); res[f'mil_{kind}_pos'] = cs['pos']
        del d, lg
        gc.collect(); torch.cuda.empty_cache()
    return res


def run(arm, loader, cones, seed=42):
    import hashlib
    init_path = V / f'init_s{seed}.pt'
    init_sha = hashlib.sha256(init_path.read_bytes()).hexdigest()
    T.seed(seed)
    model = Model().cuda()
    model.load_state_dict(torch.load(V / f'init_s{seed}.pt', map_location='cuda', weights_only=True))
    opt = torch.optim.Adam(model.parameters(), lr=2e-4, weight_decay=1e-3)
    best = dict(score=-1.0, step=-1, state=None)
    history = []
    domains = {dm: loader.torch_graph(dm, 'train', 'cuda') for dm in ('orig', 'trans')}
    t0 = time.perf_counter()
    for step in range(200):
        T.seed(seed + step)
        model.train(); opt.zero_grad(set_to_none=True)
        ls = {}
        for dm in ('orig', 'trans'):
            d = domains[dm]
            q = loader.step(dm, 'G0', step, seed=seed)
            idx_np = np.array(q.indices, copy=True)
            idx_sha = hashlib.sha256(idx_np.tobytes()).hexdigest()
            ids = torch.as_tensor(idx_np, dtype=torch.long, device='cuda')
            with torch.autocast('cuda', dtype=torch.bfloat16):
                logits = model(d['x'], d['edge'])
                loss = T.domain_loss(logits, d['y'], ids)
                if arm == 'NC' and dm == 'trans':
                    loss = loss + CL.cone_loss(logits, cones)
            ls[dm] = float(loss.detach()); loss.backward()
            del logits, loss, ids
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        if (step + 1) % 5 == 0 or step == 199:
            ev = evaluate(model, loader, cones, 'val')
            score = ev['node_ap']
            history.append(dict(step=step + 1, orig=ls['orig'], trans=ls['trans'], val_ap=score, idx_sha=idx_sha))
            if score > best['score']:
                best = dict(score=score, step=step + 1,
                            state={k: v.detach().cpu().clone() for k, v in model.state_dict().items()})
    last = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
    torch.save(best['state'], OUT / f'{arm}_s{seed}_best.pt'); torch.save(last, OUT / f'{arm}_s{seed}_last.pt')
    model.load_state_dict(best['state'])
    best_ev = evaluate(model, loader, cones, 'val'); best_te = evaluate(model, loader, cones, 'test')
    model.load_state_dict(last)
    last_ev = evaluate(model, loader, cones, 'val'); last_te = evaluate(model, loader, cones, 'test')
    np.savez(OUT / f'{arm}_s{seed}_scores.npz',
             val_best=best_ev.pop('_margin'), test_best=best_te.pop('_margin'),
             y_val=best_ev.pop('_y'), trust_val=best_ev.pop('_trust'),
             y_test=best_te.pop('_y'), trust_test=best_te.pop('_trust'),
             val_last=last_ev.pop('_margin'), test_last=last_te.pop('_margin'))
    for ev in (last_ev, last_te):
        ev.pop('_margin', None); ev.pop('_y', None); ev.pop('_trust', None)
    return dict(arm=arm, seed=seed, init_sha=init_sha, best_step=best['step'], best_score=best['score'],
                best_val=best_ev, best_test=best_te, last_val=last_ev, last_test=last_te,
                history=history, seconds=time.perf_counter() - t0)


def main():
    assert 'ginvenv_gpu' in sys.executable and torch.cuda.is_available()
    torch.set_num_threads(2)
    loader = FiveGroupLoader()
    T.CONTRACT = loader.feature_contract; T.NORM = loader.normalization; T.arrays = loader.arrays
    assert T.MASK_MODE == 'old' and not T.EXTRA and T.EQ == 0
    trust = np.asarray(loader.arrays('trans')['trusted'])
    cones = CL.cone_tensors(CL.load_cones('train', 'D', trust=trust))
    out = {}
    seeds = [int(x) for x in sys.argv[1:]] or [42]
    for seed in seeds:
        for arm in ('N', 'NC'):
            t = time.perf_counter()
            key = f'{arm}_s{seed}'
            out[key] = run(arm, loader, cones, seed)
            out[key]['wall'] = round(time.perf_counter() - t, 1)
            print('DONE', key, out[key]['best_step'], out[key]['best_score'], flush=True)
            gc.collect(); torch.cuda.empty_cache()
    (OUT / 'RESULTS_ALL.json').write_text(json.dumps(out, indent=2), encoding='utf-8')
    rows = []
    for key, res in out.items():
        for tag in ('best_val', 'best_test', 'last_val', 'last_test'):
            rows.append(dict(run=key, point=tag, **{k: v for k, v in res[tag].items()}))
    import csv
    with (OUT / 'METRICS_ALL.csv').open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    print('PAIR_COMPLETE', {a: out[a]['best_step'] for a in out})


if __name__ == '__main__':
    main()
