"""Byte-preserving append to master docs (backup first) + registry row."""
import shutil
from pathlib import Path

ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = ROOT / '_p0pilot/four_group_contract_20261109'

NOTE = """

### 2026-11-10 四组三种子交互差（seed42+1/2）

- 审计：`10.15/00_说明/返回审计_四组三种子交互_20261110.md`；证据 `FOUR_EVAL_ALL.json`、`run_{A,B}_{N,NC}[_s1/_s2]/`。
- 已补 seed1/2 各四组 8 次 200 更新；共用 init_s1/s2、T.seed(seed+step)、共同归一化/验证池、200 步冻结采样、11,187 锥（558/10,629）、λ=1/pw=10；未重跑 seed42。
- 测试交互差（best）[NC−N]_B−[NC−N]_A：基础池 +0.0240/+0.0106/+0.0083 → 均值 +0.0143±0.0085（3/3 正）；aig/nand −0.0275/−0.0166/−0.0803 → −0.0414±0.0341（2/3 负）。
- 正常可信节点 FPR（best）：A 组 NC 2/3 降低、B 组 3/3 升高；B 组基线更低；全物理/视图报警在 JSON。
- best/last 分列；源/recipe 不作额外种子；未做显著性；深度/RF 仍 null，不预设展开因果；A/B 实际召回在 JSON，未单独制表。
- 结论：基础池正交互小但可重复；aig/nand 负交互多数可重复但 seed 间不一致；保留负结果，不扩配置。
"""

for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name
    bak = OUT / (name + '.before_four_3seed')
    if not bak.exists():
        shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8'))
    print('appended', name)

reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-10T02:20:00+08:00,四组三种子交互,four_group_contract_20261109,'
        '训练:seed1/2共8次;评价FOUR_EVAL_ALL;0 SAT;0 EQ,seed42/1/2,hosts_bt31 trans+orig,'
        '返回审计_四组三种子交互_20261110.md,'
        'base +0.0143±0.0085(3/3);add -0.0414±0.0341(2/3);未补其他种子\n')
with reg.open('ab') as f:
    f.write(line.encode('utf-8'))
print('registry appended')
