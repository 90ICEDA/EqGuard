"""Append docs and registry."""
import shutil
from pathlib import Path
ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); H = ROOT / '_p0pilot/heldout_composition_20261110'
NOTE = """

### 2026-11-10 no-keep 面板阶段 1（rs232t1000，6 组合）

- 审计：`10.15/00_说明/返回审计_keep阶段1_20261110.md`；证据 `generate_trans/keepab_panel_stage1/`、`KEEP_STAGE1_TABLE.csv`、`KEEP_STAGE1.json`、`KEEP_AUDIT.json`。
- 12 次综合（none/cur × alpha/delta × abc/aig/nand），--skip-cec，全部 yosys_rc=0/conv rc=0。
- 4/6 支持：abc/nand 两注入 none anchor≈0（0/0.048）vs cur 0.444/0.476；**aig 两注入不一致**（none 0.444/0.381）。
- 撤回 keep_removal_pilot_supported（两宿主 pilot 仅 abc/单视图）；none 非 recipe 无关，no-keep 需按 recipe/注入分层；剩余 24 组合（48 次综合）暂不启动。
- CEC 未跑；clean≠CEC PASS；面板 GT 未建；未训练。
"""
for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name; bak = H / (name + '.before_stage1')
    if not bak.exists(): shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8')); print('appended', name)
reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-10T18:25:00+08:00,no-keep阶段1,heldout_composition_20261110,'
        '综合:12次;4/6支持;aig不一致;skip-cec;0训练,seed42/1/2,rs232t1000 alpha/delta abc/aig/nand,'
        '返回审计_keep阶段1_20261110.md,'
        'none anchor 0/.048 vs cur .444/.476;aig .444/.381;面板停\n')
with reg.open('ab') as f: f.write(line.encode('utf-8'))
print('registry')
