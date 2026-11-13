"""Attribution per recipe/source for v2c and independent eval cones from unused cache cones."""
import csv, json
from pathlib import Path
import numpy as np
from sklearn.metrics import average_precision_score
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FG = R / '_p0pilot/four_group_contract_20261109'
O = R / '_p0pilot/lcone_v2c_20261110'; B = R / '_p0pilot/control_boundary_v3_20261104'
CACHE = R / '_p0pilot/seed42_supervised_prep_20261109/CONE_CACHE_V2.csv'
c = json.loads((B / 'input_contract.json').read_text(encoding='utf-8')); vs = {v['view']: v for v in c['shared_inputs']['trans_test']['views']}
def ap_from(npz):
    z = np.load(npz); s, rows, y, tr = z['scores'], z['rows'], z['y'], z['trusted']
    out = {}
    for v, lay in vs.items():
        a, b = np.searchsorted(rows, [lay['start'], lay['stop']])
        if len(np.unique(y[a:b][tr[a:b]])) > 1:
            out.setdefault(v.split('__ys_')[0], {}).setdefault(v.split('__')[-1], average_precision_score(y[a:b][tr[a:b]], s[a:b][tr[a:b]]))
    return out
sets = {}
for seed, d in ((42, 'run_B_N'), (1, 'run_B_N_s1'), (2, 'run_B_N_s2')):
    sets[('N', seed)] = ap_from(FG / d / 'best_testpred.npz')
for arm in ('base', 'all'):
    for seed in (42, 1, 2):
        sets[(arm, seed)] = ap_from(O / f'run_{arm}_s{seed}' / 'best_testpred.npz')
rows = []
for src in sorted({k for v in sets.values() for k in v}):
    for rec in ('ys_abc', 'ys_opt', 'ys_aig', 'ys_nand'):
        vals = {}
        for key, d in sets.items():
            vals[key] = d.get(src, {}).get(rec)
        def mean(arm):
            xs = [vals[(arm, s)] for s in (42, 1, 2) if vals[(arm, s)] is not None]
            return float(np.mean(xs)) if xs else None
        n, b, a = mean('N'), mean('base'), mean('all')
        rows.append(dict(source=src, recipe=rec, N=n, base=b, all=a,
                         base_minus_N=(None if None in (n, b) else b - n),
                         all_minus_N=(None if None in (n, a) else a - n),
                         all_minus_base=(None if None in (b, a) else a - b)))
(O / 'LCONE_V2C_ATTRIBUTION.csv').write_text('')
with (O / 'LCONE_V2C_ATTRIBUTION.csv').open('w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
(O / 'LCONE_V2C_ATTRIBUTION.json').write_text(json.dumps(dict(rows=rows, nand_note='nand has only 2 training cones -> not_evaluable for attribution'), indent=2), encoding='utf-8')
# independent eval cones: cache cones not selected into v2c base/all (leftover after first n)
g = np.load(FG / 'group_B.npz'); o2n, tr, ph = g['old2new'], g['trusted'], g['physical']
by = {}
for r in csv.DictReader(CACHE.open(encoding='utf-8-sig', newline='')):
    if r['split'] != 'train' or r['kind'] not in ('D', 'PO') or int(r['label']) < 0 or int(r['n_phys']) < 2: continue
    rec = r['view'].split('__')[-1]
    old = np.array([int(x) for x in r['phys_rows'].split('|') if x], np.int64)
    loc = o2n[old]; loc = loc[loc >= 0]; loc = loc[tr[loc] & ph[loc]]
    if len(loc) >= 2:
        by.setdefault((r['kind'], rec, int(r['label'])), []).append((r['view'], r['cone_id'], loc))
rep = {}
for kind in ('D', 'PO'):
    for rec in ('ys_abc', 'ys_id', 'ys_opt', 'ys_aig', 'ys_nand'):
        for lab in (1, 0):
            allc = by.get((kind, rec, lab), [])
            used = {'ys_abc': 200, 'ys_id': 199, 'ys_opt': 159, 'ys_aig': 127, 'ys_nand': 2} if kind == 'D' else {}
            nused = used.get(rec, 0) if lab == 1 else used.get(rec, 0)
            left = allc[nused:]
            rep[f'{kind}|{rec}|{lab}'] = dict(total=len(allc), used=nused, leftover=len(left),
                                              status='ok' if len(left) > 0 else 'not_evaluable')
(O / 'EVAL_CONE_REPORT.json').write_text(json.dumps(rep, indent=2), encoding='utf-8')
print(json.dumps(rep, indent=1)[:1000])
