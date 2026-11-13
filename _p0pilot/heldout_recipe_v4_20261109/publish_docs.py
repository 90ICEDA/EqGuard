"""Byte-preserving append to master docs (backup first) + registry row."""
import shutil
from pathlib import Path

ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = ROOT / '_p0pilot/heldout_recipe_v4_20261109'

NOTE = """

### 2026-11-09 held-out v4 真实门禁（通过，未训练）

- 审计：`10.15/00_说明/返回审计_heldout_v4门禁_20261109.md`；证据 `_p0pilot/heldout_recipe_v4_20261109/`。
- 撤销 v3 “30 项全部通过即可训练”：v3 mapping/new2old、拒绝测试、margin 检查存在漏检；v4 重新修正并门禁。
- 修复：new2old=rows、old2new 保存并往返校验、特征/边对应；共用 load_fold 使用折内 mean/std（前 25 维不变、25:39 clip）；完整 step0 全正例+8192+144（非 5 个正例），200 步哈希与组成复核；留出视图实际传入加载器抛 ValueError；二维 logits 不同偏移 c_i 下 margin/AP/Top-k 不变，误用 logits[:,1] 排名改变。
- 预检：三折节点/锥梯度（2.571/1.486、2.555/2.194、2.573/1.883）有限、锥非零、0 step、参数/BN/RNG 恢复。
- `GATE_V4.json passed=true`（21 项）；本轮未训练；训练保存路径沿用 v3 结构。
"""

for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name
    bak = OUT / (name + '.before_heldout_v4')
    if not bak.exists():
        shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8'))
    print('appended', name)

reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-09T21:00:00+08:00,heldout v4真实门禁,heldout_recipe_v4_20261109,'
        '只读:映射修复+共用加载+拒绝+2D margin+无更新预检;0训练,seed42,hosts_bt31 trans+orig,'
        '返回审计_heldout_v4门禁_20261109.md,'
        'GATE 21项True;节点/锥梯度有限;未训练\n')
with reg.open('ab') as f:
    f.write(line.encode('utf-8'))
print('registry appended')
