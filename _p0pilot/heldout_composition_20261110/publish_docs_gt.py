"""Append docs and registry."""
import shutil
from pathlib import Path
ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); H = ROOT / '_p0pilot/heldout_composition_20261110'
NOTE = """

### 2026-11-10 GT 可映射性审计与 keep 反例定稿

- 审计：`10.15/00_说明/返回审计_GT映射与keep反例_20261110.md`；证据 `GT_AVAILABILITY_V2.json/CSV`、`KEEP_AUDIT.json`。
- mapping JSON 仅 instance->instance（node_alignment），无 Q/D/PO/PI 字段；rs232 示例 TrojanU303->3 dst；4 宿主有 tr42，s38417t100 missing；端点 DFF/PO/PI 全部 unmapped（未做 pin 解析）。
- keep 反例标 not_executed：输入/命令/预期证据/判定标准已定稿，预计 1 次综合 1–3 分钟；未执行。
- 面板 30/30 cec/keep/no-keep 覆盖仍为 0；STATUS 区分盘点完成/GT 部分/反例未执行/综合未启动。
- L_cone 已收束不改；未完成：pin 级映射、s38417t100、keep 反例、成对资产、hoco id/opt、深度 RF、角色、独立审计。
"""
for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name; bak = H / (name + '.before_gt_keep')
    if not bak.exists(): shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8')); print('appended', name)
reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-10T16:00:00+08:00,GT可映射性审计+keep反例定稿,heldout_composition_20261110,'
        '只读:JSON结构;端点unmapped;s38417missing;反例未执行;0训练,seed42/1/2,hosts_bt31 design,'
        '返回审计_GT映射与keep反例_20261110.md,'
        'instance-only;端点0 verified;s38417t100 missing;keep反例not_executed\n')
with reg.open('ab') as f: f.write(line.encode('utf-8'))
print('registry')
