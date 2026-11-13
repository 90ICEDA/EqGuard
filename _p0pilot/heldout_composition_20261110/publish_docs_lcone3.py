"""Append docs, registry, STATUS."""
import json, shutil
from pathlib import Path
ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); H = ROOT / '_p0pilot/heldout_composition_20261110'
NOTE = """

### 2026-11-10 L_cone 检查点更正、评价 V2 与 seed1/2 四臂

- 审计：`10.15/00_说明/返回审计_Lcone三seed_20261110.md`；证据 `CORRECTION_LCONE.json`、`LCONE_EVAL_V2.json`、`SELF_AUDIT_LCONE.json`、`LCONE_SEEDS12.json`、`LCONE_INTERACTION.json`。
- best_resume：模型/优化器在 best step、RNG/completed 在 200 → 仅推理不可恢复；last 可恢复；未覆盖旧文件。
- 评价 V2 补齐 AP/Top/normal 四项/A/B/D-PO 弱 MIL；自审 112+128 字段 0 mismatch（自审≠独立）。
- 资产口径更正：L_cone 实际用 four_group A（502 正例/11,187 锥），非 hoco_A（287/10,742）。
- seed1/2 四臂完成；三种子 I（best）：NC1−N base −0.0126±0.0189（1/3 正）、add +0.0097±0.0178（2/3 正）；NC01−N base −0.0109±0.0176、add −0.0014±0.0048；方向不一致，不称稳定。
- C-only 节点排序崩溃（base .0664/.0235/.0095），仅说明无节点监督不可用，不推断锥项无信号；总损失尺度不可比。
- 未完成：hoco id/opt、no-keep/GT、深度 RF、角色、独立审计；seed1/2 的 Top/A/B/正常/MIL 未逐臂全量落盘。
"""
for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name; bak = H / (name + '.before_lcone_3seed')
    if not bak.exists(): shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8')); print('appended', name)
reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-10T14:25:00+08:00,L_cone三seed与检查点,heldout_composition_20261110,'
        '训练:seed1/2共8次;评价V2;自审PASS;0综合,seed42/1/2,hosts_bt31 train+test,'
        '返回审计_Lcone三seed_20261110.md,'
        'NC1-N base -.0126±.0189(1/3);add +.0097±.0178(2/3);C崩溃\n')
with reg.open('ab') as f: f.write(line.encode('utf-8'))
st = dict(phase='lcone_3seed_done', completed=['checkpoint correction', 'eval V2', 'self-audit PASS', 'seed1/2 8 arms',
          '3-seed I'], not_done=['hoco id/opt', 'no-keep/GT', 'depth/RF', 'role', 'independent audit', 'seed1/2 full V2 fields'])
(H / 'STATUS.json').write_text(json.dumps(st, indent=2), encoding='utf-8')
print('registry+status')
