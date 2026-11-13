"""Append docs and registry."""
import shutil
from pathlib import Path
ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); H = ROOT / '_p0pilot/heldout_composition_20261110'
NOTE = """

### 2026-11-10 面板 CEC 40/40 与 GT V4

- 审计：`10.15/00_说明/返回审计_CEC40与GT_V4_20261110.md`；证据 `CEC_STAGE3A/3B.json/CSV`、`PANEL_STATUS.json`、`GT_AVAILABILITY_V4.json/CSV`。
- CEC 参照为对应含木马源视图（非 clean）；3a rs232 8/8 PASS，3b 4宿主 32/32 PASS；总 40/40，unproven=0；无失败/超时。
- PANEL_STATUS：syntheses 40、cec 40/40、gt partial；clean 未用且≠PASS；aig 排除。
- GT：rs232tr45 verified 示例（128 行），s15850/s35932/s38584 can_attempt，s38417t100 missing；面板逐组合 GT 未建。
- 未训练/未新增综合/未改标签。
"""
for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name; bak = H / (name + '.before_cec40')
    if not bak.exists(): shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8')); print('appended', name)
reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-10T22:40:00+08:00,面板CEC40+GT_V4,heldout_composition_20261110,'
        'CEC:40次;40/40 PASS;0训练,seed42/1/2,5宿主 alpha/delta abc/nand,'
        '返回审计_CEC40与GT_V4_20261110.md,'
        '3a8/8;3b32/32;GT partial;s38417 missing\n')
with reg.open('ab') as f: f.write(line.encode('utf-8'))
print('registry')
