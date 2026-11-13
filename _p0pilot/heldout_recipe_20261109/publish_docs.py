"""Byte-preserving append to master docs (backup first) + registry row."""
import shutil
from pathlib import Path

ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = ROOT / '_p0pilot/heldout_recipe_20261109'

NOTE = """

### 2026-11-09 held-out recipe 三折 seed42（宿主留出条件下的 recipe 留出）

- 审计：`10.15/00_说明/返回审计_heldout_seed42三折_20261109.md`；证据 `_p0pilot/heldout_recipe_20261109/`。
- 命名：测试宿主 s38584 未见于训练，本轮为“宿主留出条件下的 recipe 留出”，不是单因素 recipe 实验。
- 资产：abc/aig/nand 折训练 194/217/217、验证 52/52/52、测试 13/13/13；折内子图重编号、折内归一化重拟合、G0 预算重建（正例全取 + 8336 负/步）、锥按视图筛选重映射（11,389/11,356/11,665）。
- 门禁：视图数与视图名排除断言、归一化来源断言、双侧损失+锥损失梯度有限、0 step、参数/BN/RNG 恢复；`GATE.json passed=true`。
- 结果（best）：abc N/NC test .0120/.0089；aig .2852/.2443；nand .0946/.1262；val NC−N 均值 −0.0185，test 均值 −0.0042（2/3 折为负）。
- 缺口：本轮只保存逐视图 AP，未保存 Top-k/角色/锥 MIL/A-B 与检查点，相关指标不可报告，不补造。
- 结论：NC 在该配置无稳定收益；不扩 seed1/2，不写主表；继续前需补折内预测与评价保存。
"""

for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name
    bak = OUT / (name + '.before_heldout_run')
    if not bak.exists():
        shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8'))
    print('appended', name)

reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-09T19:50:00+08:00,heldout recipe三折seed42,heldout_recipe_20261109,'
        '训练:6次200更新;折内归一化/子图/锥重建;0 SAT;0合成,seed42,hosts_bt31 trans,'
        '返回审计_heldout_seed42三折_20261109.md,'
        'val d-0.0185;test d-0.0042;2/3负;GATE true;未保存Top-k/角色/锥A-B\n')
with reg.open('ab') as f:
    f.write(line.encode('utf-8'))
print('registry appended')
