"""Byte-preserving append to master docs (backup first) + registry row."""
import shutil
from pathlib import Path

ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = ROOT / '_p0pilot/four_group_contract_20261109'

NOTE = """

### 2026-11-10 四组采样修复（部分完成，未训练）

- 审计：`10.15/00_说明/返回审计_四组采样修复_20261110.md`；资产 `sup_A.npz/sup_B.npz/SUP_OK.json`。
- 纠正：A 组 H 不为空（A common 48,626 / H 46,496；B 75,850 / 69,683）；真实错误是 common/H 互斥交集逻辑，已改为 `setdiff1d(H, 已抽common)` 抽 144。
- 已落盘 200 步实际 indices（非仅哈希）、502 正例/步、8,192 common+144 extra、源配额与哈希；采样反例（互斥、重复、不足、错误类别）通过。
- 未执行：锥资产（(split,view,cone_id) 匹配/配额/曝光）、A/B 模型预检（组合脚本 >30 分钟无输出被终止）→ 执行门禁未通过、未启动四组训练。阻塞点在锥匹配/预检阶段，未作未经验证的归因。
"""

for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name
    bak = OUT / (name + '.before_sup_fixed')
    if not bak.exists():
        shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8'))
    print('appended', name)

reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-10T00:55:00+08:00,四组采样修复,four_group_contract_20261109,'
        '只读:200步indices落盘;采样反例;锥/预检未执行;0训练,seed42,hosts_bt31 trans_train,'
        '返回审计_四组采样修复_20261110.md,'
        'A common48626/H46496;B 75850/69683;502正;锥/模型预检未完成\n')
with reg.open('ab') as f:
    f.write(line.encode('utf-8'))
print('registry appended')
