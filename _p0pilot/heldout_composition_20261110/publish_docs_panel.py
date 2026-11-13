"""Append docs, registry, STATUS."""
import json, shutil
from pathlib import Path
ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); H = ROOT / '_p0pilot/heldout_composition_20261110'
NOTE = """

### 2026-11-10 L_cone 文档更正与 no-keep 盘点

- 审计：`10.15/00_说明/返回审计_Lcone更正与no-keep盘点_20261110.md`；证据 `LCONE_I_RECHECK.json`、`NO_KEEP_PANEL.json/CSV`。
- 旧 L_cone 表追加更正：N seed1/2 .2913/.3021→.2731/.3448；C .0235/.0095→.0811/.0580；旧表作废，V3 为准；SAT 文档未引用旧数值，无需改。
- I 复核与 V3 一致：NC1−N base −0.0126±0.0189（1/3 正）、add +0.0097±0.0178（2/3 正）；NC01−N base −0.0109±0.0176、add −0.0014±0.0048；方向不一致，不称稳定；收束。
- no-keep：5 宿主×2 注入×3 recipe=30 组合，0 成对、30 需重综合；cec 113 行/10 空、manifest 371 行/371 clean=True（clean≠CEC PASS）；keep 移除未证实；端点 GT 可映射性 unknown；未综合。
"""
for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name; bak = H / (name + '.before_panel')
    if not bak.exists(): shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8')); print('appended', name)
reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-10T15:15:00+08:00,L_cone更正+no-keep盘点,heldout_composition_20261110,'
        '只读:旧表更正;I复核;30组合盘点;0训练,seed42/1/2,hosts_bt31 trans_test+design,'
        '返回审计_Lcone更正与no-keep盘点_20261110.md,'
        '0成对/30需综合;cec113/10;manifest371/371;未综合\n')
with reg.open('ab') as f: f.write(line.encode('utf-8'))
st = dict(phase='lcone_corrected_nokeep_inventory', status='training_eval_done_self_audit_pass_independent_pending',
          completed=['old table correction', 'I recheck', 'panel 30 combos', 'cec/clean verification', 'STATUS'],
          not_done=['keep removal proof', 'endpoint GT mapping', 'paired no-keep assets', 'hoco id/opt', 'depth/RF', 'role', 'independent audit'],
          note='no-keep inventory only; no synthesis/CEC')
(H / 'STATUS.json').write_text(json.dumps(st, indent=2), encoding='utf-8')
print('registry+status')
