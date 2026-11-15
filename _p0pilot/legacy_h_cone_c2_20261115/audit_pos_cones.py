"""Audit nand/aig positive-D cone member composition and sharing."""
import sys
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np
import pandas as pd

RUN = Path(__file__).resolve().parent.parent / 'legacy_h_cone_20261115'
sys.path.insert(0, str(RUN))
import run

OUT = Path(__file__).resolve().parent
mod, _ = run.configure(42, cone=False)
CONE = run.load_module(run.CL, 'task_one_d_loss')
d = mod.T.arrays('trans', 'train')
raw = pd.read_csv(CONE.OUT / 'CONE_CACHE_V2.csv', low_memory=False)
raw = raw[(raw.split == 'train') & (raw.kind == 'D') & (raw.label.astype(int) >= 0) & (raw.n_phys.astype(int) >= 2)].copy()
raw['recipe'] = raw.view.str.extract(r'__(ys_[a-z]+)$')[0]
raw['members'] = raw.phys_rows.fillna('').map(lambda s: [int(x) for x in s.split('|') if x])
pos = raw[raw.label == 1]; neg = raw[raw.label == 0]

occ = Counter()
for mem in pos.members: occ.update(mem)
neg_occ = Counter()
for mem in neg.members: neg_occ.update(mem)

rows = []
for rec, g in pos.groupby('recipe'):
    n_members = shared = exclusive = ypos = yneg = yunk = trusted = physical = all_shared = no_pos_excl = 0
    for mem in g.members:
        n_members += len(mem)
        shared += sum(occ[x] >= 2 for x in mem)
        exclusive += sum(occ[x] == 1 for x in mem)
        ypos += sum(d['y'][x] == 1 for x in mem)
        yneg += sum(d['y'][x] == 0 for x in mem)
        yunk += sum(d['y'][x] < 0 for x in mem)
        trusted += sum(bool(d['trusted'][x]) for x in mem)
        physical += sum(bool(d['physical'][x]) for x in mem)
        all_shared += int(all(occ[x] >= 2 for x in mem))
        no_pos_excl += int(not any((d['y'][x] == 1) and occ[x] == 1 for x in mem))
    rows.append(dict(recipe=rec, cones=len(g), members=n_members, shared=shared, exclusive=exclusive,
        ypos=ypos, yneg=yneg, yunk=yunk, trusted=trusted, physical=physical,
        all_shared_cones=all_shared, no_pos_exclusive_cones=no_pos_excl,
        mean_members=n_members/len(g)))
out = pd.DataFrame(rows).sort_values('members', ascending=False)
OUT.joinpath('POS_CONE_COMPOSITION.csv').write_text(out.to_csv(index=False), encoding='utf-8')
print(out.to_string(index=False))

# top shared positive-cone members
top = []
for x, n in occ.most_common(50):
    top.append(dict(row=x, occ=n, y=int(d['y'][x]), trusted=bool(d['trusted'][x]), physical=bool(d['physical'][x]),
                    in_negative_cone=int(neg_occ.get(x, 0))))
OUT.joinpath('TOP_SHARED.csv').write_text(pd.DataFrame(top).to_csv(index=False), encoding='utf-8')
print('\nTOP SHARED')
print(pd.DataFrame(top).head(20).to_string(index=False))
