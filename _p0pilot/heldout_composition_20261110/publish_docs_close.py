"""Append docs, registry, STATUS."""
import json, shutil
from pathlib import Path
ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); H = ROOT / '_p0pilot/heldout_composition_20261110'
NOTE = """

### 2026-11-10 hoco 全量自审收束 + L_cone seed42 四臂

- 审计：`10.15/00_说明/返回审计_hoco收束与Lcone_20261110.md`。
- hoco 自审：348+240 字段全部一致，0 mismatch，SELF_AUDIT PASS（自审≠独立）；best_step 从 LOG 补记，best 仍不可恢复，last 可恢复。
- hoco 收束：I（best）基础 +0.0006±0.0519（1/3 正）、aig/nand −0.0104±0.0368（1/3 正）；方向不一致，不宣称组成效应；不启动 id/opt 折、不扩种子。
- L_cone seed42：N/NC1/NC01/C 验证 .3040/.2824/.2963/.0515；测试基础池 .2777/.2856/.2855/.0664，aig/nand .1995/.1897/.1959/.1247；C-only 节点排序崩溃；单种子不称稳定。
- 未完成：hoco id/opt 折、L_cone seed1/2、Cone MIL/正常四项全量、独立审计、no-keep/GT、深度 RF。
"""
for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name; bak = H / (name + '.before_hoco_close_lcone')
    if not bak.exists(): shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8')); print('appended', name)
reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-10T14:35:00+08:00,hoco收束+L_cone seed42,heldout_composition_20261110,'
        '训练:L_cone 4臂200更新;自审;0综合,seed42,hosts_bt31 train+test,'
        '返回审计_hoco收束与Lcone_20261110.md,'
        'hoco自审0 mismatch;I不一致;Lcone N .2777/NC .2856/C .0664\n')
with reg.open('ab') as f: f.write(line.encode('utf-8'))
st = dict(phase='hoco_closed_lcone_seed42_done',
          completed=['full hoco self-audit PASS', 'checkpoint correction', 'hoco closed', 'Lcone 4 arms 200'],
          not_done=['id/opt fold', 'Lcone seed1/2', 'cone MIL/normal full', 'independent audit', 'no-keep/GT', 'depth/RF'])
(H / 'STATUS.json').write_text(json.dumps(st, indent=2), encoding='utf-8')
print('registry+status')
