"""Phase0: D-cone availability per recipe in group_B from CONE_CACHE_V2."""
import csv, json
from pathlib import Path
import numpy as np
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FG = R / '_p0pilot/four_group_contract_20261109'
CACHE = R / '_p0pilot/seed42_supervised_prep_20261109/CONE_CACHE_V2.csv'
OUT = R / '_p0pilot/lcone_v2c_20261110'; OUT.mkdir(exist_ok=True)
g = np.load(FG / 'group_B.npz'); o2n, tr, ph = g['old2new'], g['trusted'], g['physical']
rows = list(csv.DictReader(CACHE.open(encoding='utf-8-sig', newline='')))
stat = {}
for r in rows:
    if r['split'] != 'train' or r['kind'] != 'D' or int(r['label']) < 0 or int(r['n_phys']) < 2: continue
    rec = r['view'].split('__')[-1]; s = stat.setdefault(rec, dict(pos=0, neg=0, mem=[], single=0, two=0, unknown=0))
    old = np.array([int(x) for x in r['phys_rows'].split('|') if x], np.int64)
    loc = o2n[old]; loc = loc[loc >= 0]
    ok = loc[tr[loc] & ph[loc]]
    if len(ok) < 2:
        if len(loc) < 2: s['single'] += 1
        else: s['unknown'] += 1
        continue
    if int(r['label']) == 1: s['pos'] += 1
    elif int(r['label']) == 0: s['neg'] += 1
    s['mem'].append(len(ok))
    if len(ok) == 2: s['two'] += 1
out = {}
for rec, s in stat.items():
    out[rec] = dict(pos=s['pos'], neg=s['neg'], mem_mean=(round(float(np.mean(s['mem'])), 2) if s['mem'] else 0),
                    mem_max=(int(np.max(s['mem'])) if s['mem'] else 0), two_frac=(round(s['two'] / max(1, len(s['mem'])), 3)),
                    unknown=s['unknown'], single=s['single'])
(OUT / 'CONE_AVAIL_V2B.json').write_text(json.dumps(out, indent=2), encoding='utf-8')
print(json.dumps(out, ensure_ascii=False))
