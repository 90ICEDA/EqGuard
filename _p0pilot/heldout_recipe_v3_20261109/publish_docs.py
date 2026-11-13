"""Byte-preserving append to master docs (backup first) + registry row."""
import shutil
from pathlib import Path

ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = ROOT / '_p0pilot/heldout_recipe_v3_20261109'

NOTE = """

### 2026-11-09 held-out recipe v3 加载门禁（通过，未训练）

- 审计：`10.15/00_说明/返回审计_heldout_v3门禁_20260911.md` 的对应 v3 版本：`返回审计_heldout_v3门禁_20261109.md`；证据 `_p0pilot/heldout_recipe_v3_20261109/`。
- 纠正错误：辅助节点原 split 已含（train154/val429/test1246），用 [start,stop) 即可，无需扩展 1,829 行；每折预算为“正例+8192 common+144 extra”，不是固定 9,165。
- 折内资产：训练节点 1,073,607/895,147/892,130（各含 154 aux）；正例 614/703/648；common 池 59,650–66,442、H 池 56,706–59,473 均满足预算；曝光 max=200；锥 11,389/11,356/11,665。
- 归一化：仅折内 orig+trans 训练数据拟合 25:39，clip[-10,10]，前 25 维不变；拟合行清单与 hash 保存。
- 门禁：三折 30 项检查全部通过（视图/recipe 隔离、同宿主留出注入拒绝、锥范围、G0 组成与容量、margin 偏移不变性、训练模式无更新预检、参数/BN/RNG 恢复）；`GATE_V3.json passed=true`。
- 未训练；保存路径已建；门禁通过后再申请 seed42 三折 6 次运行，不补其他种子。
"""

for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name
    bak = OUT / (name + '.before_heldout_v3_gate')
    if not bak.exists():
        shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8'))
    print('appended', name)

reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-09T20:30:00+08:00,heldout recipe v3门禁,heldout_recipe_v3_20261109,'
        '只读:[start,stop)+aux;折内G0重建;归一化门禁;无更新预检;0训练,seed42,hosts_bt31 trans+orig,'
        '返回审计_heldout_v3门禁_20261109.md,'
        'train 1073607/895147/892130 aux154;GATE 30项True;未训练\n')
with reg.open('ab') as f:
    f.write(line.encode('utf-8'))
print('registry appended')
