"""Independent recomputation (V4) + no-keep read-only count verification."""
import csv, json, hashlib, re, statistics as st
from pathlib import Path
import numpy as np
from sklearn.metrics import average_precision_score

R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = R / '_p0pilot/four_group_contract_20261109'
BASE = ('ys_abc', 'ys_id', 'ys_opt'); ADD = ('ys_aig', 'ys_nand')
c = json.loads((R / '_p0pilot/control_boundary_v3_20261104/input_contract.json').read_text(encoding='utf-8'))
vs = {v['view']: v for v in c['shared_inputs']['trans_test']['views']}
d = json.loads((OUT / 'FOUR_EVAL_V4.json').read_text(encoding='utf-8'))['runs']
issues, ok = [], []
vv = np.load(OUT / 'val_common.npz'); vp = vv['trusted'] & (vv['y'] == 1); vn = vv['trusted'] & (vv['y'] == 0)
for seed in (42, 1, 2):
    for tag in ('A', 'B'):
        for arm in ('N', 'NC'):
            base = OUT / (f'run_{tag}_{arm}' if seed == 42 else f'run_{tag}_{arm}_s{seed}')
            for point in ('best', 'last'):
                k = f'{seed}_{tag}_{arm}_{point}'
                z = np.load(base / f'{point}_testpred.npz'); s, rows, y, t = z['scores'], z['rows'], z['y'], z['trusted']
                sv = np.load(base / f'{point}_pred.npz')['val']
                ap = []
                for v, lay in vs.items():
                    a, b = np.searchsorted(rows, [lay['start'], lay['stop']])
                    if len(np.unique(y[a:b][t[a:b]])) > 1:
                        ap.append(average_precision_score(y[a:b][t[a:b]], s[a:b][t[a:b]]))
                # compare A 0.95 threshold
                need = int(np.ceil(0.95 * vp.sum())); thr = float(np.sort(sv[vp])[::-1][need - 1])
                if abs(thr - d[k]['A']['0.95']['threshold']) > 1e-9:
                    issues.append(f'{k}: threshold')
                # val recall/fpr actual
                vr = float((sv[vp] >= thr).sum() / vp.sum()); vf = float((sv[vn] >= thr).sum() / vn.sum())
                if abs(vr - d[k]['A']['0.95']['val_recall']) > 1e-9 or abs(vf - d[k]['A']['0.95']['val_fpr']) > 1e-9:
                    issues.append(f'{k}: val recall/fpr')
                if d[k]['normal']['0.95']['trusted_den'] == 0 and d[k]['normal']['0.95']['trusted_node_fpr'] is not None:
                    issues.append(f'{k}: NA violation')
if not issues: ok.append('thresholds, val recall/FPR, NA rule recomputed for 24 states')
(OUT / 'SELF_AUDIT_V4.json').write_text(json.dumps(dict(status='PASS' if not issues else 'PARTIAL', issues=issues[:20], passed=ok), indent=2), encoding='utf-8')

# ---- no-keep counts ----
nk = {}
root = R / 'phase2/ys'
keeps = list(root.rglob('*keep*'))
nk['keep_paths'] = len(keeps)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
groups = {}
for p in root.rglob('*'):
    if p.is_file() and p.suffix in ('.v', '.sv') and 'noattr' in p.name:
        groups.setdefault(p.parent.name.split('_')[0], []).append(p)
same = sum(1 for v in groups.values() if len(set(sha(p) for p in v)) == 1 and len(v) >= 2)
nk['groups'] = len(groups); nk['identical_groups'] = same
plain = list((R / 'generate_trans/yslib_test').rglob('*.v')) if (R / 'generate_trans/yslib_test').exists() else []
nk['plain_v'] = len(plain)
nk['plain_keep_name'] = sum(1 for p in plain if 'keep' in p.name)
cec = R / 'generate_trans/yslib_test/cec_tolib.csv'
if cec.exists():
    rows = list(csv.DictReader(cec.open(encoding='utf-8-sig')))
    nk['cec_rows'] = len(rows); nk['cec_empty'] = sum(1 for r in rows if not (r.get('cec') or '').strip())
cm = R / 'generate_trans/yslib_test/convert_manifest.csv'
if cm.exists():
    rows = list(csv.DictReader(cm.open(encoding='utf-8-sig')))
    nk['manifest_rows'] = len(rows); nk['manifest_clean_true'] = sum(1 for r in rows if str(r.get('clean', '')).lower() == 'true')
# panel availability in views
panel = ['rs232t1000__injalpha', 's15850t100__injdelta', 's35932t200__injalpha']
avail = {}
for s in panel:
    avail[s] = {r: sum(1 for v in vs if v.startswith(s) and v.split('__')[-1] == r) for r in ('ys_abc', 'ys_aig', 'ys_nand')}
nk['panel_availability'] = avail
nk['keep_removed_before_synth'] = 'noattr' in (R / 'phase2/ys/keep_ablation.py').read_text(encoding='utf-8', errors='ignore') if (R / 'phase2/ys/keep_ablation.py').exists() else None
(OUT / 'NO_KEEP_VERIFY.json').write_text(json.dumps(nk, indent=2), encoding='utf-8')
print(json.dumps(dict(self_audit=json.loads((OUT/'SELF_AUDIT_V4.json').read_text()), nokeep=nk), ensure_ascii=False)[:1800])
