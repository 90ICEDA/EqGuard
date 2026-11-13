"""Append docs and registry."""
import shutil
from pathlib import Path
ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); H = ROOT / '_p0pilot/heldout_composition_20261110'; D = ROOT / '_p0pilot/p0p1_contracts_20261110'
NOTE = """

### 2026-11-10 P0/P1/P2/P3 第一次交付

- 审计：`10.15/00_说明/返回审计_P0P1P2P3交付_20261110.md`；证据 `_p0pilot/p0p1_contracts_20261110/`、`CHECK_CONSISTENCY.json`、`GT_AVAILABILITY_V5.json/CSV`。
- A：6 次 N/NC×3seed 全部冻结项与 L_cone 一致 → 可复用，新训练=0；配置矩阵/锥标签/指标合同已落盘。
- C：v5 18 次 not_reusable（三折 vs h=abc 单折）；hoco 12 次可复用 → 新训练=0；评价缺口已列。
- B：CEC 40/40、PANEL 20/40、GT V5（5 宿主，s38417 missing，panel_gt not_built）；功能影响 GT 与区域标签分开，CEC 不证锥影响。
- P3：CHECK_CONSISTENCY PASS（40 CEC、20/40 面板、GT 5 行、无禁用字符串）。
- 未训练/未排队/未新增综合/未 CEC/未改标签。
"""
for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name; bak = D / (name + '.before_p0p1')
    if not bak.exists(): shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8')); print('appended', name)
reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-10T23:10:00+08:00,P0P1P2P3交付,p0p1_contracts_20261110,'
        '合同/矩阵/GT;一致性PASS;0训练,seed42/1/2,hosts_bt31,'
        '返回审计_P0P1P2P3交付_20261110.md,'
        'A复用6;C hoco复用12;GT V5;CHECK PASS\n')
with reg.open('ab') as f: f.write(line.encode('utf-8'))
print('registry')
