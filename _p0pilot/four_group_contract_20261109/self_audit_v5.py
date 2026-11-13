"""Independent full-AP recomputation from saved scores vs FOUR_EVAL_V5."""
import json
from pathlib import Path
import numpy as np
from sklearn.metrics import average_precision_score

R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = R / '_p0pilot/four_group_contract_20261109'
BASE = ('ys_abc', 'ys_id', 'ys_opt'); ADD = ('ys_aig', 'ys_nand')
c = json.loads((R / '_p0pilot/control_boundary_v3_20261104/input_contract.json').read_text(encoding='utf-8'))
vs = {v['view']: v for v in c['shared_inputs']['trans_test']['views']}
d = json.loads((OUT / 'FOUR_EVAL_V5.json').read_text(encoding='utf-8'))['runs']
issues = []
for seed in (42, 1, 2):
    for tag in ('A', 'B'):
        for arm in ('N', 'NC'):
            base = OUT / (f'run_{tag}_{arm}' if seed == 42 else f'run_{tag}_{arm}_s{seed}')
            for point in ('best', 'last'):
                z = np.load(base / f'{point}_testpred.npz'); s, rows, y, t = z['scores'], z['rows'], z['y'], z['trusted']
                rec = {}
                for v, lay in vs.items():
                    a, b = np.searchsorted(rows, [lay['start'], lay['stop']])
                    if len(np.unique(y[a:b][t[a:b]])) > 1:
                        rec.setdefault(v.split('__')[-1], []).append(average_precision_score(y[a:b][t[a:b]], s[a:b][t[a:b]]))
                macro = {r: float(np.mean(v)) for r, v in rec.items()}
                b = float(np.mean([macro[r] for r in BASE if r in macro])); a = float(np.mean([macro[r] for r in ADD if r in macro]))
                k = f'{seed}_{tag}_{arm}_{point}'
                if abs(b - d[k]['base_ap']) > 1e-9 or abs(a - d[k]['add_ap']) > 1e-9:
                    issues.append(k)
out = dict(status='PASS' if not issues else 'PARTIAL', issues=issues,
           note='independent recomputation of per-view AP and recipe macro; not full interaction audit')
(OUT / 'SELF_AUDIT_V5.json').write_text(json.dumps(out, indent=2), encoding='utf-8')
print(json.dumps(out))
