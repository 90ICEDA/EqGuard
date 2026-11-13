"""Append docs and registry."""
import shutil
from pathlib import Path
ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); H = ROOT / '_p0pilot/heldout_composition_20261110'
NOTE = """

### 2026-11-10 aig 排除闭环与 no-keep 阶段 2a

- 审计：`10.15/00_说明/返回审计_keep阶段2a_20261110.md`；证据 `KEEP_STAGE2A.json/CSV`、`CHECK_KEEP_STATE.json`、`KEEP_AUDIT.json`、`STATUS.json`。
- aig 状态统一 not_usable（指标不可用，不是无 keep 效应）；CSV 列改 name_diff_removed/added；check_keep_state PASS。
- 面板 20 组合/40 次冻结；aig 排除；阶段 2a rs232 4 组合 none anchor 0 vs cur 5/5/8/12，DFF 不变，4/4 supported；manifest sha 4a945e95…。
- 阶段 2b 剩余 16 组合/32 次，未执行；CEC/面板 GT/深度 RF/角色待办；未训练。
"""
for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name; bak = H / (name + '.before_stage2a')
    if not bak.exists(): shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8')); print('appended', name)
reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-10T20:50:00+08:00,no-keep阶段2a,heldout_composition_20261110,'
        '综合:8次;4/4 supported;aig排除;0训练,seed42/1/2,rs232t1000 alpha/delta abc/nand,'
        '返回审计_keep阶段2a_20261110.md,'
        'none0 vs cur5/5/8/12;DFF不变;32次待跑\n')
with reg.open('ab') as f: f.write(line.encode('utf-8'))
print('registry')
