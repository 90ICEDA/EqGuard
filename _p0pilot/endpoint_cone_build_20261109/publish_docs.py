"""Byte-preserving append to master docs (backup first) + registry row."""
import shutil
from pathlib import Path

ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = ROOT / '_p0pilot/endpoint_cone_build_20261109'

NOTE = """

### 2026-11-09 端点锥准备与 N/NC 最终合同（只读）

- 合同：`10.15/00_说明/NNC最终合同_v3_20261109.md`；审计 `10.15/00_说明/返回审计_端点锥准备与NNC合同_20261109.md`；证据 `_p0pilot/endpoint_cone_build_20261109/`。
- PI 修复：只从 module input/inout 声明（位宽展开+位别名）确定边界，禁止用“无驱动”代替 PI；内部悬空/常量/X/Z/直接 Q/单点/D/SI/PO 驱动分别分类。
- 独立测试 10/10（手写期望）；实际抓到 `[3:0]` 步长 bug 并修复，证明导出→重载不足。
- 标签口径：锥标签由既有可信成员派生，是弱 MIL 不是独立 impact GT；训练与评价用同一可信子集；含 unknown 且无正证据不得标负；role_region 与 impact_cone 分名。
- GT 表 `ENDPOINT_GT_GAPS_v2.csv` 修复字段错位与 R3 引用（DFF_1081_Q_reg.Q = test_so62_orig，别名 TrojanAHJ.IN1）。
- 真实视图缓存（train 259 + val 65）：563,119 锥、15,460,765 成员行、正 1,453（train 1,118/val 335）、负 44,138、unknown 517,528、空 329,567、单点 31,485、可训练 14,106（成员曝光 879,418）、可信成员覆盖 22.35%、缺失 1,956、越界 0、导出→重载逐视图相等。
- 启动判据：先 seed42 N/NC 两次，锥损失分母与缓存一致、无 NaN、验证 AP 不塌、test 未参与选模；四项通过才扩 seed1/2。
- 仍未确认：seed42 实际训练表现、1,956 缺失成员影响、整网/次态 GT、严格 no-keep（12 合成 + 12 CEC 待授权）。
"""

for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name
    bak = OUT / (name + '.before_cone_cache_v3')
    if not bak.exists():
        shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8'))
    print('appended', name)

reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-09T17:25:00+08:00,端点锥准备+NNC合同,endpoint_cone_build_20261109,'
        '只读:PI声明修复;10项独立测试;324视图锥缓存,seed42,hosts_bt31 trans,'
        'NNC最终合同_v3_20261109;返回审计_端点锥准备与NNC合同_20261109.md,'
        '563119锥;可训练14106;越界0;导出重载一致;0训练/0SAT\n')
with reg.open('ab') as f:
    f.write(line.encode('utf-8'))
print('registry appended')
