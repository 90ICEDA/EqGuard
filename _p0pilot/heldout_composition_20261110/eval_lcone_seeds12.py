"""Eval L_cone seeds 1/2 (AP/base/add) + aggregate I vs N across 3 seeds."""
import json
from pathlib import Path
import numpy as np, torch
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); OUT = R / '_p0pilot/heldout_composition_20261110'
FG = R / '_p0pilot/four_group_contract_20261109'; B = R / '_p0pilot/control_boundary_v3_20261104'
import sys; sys.path.insert(0, str(R / '_p0pilot/control_best200_20261104'))
from evaluate import Model
from sklearn.metrics import average_precision_score
BASE = ('ys_abc', 'ys_id', 'ys_opt'); ADD = ('ys_aig', 'ys_nand')
c = json.loads((B / 'input_contract.json').read_text(encoding='utf-8')); vs = {v['view']: v for v in c['shared_inputs']['trans_test']['views']}
f = B / 'inputs/trans_test'
x = np.load(f / 'x39.npy'); edge = np.load(f / 'edge_index.npy'); y = np.load(f / 'y.npy'); tr = np.load(f / 'trusted.npy'); ph = np.load(f / 'physical.npy')
rows = np.concatenate([np.arange(vs[v]['start'], vs[v]['stop']) for v in vs])
o2n = np.full(len(y), -1, np.int64); o2n[rows] = np.arange(len(rows)); m = (o2n[edge[0]] >= 0) & (o2n[edge[1]] >= 0)
val = np.load(FG / 'val_common.npz'); mean, std = val['mean'], val['std']
xx = np.array(x[rows], np.float32, copy=True); xx[:, 25:] = np.clip((xx[:, 25:] - mean) / std, -10, 10)
tx = torch.as_tensor(xx, device='cuda'); te = torch.as_tensor(np.stack([o2n[edge[0][m]], o2n[edge[1][m]]]), device='cuda')
res = {}
for seed in (1, 2):
    for arm in ('N', 'NC1', 'NC01', 'C'):
        d0 = OUT / f'lcone_{arm}_s{seed}'
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
            res[f'{seed}_{arm}_{point}'] = dict(ap=ap, base_ap=float(np.mean([ap[r] for r in BASE if r in ap])),
                                                add_ap=float(np.mean([ap[r] for r in ADD if r in ap])))
(OUT / 'LCONE_SEEDS12.json').write_text(json.dumps(res, indent=2), encoding='utf-8')
# aggregate with seed42 from LCONE_EVAL_V2
seed42 = json.loads((OUT / 'LCONE_EVAL_V2.json').read_text(encoding='utf-8'))
agg = {}
for point in ('best', 'last'):
    for arm, base_arm in (('NC1', 'N'), ('NC01', 'N')):
        for fam in ('base', 'add'):
            ds = []
            for seed in (42, 1, 2):
                if seed == 42:
                    v = seed42[f'{arm}_{point}']; n = seed42[f'{base_arm}_{point}']
                else:
                    v = res[f'{seed}_{arm}_{point}']; n = res[f'{seed}_{base_arm}_{point}']
                ds.append(v[f'{fam}_ap'] - n[f'{fam}_ap'])
            agg[f'{arm}_{point}_{fam}'] = ds
(OUT / 'LCONE_INTERACTION.json').write_text(json.dumps(agg, indent=2), encoding='utf-8')
print(json.dumps(agg, indent=2))
