"""Read-only: root-positive pairs after excluding aig/nand and filtering by cone size."""
import collections
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
J = ROOT / '_p0pilot/cec_joint_expand_20261105'
ACT = ROOT / '_p0pilot/cec_actual_functions_seed42_20261105'

pairs = json.loads((J / 'final_pairs.json').read_text(encoding='utf-8'))
cones = {c['cone_id']: c for c in json.loads((J / 'final_cones.json').read_text(encoding='utf-8'))}
byid = {p['pair_id']: p for p in pairs}
rows = list(csv.DictReader((ACT / 'actual_positive_functions_12.csv').open(encoding='utf-8-sig')))


def info(pid):
    p = byid[pid]
    lv, rv = p['left_cone'], p['right_cone']
    rec = '|'.join(sorted([cones[lv]['view'].split('__')[-1], cones[rv]['view'].split('__')[-1]]))
    m = min(len(cones[lv]['graph_rows']), len(cones[rv]['graph_rows']))
    return p['split'], rec, m


def keep_rec(rec):
    return ('aig' not in rec) and ('nand' not in rec)


print('root-positive pairs (12):')
cnt = collections.Counter(); cnt16 = collections.Counter(); by_rec = collections.Counter()
for r in rows:
    pid = r['pair_id']
    if pid not in byid:
        print(' missing', r['source'], r['left_view'])
        continue
    split, rec, m = info(pid)
    ok = keep_rec(rec)
    print(f" {r['source']:30s} {split:5s} {rec:14s} mincone={m:4d} keep={ok}")
    if ok:
        cnt[r['source']] += 1
        by_rec[rec] += 1
        if m >= 16:
            cnt16[r['source']] += 1
print('\nroot kept by source:', dict(cnt))
print('root kept mincone>=16:', dict(cnt16))
print('root kept by recipe:', dict(by_rec))

# support: all kept pairs (root + non-root) per source with min cone >=16
print('\nall kept pairs by source (mincone>=16):')
sup = collections.Counter()
for p in pairs:
    if p['split'] != 'train':
        continue
    lv, rv = p['left_cone'], p['right_cone']
    rec = '|'.join(sorted([cones[lv]['view'].split('__')[-1], cones[rv]['view'].split('__')[-1]]))
    if not keep_rec(rec):
        continue
    if min(len(cones[lv]['graph_rows']), len(cones[rv]['graph_rows'])) >= 16:
        sup[p['source_object']] += 1
for s, n in sorted(sup.items()):
    print(f' {s:32s} {n}')
print('total', sum(sup.values()))
