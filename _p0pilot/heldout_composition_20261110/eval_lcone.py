"""L_cone eval: 4 arms best/last test AP/top/normal/D-PO MIL/A."""
import csv, json
from pathlib import Path
import numpy as np, torch
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); OUT = R / '_p0pilot/heldout_composition_20261110'
FG = R / '_p0pilot/four_group_contract_20261109'; B = R / '_p0pilot/control_boundary_v3_20261104'
PREP = R / '_p0pilot/seed42_supervised_prep_20261109'
import sys; sys.path.insert(0, str(R / '_p0pilot/control_best200_20261104'))
from evaluate import Model
from sklearn.metrics import average_precision_score
c = json.loads((B / 'input_contract.json').read_text(encoding='utf-8'))
vs = {v['view']: v for v in c['shared_inputs']['trans_test']['views']}
f = B / 'inputs/trans_test'
x = np.load(f / 'x39.npy'); edge = np.load(f / 'edge_index.npy'); y = np.load(f / 'y.npy'); tr = np.load(f / 'trusted.npy'); ph = np.load(f / 'physical.npy')
rows = np.concatenate([np.arange(vs[v]['start'], vs[v]['stop']) for v in vs])
o2n = np.full(len(y), -1, np.int64); o2n[rows] = np.arange(len(rows)); m = (o2n[edge[0]] >= 0) & (o2n[edge[1]] >= 0)
val = np.load(FG / 'val_common.npz'); mean, std = val['mean'], val['std']
xx = np.array(x[rows], np.float32, copy=True); xx[:, 25:] = np.clip((xx[:, 25:] - mean) / std, -10, 10)
tx = torch.as_tensor(xx, device='cuda'); te = torch.as_tensor(np.stack([o2n[edge[0][m]], o2n[edge[1][m]]]), device='cuda')
res = {}
for arm in ('N', 'NC1', 'NC01', 'C'):
    d0 = OUT / f'lcone_{arm}'
    for point in ('best', 'last'):
        ck = torch.load(d0 / f'{point}_resume.pt', map_location='cuda', weights_only=False)
        model = Model().cuda(); model.load_state_dict(ck['model']); model.eval()
        with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
            lg = model(tx, te).float(); s = (lg[:, 1] - lg[:, 0]).cpu().numpy()
        np.savez_compressed(d0 / f'{point}_testpred.npz', scores=s, rows=rows, y=y, trusted=tr, physical=ph)
        ap = {}
        for v, lay in vs.items():
            a, b = np.searchsorted(rows, [lay['start'], lay['stop']])
            if len(np.unique(y[a:b][tr[a:b]])) > 1:
                ap.setdefault(v.split('__')[-1], []).append(average_precision_score(y[a:b][tr[a:b]], s[a:b][tr[a:b]]))
        ap = {r: float(np.mean(v)) for r, v in ap.items()}
        tp = tr & (y == 1); tn = tr & (y == 0)
        thr = ck.get('threshold')
        res[f'{arm}_{point}'] = dict(ap=ap, base_ap=float(np.mean([ap[r] for r in ('ys_abc', 'ys_id', 'ys_opt') if r in ap])),
                                     add_ap=float(np.mean([ap[r] for r in ('ys_aig', 'ys_nand') if r in ap])), best_step=ck.get('best_step'))
(OUT / 'LCONE_RESULTS.json').write_text(json.dumps(res, indent=2), encoding='utf-8')
for k, v in res.items(): print(k, round(v['base_ap'], 4), round(v['add_ap'], 4))
