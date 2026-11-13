"""Append docs, registry, STATUS."""
import json, shutil
from pathlib import Path
ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); H = ROOT / '_p0pilot/heldout_composition_20261110'
NOTE = """

### 2026-11-10 L_cone 评价闭环收束

- 审计：`10.15/00_说明/返回审计_Lcone评价闭环_20261110.md`；证据 `CORRECTION_LCONE_FULL.json`、`LCONE_EVAL_V3.json`、`SELF_AUDIT_LCONE_V3.json`、`LCONE_INTERACTION_V3.json`。
- 24 个 resume 按规则判定：N/C 的 best（best_step=200）可恢复；NC1/NC01 best（<200）仅推理；last 全部可恢复；旧文件保留。
- V3 覆盖 24 状态，val_common 阈值，资产为 four_group A（502/11,187，非 hoco）；自审 768 项 0 mismatch，PASS（自审≠独立）。
- 三种子 I：NC1−N base −0.0126±0.0189（1/3 正）、add +0.0097±0.0178（2/3 正）；NC01−N base −0.0109±0.0176、add −0.0014±0.0048；方向不一致，不称稳定；λ1/λ0.1 差异小。
- C-only 节点排序崩溃（.0664/.0811/.0580），只作无节点监督对照，不推断锥项无信号；总损失尺度不可比；与 hoco 不横比。
- 收束：不补种子/臂；下一主线仅准备 no-keep 成对资产/端点 GT；hoco id/opt、深度 RF、角色待办。
"""
for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name; bak = H / (name + '.before_lcone_close')
    if not bak.exists(): shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8')); print('appended', name)
reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-10T14:55:00+08:00,L_cone评价闭环收束,heldout_composition_20261110,'
        '纯离线:24状态V3;自审768项;0训练,seed42/1/2,hosts_bt31 train+test,'
        '返回审计_Lcone评价闭环_20261110.md,'
        'NC1-N base -.0126±.0189(1/3);add +.0097±.0178(2/3);C崩溃\n')
with reg.open('ab') as f: f.write(line.encode('utf-8'))
st = dict(phase='lcone_closed', completed=['24 ckpt correction', 'LCONE_EVAL_V3', 'self-audit 768 PASS',
          '3-seed I', 'Lcone closed'], not_done=['independent audit', 'no-keep pairs/GT', 'hoco id/opt', 'depth/RF', 'role'])
(H / 'STATUS.json').write_text(json.dumps(st, indent=2), encoding='utf-8')
print('registry+status')
