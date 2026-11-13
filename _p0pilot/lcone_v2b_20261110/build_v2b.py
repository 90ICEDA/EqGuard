"""Build balanced D-cone sets on group_B: base (abc/id/opt) vs all (5 recipes), budget-capped."""
import csv, hashlib, json
from pathlib import Path
import numpy as np
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FG = R / '_p0pilot/four_group_contract_20261109'
OUT = R / '_p0pilot/lcone_v2b_20261110'; OUT.mkdir(exist_ok=True)
g = np.load(FG / 'group_B.npz'); c = np.load(FG / 'cones_B.npz'); sup = np.load(FG / 'sup_B.npz')
rows, ptr, lab, view = c['rows'], c['ptr'], c['label'], c['view']
# split into cones
cones = []
for i in range(len(lab)):
    mem = rows[ptr[i]:ptr[i + 1]]
    rec = str(view[i]).split('__')[-1]
    cones.append(dict(i=i, view=str(view[i]), recipe=rec, label=int(lab[i]), mem=mem, src=str(view[i]).split('__ys_')[0]))
def cap(mem, seed, capn=20):
    if len(mem) <= capn: return mem
    h = hashlib.sha256((str(seed) + ':' + ','.join(map(str, mem[:5]))).encode()).hexdigest()
    rng = np.random.default_rng(int(h[:8], 16))
    return np.sort(rng.choice(mem, capn, replace=False))
def build(recipes, per_recipe):
    sel = []
    stats = {}
    for rec in recipes:
        pos = [x for x in cones if x['recipe'] == rec and x['label'] == 1]
        neg = [x for x in cones if x['recipe'] == rec and x['label'] == 0]
        npos = min(len(pos), per_recipe // 2)
        nneg = min(len(neg), npos)
        use_pos = pos[:npos]; use_neg = neg[:nneg]
        stats[rec] = dict(pos_avail=len(pos), neg_avail=len(neg), pos_used=npos, neg_used=nneg,
                          budget=per_recipe, shortfall=per_recipe - (npos + nneg))
        sel += use_pos + use_neg
    return sel, stats
base, stats_base = build(['ys_abc', 'ys_id', 'ys_opt'], 1000)
allr, stats_all = build(['ys_abc', 'ys_id', 'ys_opt', 'ys_aig', 'ys_nand'], 600)
def pack(sel, name):
    flat, p = [], [0]
    for x in sel:
        m = cap(x['mem'], x['i'])
        flat.extend(m.tolist()); p.append(len(flat))
    np.savez_compressed(OUT / f'cones_v2b_{name}_D.npz', rows=np.array(flat, np.int64),
                        label=np.array([x['label'] for x in sel], np.int8), ptr=np.array(p, np.int64),
                        view=np.array([x['view'] for x in sel]), cid=np.array([str(x['i']) for x in sel]))
    return dict(cones=len(sel), pos=int(sum(1 for x in sel if x['label'] == 1)), neg=int(sum(1 for x in sel if x['label'] == 0)),
                members=int(len(flat)), mean_members=round(len(flat) / max(1, len(sel)), 2))
rep = dict(base=pack(base, 'base'), all=pack(allr, 'all'), stats_base=stats_base, stats_all=stats_all,
           budget_target=3000, note='1:1 per recipe; positive availability limits budget; shortfall recorded')
(OUT / 'cone_budget_v2b.json').write_text(json.dumps(rep, indent=2), encoding='utf-8')
(OUT / 'LCONE_V2B_DIAGNOSIS.json').write_text(json.dumps(dict(
    old_lcone=dict(cones=11187, pos=558, neg=10629, id_share='10319/11187=92%', weighted_pos_mass='~93%',
                   cone_loss_below_002_at_step=85),
    old_note='old NC trained on group_A only; does not answer adding aig/nand cones',
    new_budget=rep, conclusion='budget 3000 unreachable with 1:1; actual totals recorded'),
    indent=2), encoding='utf-8')
print(json.dumps(rep, indent=1)[:1200])
