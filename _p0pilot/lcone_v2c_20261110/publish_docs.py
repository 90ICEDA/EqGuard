"""Append docs and registry."""
import shutil
from pathlib import Path
ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); O = ROOT / '_p0pilot/lcone_v2c_20261110'
NOTE = """

### 2026-11-10 L_cone v2c（group_B 同预算锥组成）

- 审计：`10.15/00_说明/返回审计_Lcone_v2c_20261110.md`；证据 `_p0pilot/lcone_v2c_20261110/`。
- 可用性：abc 200/245、id 199/10120、opt 159/264、aig 166/312、nand 167/2；旧缺 opt/nand 是旧匹配截断，非数据无锥；nand 负锥仅 2。
- 同预算：base/all 均 1116（558/558），members 11779 vs 11680（近似等质量）；all 含 aig 127、nand 2。
- 门禁：node 2.532；cone base 8.45(3.34x)/all 7.97(3.15x)；有限/恢复；0 step。
- 6 次训练：验证 base .246/.254/.293 vs all .230/.237/.289；测试 base−N −.0451、all−N −.0863；all−base 基础 −.0412（0/3）、add +.0337（3/3）。
- 结论：加入 aig/nand 无净增益（基础降、add 略升）；失效范围限 D 锥/cap20/pw10/group_B/200；未训练他线。
"""
for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name; bak = O / (name + '.before_v2c')
    if not bak.exists(): shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8')); print('appended', name)
reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-10T23:55:00+08:00,L_cone v2c,lcone_v2c_20261110,'
        '训练:6次;同预算;0综合,seed42/1/2,group_B,'
        '返回审计_Lcone_v2c_20261110.md,'
        'base/all 1116;all-base base-.0412/add+.0337;无净增益\n')
with reg.open('ab') as f: f.write(line.encode('utf-8'))
print('registry')
