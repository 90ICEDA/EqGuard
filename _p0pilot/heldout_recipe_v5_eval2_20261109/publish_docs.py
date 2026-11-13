"""Byte-preserving append to master docs (backup first) + registry row."""
import shutil
from pathlib import Path

ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = ROOT / '_p0pilot/heldout_recipe_v5_eval2_20261109'

NOTE = """

### 2026-11-09 held-out v5 跨 recipe 离线补评（不训练）

- 审计：`10.15/00_说明/返回审计_heldout_v5跨recipe_20261109.md`；证据 `_p0pilot/heldout_recipe_v5_eval2_20261109/`。
- 跨 recipe（同测试宿主 s38584，各折自身归一化）：留出 vs 已见均值——abc N/NC 留出 .1267/.1588 vs 已见 .2531/.2557；aig .3260/.3003 vs .2638/.2845；nand .1298/.1115 vs .2656/.2273。abc/nand 留出明显更低，aig 反向；NC 仅 abc 缩小差距。
- 证据范围更正：LOG 的 trans 为节点+锥合计损失；best/last.pt 仅模型状态，不是完整训练恢复检查点。abc 的实际召回≠目标召回，不能写成严格等召回。
- 缺口：正常 FPR（可信/视图/全物理）与角色召回未计算；已见/留出源对象未做匹配子集比较；不补造。
- 结论：当前探索收益不明确（1/3 折留出 test 为正），正式多种子验证仍未完成；不建议补 seed1/2，先补匹配源比较、正常 FPR 与角色映射。
"""

for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name
    bak = OUT / (name + '.before_cross_recipe')
    if not bak.exists():
        shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8'))
    print('appended', name)

reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-09T21:40:00+08:00,heldout v5跨recipe离线评价,heldout_recipe_v5_eval2_20261109,'
        '纯推理:12检查点;5recipe;0训练,seed42,hosts_bt31 trans_test,'
        '返回审计_heldout_v5跨recipe_20261109.md,'
        'abc/nand留出低于已见;aig反向;NC仅abc缩差;不建议补seed1/2\n')
with reg.open('ab') as f:
    f.write(line.encode('utf-8'))
print('registry appended')
