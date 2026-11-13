"""Offline recompute N vs lambda0.1 from saved testpred; rename lambda01 results; final table."""
import json, statistics as st
from pathlib import Path
import numpy as np
from sklearn.metrics import average_precision_score
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FG = R / '_p0pilot/four_group_contract_20261109'
O = R / '_p0pilot/lcone_v2c_20261110'; B = R / '_p0pilot/control_boundary_v3_20261104'
BASE = ('ys_abc', 'ys_id', 'ys_opt'); ADD = ('ys_aig', 'ys_nand')
c = json.loads((B / 'input_contract.json').read_text(encoding='utf-8')); vs = {v['view']: v for v in c['shared_inputs']['trans_test']['views']}
def metrics(npz):
    z = np.load(npz); s, rows, y, tr, ph = z['scores'], z['rows'], z['y'], z['trusted'], z['physical']
    ap = {}
    for v, lay in vs.items():
        a, b = np.searchsorted(rows, [lay['start'], lay['stop']])
        if len(np.unique(y[a:b][tr[a:b]])) > 1:
            ap.setdefault(v.split('__')[-1], []).append(average_precision_score(y[a:b][tr[a:b]], s[a:b][tr[a:b]]))
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
    need = int(np.ceil(0.95 * tp.sum())); thr = float(np.sort(s[tp])[::-1][need - 1])
    tnum = tden = an = ad = 0; at = []
    for v in [x for x in vs if 'ctl' in x]:
        lay = vs[v]; a, b = np.searchsorted(rows, [lay['start'], lay['stop']])
        tt = tr[a:b] & ph[a:b]; yy = y[a:b]; ss = s[a:b]
        if tt.any():
            at.append(float(ss[tt].max() >= thr)); neg = tt & (yy == 0); tnum += int((ss[neg] >= thr).sum()); tden += int(neg.sum())
        pn = ph[a:b] & (yy == 0); an += int((ss[pn] >= thr).sum()); ad += int(pn.sum())
    return dict(ap=ap, base_ap=float(np.mean([ap[r] for r in BASE if r in ap])), add_ap=float(np.mean([ap[r] for r in ADD if r in ap])),
                top=top, b95=dict(need=need, threshold=thr, recall=float((s[tp] >= thr).sum() / tp.sum()),
                                  fpr=float((s[tn] >= thr).sum() / max(1, tn.sum()))),
                normal=dict(trusted_fpr=(None if tden == 0 else tnum / tden), allphys_fpr=(None if ad == 0 else an / ad),
                            view_alarm=(None if not at else float(np.mean(at)))))
res = {}
for seed, d in ((42, 'run_B_N'), (1, 'run_B_N_s1'), (2, 'run_B_N_s2')):
    res[f'N_{seed}'] = metrics(FG / d / 'best_testpred.npz')
for arm in ('base', 'all'):
    for seed in (42, 1, 2):
        res[f'{arm}_{seed}'] = metrics(O / 'lambda01' / f'run_{arm}_s{seed}' / 'best_testpred.npz')
out = {'metrics': res}
for arm in ('base', 'all'):
    db = [res[f'{arm}_{s}']['base_ap'] - res[f'N_{s}']['base_ap'] for s in (42, 1, 2)]
    da = [res[f'{arm}_{s}']['add_ap'] - res[f'N_{s}']['add_ap'] for s in (42, 1, 2)]
    out[f'{arm}_vs_N'] = dict(base=db, base_mean=st.mean(db), base_sd=st.stdev(db), base_pos=sum(1 for x in db if x > 0),
                              add=da, add_mean=st.mean(da), add_sd=st.stdev(da), add_pos=sum(1 for x in da if x > 0))
db = [res[f'all_{s}']['base_ap'] - res[f'base_{s}']['base_ap'] for s in (42, 1, 2)]
da = [res[f'all_{s}']['add_ap'] - res[f'base_{s}']['add_ap'] for s in (42, 1, 2)]
out['all_minus_base'] = dict(base=db, base_mean=st.mean(db), base_sd=st.stdev(db), base_pos=sum(1 for x in db if x > 0),
                             add=da, add_mean=st.mean(da), add_sd=st.stdev(da), add_pos=sum(1 for x in da if x > 0))
out['notes'] = ['lambda1 checkpoints/JSON overwritten; historical_not_recomputable',
                'nand only 2 cones; add gain mainly aig', 'A threshold not recomputed (no lambda01 val preds); B95 reported']
(O / 'LCONE_FINAL_OFFLINE.json').write_text(json.dumps(out, indent=2), encoding='utf-8')
# rename lambda01 result file, mark old summary invalid
src = O / 'LCONE_V2C_RESULTS.json'
if src.exists():
    (O / 'LCONE_V2C_RESULTS_lambda01.json').write_text(src.read_text(encoding='utf-8'), encoding='utf-8')
    (O / 'LCONE_V2C_RESULTS.json').write_text(json.dumps(dict(status='INVALID_OVERWRITTEN_BY_LAMBDA01',
                                                               note='lambda1 results overwritten; see LCONE_V2C_RESULTS_lambda01.json and LCONE_FINAL_OFFLINE.json'), indent=2), encoding='utf-8')
print(json.dumps({k: out[k] for k in ('base_vs_N', 'all_vs_N', 'all_minus_base')}, ensure_ascii=False)[:1200])
