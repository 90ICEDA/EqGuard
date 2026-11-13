"""Byte-preserving append to the master docs (backup first) + registry row."""
import shutil
from pathlib import Path

ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = ROOT / '_p0pilot/control_signed_carrier_20261109_v2'

NOTE = """

### 2026-11-09 带相位功能承载对应 v2（接口与验收修正，只读）

- 新目录 `_p0pilot/control_signed_carrier_20261109_v2/`，v1 全部结果保留未改。
- 修正：`target_driver_cells` 严格等于目标信号唯一实际驱动门；区域中间门单列 `REGION_MEMBERS_V2.csv`（输出引脚+相位）；R4/R5 只把 INV 输出当 +1 载体，AND 中间级登记为 −1 区域成员，禁止当同相正对。
- 验收：`load_relations.py` 重读网表，逐条核对坐标、驱动、相位、边界别名（exact/pin_alias/driver_cell/inv_formula）、上下文、哈希、宿主用途并复算真值；`verify_v2.py` 的 8 项篡改（相位、边界、驱动、上下文、哈希、标签、区域成员相位、扩展相位）**全部被拒绝**。
- 7 个原未确认对象重试：12 候选/7 重试/2 接受（V2_EXT11 +1 活跃、V2_EXT12 +1 悬空）、19 次尝试、17 次边界未对齐、0 函数不符；模式 8/65536；未检查后代 5，已记录。
- 仍未恢复任何 −1 承载：未对齐来自无名字桥接的前级中间网，不是放宽相位门槛。
- 结论：R1/R2/R3 可作未来候选（带相位标记），R4/R5 与区域成员只作诊断、禁止拉近；V2_EXT11/12 仅作覆盖统计。
- 报告：`10.15/00_说明/返回审计_带相位功能承载对应_v2_20261109.md`。
"""

for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name
    bak = OUT / (name + '.before_signed_carrier_v2')
    if not bak.exists():
        shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8'))
    print('appended', name)

reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-09T15:20:00+08:00,带相位功能承载对应v2,control_signed_carrier_20261109_v2,'
        '只读:严格驱动门+区域成员;导出-加载-验证;8项篡改拒绝;7对象重试,seed42,'
        'hosts_bt31 orig+trans,返回审计_带相位功能承载对应_v2_20261109.md,'
        '8关系+2扩展关系,6+2关系验证通过;7重试2接受17未对齐;0训练/0SAT\n')
with reg.open('ab') as f:
    f.write(line.encode('utf-8'))
print('registry appended')
