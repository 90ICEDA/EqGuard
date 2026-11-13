"""L_cone checkpoint correction + independent self-audit of LCONE_EVAL_V2."""
import csv, json
from pathlib import Path
import numpy as np, torch
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); OUT = R / '_p0pilot/heldout_composition_20261110'
FG = R / '_p0pilot/four_group_contract_20261109'; B = R / '_p0pilot/control_boundary_v3_20261104'
OLD = R / '_p0pilot/seed42_nc_ablation_20261109'
from sklearn.metrics import average_precision_score
d = json.loads((OUT / 'LCONE_EVAL_V2.json').read_text(encoding='utf-8'))
corr = {}
for arm in ('N', 'NC1', 'NC01', 'C'):
    for point in ('best', 'last'):
        p = OUT / f'lcone_{arm}' / f'{point}_resume.pt'
        ck = torch.load(p, map_location='cpu', weights_only=False)
        corr[f'lcone_{arm}/{point}_resume.pt'] = dict(fields=sorted(ck.keys()), best_step=ck.get('best_step'),
                                                     completed=ck.get('completed'), has_optimizer=ck.get('optimizer') is not None,
                                                     resumable=(point == 'last'),
                                                     note=('best: model/opt at best step; RNG/completed at 200 -> inference only' if point == 'best'
                                                           else 'last: model/opt/completed/RNG final step; optimizer step consistent'))
(OUT / 'CORRECTION_LCONE.json').write_text(json.dumps(corr, indent=2), encoding='utf-8')
# independent audit
c = json.loads((B / 'input_contract.json').read_text(encoding='utf-8')); vs = {v['view']: v for v in c['shared_inputs']['trans_test']['views']}
f = B / 'inputs/trans_test'; y = np.load(f / 'y.npy'); tr = np.load(f / 'trusted.npy'); ph = np.load(f / 'physical.npy')
rows_all = np.concatenate([np.arange(vs[v]['start'], vs[v]['stop']) for v in vs])
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
for arm in ('N', 'NC1', 'NC01', 'C'):
    for point in ('best', 'last'):
        d0 = OUT / f'lcone_{arm}'
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
        ap = {r: float(np.mean(v)) for r, v in ap.items()}; k = f'{arm}_{point}'
        for r, v in ap.items(): cmp(f'{k}.ap.{r}', v, d[k]['ap'].get(r))
        cmp(f'{k}.base', float(np.mean([ap[r] for r in ('ys_abc', 'ys_id', 'ys_opt') if r in ap])), d[k]['base_ap'])
        cmp(f'{k}.add', float(np.mean([ap[r] for r in ('ys_aig', 'ys_nand') if r in ap])), d[k]['add_ap'])
        tp = tr & (y == 1); tn = tr & (y == 0)
        for q in ('0.95',):
            need = int(np.ceil(float(q) * vp.sum())); thr = float(np.sort(sv[vp])[::-1][need - 1])
            cmp(f'{k}.A.{q}.thr', thr, d[k]['A'][q]['threshold'])
            cmp(f'{k}.A.{q}.rec', float((s[tp] >= thr).sum() / tp.sum()), d[k]['A'][q]['test_recall'])
            cmp(f'{k}.A.{q}.fpr', float((s[tn] >= thr).sum() / tn.sum()), d[k]['A'][q]['test_fpr'])
        # normal trusted/allphys node fpr at A95
        thr = d[k]['A']['0.95']['threshold']; num = den = an = ad = 0
        for v in [z2 for z2 in vs if 'ctl' in z2]:
            lay = vs[v]; a, b = np.searchsorted(rows, [lay['start'], lay['stop']])
            tt = tr[a:b] & ph[a:b]; yy = y[a:b]; ss = s[a:b]
            if tt.any():
                neg = tt & (yy == 0); num += int((ss[neg] >= thr).sum()); den += int(neg.sum())
            pn = ph[a:b] & (yy == 0); an += int((ss[pn] >= thr).sum()); ad += int(pn.sum())
        cmp(f'{k}.normal.trusted', num / max(1, den), d[k]['normal']['0.95']['trusted_node_fpr'])
        cmp(f'{k}.normal.allphys', an / max(1, ad), d[k]['normal']['0.95']['allphys_node_fpr'])
        # MIL D
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
            apm = float(average_precision_score(lab, sc)) if len(np.unique(lab)) > 1 else None
            cmp(f'{k}.mil.{kind}', apm, d[k]['mil'][kind]['ap'])
sa = dict(status='PASS' if not issues else 'PARTIAL', checked=ok, mismatches=issues,
          note='self-audit, not independent; L_cone used four_group A assets (502 positives, 11187 cones), not hoco_A (287/10742)')
(OUT / 'SELF_AUDIT_LCONE.json').write_text(json.dumps(sa, indent=2), encoding='utf-8')
print(json.dumps(dict(status=sa['status'], checked=ok, bad=len(issues), first=issues[:3]), ensure_ascii=False)[:1000])
