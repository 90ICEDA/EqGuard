"""Append docs and registry (honest failure notes)."""
import shutil
from pathlib import Path
ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); O = ROOT / '_p0pilot/lcone_v2c_20261110'
NOTE = """

### 2026-11-10 nand 归因、独立评价锥与 λ0.1

- 审计：`10.15/00_说明/返回审计_nand归因与lambda01_20261110.md`；证据 `LCONE_V2C_ATTRIBUTION.json/CSV`、`EVAL_CONE_REPORT.json`、`lambda01/`。
- nand 训练仅 2 锥，标 not_evaluable；all−base：base −.0412(0/3)、add +.0337(3/3)，净负/不稳定。
- 独立评价锥：abc/id/opt 正锥 leftover=0（不足），PO 可用；未硬造。
- λ0.1 6 次完成：验证 base .264/.251/.319、all .254/.227/.303；测试 base .288/.212/.389、all .290/.199/.362。
- 相对 λ1（历史）：base 2/3 升、all 3/3 升；但 **λ0.1 vs N 与 SD 未计算**。
- 过程错误：两次补丁失败导致首轮 λ1 重跑覆盖 v2c 检查点、eval 首次覆盖 LCONE_V2C_RESULTS；λ1 仅存历史打印值；未重训补救；不补造。
- 未启动 PO 训练锥/不改 nand 标签；未训练其他主线。
"""
for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name; bak = O / (name + '.before_l01')
    if not bak.exists(): shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8')); print('appended', name)
reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-11T00:30:00+08:00,nand归因+lambda0.1,lcone_v2c_20261110,'
        '训练:6次;λ0.1;过程覆盖事故;0综合,seed42/1/2,group_B,'
        '返回审计_nand归因与lambda01_20261110.md,'
        'nand not_evaluable;λ0.1 base .288/.212/.389;all .290/.199/.362;λ1结果被覆盖\n')
with reg.open('ab') as f: f.write(line.encode('utf-8'))
print('registry')
