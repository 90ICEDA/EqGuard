"""Per-recipe AP comparison from saved per-view CSVs (B vs B+k4)."""
import csv
from collections import defaultdict
from pathlib import Path

H = Path(r'_p0pilot/p2b_main_20261031')


def load(runroot, seed, arm, split='test'):
    p = H / runroot / f'seed{seed}' / arm / f'{split}_per_view.csv'
    if not p.exists():
        return []
    with p.open(encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def recipe(view):
    return view.split('__ys_')[-1] if '__ys_' in view else view.split('__')[-1]


def agg(rows):
    d = defaultdict(list)
    for r in rows:
        if r['scope'] != 'trusted' or not r['ap']:
            continue
        if '__inj' not in r['view']:
            continue
        d[recipe(r['view'])].append(float(r['ap']))
    return {k: sum(v) / len(v) for k, v in d.items()}


out = {}
for tag, root in (('B', 'runs_oldmask'), ('B+k4', 'runs_oldmask_k4'), ('A', 'runs_oldmask'), ('A+k4', 'runs_oldmask_k4')):
    arm = tag.split('+')[0]
    per = defaultdict(list)
    for s in (42, 1, 2):
        a = agg(load(root, s, arm))
        for k, v in a.items():
            per[k].append(v)
    out[tag] = {k: sum(v) / len(v) for k, v in per.items()}

recipes = sorted(set().union(*[set(v) for v in out.values()]))
print('recipe   A       A+k4    dA      B       B+k4    dB')
for r in recipes:
    a = out['A'].get(r); ak = out['A+k4'].get(r); b = out['B'].get(r); bk = out['B+k4'].get(r)
    f = lambda x: f'{x:.4f}' if x is not None else '  -   '
    da = f'{ak-a:+.4f}' if a is not None and ak is not None else '  -   '
    db = f'{bk-b:+.4f}' if b is not None and bk is not None else '  -   '
    print(f'{r:6s} {f(a)} {f(ak)} {da}  {f(b)} {f(bk)} {db}')
