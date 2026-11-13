"""Byte-preserving append to master docs (backup first) + registry row + STATUS/contract files."""
import json, shutil
from pathlib import Path

ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = ROOT / '_p0pilot/four_group_contract_20261109'

NOTE = """

### 2026-11-10 四组评价闭环与 no-keep 准备

- 审计：`10.15/00_说明/返回审计_四组评价闭环与no-keep准备_20261110.md`；证据 `FOUR_EVAL_V3.json`、`SELF_AUDIT_V3.json`。
- 修复独立审计 5 项缺口：A 阈值迁移字段（24 状态）、两种视图报警（trusted/全物理）、源×recipe 矩阵、基础/aig-nand 各自严格源与交互、旧阈值失效原因更正（eval_full 重推 65 视图定阈值）。
- 自审 PASS（自审≠独立审计）：重算阈值、宏（源内→recipe 宏）、交互符号与 SD；best 基础 3/3 正 +0.0141±0.0087，aig/nand 3/3 负 −0.0414±0.0341；last 方向不稳。
- no-keep 仅准备：最小面板 3 源×配方=12 综合+12 CEC；既有 keep 面板/clean≠CEC/端点 GT 缺口已列；弱 MIL/结构可达/CEC 不得当功能影响 GT。
- 收束四组实验；建议下一主线转 no-keep 准备（未执行）；深度/RF、角色、独立审计仍未完成。
"""

for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name
    bak = OUT / (name + '.before_closure_v3')
    if not bak.exists():
        shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8'))
    print('appended', name)

reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-10T11:25:00+08:00,四组评价闭环+no-keep准备,four_group_contract_20261109,'
        '纯离线:V3评价;自审PASS;no-keep合同;0训练/0综合,seed42/1/2,hosts_bt31 trans_test,'
        '返回审计_四组评价闭环与no-keep准备_20261110.md,'
        'A字段/两报警/矩阵/严格源补齐;base 3/3 +.0141±.0087;add 3/3 -.0414±.0341\n')
with reg.open('ab') as f:
    f.write(line.encode('utf-8'))

status = dict(phase='evaluation_closure_and_no_keep_prep', status='self_audit_pass_independent_pending',
              completed=['A fields 24 states', 'two alarm scopes', 'source x recipe matrix',
                         'strict base/add', 'self-audit PASS', 'no-keep inventory'],
              not_done=['independent audit', 'depth/RF', 'role recall', 'no-keep execution'],
              artifacts=['FOUR_EVAL_V3.json', 'SELF_AUDIT_V3.json'])
(OUT / 'STATUS.json').write_text(json.dumps(status, indent=2), encoding='utf-8')
print('registry+status appended')
