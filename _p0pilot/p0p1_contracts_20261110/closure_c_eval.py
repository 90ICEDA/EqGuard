"""Closure check + C single-fold evaluation from hoco 12 predictions."""
import json, statistics as st
from pathlib import Path
import numpy as np
from sklearn.metrics import average_precision_score
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
L = R / '_p0pilot/lcone_v2c_20261110'; H = R / '_p0pilot/heldout_composition_20261110'
B = R / '_p0pilot/control_boundary_v3_20261104'; P = R / '_p0pilot/p0p1_contracts_20261110'
# closure check
f = json.loads((L / 'LCONE_FINAL_OFFLINE.json').read_text(encoding='utf-8'))
chk = dict(
    base_vs_N_0of3=(f['base_vs_N']['base_pos'] == 0 and f['base_vs_N']['add_pos'] == 0),
    all_vs_N_0of3=(f['all_vs_N']['base_pos'] == 0 and f['all_vs_N']['add_pos'] == 0),
    all_minus_base=(round(f['all_minus_base']['base_mean'], 4), round(f['all_minus_base']['add_mean'], 4)),
    lambda1='historical_not_recomputable', nand='2 cones not_evaluable',
    v2b='budget unequal 792/1116', ratio='cone/node ~3')
chk['status'] = 'PASS' if chk['base_vs_N_0of3'] and chk['all_vs_N_0of3'] else 'PARTIAL'
(L / 'LCONE_CLOSURE_CHECK.json').write_text(json.dumps(chk, indent=2), encoding='utf-8')
# C eval
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
    return dict(ap=ap, base_ap=float(np.mean([ap[r] for r in BASE if r in ap])), add_ap=float(np.mean([ap[r] for r in ADD if r in ap])),
                top=top, b95=dict(recall=float((s[tp] >= thr).sum() / tp.sum()), fpr=float((s[tn] >= thr).sum() / max(1, tn.sum()))))
res = {}
for seed in (42, 1, 2):
    for tag in ('A', 'B'):
        for arm in ('N', 'NC'):
            d = H / (f'run_{tag}_{arm}' if seed == 42 else f'run_{tag}_{arm}_s{seed}')
            p = d / 'best_testpred.npz'
            if p.exists(): res[f'{seed}_{tag}_{arm}'] = metrics(p)
out = {'metrics': res, 'design': 'h=abc single fold, A=id/opt, B=A+aig/nand', 'cec': 'not functional GT'}
for tag in ('A', 'B'):
    db = [res[f'{s}_{tag}_NC']['base_ap'] - res[f'{s}_{tag}_N']['base_ap'] for s in (42, 1, 2) if f'{s}_{tag}_NC' in res and f'{s}_{tag}_N' in res]
    da = [res[f'{s}_{tag}_NC']['add_ap'] - res[f'{s}_{tag}_N']['add_ap'] for s in (42, 1, 2) if f'{s}_{tag}_NC' in res and f'{s}_{tag}_N' in res]
    out[f'{tag}_NC_minus_N'] = dict(base=db, base_mean=st.mean(db) if db else None, base_sd=st.stdev(db) if len(db) > 1 else None, base_pos=sum(1 for x in db if x > 0),
                                    add=da, add_mean=st.mean(da) if da else None, add_sd=st.stdev(da) if len(da) > 1 else None, add_pos=sum(1 for x in da if x > 0))
(H / 'C_EVAL_FINAL.json').write_text(json.dumps(out, indent=2), encoding='utf-8')
(P / 'GT_PLAN_V5.md').write_text("""# GT_PLAN_V5

- CEC 40/40 只证实现等价；clean 不是 CEC PASS。
- host GT：rs232 verified_example；s15850/s35932/s38584 can_attempt；s38417t100 missing。
- 面板逐组合 GT 未建；需按宿主 mapping 逐组合判定，s38417t100 单列。
- 功能影响 GT 与区域标签分开；unknown 不默认负；弱 MIL/结构可达/CEC 等价不作 GT。
""", encoding='utf-8')
print(json.dumps({k: (v['base_mean'], v['add_mean'], v['base_pos'], v['add_pos']) for k, v in out.items() if k.endswith('NC_minus_N')}, ensure_ascii=False))
