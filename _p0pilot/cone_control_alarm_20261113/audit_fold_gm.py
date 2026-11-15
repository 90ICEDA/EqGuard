"""Count which frozen v5 difficult-negative draws admit a verified M replacement."""
import csv
from collections import Counter
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent
P = OUT.parent
with (P / 'control_budget_bounded_20261105/M_fanout_pair_audit.csv').open(
        encoding='utf-8-sig', newline='') as f:
    pairs = [r for r in csv.DictReader(f) if r['domain'] == 'trans' and r['main_eligible'] == 'True']

rows = []
for fold in ('ys_abc', 'ys_aig', 'ys_nand'):
    with np.load(P / f'heldout_recipe_v4_20261109/{fold}_train_map.npz') as z:
        old2new, old_rows = z['old2new'], z['rows']
        h, common, y = z['h_pool'], z['common_pool'], z['y']
        trust, physical = z['trusted'], z['physical']
    present = [r for r in pairs if r['recipe'] != fold
               and old2new[int(r['H_row'])] >= 0 and old2new[int(r['normal_row'])] >= 0]
    usable = {}
    for pair in present:
        a, b = [int(old2new[int(pair[k])]) for k in ('H_row', 'normal_row')]
        assert y[a] == y[b] == 0 and trust[a] and trust[b] and physical[a] and physical[b]
        assert a not in usable
        usable[a] = b
    counts, frequencies = [], Counter()
    for step in range(200):
        rng = np.random.default_rng(42 + step)
        common_draw = set(rng.choice(common, 8192, replace=False))
        h_draw = set(rng.choice(h, 144, replace=False))
        m = {i: usable[i] for i in h_draw & usable.keys() if usable[i] not in (common_draw | h_draw)}
        assert len(m) == len(set(m.values()))
        frequencies.update(m.keys())
        counts.append(len(m))
    rows.append(dict(fold=fold, mapped_pairs=len(present), eligible_H_in_pool=len(set(h) & usable.keys()),
                     H_exposures_with_M=sum(counts), min_per_step=min(counts), max_per_step=max(counts),
                     steps_with_any=sum(x > 0 for x in counts), unique_H_used=len(frequencies)))
with (OUT / 'FOLD_GM_FEASIBILITY.csv').open('w', encoding='utf-8', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
print(rows)
