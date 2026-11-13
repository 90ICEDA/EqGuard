"""Byte-preserving append to master docs (backup first) + registry row."""
import shutil
from pathlib import Path

ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = ROOT / '_p0pilot/heldout_recipe_v2_20261109'

NOTE = """

### 2026-11-09 held-out recipe v2 预检（门禁未通过，未训练）

- 审计：`10.15/00_说明/返回审计_heldout_v2预检_20261109.md`；证据 `_p0pilot/heldout_recipe_v2_20261109/`；旧结果标记“协议不合格，不用于判断锥监督收益”。
- v2 资产：abc/aig/nand 训练 194/217/217、验证 52、测试 13；折内归一化按原规则只用 orig+trans 训练节点拟合 25:39 列并 clip，前 25 维不变；锥筛选重映射（11,389/11,356/11,665）。
- 门禁失败：① 154 个辅助节点不在 split 行内（aux_train=0），未扩展图无法恢复；② 官方 G0 索引过滤到折内后 200/200 步不足（7,169–8,090 vs 9,165），不得用随机负例替代。
- 按合同停止在预检，未训练；旧 v1 的随机负例、trans-only 归一化、未保存预测等问题已作废。
- 下一轮：扩展虚拟/辅助行与边、折内重建 G0 候选池、重做门禁（含同宿主留出视图拒绝测试），通过后才训练并保存逐步索引/损失/检查点/预测。
"""

for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name
    bak = OUT / (name + '.before_heldout_v2')
    if not bak.exists():
        shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8'))
    print('appended', name)

reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-09T20:05:00+08:00,heldout recipe v2预检,heldout_recipe_v2_20261109,'
        '只读:折内资产+门禁;0训练;旧结果作废,seed42,hosts_bt31 trans,'
        '返回审计_heldout_v2预检_20261109.md,'
        'aux=0失败;G0过滤后179-8090不足;门禁False未训练\n')
with reg.open('ab') as f:
    f.write(line.encode('utf-8'))
print('registry appended')
