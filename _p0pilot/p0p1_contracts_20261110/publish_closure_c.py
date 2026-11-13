"""Append docs and registry."""
import shutil
from pathlib import Path
ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); L = ROOT / '_p0pilot/lcone_v2c_20261110'; P = ROOT / '_p0pilot/p0p1_contracts_20261110'; H = ROOT / '_p0pilot/heldout_composition_20261110'
NOTE = """

### 2026-11-10 L_cone 关闭确认与 C 单折评价

- 审计：`10.15/00_说明/返回审计_Lcone关闭与C评价_20261110.md`；证据 `LCONE_CLOSURE_CHECK.json`、`C_EVAL_FINAL.json`、`GT_PLAN_V5.md`。
- 关闭检查 PASS：λ0.1 与 all 对 N 的 base/add 均 0/3 正；all−base base −.0127、add +.0193；λ1 不可复核、v2b 不等、nand 2 锥。
- C 单折（h=abc，12 次 hoco 复用）：NC−N A 组 base +.0064(1/3)/add −.0094(2/3)；B 组 base +.0069(2/3)/add −.0197(0/3)；不可外推。
- B 的 GT 计划：CEC 仅实现等价，host-level GT，s38417t100 missing，面板 GT 未建。
- 未训练/未综合/未 CEC/未改标签。
"""
for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name; bak = L / (name + '.before_closure_c')
    if not bak.exists(): shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8')); print('appended', name)
reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-11T01:40:00+08:00,L_cone关闭+C单折评价,p0p1_contracts_20261110,'
        '只读:关闭检查PASS;C评价;GT计划;0训练,seed42/1/2,hoco,'
        '返回审计_Lcone关闭与C评价_20261110.md,'
        'λ0.1 0/3;C A base+.0064/B base+.0069;GT host-level\n')
with reg.open('ab') as f: f.write(line.encode('utf-8'))
print('registry')
