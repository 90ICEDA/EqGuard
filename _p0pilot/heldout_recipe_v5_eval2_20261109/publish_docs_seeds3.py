"""Byte-preserving append to master docs (backup first) + registry row."""
import shutil
from pathlib import Path

ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = ROOT / '_p0pilot/heldout_recipe_v5_eval2_20261109'

NOTE = """

### 2026-11-09 held-out v5 三 seed 补齐与口径修正

- 审计：`10.15/00_说明/返回审计_heldout_v5三seed_20261109.md`；证据 `_p0pilot/heldout_recipe_v5_eval2_20261109/SEEDS3.json`、`_p0pilot/heldout_recipe_v5_20261109/{fold}/{arm}/seed{1,2}/`。
- 匹配修正：严格四 recipe 交集为 4 个含木马源（alpha/epsilon/gamma/zeta，ys_opt 缺 delta）；五源宏 AP 仍为主指标；撤销“五源全部完整匹配”。
- 补齐 seed1/2：12 次，init_s1/s2、T.seed(seed+step)、冻结采样、同一 fold_io；共 18 次（三折×两臂×三种子）。
- 三 seed 留出五源宏 AP（NC−N）：abc best +0.0083（SD .0385）/ last +0.0357（.0263）；aig −0.0075/−0.0141；nand −0.0194/−0.0186；方向不一致，三折合计约 −0.006。
- 四源交集诊断与五源同向；正常视图 95% 阈值 40/40 报警；seed1/2 的 A/B 未计算（缺口）；角色 NA；测试未参与选择。
- 结论：该配置正式多种子已完成，**不支持锥监督稳定改进**；不建议再扩配置或按方向筛折。
"""

for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name
    bak = OUT / (name + '.before_seeds3')
    if not bak.exists():
        shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8'))
    print('appended', name)

reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-09T23:05:00+08:00,heldout v5三seed补齐,heldout_recipe_v5_20261109,'
        '训练:seed1/2共12次;0 SAT;0综合,seed42/1/2,hosts_bt31 trans,'
        '返回审计_heldout_v5三seed_20261109.md,'
        'abc +.0083/-.0357;aig -.0075/-.0141;nand -.0194/-.0186;18次完成\n')
with reg.open('ab') as f:
    f.write(line.encode('utf-8'))
print('registry appended')
