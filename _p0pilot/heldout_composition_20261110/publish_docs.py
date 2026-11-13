"""Byte-preserving append + registry + STATUS updates."""
import json, shutil
from pathlib import Path

ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
F = ROOT / '_p0pilot/four_group_contract_20261109'
H = ROOT / '_p0pilot/heldout_composition_20261110'

NOTE = """

### 2026-11-10 V5 更正与 held-out 组成资产/L_cone 接口

- 审计：`10.15/00_说明/返回审计_V5更正与组成资产_20261110.md`；产物 `FOUR_EVAL_V5_FIXED.json`、`heldout_composition_20261110/`。
- V5：strict_full→strict_evaluable；测试宿主 13 源、仅 5 含木马源有正例；可评价基础 4/add 5；12/13 仅存在性诊断；source_recipe=13 源（66 仅训练源）；52 行逐源交互独立复算 mismatch=0；SELF_AUDIT PASS（非独立审计）。
- h=abc 资产：A 106 视图/358,012 节点/154 辅助；B 190/1,072,063/154；66 源；配额 287/步；200 步索引；共同归一化 sha ec8fded7；val id/opt 26 视图/277,554；锥 A/B 各 10,742（358/10,384）；A/B 门禁 node/cone grad 2.847/1.854、2.641/2.353，0 step，恢复通过；反例通过。
- L_cone：四臂 runner + smoke（1 步不更新）完成，分项损失记录；N/NC1/NC01/C 总损失 1.178/2.005/1.267/0.833；未跑 200。
- 未完成：4×200、独立审计、no-keep 成对/GT、深度 RF、h=id/opt 折。
"""

for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name
    bak = F / (name + '.before_v5fix_hoco')
    if not bak.exists():
        shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8'))
    print('appended', name)

reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-10T13:10:00+08:00,V5更正+组成资产+L_cone接口,four_group_contract_20261109+heldout_composition_20261110,'
        '只读:V5字段;hoco资产;A/B门禁;L_cone smoke;0训练,seed42,hosts_bt31 train+val,'
        '返回审计_V5更正与组成资产_20261110.md,'
        'V5 52行交互PASS;A/B hoco门禁通过;L_cone smoke 4臂;未跑200\n')
with reg.open('ab') as f:
    f.write(line.encode('utf-8'))

for target, phase, completed in (
    (F, 'v5_fixed_hoco_assets_ready', ['strict_evaluable rename', '52 interaction rows', 'self-audit PASS AP+interactions']),
    (H, 'assets_and_gates_ready_no_training', ['hoco A/B graphs', 'shared normalization', '200-step sup', 'cones 10742',
                                               'val 26 views', 'GATE A/B passed', 'lcone smoke 4 arms'])):
    st = dict(phase=phase, completed=completed,
              not_done=['4x200 training', 'independent audit', 'no-keep pairs/GT', 'depth/RF', 'h=id/opt fold'])
    (target / 'STATUS.json').write_text(json.dumps(st, indent=2), encoding='utf-8')
print('registry+status appended')
