"""Append docs and registry."""
import shutil
from pathlib import Path
ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); O = ROOT / '_p0pilot/lcone_v2c_20261110'
NOTE = """

### 2026-11-10 λ0.1 证据修复与 L_cone 关闭

- 审计：`10.15/00_说明/返回审计_Lcone最终结论_20261110.md`；证据 `LCONE_FINAL_OFFLINE.json`、`LCONE_CLOSURE.md`。
- N-B 离线重算完成（不再需重训）；λ0.1 vs N：base −.0273±.0208（0/3）、add −.0729±.0171（0/3）；all−base：base −.0127（0/3）、add +.0193（3/3）。
- 结论：L_cone 无稳定增益，关闭；不扫其他 λ/pos_weight/PO 训练锥/补 seed。
- λ1 检查点/JSON 被覆盖，historical_not_recomputable；LCONE_V2C_RESULTS 标 INVALID，λ0.1 结果另存。
- nand 仅 2 锥不可评价；add 正效应主要来自 aig 127 锥；机制见 closure。
- 未训练/未综合/未 CEC/未改标签。
"""
for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name; bak = O / (name + '.before_final')
    if not bak.exists(): shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8')); print('appended', name)
reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-11T01:10:00+08:00,L_cone最终结论,lcone_v2c_20261110,'
        '只读:N重算;λ0.1关闭;0训练,seed42/1/2,group_B,'
        '返回审计_Lcone最终结论_20261110.md,'
        'base-.0273/add-.0729(0/3);all-base add+.0193;闭合\n')
with reg.open('ab') as f: f.write(line.encode('utf-8'))
print('registry')
