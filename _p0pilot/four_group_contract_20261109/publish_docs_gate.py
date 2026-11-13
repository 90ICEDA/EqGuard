"""Byte-preserving append to master docs (backup first) + registry row."""
import shutil
from pathlib import Path

ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = ROOT / '_p0pilot/four_group_contract_20261109'

NOTE = """

### 2026-11-09 四组可执行资产与资产门禁（未训练）

- 审计：`10.15/00_说明/返回审计_四组资产与门禁_20261109.md`；资产 `_p0pilot/four_group_contract_20261109/{group_A.npz,group_B.npz,ASSETS.json,GATE_ASSETS.json}`。
- A/B 子图：171/255 视图、66 源、154 辅助节点、535,069/1,249,120 节点；`[start,stop)` 完整范围，old2new/new2old 往返、边过滤通过；ys_rt 两组排除；keep 变体不当作独立源。
- 200 步索引：按源配额 502 正例/步、8,192 common+144 extra、extra 去重；pool 277,354/419,860；哈希已落盘，N/NC 共用。
- 锥预算：A/B 各 264（132 正/132 负），共同协议；成员 trusted∧physical；未静默重复/删源。
- 共同归一化：仅 A 组 orig+trans 拟合 25:39，clip[-10,10]，sha cb2604ce。
- 资产门禁 10 项通过；**模型 precheck 未执行（NOT_EXECUTED）**，分项损失/独立梯度/margin/BN/RNG 未验证，故执行门禁未通过、未训练；A/B 实际召回/误报与深度/RF 为待办（null）。
"""

for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name
    bak = OUT / (name + '.before_assets_gate')
    if not bak.exists():
        shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8'))
    print('appended', name)

reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-10T00:10:00+08:00,四组资产与资产门禁,four_group_contract_20261109,'
        '只读:子图/索引/锥预算/归一化;资产门禁;模型预检未执行,seed42,hosts_bt31 trans_train+orig_train,'
        '返回审计_四组资产与门禁_20261109.md,'
        'A535069/B1249120;502正;264锥(132/132);asset gate true;model precheck NOT_EXECUTED\n')
with reg.open('ab') as f:
    f.write(line.encode('utf-8'))
print('registry appended')
