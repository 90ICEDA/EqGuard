"""Extra L_cone audit: Top1/5, A80/90, normal80/90, B80/90/95."""
import json
from pathlib import Path
import numpy as np
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); OUT = R / '_p0pilot/heldout_composition_20261110'
FG = R / '_p0pilot/four_group_contract_20261109'; B = R / '_p0pilot/control_boundary_v3_20261104'
c = json.loads((B / 'input_contract.json').read_text(encoding='utf-8')); vs = {v['view']: v for v in c['shared_inputs']['trans_test']['views']}
y = np.load(B / 'inputs/trans_test/y.npy'); tr = np.load(B / 'inputs/trans_test/trusted.npy'); ph = np.load(B / 'inputs/trans_test/physical.npy')
val = np.load(FG / 'val_common.npz'); vp = val['trusted'] & (val['y'] == 1); vn = val['trusted'] & (val['y'] == 0)
import torch, sys; sys.path.insert(0, str(R / '_p0pilot/control_best200_20261104'))
from evaluate import Model
d = json.loads((OUT / 'LCONE_EVAL_V2.json').read_text(encoding='utf-8'))
issues = []; ok = 0
def cmp(n, a, b, tol=1e-9):
    global ok
    if a is None and b is None: ok += 1; return
    if a is None or b is None or abs(a - b) > tol: issues.append(dict(field=n, got=a, saved=b)); return
    ok += 1
for arm in ('N', 'NC1', 'NC01', 'C'):
    for point in ('best', 'last'):
        z = np.load(OUT / f'lcone_{arm}' / f'{point}_testpred.npz'); s = z['scores']; rows = z['rows']
        ck = torch.load(OUT / f'lcone_{arm}' / f'{point}_resume.pt', map_location='cuda', weights_only=False)
        model = Model().cuda(); model.load_state_dict(ck['model']); model.eval()
        vx = torch.as_tensor(val['x'], device='cuda'); ve = torch.as_tensor(val['edge'], device='cuda')
        with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
            lv = model(vx, ve).float(); sv = (lv[:, 1] - lv[:, 0]).cpu().numpy()
        k = f'{arm}_{point}'
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
        for q in ('0.8', '0.9'):
            need = int(np.ceil(float(q) * vp.sum())); thr = float(np.sort(sv[vp])[::-1][need - 1])
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
        for q in ('0.8', '0.9', '0.95'):
            need = int(np.ceil(float(q) * tp.sum())); thr = float(np.sort(s[tp])[::-1][need - 1])
            cmp(f'{k}.B{q}.rec', float((s[tp] >= thr).sum() / tp.sum()), d[k]['B'][q]['test_recall'])
            cmp(f'{k}.B{q}.fpr', float((s[tn] >= thr).sum() / tn.sum()), d[k]['B'][q]['test_fpr'])
sa = json.loads((OUT / 'SELF_AUDIT_LCONE.json').read_text(encoding='utf-8'))
sa['extra_checked'] = ok; sa['extra_mismatches'] = issues
sa['status'] = 'PASS' if sa['status'] == 'PASS' and not issues else 'PARTIAL'
sa['note'] = 'self-audit, not independent; AP/Top1-5/A80-95/B/normal/MIL recomputed; four_group A assets (502/11187)'
(OUT / 'SELF_AUDIT_LCONE.json').write_text(json.dumps(sa, indent=2), encoding='utf-8')
print(json.dumps(dict(ok=ok, bad=len(issues), status=sa['status'])))
