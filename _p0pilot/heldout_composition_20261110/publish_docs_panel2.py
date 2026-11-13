"""Append docs and registry."""
import shutil
from pathlib import Path
ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); H = ROOT / '_p0pilot/heldout_composition_20261110'
NOTE = """

### 2026-11-10 no-keep 面板更正与 GT/keep 边界

- 审计：`10.15/00_说明/返回审计_no-keep面板更正_20261110.md`；证据 `NO_KEEP_PANEL.json/CSV`、`KEEP_AUDIT.json`、`GT_AVAILABILITY.json`。
- 面板：30/30 组合 cec_rows=0、manifest_rows=0；keep_files=0、paired=0、no_keep_variant=0；仅单一 plain 设计；全局 113/371 不是面板证据。
- keep：none 不发 keep 指令，proc+opt -full，write_verilog -noattr 只隐藏属性；keep 移除未证实；已列最小反例。
- GT：mappings 目录仅为候选，DFF/PO/PI 对应未核验 → unknown；弱 MIL/结构可达/CEC 不等价功能 GT。
- L_cone 审计已追加边界：group_A 502/11,187 机制探针，不替代四组结论、不与 hoco 287/10,742 横比。
- STATUS：L_cone 收束；no-keep 待重综合与 GT 映射；未综合/CEC/训练。
"""
for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name; bak = H / (name + '.before_panel_fix2')
    if not bak.exists(): shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8')); print('appended', name)
reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-10T15:40:00+08:00,no-keep面板更正+GT边界,heldout_composition_20261110,'
        '只读:coverage0/30;keep审计;GT unknown;0训练,seed42/1/2,hosts_bt31 design,'
        '返回审计_no-keep面板更正_20261110.md,'
        'cec/manifest/keep/no-keep均0/30;keep移除未证;GT unknown\n')
with reg.open('ab') as f: f.write(line.encode('utf-8'))
print('registry')
