"""Append docs, registry, STATUS."""
import json, shutil
from pathlib import Path
ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); H = ROOT / '_p0pilot/heldout_composition_20261110'
NOTE = """

### 2026-11-10 hoco 检查点更正与三 seed

- 审计：`10.15/00_说明/返回审计_hoco三seed与检查点_20261110.md`；证据 `CORRECTION_CHECKPOINTS.json`、`HOCO_EVAL_V2.json`、`SELF_AUDIT_HOCO.json`、`INTERACTION_3SEED.json`。
- 检查点：best 的模型/优化器在 best step，但 RNG/完成步在 200 → 仅推理不可直接恢复；last 可恢复；24 文件字段已枚举，旧文件未覆盖。
- seed1/2 四组 8 次完成；三种子验证 AP：42 .2154/.1974/.1220/.1050；1 .2161/.2357/.1519/.1806；2 .3363/.2780/.2316/.2088（A-N/A-NC/B-N/B-NC）。
- 三种子 I（best）：基础 −0.0274/+0.0605/−0.0314 → 均值 +0.0006±0.0519（1/3 正）；aig/nand +0.0283/−0.0143/−0.0451 → −0.0104±0.0368（1/3 正）；方向不一致，不称稳定。
- 自审 PASS 仅覆盖逐 recipe AP/base-add 宏；id/opt 折、no-keep/GT、深度 RF、角色、独立审计未完成。
"""
for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name; bak = H / (name + '.before_hoco_3seed')
    if not bak.exists(): shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8')); print('appended', name)
reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-10T14:05:00+08:00,hoco三seed与检查点,heldout_composition_20261110,'
        '训练:seed1/2共8次;评价V2;自审;0综合,seed42/1/2,hosts_bt31 train+test,'
        '返回审计_hoco三seed与检查点_20261110.md,'
        'I base +.0006±.0519(1/3);add -.0104±.0368(1/3);best不可恢复\n')
with reg.open('ab') as f: f.write(line.encode('utf-8'))
st = dict(phase='hoco_3seed_done', completed=['checkpoint correction', 'HOCO_EVAL_V2', 'seed1/2 8 runs',
          'self-audit AP', '3-seed I'], not_done=['id/opt fold', 'full audit', 'no-keep/GT', 'depth/RF', 'role'])
(H / 'STATUS.json').write_text(json.dumps(st, indent=2), encoding='utf-8')
print('registry+status')
