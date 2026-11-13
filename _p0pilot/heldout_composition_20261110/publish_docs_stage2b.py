"""Append docs and registry."""
import shutil
from pathlib import Path
ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); H = ROOT / '_p0pilot/heldout_composition_20261110'
NOTE = """

### 2026-11-10 统一指标 + keep 面板 2b（20/20 supported）

- 审计：`10.15/00_说明/返回审计_keep阶段2b_20261110.md`；证据 `PANEL_STATUS.json`、`KEEP_STAGE2B.json/CSV`、`METRIC_SPEC.md`、`METRIC_RECHECK.json`。
- 统一指标：仅 gate/DFF，canonical 9 类，anchor 前缀 Trojan/Ctl，disturbance_L1=Σ|Δtype|；stage1/2a 重算 0 mismatch。
- 阶段 2a 4/4 复核通过；阶段 2b 16 组合/32 次综合全部 yosys_rc=0，16/16 supported。
- 面板 20/20 supported、40 次综合；aig 排除（not_usable，不是无效应）；CEC/面板 GT 未做；s38417t100 mapping missing 单列。
- 未训练/未改标签/未跑 CEC。
"""
for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name; bak = H / (name + '.before_stage2b')
    if not bak.exists(): shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8')); print('appended', name)
reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-10T21:30:00+08:00,keep面板2b,heldout_composition_20261110,'
        '综合:32次;20/20 supported;0训练,seed42/1/2,4宿主 alpha/delta abc/nand,'
        '返回审计_keep阶段2b_20261110.md,'
        '16/16+4/4;no anchor0;cur>0;DFF0;40次完成\n')
with reg.open('ab') as f: f.write(line.encode('utf-8'))
print('registry')
