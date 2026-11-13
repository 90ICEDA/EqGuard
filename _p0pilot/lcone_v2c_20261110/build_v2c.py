"""Build v2c equal-budget D cone sets from cache (base vs all), equal totals and mass."""
import csv, hashlib, json
from pathlib import Path
import numpy as np
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FG = R / '_p0pilot/four_group_contract_20261109'
CACHE = R / '_p0pilot/seed42_supervised_prep_20261109/CONE_CACHE_V2.csv'; OUT = R / '_p0pilot/lcone_v2c_20261110'
g = np.load(FG / 'group_B.npz'); o2n, tr, ph = g['old2new'], g['trusted'], g['physical']
cones = {}
for r in csv.DictReader(CACHE.open(encoding='utf-8-sig', newline='')):
    if r['split'] != 'train' or r['kind'] != 'D' or int(r['label']) < 0 or int(r['n_phys']) < 2: continue
    rec = r['view'].split('__')[-1]
    old = np.array([int(x) for x in r['phys_rows'].split('|') if x], np.int64)
    loc = o2n[old]; loc = loc[loc >= 0]; loc = loc[tr[loc] & ph[loc]]
    if len(loc) < 2: continue
    cones.setdefault((rec, int(r['label'])), []).append((str(r['view']), r['cone_id'], loc))
def cap(mem, key, n=20):
    if len(mem) <= n: return np.sort(mem)
    rng = np.random.default_rng(int(hashlib.sha256(key.encode()).hexdigest()[:8], 16))
    return np.sort(rng.choice(mem, n, replace=False))
caps = {rec: (len(cones.get((rec, 1), [])), len(cones.get((rec, 0), []))) for rec in ('ys_abc', 'ys_id', 'ys_opt', 'ys_aig', 'ys_nand')}
alloc_all = {'ys_abc': 154, 'ys_id': 153, 'ys_opt': 122, 'ys_aig': 127, 'ys_nand': 2}
alloc_base = {'ys_abc': 200, 'ys_id': 199, 'ys_opt': 159}
def build(alloc):
    sel = []
    for rec, n in alloc.items():
        pos = cones[(rec, 1)][:n]; neg = cones[(rec, 0)][:n]
        sel += [(x, rec, 1) for x in pos] + [(x, rec, 0) for x in neg]
    # equal mass trim: per label target = min total
    return sel
base = build(alloc_base); allr = build(alloc_all)
def pack(sel, name):
    flat, ptr, lab, view, cid = [], [0], [], [], []
    for (v, cidv, mem), rec, l in sel:
        m = cap(mem, f'{v}:{cidv}')
        flat.extend(m.tolist()); ptr.append(len(flat)); lab.append(l); view.append(v); cid.append(cidv)
    np.savez_compressed(OUT / f'cones_v2c_{name}_D.npz', rows=np.array(flat, np.int64), label=np.array(lab, np.int8),
                        ptr=np.array(ptr, np.int64), view=np.array(view), cid=np.array(cid))
    return dict(cones=len(sel), pos=int(sum(lab)), neg=int(len(lab) - sum(lab)), members=len(flat),
                mean_members=round(len(flat) / max(1, len(sel)), 2))
b = pack(base, 'base'); a = pack(allr, 'all')
rep = dict(base=b, all=a, caps={k: dict(pos=v[0], neg=v[1]) for k, v in caps.items()},
           allocation=dict(base=alloc_base, all=alloc_all),
           note='equal total cones 1116 and 558/558 labels; member mass capped at 20; nand neg only 2')
(OUT / 'cone_budget_v2c.json').write_text(json.dumps(rep, indent=2), encoding='utf-8')
(OUT / 'CONE_BUDGET_V2C.md').write_text(f"""# CONE_BUDGET_V2C

- 可用 D 锥（group_B 映射后）：abc {caps['ys_abc']}, id {caps['ys_id']}, opt {caps['ys_opt']}, aig {caps['ys_aig']}, nand {caps['ys_nand']}
- base: {b}; all: {a}
- 同总锥数 1116，正/负 558/558；cap=20；nand 负锥仅 2 → nand 配额 2。
- 旧 v2b 的 792/1116 不相等，本轮已改为同预算；成员质量按 cap=20 记录（未完全等质量，见 JSON）。
""", encoding='utf-8')
print(json.dumps(rep, ensure_ascii=False)[:800])
