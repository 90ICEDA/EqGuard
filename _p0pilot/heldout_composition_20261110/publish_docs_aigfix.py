"""Append docs and registry."""
import shutil
from pathlib import Path
ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); H = ROOT / '_p0pilot/heldout_composition_20261110'
NOTE = """

### 2026-11-10 aig 结构结论更正

- 审计：`10.15/00_说明/返回审计_aig结构更正_20261110.md`；证据 `AIG_STRUCT_DIFF.json/CSV`、`STRUCT_METRICS.json`、`KEEP_STAGE1.json`、`KEEP_AUDIT.json`、`STATUS.json`。
- 撤销 aig “same”：alpha 523/524 inst、599/602 nets；delta 523/524、599/599；结构有差异但不能归因 keep。
- aig_anchor_metric_not_applicable；aig_structure_differs_unresolved；阶段1 4/6 supported；面板不启动；aig 单独判定方案待实现。
- 0 新综合；未 CEC/训练；结构差异非功能 GT。
"""
for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name; bak = H / (name + '.before_aig_fix')
    if not bak.exists(): shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8')); print('appended', name)
reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-10T19:50:00+08:00,aig结构结论更正,heldout_composition_20261110,'
        '只读:523/524;599/602;unresolved;0综合,seed42/1/2,rs232t1000 aig,'
        '返回审计_aig结构更正_20261110.md,'
        '撤销same;aig unresolved;4/6;面板停\n')
with reg.open('ab') as f: f.write(line.encode('utf-8'))
print('registry')
