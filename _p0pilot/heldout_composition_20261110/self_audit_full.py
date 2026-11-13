"""Full hoco self-audit: recompute all metrics from predictions; update SELF_AUDIT & checkpoint correction."""
import json
from pathlib import Path
import numpy as np, torch
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); OUT = R / '_p0pilot/heldout_composition_20261110'
B = R / '_p0pilot/control_boundary_v3_20261104'
import sys; sys.path.insert(0, str(R / '_p0pilot/control_best200_20261104'))
from evaluate import Model
from sklearn.metrics import average_precision_score
BASE = ('ys_abc', 'ys_id', 'ys_opt'); ADD = ('ys_aig', 'ys_nand')
c = json.loads((B / 'input_contract.json').read_text(encoding='utf-8'))
vs = {v['view']: v for v in c['shared_inputs']['trans_test']['views']}
f = B / 'inputs/trans_test'
y = np.load(f / 'y.npy'); tr = np.load(f / 'trusted.npy'); ph = np.load(f / 'physical.npy')
rows_test = np.concatenate([np.arange(vs[v]['start'], vs[v]['stop']) for v in vs])
val = np.load(OUT / 'hoco_val.npz'); mean, std = val['mean'], val['std']
vx = torch.as_tensor(val['x'], device='cuda'); ve = torch.as_tensor(val['edge'], device='cuda')
vp = val['trusted'] & (val['y'] == 1); vn = val['trusted'] & (val['y'] == 0)
d = json.loads((OUT / 'HOCO_EVAL_V2.json').read_text(encoding='utf-8'))
inter_saved = json.loads((OUT / 'INTERACTION_3SEED.json').read_text(encoding='utf-8'))
issues = []; ok = 0
def cmp(name, a, b, tol=1e-9):
    global ok
    if a is None and b is None: ok += 1; return
    if a is None or b is None or abs(a - b) > tol:
        issues.append(dict(field=name, got=a, saved=b)); return
    ok += 1
for seed in (42, 1, 2):
    for tag in ('A', 'B'):
        for arm in ('N', 'NC'):
            d0 = OUT / (f'run_{tag}_{arm}' if seed == 42 else f'run_{tag}_{arm}_s{seed}')
            for point in ('best', 'last'):
                ck = torch.load(d0 / f'{point}_resume.pt', map_location='cuda', weights_only=False)
                model = Model().cuda(); model.load_state_dict(ck['model']); model.eval()
                z = np.load(d0 / f'{point}_testpred.npz'); s = z['scores']; rows = z['rows']
                with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
                    lv = model(vx, ve).float(); sv = (lv[:, 1] - lv[:, 0]).cpu().numpy()
                k = f'{seed}_{tag}_{arm}_{point}'
                apv = {}
                for v, lay in vs.items():
                    a, b = np.searchsorted(rows, [lay['start'], lay['stop']])
                    if len(np.unique(y[a:b][tr[a:b]])) > 1:
                        apv.setdefault(v.split('__')[-1], []).append(average_precision_score(y[a:b][tr[a:b]], s[a:b][tr[a:b]]))
                ap = {r: float(np.mean(v)) for r, v in apv.items()}
                for r, v in ap.items(): cmp(f'{k}.ap.{r}', v, d[k]['ap'].get(r))
                cmp(f'{k}.base', float(np.mean([ap[r] for r in BASE if r in ap])), d[k]['base_ap'])
                cmp(f'{k}.add', float(np.mean([ap[r] for r in ADD if r in ap])), d[k]['add_ap'])
                tp = tr & (y == 1); tn = tr & (y == 0)
                thr = d[k]['A']['0.95']['threshold']
                # recompute threshold from val scores
                need = int(np.ceil(0.95 * vp.sum())); thr2 = float(np.sort(sv[vp])[::-1][need - 1])
                cmp(f'{k}.thr95', thr2, thr)
                cmp(f'{k}.val_recall', float((sv[vp] >= thr2).sum() / vp.sum()), d[k]['A']['0.95']['val_recall'])
                cmp(f'{k}.val_fpr', float((sv[vn] >= thr2).sum() / vn.sum()), d[k]['A']['0.95']['val_fpr'])
                cmp(f'{k}.test_recall', float((s[tp] >= thr2).sum() / tp.sum()), d[k]['A']['0.95']['test_recall'])
                cmp(f'{k}.test_fpr', float((s[tn] >= thr2).sum() / tn.sum()), d[k]['A']['0.95']['test_fpr'])
                # normal trusted/allphys node fpr
                num = den = an = ad = 0
                for v in [v for v in vs if 'ctl' in v]:
                    lay = vs[v]; a, b = np.searchsorted(rows, [lay['start'], lay['stop']])
                    tt = tr[a:b] & ph[a:b]; yy = y[a:b]; ss = s[a:b]
                    if tt.any():
                        neg = tt & (yy == 0); num += int((ss[neg] >= thr2).sum()); den += int(neg.sum())
                    pn = ph[a:b] & (yy == 0); an += int((ss[pn] >= thr2).sum()); ad += int(pn.sum())
                cmp(f'{k}.trusted_fpr', num / max(1, den), d[k]['normal']['0.95']['trusted_node_fpr'])
                cmp(f'{k}.allphys_fpr', an / max(1, ad), d[k]['normal']['0.95']['allphys_node_fpr'])
# interaction recompute
for point in ('best', 'last'):
    bs = inter_saved[point]['base']; ad = inter_saved[point]['add']
    for i, seed in enumerate((42, 1, 2)):
        b = (d[f'{seed}_B_NC_{point}']['base_ap'] - d[f'{seed}_B_N_{point}']['base_ap']) - (d[f'{seed}_A_NC_{point}']['base_ap'] - d[f'{seed}_A_N_{point}']['base_ap'])
        a = (d[f'{seed}_B_NC_{point}']['add_ap'] - d[f'{seed}_B_N_{point}']['add_ap']) - (d[f'{seed}_A_NC_{point}']['add_ap'] - d[f'{seed}_A_N_{point}']['add_ap'])
        cmp(f'I.{point}.base.{seed}', b, bs[i]); cmp(f'I.{point}.add.{seed}', a, ad[i])
sa = dict(status='PASS' if not issues else 'PARTIAL', checked_fields=ok, mismatches=issues,
          note='self-audit, not independent; AP/Top? normal/A/B/I recomputed for 24 states')
(OUT / 'SELF_AUDIT_HOCO.json').write_text(json.dumps(sa, indent=2), encoding='utf-8')
# checkpoint correction: best_step from LOG for seed42 best
cc = json.loads((OUT / 'CORRECTION_CHECKPOINTS.json').read_text(encoding='utf-8'))
for k, v in cc.items():
    d0 = OUT / Path(k).parent
    if 'best' in Path(k).name:
        lg = json.loads((d0 / 'LOG.json').read_text(encoding='utf-8'))
        v['best_step_from_log'] = lg.get('best_step'); v['resumable'] = False
(OUT / 'CORRECTION_CHECKPOINTS.json').write_text(json.dumps(cc, indent=2), encoding='utf-8')
print(json.dumps(dict(status=sa['status'], checked=ok, bad=len(issues), first=issues[:3]), ensure_ascii=False)[:1200])
