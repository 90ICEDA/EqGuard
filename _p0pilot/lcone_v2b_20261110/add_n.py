"""Add N-B arms from saved testpred and compute base/all vs N deltas."""
import json
from pathlib import Path
import numpy as np
from sklearn.metrics import average_precision_score
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FG = R / '_p0pilot/four_group_contract_20261109'
OUT = R / '_p0pilot/lcone_v2b_20261110'; B = R / '_p0pilot/control_boundary_v3_20261104'
BASE = ('ys_abc', 'ys_id', 'ys_opt'); ADD = ('ys_aig', 'ys_nand')
c = json.loads((B / 'input_contract.json').read_text(encoding='utf-8')); vs = {v['view']: v for v in c['shared_inputs']['trans_test']['views']}
res = json.loads((OUT / 'LCONE_V2B_RESULTS.json').read_text(encoding='utf-8'))
for seed, dname in ((42, 'run_B_N'), (1, 'run_B_N_s1'), (2, 'run_B_N_s2')):
    d0 = FG / dname
    for point in ('best', 'last'):
        z = np.load(d0 / f'{point}_testpred.npz'); s, rows, y, tr = z['scores'], z['rows'], z['y'], z['trusted']
        ap = {}
        for v, lay in vs.items():
            a, b = np.searchsorted(rows, [lay['start'], lay['stop']])
            if len(np.unique(y[a:b][tr[a:b]])) > 1:
                ap.setdefault(v.split('__')[-1], []).append(average_precision_score(y[a:b][tr[a:b]], s[a:b][tr[a:b]]))
        ap = {r: float(np.mean(v)) for r, v in ap.items()}
        res[f'N_{seed}_{point}'] = dict(ap=ap, base_ap=float(np.mean([ap[r] for r in BASE if r in ap])),
                                        add_ap=float(np.mean([ap[r] for r in ADD if r in ap])),
                                        source='reused four_group run_B_N')
(OUT / 'LCONE_V2B_RESULTS.json').write_text(json.dumps(res, indent=2), encoding='utf-8')
# deltas per seed vs N
for point in ('best', 'last'):
    print(point)
    for arm in ('base', 'all'):
        db = [res[f'{arm}_{seed}_{point}']['base_ap'] - res[f'N_{seed}_{point}']['base_ap'] for seed in (42, 1, 2)]
        da = [res[f'{arm}_{seed}_{point}']['add_ap'] - res[f'N_{seed}_{point}']['add_ap'] for seed in (42, 1, 2)]
        print(arm, 'base', [round(x, 4) for x in db], 'add', [round(x, 4) for x in da])
