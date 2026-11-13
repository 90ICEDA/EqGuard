"""Byte-preserving append to master docs (backup first) + registry row + STATUS/contract stubs."""
import json, shutil
from pathlib import Path

ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = ROOT / '_p0pilot/four_group_contract_20261109'

NOTE = """

### 2026-11-10 四组评价 V4 与 no-keep 只读核验

- 审计：`10.15/00_说明/返回审计_四组评价V4与no-keep核验_20261110.md`；证据 `FOUR_EVAL_V4.json`、`SELF_AUDIT_V4.json`、`NO_KEEP_VERIFY.json`。
- V4：A 保存验证实际召回/FPR、测试实际召回/FPR/阈值/分母；正常四项分开且零支持 NA；严格源按数据求交（基础 4 源、aig/nand 5 源），撤销“一律四源”；逐源 NC−N 与 I 分列。
- 自审 PASS 仅覆盖阈值、val recall/FPR、NA 规则（24 状态）；全量 AP/交互独立复算未做，独立审计未完成，不能写“评价闭环完成”。
- no-keep 核验：cec 113 行/10 空、manifest 371 行/371 clean=True 证实（clean≠CEC PASS）；30 组/14 相同、128/317、30 keep 文件均未证实（实际 keep 路径 5、plain 371、名称含 keep 0）；面板三源在目标 recipe 计数全 0，面板作废；keep 移除与端点 GT 未核验。
- 结论：评价字段补齐但仅自审；no-keep 合同不可执行，先重建面板并核实 keep/GT。未执行综合/CEC/训练。
"""

for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name
    bak = OUT / (name + '.before_v4_nokeep')
    if not bak.exists():
        shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8'))
    print('appended', name)

reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-10T11:50:00+08:00,四组评价V4+no-keep核验,four_group_contract_20261109,'
        '只读:A字段/四项正常/严格源/逐源交互;no-keep计数;0训练,seed42/1/2,hosts_bt31 trans_test,'
        '返回审计_四组评价V4与no-keep核验_20261110.md,'
        '自审PASS(限字段);keep计数未证实;面板源0可用;合同未执行\n')
with reg.open('ab') as f:
    f.write(line.encode('utf-8'))

status = dict(phase='eval_v4_and_nokeep_verification',
              status='self_audit_partial_scope_independent_pending_nokeep_blocked',
              completed=['A val/test actual recall/FPR', '4 normal fields with NA', 'data-derived strict sets',
                         'per-source interaction', 'cec/manifest counts', 'keep/panel counts rechecked'],
              not_done=['full independent AP/interaction audit', 'no-keep panel rebuild', 'keep removal proof',
                        'endpoint GT verification', 'depth/RF', 'role recall'],
              invalidated=['V3 A fields', 'single view_alarm', 'strict four-source blanket', 'old keep panel'])
(OUT / 'STATUS_V4.json').write_text(json.dumps(status, indent=2), encoding='utf-8')
print('registry+status appended')
