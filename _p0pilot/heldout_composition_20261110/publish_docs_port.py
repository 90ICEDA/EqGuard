"""Append docs and registry."""
import shutil
from pathlib import Path
ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); H = ROOT / '_p0pilot/heldout_composition_20261110'
NOTE = """

### 2026-11-10 GT 端口闭合与 keep 字段更正

- 审计：`10.15/00_说明/返回审计_GT端口闭合_20261110.md`；证据 `GT_AVAILABILITY_V3.json`、`KEEP_AUDIT.json`。
- rs232 uart 端口 13：PI 7、PO 5、sys_clk 按时钟排除（excluded_reason=clock）；rows/CSV 128 与 counts 一致（DFF_Q58+DFF_D58+PI7+PO5）。
- 旧“9 PI/4 PO”为错误计数，已在 port_closure 说明变化；tr45 仅宿主示例，面板 30 组合 GT 未建；s38417t100 missing。
- KEEP_AUDIT 增加视图路径/存在/sha256；命令 ready_but_not_run，反例 not_executed；未综合。
"""
for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name; bak = H / (name + '.before_port_close')
    if not bak.exists(): shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8')); print('appended', name)
reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-10T17:00:00+08:00,GT端口闭合,heldout_composition_20261110,'
        '只读:13端口;PI7/PO5;sys_clk排除;keep待跑;0训练,seed42/1/2,hosts_bt31 design,'
        '返回审计_GT端口闭合_20261110.md,'
        'rows128=counts;tr45示例;面板GT未建\n')
with reg.open('ab') as f: f.write(line.encode('utf-8'))
print('registry')
