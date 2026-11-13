"""Extra audit: Top-1/5, B need/recall/FPR, trusted/allphys view alarms for 24 hoco states."""
import json
from pathlib import Path
import numpy as np
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); OUT = R / '_p0pilot/heldout_composition_20261110'
B = R / '_p0pilot/control_boundary_v3_20261104'
c = json.loads((B / 'input_contract.json').read_text(encoding='utf-8'))
vs = {v['view']: v for v in c['shared_inputs']['trans_test']['views']}
y = np.load(B / 'inputs/trans_test/y.npy'); tr = np.load(B / 'inputs/trans_test/trusted.npy'); ph = np.load(B / 'inputs/trans_test/physical.npy')
d = json.loads((OUT / 'HOCO_EVAL_V2.json').read_text(encoding='utf-8'))
issues = []; ok = 0
def cmp(n, a, b, tol=1e-9):
    global ok
    if a is None and b is None: ok += 1; return
    if a is None or b is None or abs(a - b) > tol: issues.append(dict(field=n, got=a, saved=b)); return
    ok += 1
for seed in (42, 1, 2):
    for tag in ('A', 'B'):
        for arm in ('N', 'NC'):
            d0 = OUT / (f'run_{tag}_{arm}' if seed == 42 else f'run_{tag}_{arm}_s{seed}')
            for point in ('best', 'last'):
                z = np.load(d0 / f'{point}_testpred.npz'); s = z['scores']; rows = z['rows']
                k = f'{seed}_{tag}_{arm}_{point}'
                # top1/5
                for frac in (1, 5):
                    vals = []
                    for v, lay in vs.items():
                        a, b = np.searchsorted(rows, [lay['start'], lay['stop']]); tt = tr[a:b]; yy = y[a:b]; ss = s[a:b]
                        if tt.sum() < 2: continue
                        order = np.lexsort((np.arange(b - a)[tt], -ss[tt])); pos = (yy[tt] == 1)[order]
                        kk = max(1, int(tt.sum() * frac / 100))
                        if pos.sum(): vals.append(float(pos[:kk].sum() / pos.sum()))
                    cmp(f'{k}.top{frac}', float(np.mean(vals)) if vals else None, d[k]['top'].get(f'top{frac}'))
                # B
                tp = tr & (y == 1); tn = tr & (y == 0)
                for q in ('0.8', '0.9', '0.95'):
                    need = int(np.ceil(float(q) * tp.sum())); thr = float(np.sort(s[tp])[::-1][need - 1])
                    rec = float((s[tp] >= thr).sum() / tp.sum()); fpr = float((s[tn] >= thr).sum() / tn.sum())
                    cmp(f'{k}.Brec.{q}', rec, d[k]['B'][q]['test_recall'])
                    cmp(f'{k}.Bfpr.{q}', fpr, d[k]['B'][q]['test_fpr'])
                # view alarms at saved A95 threshold
                thr = d[k]['A']['0.95']['threshold']; at = []; ap = []
                for v in [v for v in vs if 'ctl' in v]:
                    lay = vs[v]; a, b = np.searchsorted(rows, [lay['start'], lay['stop']])
                    tt = tr[a:b] & ph[a:b]; ss = s[a:b]; pn = ph[a:b] & (y[a:b] == 0)
                    if tt.any(): at.append(float(ss[tt].max() >= thr))
                    if pn.any(): ap.append(float(ss[pn].max() >= thr))
                cmp(f'{k}.alarmT', float(np.mean(at)) if at else None, d[k]['normal']['0.95']['trusted_view_alarm'])
                cmp(f'{k}.alarmP', float(np.mean(ap)) if ap else None, d[k]['normal']['0.95']['allphys_view_alarm'])
sa = json.loads((OUT / 'SELF_AUDIT_HOCO.json').read_text(encoding='utf-8'))
sa['extra_checked'] = ok; sa['extra_mismatches'] = issues
sa['status'] = 'PASS' if sa['status'] == 'PASS' and not issues else 'PARTIAL'
sa['note'] = 'self-audit, not independent; AP/macros/A95/normal nodes/I + Top1/5, B80-95, view alarms recomputed'
(OUT / 'SELF_AUDIT_HOCO.json').write_text(json.dumps(sa, indent=2), encoding='utf-8')
print(json.dumps(dict(ok=ok, bad=len(issues), status=sa['status'], first=issues[:2]), ensure_ascii=False)[:800])
