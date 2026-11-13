"""Self-audit: independent recomputation from saved predictions vs FOUR_EVAL_V3.json."""
import json, statistics as st
from pathlib import Path
import numpy as np

R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = R / '_p0pilot/four_group_contract_20261109'
BASE = ('ys_abc', 'ys_id', 'ys_opt'); ADD = ('ys_aig', 'ys_nand')
d = json.loads((OUT / 'FOUR_EVAL_V3.json').read_text(encoding='utf-8'))
issues = []; ok = []
# 1) A fields and two alarm scopes
for k, v in d.items():
    if 'A' not in v or not all('test_recall' in x and 'test_fpr' in x for x in v['A'].values()):
        issues.append(f'{k}: A fields incomplete')
    if v.get('alarm_trusted') is None or v.get('alarm_allphys') is None:
        issues.append(f'{k}: alarm scope missing')
    if v.get('strict_base') is None or v.get('strict_add') is None:
        issues.append(f'{k}: strict sets missing')
if not any('A fields' in x for x in issues): ok.append('A transfer fields present for 24 states')
if not any('alarm scope' in x for x in issues): ok.append('two view-alarm scopes present')
if not any('strict sets' in x for x in issues): ok.append('strict base/add sets present')
# 2) macro recompute from source_recipe
for k, v in d.items():
    mat = v['source_recipe']
    def macro(fam):
        rec = []
        for r in fam:
            vals = [sr[r] for sr in mat.values() if r in sr]
            if vals: rec.append(float(np.mean(vals)))
        return float(np.mean(rec)) if rec else None
    if macro(BASE) is not None and abs(macro(BASE) - v['base_ap']) > 1e-9:
        issues.append(f'{k}: base macro mismatch')
    if macro(ADD) is not None and abs(macro(ADD) - v['add_ap']) > 1e-9:
        issues.append(f'{k}: add macro mismatch')
if not any('macro mismatch' in x for x in issues): ok.append('base/add macro recomputed (source-internal then recipe macro)')
# 3) thresholds from val_common predictions
vv = np.load(OUT / 'val_common.npz'); vp = vv['trusted'] & (vv['y'] == 1)
for seed in (42, 1, 2):
    for tag in ('A', 'B'):
        for arm in ('N', 'NC'):
            base = OUT / (f'run_{tag}_{arm}' if seed == 42 else f'run_{tag}_{arm}_s{seed}')
            sv = np.load(base / 'best_pred.npz')['val']
            for q in ('0.8', '0.95'):
                need = int(np.ceil(float(q) * vp.sum())); thr = float(np.sort(sv[vp])[::-1][need - 1])
                if abs(thr - d[f'{seed}_{tag}_{arm}_best']['A'][q]['threshold']) > 1e-9:
                    issues.append(f'{seed}_{tag}_{arm}: threshold mismatch {q}')
if not any('threshold mismatch' in x for x in issues): ok.append('A thresholds recomputed from val_common')
# 4) interactions
inter = {}
for point in ('best', 'last'):
    b = []; a = []
    for seed in (42, 1, 2):
        b0 = d[f'{seed}_B_N_{point}']['base_ap']; b1 = d[f'{seed}_B_NC_{point}']['base_ap']
        a0 = d[f'{seed}_A_N_{point}']['base_ap']; a1 = d[f'{seed}_A_NC_{point}']['base_ap']
        b.append((b1 - b0) - (a1 - a0))
        a0 = d[f'{seed}_A_N_{point}']['add_ap']; a1 = d[f'{seed}_A_NC_{point}']['add_ap']
        b0 = d[f'{seed}_B_N_{point}']['add_ap']; b1 = d[f'{seed}_B_NC_{point}']['add_ap']
        a.append((b1 - b0) - (a1 - a0))
    inter[point] = dict(base=b, base_mean=st.mean(b), base_sd=st.stdev(b),
                        add=a, add_mean=st.mean(a), add_sd=st.stdev(a))
out = dict(status='PASS' if not issues else 'PARTIAL', issues=issues, passed=ok,
           interactions=inter, note='self-audit; not independent audit')
(OUT / 'SELF_AUDIT_V3.json').write_text(json.dumps(out, indent=2), encoding='utf-8')
print(json.dumps(out, ensure_ascii=False)[:1500])
