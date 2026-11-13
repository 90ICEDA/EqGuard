"""Evaluate v2b runs: node AP base/add, Top-k, normal, D/PO test-cone AP."""
import csv, json, sys
from pathlib import Path
import numpy as np, torch
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FG = R / '_p0pilot/four_group_contract_20261109'
OUT = R / '_p0pilot/lcone_v2b_20261110'; B = R / '_p0pilot/control_boundary_v3_20261104'
OLD = R / '_p0pilot/seed42_nc_ablation_20261109'
sys.path.insert(0, str(R / '_p0pilot/control_best200_20261104'))
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
vx = torch.as_tensor(val['x'], device='cuda'); ve = torch.as_tensor(val['edge'], device='cuda')
vp = val['trusted'] & (val['y'] == 1); vn = val['trusted'] & (val['y'] == 0)
cone_rows = list(csv.DictReader((OLD / 'CONE_CACHE_TEST.csv').open(encoding='utf-8-sig', newline='')))
loc = {r: i for i, r in enumerate(rows.tolist())}
res = {}
for arm in ('base', 'all'):
    for seed in (42, 1, 2):
        d0 = OUT / f'run_{arm}_s{seed}'
        for point in ('best', 'last'):
            ck = torch.load(d0 / f'{point}_resume.pt', map_location='cuda', weights_only=False)
            model = Model().cuda(); model.load_state_dict(ck['model']); model.eval()
            with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
                lg = model(tx, te).float(); s = (lg[:, 1] - lg[:, 0]).cpu().numpy()
                lv = model(vx, ve).float(); sv = (lv[:, 1] - lv[:, 0]).cpu().numpy()
            np.savez_compressed(d0 / f'{point}_testpred.npz', scores=s, rows=rows, y=y, trusted=tr, physical=ph)
            ap, src = {}, {}
            for v, lay in vs.items():
                a, b = np.searchsorted(rows, [lay['start'], lay['stop']])
                if len(np.unique(y[a:b][tr[a:b]])) > 1:
                    av = average_precision_score(y[a:b][tr[a:b]], s[a:b][tr[a:b]])
                    ap.setdefault(v.split('__')[-1], []).append(av)
                    src.setdefault(v.split('__ys_')[0], {}).setdefault(v.split('__')[-1], []).append(av)
            ap = {r: float(np.mean(v)) for r, v in ap.items()}
            top = {}
            for frac in (1, 5):
                vals = []
                for v, lay in vs.items():
                    a, b = np.searchsorted(rows, [lay['start'], lay['stop']]); tt = tr[a:b]; yy = y[a:b]; ss = s[a:b]
                    if tt.sum() < 2: continue
                    order = np.lexsort((np.arange(b - a)[tt], -ss[tt])); pos = (yy[tt] == 1)[order]
                    k = max(1, int(tt.sum() * frac / 100))
                    if pos.sum(): vals.append(float(pos[:k].sum() / pos.sum()))
                top[f'top{frac}'] = float(np.mean(vals)) if vals else None
            tp = tr & (y == 1); tn = tr & (y == 0)
            A = {}
            for q in (0.8, 0.9, 0.95):
                need = int(np.ceil(q * vp.sum())); thr = float(np.sort(sv[vp])[::-1][need - 1])
                A[str(q)] = dict(threshold=thr, test_recall=float((s[tp] >= thr).sum() / tp.sum()), test_fpr=float((s[tn] >= thr).sum() / tn.sum()))
            mil = {}
            for kind in ('D', 'PO'):
                lab, sc = [], []
                for r in cone_rows:
                    if r['split'] != 'test' or r['kind'] != kind or int(r['label']) < 0: continue
                    mem = [loc[int(q)] for q in r['phys_rows'].split('|') if q and int(q) in loc]
                    mem = [q for q in mem if tr[q] and ph[q]]
                    if len(mem) < 2: continue
                    lab.append(int(r['label'])); sc.append(float(max(s[q] for q in mem)))
                lab = np.array(lab); sc = np.array(sc)
                mil[kind] = dict(pos=int(lab.sum()), neg=int((lab == 0).sum()),
                                 ap=(float(average_precision_score(lab, sc)) if len(np.unique(lab)) > 1 else None))
            res[f'{arm}_{seed}_{point}'] = dict(ap=ap, base_ap=float(np.mean([ap[r] for r in BASE if r in ap])),
                                                add_ap=float(np.mean([ap[r] for r in ADD if r in ap])), top=top, A=A, mil=mil)
            print('E', arm, seed, point, round(res[f'{arm}_{seed}_{point}']['base_ap'], 4), flush=True)
(OUT / 'LCONE_V2B_RESULTS.json').write_text(json.dumps(res, indent=2), encoding='utf-8')
print('done')
