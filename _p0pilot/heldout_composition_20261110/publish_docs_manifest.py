"""Append docs and registry."""
import shutil
from pathlib import Path
ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); H = ROOT / '_p0pilot/heldout_composition_20261110'
NOTE = """

### 2026-11-10 阶段2b manifest 重建与面板冻结

- 审计：`10.15/00_说明/返回审计_keep_manifest重建_20261110.md`；证据 `MANIFEST_STAGE2B.csv`、`PANEL_STATUS.json`、`CEC_TEXT_CHECK.json`。
- manifest 32 行（4宿主×2注入×2recipe×2scheme），rc=0/conv>0/ok；cec=skipped；sha 2b280e94…；旧 manifest 标 SUPERSEDED。
- 指标复核 16 行 0 mismatch；20/20 supported（2a4+2b16）；面板冻结；CEC/GT 未跑；clean≠CEC PASS。
- 旧 sha 5dbf0e62 已清除；aig 排除为指标不可用。
- 未训练/未新增综合/未改标签。
"""
for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name; bak = H / (name + '.before_manifest')
    if not bak.exists(): shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8')); print('appended', name)
reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-10T22:00:00+08:00,阶段2b manifest重建,heldout_composition_20261110,'
        '只读:32行;0 mismatch;CEC skipped;0训练,seed42/1/2,4宿主,'
        '返回审计_keep_manifest重建_20261110.md,'
        'sha2b280e94;20/20;面板冻结\n')
with reg.open('ab') as f: f.write(line.encode('utf-8'))
print('registry')
