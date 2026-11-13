"""Evaluate hoco seed42 four arms on test host: base/add AP, normal FPR, A/B, interaction."""
import json
from pathlib import Path
import numpy as np, torch
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = R / '_p0pilot/heldout_composition_20261110'
B = R / '_p0pilot/control_boundary_v3_20261104'
import sys; sys.path.insert(0, str(R / '_p0pilot/control_best200_20261104'))
from evaluate import Model
from sklearn.metrics import average_precision_score
BASE = ('ys_abc', 'ys_id', 'ys_opt'); ADD = ('ys_aig', 'ys_nand')
c = json.loads((B / 'input_contract.json').read_text(encoding='utf-8'))
vs = {v['view']: v for v in c['shared_inputs']['trans_test']['views']}
folder = B / 'inputs/trans_test'
x = np.load(folder / 'x39.npy'); edge = np.load(folder / 'edge_index.npy'); y = np.load(folder / 'y.npy'); tr = np.load(folder / 'trusted.npy'); ph = np.load(folder / 'physical.npy')
rows = np.concatenate([np.arange(vs[v]['start'], vs[v]['stop']) for v in vs])
o2n = np.full(len(y), -1, np.int64); o2n[rows] = np.arange(len(rows)); m = (o2n[edge[0]] >= 0) & (o2n[edge[1]] >= 0)
val = np.load(OUT / 'hoco_val.npz'); mean, std = val['mean'], val['std']
xx = np.array(x[rows], np.float32, copy=True); xx[:, 25:] = np.clip((xx[:, 25:] - mean) / std, -10, 10)
tx = torch.as_tensor(xx, device='cuda'); te = torch.as_tensor(np.stack([o2n[edge[0][m]], o2n[edge[1][m]]]), device='cuda')
res = {}
for tag in ('A', 'B'):
    for arm in ('N', 'NC'):
        ck = torch.load(OUT / f'run_{tag}_{arm}' / 'best_resume.pt', map_location='cuda', weights_only=False)
        model = Model().cuda(); model.load_state_dict(ck['model']); model.eval()
        with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
            lg = model(tx, te).float(); s = (lg[:, 1] - lg[:, 0]).cpu().numpy()
        np.savez_compressed(OUT / f'run_{tag}_{arm}' / 'test_pred.npz', scores=s, rows=rows, y=y, trusted=tr, physical=ph)
        by = {}
        for v, lay in vs.items():
            a, b = np.searchsorted(rows, [lay['start'], lay['stop']])
            if len(np.unique(y[a:b][tr[a:b]])) > 1:
                by.setdefault(v.split('__')[-1], []).append(average_precision_score(y[a:b][tr[a:b]], s[a:b][tr[a:b]]))
        ap = {r: float(np.mean(v)) for r, v in by.items()}
        tp = tr & (y == 1); tn = tr & (y == 0)
        # threshold from hoco val at 95%
        sv = np.zeros(len(val['y']))
        model_v = Model().cuda(); model_v.load_state_dict(ck['model']); model_v.eval()
        vx = torch.as_tensor(val['x'], device='cuda'); ve = torch.as_tensor(val['edge'], device='cuda')
        with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
            lv = model_v(vx, ve).float(); sv = (lv[:, 1] - lv[:, 0]).cpu().numpy()
        vp = val['trusted'] & (val['y'] == 1); need = int(np.ceil(0.95 * vp.sum())); thr = float(np.sort(sv[vp])[::-1][need - 1])
        ctl = [v for v in vs if 'ctl' in v]; tnum = tden = anum = aden = 0; at = []
        for v in ctl:
            lay = vs[v]; a, b = np.searchsorted(rows, [lay['start'], lay['stop']])
            tt = tr[a:b] & ph[a:b]; yy = y[a:b]; ss = s[a:b]
            if tt.any():
                at.append(float(ss[tt].max() >= thr)); neg = tt & (yy == 0); tnum += int((ss[neg] >= thr).sum()); tden += int(neg.sum())
            pn = ph[a:b] & (yy == 0); anum += int((ss[pn] >= thr).sum()); aden += int(pn.sum())
        res[f'{tag}_{arm}'] = dict(ap=ap, base_ap=float(np.mean([ap[r] for r in BASE if r in ap])),
                                   add_ap=float(np.mean([ap[r] for r in ADD if r in ap])),
                                   normal_trusted_fpr=tnum / max(1, tden), normal_allphys_fpr=anum / max(1, aden),
                                   view_alarm=float(np.mean(at)) if at else None,
                                   A=dict(threshold=thr, test_recall=float((s[tp] >= thr).sum() / tp.sum()),
                                          test_fpr=float((s[tn] >= thr).sum() / tn.sum())))
(OUT / 'HOCO_RESULTS.json').write_text(json.dumps(res, indent=2), encoding='utf-8')
print(json.dumps({k: (round(v['base_ap'], 4), round(v['add_ap'], 4), round(v['normal_trusted_fpr'], 3)) for k, v in res.items()}))
