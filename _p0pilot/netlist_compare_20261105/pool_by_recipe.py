"""Equivalence-cone pool statistics excluding aig/nand recipes (read-only)."""
from pathlib import Path
import collections
import json
import statistics

ROOT = Path(__file__).resolve().parents[2]
J = ROOT / '_p0pilot/cec_joint_expand_20261105'

pairs = json.loads((J / 'final_pairs.json').read_text(encoding='utf-8'))
cones = {c['cone_id']: c for c in json.loads((J / 'final_cones.json').read_text(encoding='utf-8'))}

def recipe(pid):
    p = byid[pid]
    a, b = cones[p['left_cone']]['view'].split('__')[-1], cones[p['right_cone']]['view'].split('__')[-1]
    return '|'.join(sorted([a, b]))

byid = {p['pair_id']: p for p in pairs}

def role(s):
    return 'a4trojan' if 'a4trojan' in s else ('injection' if '__inj' in s else 'control')

rows = collections.defaultdict(lambda: dict(pairs=0, sources=set(), sizes=[], diffs=[]))
for p in pairs:
    r = recipe(p['pair_id'])
    key = (p['split'], r)
    d = rows[key]
    d['pairs'] += 1
    d['sources'].add(p['source_object'])
    la, ra = len(cones[p['left_cone']]['graph_rows']), len(cones[p['right_cone']]['graph_rows'])
    d['sizes'] += [la, ra]
    d['diffs'].append(abs(la - ra))

out = []
for (split, r), d in sorted(rows.items()):
    aig = ('aig' in r) or ('nand' in r)
    out.append(dict(split=split, recipe=r, pairs=d['pairs'], sources=len(d['sources']),
                    median_cone=int(statistics.median(d['sizes'])),
                    mean_cone=round(statistics.mean(d['sizes']), 1),
                    median_abs_size_diff=round(statistics.median(d['diffs']), 1),
                    excluded_by_default=bool(aig)))

print(json.dumps(out, ensure_ascii=False, indent=1))
(Path(__file__).resolve().parent / 'pool_by_recipe.json').write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')

# keep-only summary
keep = [r for r in out if not r['excluded_by_default']]
print('\nKEEP (no aig/nand):')
for r in keep:
    print(r['split'], r['recipe'], 'pairs', r['pairs'], 'sources', r['sources'],
          'median_cone', r['median_cone'], 'median_size_diff', r['median_abs_size_diff'])
tot = collections.Counter()
for r in keep:
    tot[r['split']] += r['pairs']
print('totals', dict(tot))
