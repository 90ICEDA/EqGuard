"""Byte-preserving append to master docs (backup first) + registry row."""
import shutil
from pathlib import Path

ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = ROOT / '_p0pilot/heldout_recipe_v5_20261109'

NOTE = """

### 2026-11-09 held-out v5 门禁与 seed42 三折执行

- 审计：`10.15/00_说明/返回审计_heldout_v5执行_20261109.md`；证据 `_p0pilot/heldout_recipe_v5_20261109/`。
- 接口：old2new 长度=完整 split 节点（train/val/test 尾部 -1）、new2old=rows；单一 rng(42+step) 先 8192 common 再 144 extra 再拼正例；orig/trans 均用折内 mean/std（前 25 维不变、25:39 clip）；orig 不再走旧归一化。
- 门禁 `GATE_V5.json passed=true`（30 项）：归一化逐元素、留出注入真实抛错、二维 margin 反例、实际 step0 无更新预检（节点/锥梯度有限、锥非零、0 step、参数/BN/RNG 恢复）。
- 6 次 seed42：abc N/NC test .1267/.1589；aig .3260/.3003；nand .1298/.1115；test 配对均值 −0.0039（1/3 折为正），val 均值 −0.0040；无稳定收益，不扩 seed1/2。
- 评价：逐源 AP、Top-1%（trusted physical）、D/PO 弱 MIL、A/B 分列；角色缺映射证据记 NA；best/last 分列，测试未参与选择。
"""

for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name
    bak = OUT / (name + '.before_heldout_v5_run')
    if not bak.exists():
        shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8'))
    print('appended', name)

reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-09T21:20:00+08:00,heldout v5门禁+seed42三折,heldout_recipe_v5_20261109,'
        '训练:6次200更新;共享fold_io;0 SAT;0综合,seed42,hosts_bt31 trans+orig,'
        '返回审计_heldout_v5执行_20261109.md,'
        'GATE 30项True;test d-0.0039(1/3正);val d-0.0040;未扩种子\n')
with reg.open('ab') as f:
    f.write(line.encode('utf-8'))
print('registry appended')
