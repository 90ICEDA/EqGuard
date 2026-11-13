"""Summarize v2b: deltas vs N, base vs all, means/SDs; budget doc."""
import json, statistics as st
from pathlib import Path
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); OUT = R / '_p0pilot/lcone_v2c_20261110'
res = json.loads((OUT / 'LCONE_V2C_RESULTS.json').read_text(encoding='utf-8'))
summary = {}
for point in ('best', 'last'):
    s = {}
    for arm in ('base', 'all'):
        db = [res[f'{arm}_{seed}_{point}']['base_ap'] - res[f'N_{seed}_{point}']['base_ap'] for seed in (42, 1, 2)]
        da = [res[f'{arm}_{seed}_{point}']['add_ap'] - res[f'N_{seed}_{point}']['add_ap'] for seed in (42, 1, 2)]
        s[f'{arm}_vs_N'] = dict(base=db, base_mean=st.mean(db), base_sd=st.stdev(db), base_pos=sum(1 for x in db if x > 0),
                                add=da, add_mean=st.mean(da), add_sd=st.stdev(da), add_pos=sum(1 for x in da if x > 0))
    db = [res[f'all_{seed}_{point}']['base_ap'] - res[f'base_{seed}_{point}']['base_ap'] for seed in (42, 1, 2)]
    da = [res[f'all_{seed}_{point}']['add_ap'] - res[f'base_{seed}_{point}']['add_ap'] for seed in (42, 1, 2)]
    s['all_minus_base'] = dict(base=db, base_mean=st.mean(db), base_sd=st.stdev(db), base_pos=sum(1 for x in db if x > 0),
                               add=da, add_mean=st.mean(da), add_sd=st.stdev(da), add_pos=sum(1 for x in da if x > 0))
    summary[point] = s
(OUT / 'LCONE_V2C_SUMMARY.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
bud = json.loads((OUT / 'cone_budget_v2b.json').read_text(encoding='utf-8'))
(OUT / 'CONE_BUDGET_V2C.md').write_text(f"""# CONE_BUDGET_V2B

- 目标 3000、1:1、每 recipe 1000/600；实际不可达（正锥不足）。
- BASE：792 锥（396/396），members 8225，mean 10.39；abc 200/200，id 196/196，opt 0（group_B opt 无 D 锥）。
- ALL：1116 锥（558/558），members 11771，mean 10.55；abc 200/200，id 196/196，aig 162/162，nand ?，opt 0。
- 短差：base 2208、all 1884；未静默重复/补造；opt 缺项记录。
- cap=20 确定性 hash；成员/标签哈希随 npz。
""", encoding='utf-8')
print(json.dumps({p: {k: (round(v['base_mean'], 4), round(v['add_mean'], 4)) for k, v in summary[p].items()} for p in summary}, ensure_ascii=False))
