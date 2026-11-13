"""Byte-preserving append to master docs (backup first) + registry row."""
import shutil
from pathlib import Path

ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = ROOT / '_p0pilot/expansion_boundary_20261109'

NOTE = """

### 2026-11-09 展开强度边界与四组训练组成合同（不训练）

- 审计：`10.15/00_说明/返回审计_展开边界与四组合同_20261109.md`；证据 `_p0pilot/expansion_boundary_20261109/`。
- seed1/2 已对测试宿主全部 5 recipe 重新推理并保存预测（24 npz），逐 recipe/源/seed/best-last 分列；seed42 复用 CLOSURE。best_resume 的模型与优化器步不一致，标记不可直接恢复，不重训。
- 展开统计：aig physical 311k（abc 131k），id/opt D 锥最深 148–203，nand trusted 覆盖最低 0.121；aig/nand 的 NC−N 为负、abc 为正，方向上与“展开过强/覆盖过低不利”一致，但仅诊断、非因果。
- 四组合合同：A=基础池(abc,id,opt)、B=A+aig+nand；×N/NC；同源分层正例配额、共同归一化、同验证池、测试分列；主分析为交互差 [NC−N]_B − [NC−N]_A；4 组 seed42 探索、正式三种子 12 次，不自动启动。
- 缺口：seed1/2 正常 FPR/A-B 未重算（不混 8/40 视图）；角色 NA。
"""

for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name
    bak = OUT / (name + '.before_expansion')
    if not bak.exists():
        shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8'))
    print('appended', name)

reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-09T23:35:00+08:00,展开边界与四组合同,expansion_boundary_20261109,'
        '纯推理/统计:seed1/2全recipe预测;展开统计;四组合合同;0训练,seed42/1/2,hosts_bt31 trans_test,'
        '返回审计_展开边界与四组合同_20261109.md,'
        'aig 311k nodes;Dmax 203;nand cov .121;四组合同未启动\n')
with reg.open('ab') as f:
    f.write(line.encode('utf-8'))
print('registry appended')
