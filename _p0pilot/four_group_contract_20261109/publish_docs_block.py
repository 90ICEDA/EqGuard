"""Byte-preserving append to master docs (backup first) + registry row."""
import shutil
from pathlib import Path

ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = ROOT / '_p0pilot/four_group_contract_20261109'

NOTE = """

### 2026-11-10 四组采样修复与执行门禁（阻断，未训练）

- 审计：`10.15/00_说明/返回审计_四组采样阻断_20261110.md`。
- 已做：common 从合同 common_negative 池、extra 从合同 H 池取；正例按制造源冻结配额（502）并源内 sha 置换抽样；资格 trusted∧physical∧y=0。
- 阻断：A 组（abc/id/opt）与 H 池交集为空，144 extra 无法按合同组成抽取，抛 ValueError；未用 common 池替代、未静默改规则 → 200 步索引未落盘、锥预算与模型预检未执行。
- 结论：四组监督资产不具备可执行性，未通过执行门禁、未训练；需先修订并冻结 H/extra 组成规则（A/B 分别定义或显式缺项），再继续。
"""

for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name
    bak = OUT / (name + '.before_sup_block')
    if not bak.exists():
        shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8'))
    print('appended', name)

reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-10T00:25:00+08:00,四组采样修复门禁,four_group_contract_20261109,'
        '只读:候选池采样;正例源配额;H池交集空;0训练,seed42,hosts_bt31 trans_train,'
        '返回审计_四组采样阻断_20261110.md,'
        'A组H池交集空;extra无法组成;门禁未通过;未训练\n')
with reg.open('ab') as f:
    f.write(line.encode('utf-8'))
print('registry appended')
