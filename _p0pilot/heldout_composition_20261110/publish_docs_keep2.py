"""Append docs and registry."""
import shutil
from pathlib import Path
ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); H = ROOT / '_p0pilot/heldout_composition_20261110'
NOTE = """

### 2026-11-10 keep pilot 两宿主闭环

- 审计：`10.15/00_说明/返回审计_keep两宿主pilot_20261110.md`；证据 `KEEP_AUDIT.json`、`STATUS.json`、`keepab_gtcheck*/`。
- 状态：command_status=executed_pilot；keep_removal_scope 两宿主/1视图/abc/3方案/各3次；全局 keep_removal_pilot_supported=true；STATUS 改为 panel-wide/CEC/GT 待办。
- 第二宿主 s15850t100：none anchor_surv 0.000 vs cur/bnd 0.444；dffq 1.0；out_insts 2644 vs 2530；无 keep 字符串；与 rs232 一致。
- 面板合同：no-keep=none、keep=cur、bnd 敏感性；30×2=60 次综合，CEC 另计；不跑面板、不把 clean 当 CEC PASS。
- 未训练/未 CEC/未改标签。
"""
for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name; bak = H / (name + '.before_keep2')
    if not bak.exists(): shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8')); print('appended', name)
reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-10T17:55:00+08:00,keep两宿主pilot,heldout_composition_20261110,'
        '综合:第二宿主3次;skip-cec;两宿主一致;0训练,seed42/1/2,s15850 injalpha abc,'
        '返回审计_keep两宿主pilot_20261110.md,'
        'anchor 0 vs .444;60次待跑;CEC未跑\n')
with reg.open('ab') as f: f.write(line.encode('utf-8'))
print('registry')
