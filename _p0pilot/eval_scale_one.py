"""Evaluate one scale-calibration run against group_B test, save metrics."""
import json, sys
from pathlib import Path
import numpy as np, torch

R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FG = R / '_p0pilot/four_group_contract_20261109'
B = R / '_p0pilot/control_boundary_v3_20261104'
sys.path.insert(0, str(R / '_p0pilot/control_best200_20261104'))
from evaluate import Model
from sklearn.metrics import average_precision_score

run = Path(sys.argv[1]); point = sys.argv[2] if len(sys.argv) > 2 else 'best'
c = json.loads((B / 'input_contract.json').read_text(encoding='utf-8'))
vs = {v['view']: v for v in c['shared_inputs']['trans_test']['views']}
f = B / 'inputs/trans_test'
x = np.load(f / 'x39.npy'); edge = np.load(f / 'edge_index.npy')
y = np.load(f / 'y.npy'); tr = np.load(f / 'trusted.npy'); ph = np.load(f / 'physical.npy')
rows = np.concatenate([np.arange(vs[v]['start'], vs[v]['stop']) for v in vs])
o2n = np.full(len(y), -1, np.int64); o2n[rows] = np.arange(len(rows))
m = (o2n[edge[0]] >= 0) & (o2n[edge[1]] >= 0)
val = np.load(FG / 'val_common.npz'); mean, std = val['mean'], val['std']
xx = np.array(x[rows], np.float32, copy=True); xx[:, 25:] = np.clip((xx[:, 25:] - mean) / std, -10, 10)
tx = torch.as_tensor(xx, device='cuda'); te = torch.as_tensor(np.stack([o2n[edge[0][m]], o2n[edge[1][m]]]), device='cuda')
ck = torch.load(run / f'{point}_resume.pt', map_location='cuda', weights_only=False)
model = Model().cuda(); model.load_state_dict(ck['model']); model.eval()
with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
    lg = model(tx, te).float(); s = (lg[:, 1] - lg[:, 0]).cpu().numpy()
    lv = model(torch.as_tensor(val['x'], device='cuda'), torch.as_tensor(val['edge'], device='cuda')).float()
    sv = (lv[:, 1] - lv[:, 0]).cpu().numpy()
np.savez_compressed(run / f'{point}_testpred.npz', scores=s, rows=rows, y=y, trusted=tr, physical=ph)
ap, top = {}, {}
for v, lay in vs.items():
    a, b = np.searchsorted(rows, [lay['start'], lay['stop']])
    yy, tt, ss = y[a:b], tr[a:b], s[a:b]
    if len(np.unique(yy[tt])) > 1:
        ap.setdefault(v.split('__')[-1], []).append(average_precision_score(yy[tt], ss[tt]))
        order = np.lexsort((np.arange(b - a)[tt], -ss[tt])); pos = (yy[tt] == 1)[order]
        for frac in (1, 5):
            k = max(1, int(tt.sum() * frac / 100))
            if pos.sum(): top.setdefault(f'top{frac}', {}).setdefault(v.split('__')[-1], []).append(float(pos[:k].sum() / pos.sum()))
ap = {r: float(np.mean(v)) for r, v in ap.items()}
top = {k: {r: float(np.mean(v)) for r, v in vv.items()} for k, vv in top.items()}
base = float(np.mean([ap[r] for r in ('ys_abc', 'ys_id', 'ys_opt') if r in ap]))
add = float(np.mean([ap[r] for r in ('ys_aig', 'ys_nand') if r in ap]))
tn = tr & (y == 0); tp = tr & (y == 1)
need = int(np.ceil(0.95 * tp.sum())); thr = float(np.sort(s[tp])[::-1][need - 1])
b95 = dict(threshold=thr, recall=float((s[tp] >= thr).sum() / tp.sum()), fpr=float((s[tn] >= thr).sum() / max(1, tn.sum())))
out = dict(run=str(run), point=point, lambda_=ck.get('lambda', None), base_ap=base, add_ap=add, ap=ap, top=top, b95=b95,
           best_step=ck.get('best_step'))
(run / f'{point}_eval.json').write_text(json.dumps(out, indent=2), encoding='utf-8')
print(json.dumps({k: out[k] for k in ('run', 'point', 'base_ap', 'add_ap', 'b95', 'best_step')}, ensure_ascii=False))
