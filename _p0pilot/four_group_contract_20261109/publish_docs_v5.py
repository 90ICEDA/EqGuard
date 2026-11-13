"""Byte-preserving append + registry + STATUS."""
import json, shutil
from pathlib import Path

ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = ROOT / '_p0pilot/four_group_contract_20261109'

NOTE = """

### 2026-11-10 V5 评价修正与设计预注册

- 审计：`10.15/00_说明/返回审计_V5评价与设计预注册_20261110.md`；证据 `FOUR_EVAL_V5.json`、`SELF_AUDIT_V5.json`、`NO_KEEP_DIRS.json`。
- V5 由 eval_v5.py 可复现；source_recipe 覆盖全部 66 源，逐源交互保存；严格匹配拆 full-source（基础 12/add 13）与 trojan-only（基础 4/add 5，诊断）；A 字段与四项正常指标保留；自审 PASS 仅覆盖逐视图 AP/recipe 宏。
- V4 失效：5 源矩阵、单一严格集合、A/正常字段缺失。
- no-keep 目录级：5 宿主目录、373 文件、18 组合各 1 文件（无 keep/no-keep 成对）；cec 113/10 空、manifest 371/371 clean=True（clean≠CEC PASS）；noattr 存在但移除未证；GT 路径 8 类未逐项映射。
- 设计合同：HELDOUT_COMPOSITION_CONTRACT_20261110（h=abc 单折×组成×监督，4×200 探索/12×200 正式）、LCONE_MECHANISM_CONTRACT_20261110（N/λ1/λ0.1/C-only，4×200/12×200）；均未执行。
- 未完成：全量交互独立复算、keep 移除证据、GT 映射、成对 no-keep 资产、深度/RF、角色。
"""

for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name
    bak = OUT / (name + '.before_v5_design')
    if not bak.exists():
        shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8'))
    print('appended', name)

reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-10T12:05:00+08:00,V5评价修正与设计预注册,four_group_contract_20261109,'
        '只读:66源矩阵;full/trojan严格;no-keep计数;两份合同;0训练,seed42/1/2,hosts_bt31 trans_test+design,'
        '返回审计_V5评价与设计预注册_20261110.md,'
        'V5自审PASS(AP);18组合无成对;合同未执行\n')
with reg.open('ab') as f:
    f.write(line.encode('utf-8'))

status = dict(phase='v5_eval_and_design_prereg',
              status='v5_self_audit_pass_ap_scope_design_only',
              completed=['66-source matrix', 'full/trojan strict split', 'A/normal fields', 'V5 AP self-audit',
                         'nokeep directory counts', 'two design contracts'],
              not_done=['full interaction independent audit', 'keep removal proof', 'GT mapping',
                        'paired no-keep assets', 'depth/RF', 'role'],
              contracts=['HELDOUT_COMPOSITION_CONTRACT_20261110.md', 'LCONE_MECHANISM_CONTRACT_20261110.md'])
(OUT / 'STATUS_V5.json').write_text(json.dumps(status, indent=2), encoding='utf-8')
print('registry+status appended')
