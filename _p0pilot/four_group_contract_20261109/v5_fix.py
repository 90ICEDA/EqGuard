"""V5 fixes: rename strict_evaluable, add 13-source/existence metadata, independent 26-row interaction recompute."""
import json
from pathlib import Path
import numpy as np
from sklearn.metrics import average_precision_score

R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = R / '_p0pilot/four_group_contract_20261109'
BASE = ('ys_abc', 'ys_id', 'ys_opt'); ADD = ('ys_aig', 'ys_nand')
c = json.loads((R / '_p0pilot/control_boundary_v3_20261104/input_contract.json').read_text(encoding='utf-8'))
vs = {v['view']: v for v in c['shared_inputs']['trans_test']['views']}
d = json.loads((OUT / 'FOUR_EVAL_V5.json').read_text(encoding='utf-8'))
runs = d['runs']
for k, v in runs.items():
    for old, new in (('strict_full_base', 'strict_evaluable_base'), ('strict_full_add', 'strict_evaluable_add')):
        if old in v:
            v[new] = v.pop(old)
    for fam, recs in (('base', BASE), ('add', ADD)):
        sets = [{x.split('__ys_')[0] for x in vs if x.split('__')[-1] == r} for r in recs]
        v[f'source_existence_{fam}'] = len(set.intersection(*sets))
    v['evaluable_note'] = 'test host has 13 sources; 5 trojan sources have positives; evaluable intersection base=4/add=5'
d['meta'] = dict(test_host_sources=13, trojan_sources=5, train_sources=66,
                 evaluable_base=4, evaluable_add=5, existence_base=12, existence_add=13)
# independent interaction recompute from scores
def ap_matrix(seed, tag, arm, point):
    base = OUT / (f'run_{tag}_{arm}' if seed == 42 else f'run_{tag}_{arm}_s{seed}')
    z = np.load(base / f'{point}_testpred.npz'); s, rows, y, t = z['scores'], z['rows'], z['y'], z['trusted']
    per = {}
    for v, lay in vs.items():
        a, b = np.searchsorted(rows, [lay['start'], lay['stop']])
        if len(np.unique(y[a:b][t[a:b]])) > 1:
            per.setdefault(v.split('__ys_')[0], {}).setdefault(v.split('__')[-1], []).append(
                average_precision_score(y[a:b][t[a:b]], s[a:b][t[a:b]]))
    return {k: {r: float(np.mean(x)) for r, x in v.items()} for k, v in per.items()}

ok = 0; bad = 0
inter = {}
for point in ('best', 'last'):
    rows_i = []
    for x in sorted({v.split('__ys_')[0] for v in vs}):
        for fam, recs in (('base', BASE), ('add', ADD)):
            def m(seed, tag, arm):
                mat = ap_matrix(seed, tag, arm, point).get(x, {})
                vals = [mat[r] for r in recs if r in mat]
                return float(np.mean(vals)) if vals else None
            a0, a1 = m(42, 'A', 'N'), m(42, 'A', 'NC')
            b0, b1 = m(42, 'B', 'N'), m(42, 'B', 'NC')
            row = dict(source=x, family=fam, point=point,
                       A_d=(None if a0 is None or a1 is None else a1 - a0),
                       B_d=(None if b0 is None or b1 is None else b1 - b0),
                       I=(None if None in (a0, a1, b0, b1) else (b1 - b0) - (a1 - a0)))
            rows_i.append(row)
    inter[point] = rows_i
# compare to saved
for point in ('best', 'last'):
    saved = {(r['source'], r['family']): r for r in d['source_interaction'][point]}
    for r in inter[point]:
        s = saved.get((r['source'], r['family']))
        if s is None:
            bad += 1; continue
        for key in ('A_d', 'B_d', 'I'):
            if (r[key] is None) != (s[key] is None) or (r[key] is not None and abs(r[key] - s[key]) > 1e-9):
                bad += 1; break
        else:
            ok += 1
d['source_interaction'] = inter
(OUT / 'FOUR_EVAL_V5_FIXED.json').write_text(json.dumps(d, indent=2), encoding='utf-8')
sa = json.loads((OUT / 'SELF_AUDIT_V5.json').read_text(encoding='utf-8'))
sa['interaction_rows_checked'] = ok; sa['interaction_mismatch'] = bad
sa['status'] = 'PASS' if sa.get('status') == 'PASS' and bad == 0 else 'PARTIAL'
sa['note'] = 'AP/recipe macro recomputed; 26 source-family rows per point independently recomputed'
(OUT / 'SELF_AUDIT_V5.json').write_text(json.dumps(sa, indent=2), encoding='utf-8')
print(json.dumps(dict(rows=ok, bad=bad, status=sa['status'])))
