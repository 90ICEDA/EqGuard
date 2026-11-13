"""CORRECTION_LCONE_FULL + independent self-audit V3 + I aggregation."""
import csv, json, statistics as st
from pathlib import Path
import numpy as np, torch
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); OUT = R / '_p0pilot/heldout_composition_20261110'
FG = R / '_p0pilot/four_group_contract_20261109'; B = R / '_p0pilot/control_boundary_v3_20261104'
OLD = R / '_p0pilot/seed42_nc_ablation_20261109'
from sklearn.metrics import average_precision_score
d = json.loads((OUT / 'LCONE_EVAL_V3.json').read_text(encoding='utf-8'))
corr = {}
for seed in (42, 1, 2):
    for arm in ('N', 'NC1', 'NC01', 'C'):
        d0 = OUT / (f'lcone_{arm}' if seed == 42 else f'lcone_{arm}_s{seed}')
        for point in ('best', 'last'):
            p = d0 / f'{point}_resume.pt'
            ck = torch.load(p, map_location='cpu', weights_only=False)
            bs, comp = ck.get('best_step'), ck.get('completed')
            resum = (point == 'last') or (bs == comp)
            corr[str(p.relative_to(OUT))] = dict(seed=seed, arm=arm, point=point, best_step=bs, completed=comp,
                                                has_optimizer=ck.get('optimizer') is not None,
                                                resumable=bool(resum),
                                                note=('same step (best_step==completed)' if resum else 'best_step<completed: inference only'))
(OUT / 'CORRECTION_LCONE_FULL.json').write_text(json.dumps(corr, indent=2), encoding='utf-8')
# independent audit
c = json.loads((B / 'input_contract.json').read_text(encoding='utf-8')); vs = {v['view']: v for v in c['shared_inputs']['trans_test']['views']}
y = np.load(B / 'inputs/trans_test/y.npy'); tr = np.load(B / 'inputs/trans_test/trusted.npy'); ph = np.load(B / 'inputs/trans_test/physical.npy')
val = np.load(FG / 'val_common.npz'); vp = val['trusted'] & (val['y'] == 1); vn = val['trusted'] & (val['y'] == 0)
cone_rows = list(csv.DictReader((OLD / 'CONE_CACHE_TEST.csv').open(encoding='utf-8-sig', newline='')))
issues = []; ok = 0
def cmp(n, a, b, tol=1e-9):
    global ok
    if a is None and b is None: ok += 1; return
    if a is None or b is None or abs(a - b) > tol: issues.append(dict(field=n, got=a, saved=b)); return
    ok += 1
import sys; sys.path.insert(0, str(R / '_p0pilot/control_best200_20261104'))
from evaluate import Model
for seed in (42, 1, 2):
    for arm in ('N', 'NC1', 'NC01', 'C'):
        d0 = OUT / (f'lcone_{arm}' if seed == 42 else f'lcone_{arm}_s{seed}')
        for point in ('best', 'last'):
            ck = torch.load(d0 / f'{point}_resume.pt', map_location='cuda', weights_only=False)
            model = Model().cuda(); model.load_state_dict(ck['model']); model.eval()
            z = np.load(d0 / f'{point}_testpred.npz'); s = z['scores']; rows = z['rows']
            vx = torch.as_tensor(val['x'], device='cuda'); ve = torch.as_tensor(val['edge'], device='cuda')
            with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
                lv = model(vx, ve).float(); sv = (lv[:, 1] - lv[:, 0]).cpu().numpy()
            ap = {}
            for v, lay in vs.items():
                a, b = np.searchsorted(rows, [lay['start'], lay['stop']])
                if len(np.unique(y[a:b][tr[a:b]])) > 1:
                    ap.setdefault(v.split('__')[-1], []).append(average_precision_score(y[a:b][tr[a:b]], s[a:b][tr[a:b]]))
            ap = {r: float(np.mean(v)) for r, v in ap.items()}; k = f'{seed}_{arm}_{point}'
            for r, v in ap.items(): cmp(f'{k}.ap.{r}', v, d[k]['ap'].get(r))
            cmp(f'{k}.base', float(np.mean([ap[r] for r in ('ys_abc', 'ys_id', 'ys_opt') if r in ap])), d[k]['base_ap'])
            cmp(f'{k}.add', float(np.mean([ap[r] for r in ('ys_aig', 'ys_nand') if r in ap])), d[k]['add_ap'])
            for frac in (1, 5):
                vals = []
                for v, lay in vs.items():
                    a, b = np.searchsorted(rows, [lay['start'], lay['stop']]); tt = tr[a:b]; yy = y[a:b]; ss = s[a:b]
                    if tt.sum() < 2: continue
                    order = np.lexsort((np.arange(b - a)[tt], -ss[tt])); pos = (yy[tt] == 1)[order]
                    kk = max(1, int(tt.sum() * frac / 100))
                    if pos.sum(): vals.append(float(pos[:kk].sum() / pos.sum()))
                cmp(f'{k}.top{frac}', float(np.mean(vals)) if vals else None, d[k]['top'][f'top{frac}'])
            tp = tr & (y == 1); tn = tr & (y == 0)
            for q in ('0.8', '0.9', '0.95'):
                need = int(np.ceil(float(q) * vp.sum())); thr = float(np.sort(sv[vp])[::-1][need - 1])
                cmp(f'{k}.A{q}.thr', thr, d[k]['A'][q]['threshold'])
                cmp(f'{k}.A{q}.rec', float((s[tp] >= thr).sum() / tp.sum()), d[k]['A'][q]['test_recall'])
                cmp(f'{k}.A{q}.fpr', float((s[tn] >= thr).sum() / tn.sum()), d[k]['A'][q]['test_fpr'])
                num = den = an = ad = 0
                for v in [z2 for z2 in vs if 'ctl' in z2]:
                    lay = vs[v]; a, b = np.searchsorted(rows, [lay['start'], lay['stop']])
                    tt = tr[a:b] & ph[a:b]; yy = y[a:b]; ss = s[a:b]
                    if tt.any():
                        neg = tt & (yy == 0); num += int((ss[neg] >= thr).sum()); den += int(neg.sum())
                    pn = ph[a:b] & (yy == 0); an += int((ss[pn] >= thr).sum()); ad += int(pn.sum())
                cmp(f'{k}.norm{q}.t', num / max(1, den), d[k]['normal'][q]['trusted_node_fpr'])
                cmp(f'{k}.norm{q}.a', an / max(1, ad), d[k]['normal'][q]['allphys_node_fpr'])
                need = int(np.ceil(float(q) * tp.sum())); thr2 = float(np.sort(s[tp])[::-1][need - 1])
                cmp(f'{k}.B{q}.rec', float((s[tp] >= thr2).sum() / tp.sum()), d[k]['B'][q]['test_recall'])
                cmp(f'{k}.B{q}.fpr', float((s[tn] >= thr2).sum() / tn.sum()), d[k]['B'][q]['test_fpr'])
            loc = {r: i for i, r in enumerate(rows.tolist())}
            for kind in ('D', 'PO'):
                lab, sc = [], []
                for r in cone_rows:
                    if r['split'] != 'test' or r['kind'] != kind or int(r['label']) < 0: continue
                    mem = [loc[int(q)] for q in r['phys_rows'].split('|') if q and int(q) in loc]
                    mem = [q for q in mem if tr[q] and ph[q]]
                    if len(mem) < 2: continue
                    lab.append(int(r['label'])); sc.append(float(max(s[q] for q in mem)))
                lab = np.array(lab); sc = np.array(sc)
                cmp(f'{k}.mil.{kind}', (float(average_precision_score(lab, sc)) if len(np.unique(lab)) > 1 else None), d[k]['mil'][kind]['ap'])
sa = dict(status='PASS' if not issues else 'PARTIAL', checked=ok, mismatches=issues,
          note='self-audit, not independent; four_group A assets (502/11187); val_common thresholds')
(OUT / 'SELF_AUDIT_LCONE_V3.json').write_text(json.dumps(sa, indent=2), encoding='utf-8')
# I aggregation
agg = {}
for point in ('best', 'last'):
    for arm in ('NC1', 'NC01'):
        for fam in ('base', 'add'):
            ds = [d[f'{seed}_{arm}_{point}'][f'{fam}_ap'] - d[f'{seed}_N_{point}'][f'{fam}_ap'] for seed in (42, 1, 2)]
            agg[f'{arm}_{point}_{fam}'] = dict(vals=ds, mean=st.mean(ds), sd=st.stdev(ds), pos=sum(1 for x in ds if x > 0))
(OUT / 'LCONE_INTERACTION_V3.json').write_text(json.dumps(agg, indent=2), encoding='utf-8')
print(json.dumps(dict(status=sa['status'], checked=ok, bad=len(issues), corr=len(corr), agg=agg), ensure_ascii=False)[:1400])
