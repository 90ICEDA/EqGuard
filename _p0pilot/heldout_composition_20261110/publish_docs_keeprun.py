"""Append docs and registry."""
import shutil
from pathlib import Path
ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); H = ROOT / '_p0pilot/heldout_composition_20261110'
NOTE = """

### 2026-11-10 最小 keep 移除反例执行

- 审计：`10.15/00_说明/返回审计_keep反例执行_20261110.md`；证据 `KEEP_AUDIT.json`、`generate_trans/keepab_gtcheck/`。
- 1 宿主 1 视图 3 方案：yosys_rc=0、convert rc=0；none anchor_surv 0.000 vs cur/bnd 0.444；dffq 均 .916；out_insts 274 vs 273；conv 网表无 keep 字符串。
- 结论：keep_removal_proven=true（本宿主/视图/recipe）；no-keep=none、keep=cur（bnd 敏感性），30 组合×2=60 次综合待跑，CEC 未跑。
- --skip-cec；clean≠CEC PASS；tr45 示例保留，面板 GT 未建；未训练。
"""
for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name; bak = H / (name + '.before_keep_run')
    if not bak.exists(): shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8')); print('appended', name)
reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-10T17:25:00+08:00,keep反例执行,heldout_composition_20261110,'
        '综合:3次;skip-cec;keep_removal_proven;0训练,seed42/1/2,rs232t1000 injalpha abc,'
        '返回审计_keep反例执行_20261110.md,'
        'anchor 0.000 vs .444;60次待跑;CEC未跑\n')
with reg.open('ab') as f: f.write(line.encode('utf-8'))
print('registry')
