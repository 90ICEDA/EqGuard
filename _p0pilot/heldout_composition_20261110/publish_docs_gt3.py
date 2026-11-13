"""Append docs and registry."""
import shutil
from pathlib import Path
ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); H = ROOT / '_p0pilot/heldout_composition_20261110'
NOTE = """

### 2026-11-10 GT 端点级映射尝试与 keep 命令核对

- 审计：`10.15/00_说明/返回审计_GT端点与keep命令_20261110.md`；证据 `GT_AVAILABILITY_V3.json/CSV`、`KEEP_AUDIT.json`。
- rs232t1000 tr45 端点尝试：13 条 verified（DFF Q/D + PI/PO，含源/目标行号）；其余宿主 s15850/s35932/s38584 can_attempt、s38417t100 missing；未把 not_attempted 写成 unmapped。
- keep 命令参数已核（host/views/recipes/schemes/out/timeout/skip-cec），command_status=ready_but_not_run；反例 not_executed；未综合。
- 面板 30/30 覆盖仍为 0；L_cone 收束不改。
"""
for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name; bak = H / (name + '.before_gt_v3')
    if not bak.exists(): shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8')); print('appended', name)
reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-10T16:20:00+08:00,GT端点映射+keep命令核对,heldout_composition_20261110,'
        '只读:rs232 tr45 13端点verified;s38417 missing;反例未执行;0训练,seed42/1/2,hosts_bt31 design,'
        '返回审计_GT端点与keep命令_20261110.md,'
        '13 verified;can_attempt3;missing1;keep命令待跑\n')
with reg.open('ab') as f: f.write(line.encode('utf-8'))
print('registry')
