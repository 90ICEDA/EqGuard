"""Byte-preserving append to master docs (backup first) + registry row."""
import shutil
from pathlib import Path

ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = ROOT / '_p0pilot/four_group_contract_20261109'

NOTE = """

### 2026-11-10 四组锥资产与 A/B 预检（门禁通过，未训练）

- 审计：`10.15/00_说明/返回审计_四组锥资产与预检_20261110.md`；证据 `cones_A/B.npz`、`CONES_REPORT.json`、`PRECHECK_A/B.json`。
- 锥构建性能修复：数组预加载、单次扫描 563,119 行、向量化映射；总耗时 4.7 s，无长阻塞。
- 锥资产：A/B 各 11,187（558 正/10,629 负），身份 (split,view,cone_id) 不跨 recipe 覆盖；逐源逐标签匹配，保留负例专属源；复用 sup_A/B。
- 预检通过：A node/cone 梯度 2.857/1.614，B 2.526/1.702；有限、锥非零、margin 反例通过；0 step；参数/BN/CPU+全部 CUDA RNG 恢复一致。
- 未训练：共同基础 recipe 验证池尚未构建，直接用留出折 val 会违反“共同验证池”合同；4×200 待办。评价/交互差/深度 RF 待办。
"""

for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name
    bak = OUT / (name + '.before_cone_precheck')
    if not bak.exists():
        shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8'))
    print('appended', name)

reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-10T01:20:00+08:00,四组锥资产与预检,four_group_contract_20261109,'
        '只读:锥资产4.7s;A/B预检通过;0训练,seed42,hosts_bt31 trans_train+orig_train,'
        '返回审计_四组锥资产与预检_20261110.md,'
        '11187锥(558/10629);grad A2.857/1.614 B2.526/1.702;共同验证池未建;未训练\n')
with reg.open('ab') as f:
    f.write(line.encode('utf-8'))
print('registry appended')
