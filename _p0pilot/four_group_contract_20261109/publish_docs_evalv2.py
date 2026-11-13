"""Byte-preserving append to master docs (backup first) + registry row."""
import shutil
from pathlib import Path

ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = ROOT / '_p0pilot/four_group_contract_20261109'

NOTE = """

### 2026-11-10 四组三种子离线评价修正

- 审计：`10.15/00_说明/返回审计_四组三seed评价修正_20261110.md`；证据 `FOUR_EVAL_V2.json`、`*_testpred.npz`。
- 阈值修正：A 只用共同 39 视图 val_common；B 测试同召回单列（测试正例 need，实际召回/阈值/支持数）；旧 FOUR_EVAL_ALL 阈值口径失效。
- 24 个 best/last 模型状态全部补评并保存预测/行映射；逐 recipe/源 AP、Top-1/5、可信/全物理 FPR 与两种视图报警；严格四源交集（alpha/epsilon/gamma/zeta）单列。
- 交互差 best：基础池 +0.0240/+0.0106/+0.0076 → 3/3 正，+0.0141±0.0087；aig/nand −0.0275/−0.0166/−0.0803 → 3/3 负，−0.0414±0.0341。last 单列（基础 2/3 正、add 2/3 负）。此前“2/3”作废。
- 检查点更正：best_resume 与末步 optimizer/RNG 混用，标记不可直接恢复，保留原文件不重训；LOG 为节点+锥合计损失。
- 建议：该四组实验可收束（单宿主三种子，方向可重复但幅度小、last 不稳），不再扩种子/配置；下一主线可转 no-keep 准备（仅建议）。
"""

for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name
    bak = OUT / (name + '.before_eval_v2_fix')
    if not bak.exists():
        shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8'))
    print('appended', name)

reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-10T11:00:00+08:00,四组三seed评价修正,four_group_contract_20261109,'
        '纯离线:24状态补评;阈值val_common;0训练,seed42/1/2,hosts_bt31 trans_test,'
        '返回审计_四组三seed评价修正_20261110.md,'
        'base 3/3 +.0141±.0087;add 3/3 -.0414±.0341;best_resume不可恢复\n')
with reg.open('ab') as f:
    f.write(line.encode('utf-8'))
print('registry appended')
