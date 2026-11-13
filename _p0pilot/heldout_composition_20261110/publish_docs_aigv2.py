"""Append docs and registry."""
import shutil
from pathlib import Path
ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); H = ROOT / '_p0pilot/heldout_composition_20261110'
NOTE = """

### 2026-11-10 aig 差分清理与面板 20 组合

- 审计：`10.15/00_说明/返回审计_aig清理_20261110.md`；证据 `AIG_STRUCT_DIFF_V2.json/CSV`、`KEEP_AUDIT.json`、`STATUS.json`。
- 清理后 alpha 522/523 inst、599/602 nets、INV −1；delta 522/523、599/599、INV −1（预期 0，已如实记录）；无 anchor 定位。
- 判定 aig_not_usable_for_keep_ablation；aig 从面板排除；面板改 20 组合（5 宿主×2 注入×abc/nand）×none/cur=40 次综合，未启动；CEC 未跑。
- 删除 15/14 表述；结构差异非功能 GT；0 新综合；未训练。
"""
for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name; bak = H / (name + '.before_aig_v2')
    if not bak.exists(): shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8')); print('appended', name)
reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-10T20:20:00+08:00,aig差分清理,heldout_composition_20261110,'
        '只读:INV-1;aig不可用;面板20;0综合,seed42/1/2,rs232t1000 aig,'
        '返回审计_aig清理_20261110.md,'
        'alpha/delta INV-1;无anchor定位;40次待跑\n')
with reg.open('ab') as f: f.write(line.encode('utf-8'))
print('registry')
