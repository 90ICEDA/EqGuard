"""Aggregate 3-seed I, independent self-audit, checkpoint correction."""
import hashlib, json, statistics as st
from pathlib import Path
import numpy as np
from sklearn.metrics import average_precision_score
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); OUT = R / '_p0pilot/heldout_composition_20261110'
BASE = ('ys_abc', 'ys_id', 'ys_opt'); ADD = ('ys_aig', 'ys_nand')
d = json.loads((OUT / 'HOCO_EVAL_V2.json').read_text(encoding='utf-8'))
c = json.loads((R / '_p0pilot/control_boundary_v3_20261104/input_contract.json').read_text(encoding='utf-8'))
vs = {v['view']: v for v in c['shared_inputs']['trans_test']['views']}
# interactions
inter = {}
for point in ('best', 'last'):
    b = []; a = []
    for seed in (42, 1, 2):
        b0 = d[f'{seed}_B_N_{point}']['base_ap']; b1 = d[f'{seed}_B_NC_{point}']['base_ap']
        a0 = d[f'{seed}_A_N_{point}']['base_ap']; a1 = d[f'{seed}_A_NC_{point}']['base_ap']
        b.append((b1 - b0) - (a1 - a0))
        b0 = d[f'{seed}_B_N_{point}']['add_ap']; b1 = d[f'{seed}_B_NC_{point}']['add_ap']
        a0 = d[f'{seed}_A_N_{point}']['add_ap']; a1 = d[f'{seed}_A_NC_{point}']['add_ap']
        a.append((b1 - b0) - (a1 - a0))
    inter[point] = dict(base=b, base_mean=st.mean(b), base_sd=st.stdev(b),
                        add=a, add_mean=st.mean(a), add_sd=st.stdev(a))
# independent AP recompute
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
                mac = {r: float(np.mean(v)) for r, v in rec.items()}
                bb = float(np.mean([mac[r] for r in BASE if r in mac])); aa = float(np.mean([mac[r] for r in ADD if r in mac]))
                k = f'{seed}_{tag}_{arm}_{point}'
                if abs(bb - d[k]['base_ap']) > 1e-9 or abs(aa - d[k]['add_ap']) > 1e-9:
                    issues.append(k)
sa = dict(status='PASS' if not issues else 'PARTIAL', issues=issues,
          checked='per-recipe AP, base/add recipe macro, 24 states', note='not full A/B/FPR re-audit')
(OUT / 'SELF_AUDIT_HOCO.json').write_text(json.dumps(sa, indent=2), encoding='utf-8')
# checkpoint correction
corr = {}
for seed in (42, 1, 2):
    for tag in ('A', 'B'):
        for arm in ('N', 'NC'):
            d0 = OUT / (f'run_{tag}_{arm}' if seed == 42 else f'run_{tag}_{arm}_s{seed}')
            for point in ('best', 'last'):
                p = d0 / f'{point}_resume.pt'
                if not p.exists(): continue
                import torch
                ck = torch.load(p, map_location='cpu', weights_only=False)
                corr[str(p.relative_to(OUT))] = dict(fields=sorted(ck.keys()), best_step=ck.get('best_step'),
                                                    completed=ck.get('completed'),
                                                    has_optimizer=ck.get('optimizer') is not None,
                                                    resumable=(point == 'last'),
                                                    note=('best: model/opt at best step but RNG saved at 200 -> inference only'
                                                          if point == 'best' else 'last: model/opt/completed/RNG same final step'))
(OUT / 'CORRECTION_CHECKPOINTS.json').write_text(json.dumps(corr, indent=2), encoding='utf-8')
(OUT / 'INTERACTION_3SEED.json').write_text(json.dumps(inter, indent=2), encoding='utf-8')
print(json.dumps(dict(inter=inter, audit=sa['status'], issues=len(issues), ckpts=len(corr)), ensure_ascii=False)[:1400])
