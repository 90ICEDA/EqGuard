"""Byte-preserving append to master docs (backup first) + registry row."""
import shutil
from pathlib import Path

ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = ROOT / '_p0pilot/heldout_recipe_v5_eval2_20261109'

NOTE = """

### 2026-11-09 held-out v5 最小离线闭环（不训练）

- 审计：`10.15/00_说明/返回审计_heldout_v5闭环_20261109.md`；证据 `_p0pilot/heldout_recipe_v5_eval2_20261109/CLOSURE.json`、`PER_SOURCE_DELTA.csv`、`*_testpred.npz`。
- 已见 recipe 纳入全部 4 个（含 id/opt）；留出与已见在 5 个含木马源上完全匹配；撤销“源集合未完全匹配”。
- 留出 vs 已见（best）：abc N/NC −0.0977/−0.0931（NC 略缩），aig +0.0875/+0.0404（NC 缩），nand −0.1553/−0.1863（NC 扩大）；撤销“只有 abc 缩小”“aig 已见同样受损”。
- 正常 FPR（95% 冻结阈值）：40/40 ctl 视图报警=1.0；可信正常节点 FPR 0.24–0.44，全物理 0.27–0.41；NC 在 abc 降低、aig/nand 升高；新增正常区域因缺可靠映射未报；角色 NA。
- 逐源差 30 行：10 正/20 负，平均 +0.0005；逐 recipe AP/Top-1/5 见 JSON；A/B 分列，abc 实际召回≠目标，不写严格等召回。
- 补 seed1/2 建议：12 次约 60 分钟 GPU + 1.5–2 小时评价；固定判据（全折全臂、不筛折、负收益保留、源匹配宏 AP 主指标）；当前建议先不补。
"""

for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name
    bak = OUT / (name + '.before_closure')
    if not bak.exists():
        shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8'))
    print('appended', name)

reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-09T22:00:00+08:00,heldout v5最小离线闭环,heldout_recipe_v5_eval2_20261109,'
        '纯推理:12检查点;5recipe;正常FPR;逐源差;0训练,seed42,hosts_bt31 trans_test,'
        '返回审计_heldout_v5闭环_20261109.md,'
        'abc/aig缩差;nand扩大;normal40/40报警;逐源10正20负;建议暂不补seed1/2\n')
with reg.open('ab') as f:
    f.write(line.encode('utf-8'))
print('registry appended')
