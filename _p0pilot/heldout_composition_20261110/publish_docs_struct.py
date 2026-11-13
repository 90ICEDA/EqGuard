"""Append docs and registry."""
import shutil
from pathlib import Path
ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); H = ROOT / '_p0pilot/heldout_composition_20261110'
NOTE = """

### 2026-11-10 结构/单元级指标重算与 aig 判定

- 审计：`10.15/00_说明/返回审计_结构指标重算_20261110.md`；证据 `STRUCT_METRICS.csv/JSON`、`KEEP_STAGE1.json`、`KEEP_AUDIT.json`、`STATUS.json`。
- 复用 12 次产物，0 新综合。abc/nand：none anchor 0 vs cur 5–12 → 结构支持；aig：none/cur anchor 单元均 0，文本 0.444 来自网名伪影。
- aig 结论 B（text invalid, structure same）；stage1 结构支持 4/6；面板不启动；剩余 24 组合（48 次）仍待方案。
- 未训练/CEC/改标签；结构指标非功能 GT。
"""
for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name; bak = H / (name + '.before_struct')
    if not bak.exists(): shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8')); print('appended', name)
reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-10T19:20:00+08:00,结构指标重算,heldout_composition_20261110,'
        '只读:0综合;abc/nand支持;aig same;0训练,seed42/1/2,rs232t1000 alpha/delta,'
        '返回审计_结构指标重算_20261110.md,'
        '4/6结构支持;aig anchor0v0;面板停\n')
with reg.open('ab') as f: f.write(line.encode('utf-8'))
print('registry')
