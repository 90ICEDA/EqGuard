"""Append docs and registry."""
import shutil
from pathlib import Path
ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); H = ROOT / '_p0pilot/heldout_composition_20261110'
NOTE = """

### 2026-11-10 DFF Q/D 端点映射补全

- 审计：`10.15/00_说明/返回审计_DFF端点映射_20261110.md`；证据 `GT_AVAILABILITY_V3.json/CSV`、`KEEP_AUDIT.json`。
- rs232t1000 tr45：DFF_Q 58、DFF_D 58 verified（实例名保留 + Q/D 网名逐条相等）；PI 7、PO 5；tr45 仅宿主示例，面板 30 组合端点 GT 未建。
- 更正旧“13 verified（DFF+PI/PO）”表述；其余宿主 can_attempt，s38417t100 missing。
- keep 视图 hosts_bt2/rs232t1000/rs232t1000__injalpha_d1_s42.v 存在，命令可执行但未跑；反例 not_executed；未综合。
- L_cone 收束不改。
"""
for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name; bak = H / (name + '.before_dff_gt')
    if not bak.exists(): shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8')); print('appended', name)
reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-10T16:45:00+08:00,DFF端点映射补全,heldout_composition_20261110,'
        '只读:58 Q+58 D verified;PI7/PO5;keep待跑;0训练,seed42/1/2,hosts_bt31 design,'
        '返回审计_DFF端点映射_20261110.md,'
        'tr45示例;面板GT未建;keep未执行\n')
with reg.open('ab') as f: f.write(line.encode('utf-8'))
print('registry')
