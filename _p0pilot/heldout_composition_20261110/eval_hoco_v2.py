"""hoco eval v2: 3 seeds x 4 arms x best/last; AP/Top-k/4 normal/A/B/I."""
import json, sys
from pathlib import Path
import numpy as np, torch
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); OUT = R / '_p0pilot/heldout_composition_20261110'
B = R / '_p0pilot/control_boundary_v3_20261104'
sys.path.insert(0, str(R / '_p0pilot/control_best200_20261104'))
from evaluate import Model
from sklearn.metrics import average_precision_score
BASE = ('ys_abc', 'ys_id', 'ys_opt'); ADD = ('ys_aig', 'ys_nand')
c = json.loads((B / 'input_contract.json').read_text(encoding='utf-8'))
vs = {v['view']: v for v in c['shared_inputs']['trans_test']['views']}
f = B / 'inputs/trans_test'
x = np.load(f / 'x39.npy'); edge = np.load(f / 'edge_index.npy'); y = np.load(f / 'y.npy'); tr = np.load(f / 'trusted.npy'); ph = np.load(f / 'physical.npy')
rows = np.concatenate([np.arange(vs[v]['start'], vs[v]['stop']) for v in vs])
o2n = np.full(len(y), -1, np.int64); o2n[rows] = np.arange(len(rows)); m = (o2n[edge[0]] >= 0) & (o2n[edge[1]] >= 0)
val = np.load(OUT / 'hoco_val.npz'); mean, std = val['mean'], val['std']
xx = np.array(x[rows], np.float32, copy=True); xx[:, 25:] = np.clip((xx[:, 25:] - mean) / std, -10, 10)
tx = torch.as_tensor(xx, device='cuda'); te = torch.as_tensor(np.stack([o2n[edge[0][m]], o2n[edge[1][m]]]), device='cuda')
vx = torch.as_tensor(val['x'], device='cuda'); ve = torch.as_tensor(val['edge'], device='cuda')
vp = val['trusted'] & (val['y'] == 1); vn = val['trusted'] & (val['y'] == 0)
res = {}
for seed in (42, 1, 2):
    for tag in ('A', 'B'):
        for arm in ('N', 'NC'):
            d = OUT / (f'run_{tag}_{arm}' if seed == 42 else f'run_{tag}_{arm}_s{seed}')
            if not d.exists(): continue
            for point in ('best', 'last'):
                ck = torch.load(d / f'{point}_resume.pt', map_location='cuda', weights_only=False)
                model = Model().cuda(); model.load_state_dict(ck['model']); model.eval()
                with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
                    lg = model(tx, te).float(); s = (lg[:, 1] - lg[:, 0]).cpu().numpy()
                    lv = model(vx, ve).float(); sv = (lv[:, 1] - lv[:, 0]).cpu().numpy()
                np.savez_compressed(d / f'{point}_testpred.npz', scores=s, rows=rows, y=y, trusted=tr, physical=ph)
                apv, src = {}, {}
                for v, lay in vs.items():
                    a, b = np.searchsorted(rows, [lay['start'], lay['stop']])
                    if len(np.unique(y[a:b][tr[a:b]])) > 1:
                        apv.setdefault(v.split('__')[-1], []).append(average_precision_score(y[a:b][tr[a:b]], s[a:b][tr[a:b]]))
                        src.setdefault(v.split('__ys_')[0], {}).setdefault(v.split('__')[-1], []).append(
                            average_precision_score(y[a:b][tr[a:b]], s[a:b][tr[a:b]]))
                ap = {r: float(np.mean(v)) for r, v in apv.items()}
                src = {k: {r: float(np.mean(v)) for r, v in dd.items()} for k, dd in src.items()}
                top = {}
                for v, lay in vs.items():
                    a, b = np.searchsorted(rows, [lay['start'], lay['stop']]); tt = tr[a:b]; yy = y[a:b]; ss = s[a:b]
                    if tt.sum() < 2: continue
                    order = np.lexsort((np.arange(b - a)[tt], -ss[tt])); pos = (yy[tt] == 1)[order]
                    for frac in (1, 5):
                        k = max(1, int(tt.sum() * frac / 100))
                        if pos.sum(): top.setdefault(f'top{frac}', []).append(float(pos[:k].sum() / pos.sum()))
                top = {k: float(np.mean(v)) for k, v in top.items()}
                tp = tr & (y == 1); tn = tr & (y == 0)
                A = {}
                for q in (0.8, 0.9, 0.95):
                    need = int(np.ceil(q * vp.sum())); thr = float(np.sort(sv[vp])[::-1][need - 1])
                    A[str(q)] = dict(threshold=thr, val_recall=float((sv[vp] >= thr).sum() / vp.sum()),
                                     val_fpr=float((sv[vn] >= thr).sum() / vn.sum()),
                                     test_recall=float((s[tp] >= thr).sum() / tp.sum()),
                                     test_fpr=float((s[tn] >= thr).sum() / tn.sum()),
                                     val_pos=int(vp.sum()), val_neg=int(vn.sum()), test_pos=int(tp.sum()), test_neg=int(tn.sum()))
                Bq = {}
                for q in (0.8, 0.9, 0.95):
                    need = int(np.ceil(q * tp.sum())); thr = float(np.sort(s[tp])[::-1][need - 1])
                    Bq[str(q)] = dict(threshold=thr, need=need, test_recall=float((s[tp] >= thr).sum() / tp.sum()),
                                      test_fpr=float((s[tn] >= thr).sum() / tn.sum()))
                def nrm(thr):
                    ct = [v for v in vs if 'ctl' in v]; tn_ = td = an = ad = 0; at = []; ap_ = []
                    for v in ct:
                        lay = vs[v]; a, b = np.searchsorted(rows, [lay['start'], lay['stop']])
                        tt = tr[a:b] & ph[a:b]; yy = y[a:b]; ss = s[a:b]
                        if tt.any():
                            at.append(float(ss[tt].max() >= thr)); neg = tt & (yy == 0)
                            tn_ += int((ss[neg] >= thr).sum()); td += int(neg.sum())
                        pn = ph[a:b] & (yy == 0)
                        if pn.any(): ap_.append(float(ss[pn].max() >= thr))
                        an += int((ss[pn] >= thr).sum()); ad += int(pn.sum())
                    return dict(trusted_node_fpr=(None if td == 0 else tn_ / td), trusted_den=int(td),
                                allphys_node_fpr=(None if ad == 0 else an / ad), allphys_den=int(ad),
                                trusted_view_alarm=(None if not at else float(np.mean(at))), trusted_views=len(at),
                                allphys_view_alarm=(None if not ap_ else float(np.mean(ap_))), allphys_views=len(ap_))
                res[f'{seed}_{tag}_{arm}_{point}'] = dict(ap=ap, source_ap=src, top=top, A=A, B=Bq,
                                                          normal={q: nrm(A[q]['threshold']) for q in A},
                                                          base_ap=float(np.mean([ap[r] for r in BASE if r in ap])),
                                                          add_ap=float(np.mean([ap[r] for r in ADD if r in ap])),
                                                          best_step=ck.get('best_step'), completed=ck.get('completed'))
                print('E', seed, tag, arm, point, round(res[f'{seed}_{tag}_{arm}_{point}']['base_ap'], 4), flush=True)
(OUT / 'HOCO_EVAL_V2.json').write_text(json.dumps(res, indent=2), encoding='utf-8')
print('done', len(res))
