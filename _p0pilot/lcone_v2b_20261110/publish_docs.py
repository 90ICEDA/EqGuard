"""Append docs and registry."""
import shutil
from pathlib import Path
ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); O = ROOT / '_p0pilot/lcone_v2b_20261110'
NOTE = """

### 2026-11-10 L_cone v2b（group_B 平衡锥）

- 审计：`10.15/00_说明/返回审计_Lcone_v2b_20261110.md`；证据 `_p0pilot/lcone_v2b_20261110/`。
- 旧锥病态：11,187（558/10,629），id 92%；新预算 3000 不可达：BASE 792（396/396）、ALL 1,116（558/558），opt 无 D 锥。
- 门禁：base cone grad 9.95、all 8.99；node 2.558；有限/恢复；0 step。
- 6 次训练完成（N-B 复用 3）；验证 AP base .225/.284/.270 vs all .216/.259/.257。
- 测试：base−N −.0496/−.1000；all−N −.0440/−.0739；all−base +.0056/+.0261（方向不稳）。无稳定增益；停止扩锥。
- 未训练其他主线/未综合/未 CEC/未改标签。
"""
for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name; bak = O / (name + '.before_v2b')
    if not bak.exists(): shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8')); print('appended', name)
reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-10T23:40:00+08:00,L_cone v2b, lcone_v2b_20261110,'
        '训练:6次;门禁通过;0综合,seed42/1/2,group_B,'
        '返回审计_Lcone_v2b_20261110.md,'
        'base792/all1116;base-.0496;all-.044;all-base+.0056;无稳定增益\n')
with reg.open('ab') as f: f.write(line.encode('utf-8'))
print('registry')
