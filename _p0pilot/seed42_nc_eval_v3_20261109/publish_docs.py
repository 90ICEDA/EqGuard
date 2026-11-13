"""Byte-preserving append to master docs (backup first) + registry row."""
import shutil
from pathlib import Path

ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = ROOT / '_p0pilot/seed42_nc_eval_v3_20261109'

NOTE = """

### 2026-11-09 离线评价 v3 与 held-out recipe 合同（纯离线）

- 审计：`10.15/00_说明/返回审计_离线评价v3与heldout合同_20261109.md`；合同 `10.15/00_说明/HELDOUT_RECIPE冻结合同_20261109.md`；证据 `_p0pilot/seed42_nc_eval_v3_20261109/`。
- 修正：B 同召回 need 用测试正例数（手算反例通过）；移除全局 T_TRUST，val/test 显式 trusted+physical 并断言；角色统一全局行号（非零视图起点反例）；unknown/empty/singleton/ineligible/missing 分列；训练定义复核 11,834（891/10,943）、202,206 成员不变（TRAIN_DEF_CHECK passed）。
- 结果修正：A@95 FPR +0.0604±0.0476；B@95 +0.0300±0.0316（测试正例 243，实际召回 80.2/90.1/95.1%）；撤销“主要来自阈值迁移”（B 也显著）。
- 正常视图身份恢复：test 40 个 ctl 正常视图（撤销“全部 NA”），整图报警 1.0（40/40），正常节点 FPR test 0.1647→0.2799、val 0.1415→0.2165；正常锥 FPR 单列，不等于新增正常区域。
- 过度结论撤销：逐 seed 不一致（seed1 test AP 负），不宣称方向一致/显著；锥 AP 饱和只说明弱 MIL 易分。
- held-out 合同：abc/aig/nand 折训练 194/217/217、验证 52/52/52、测试 13/13/13；现有 normalization（fit_count 1,360,793）为全训练集拟合，折内必须重拟合；G0 采样序列折内重建；18 次训练约 90 分钟 GPU + 1–2 天重建；no-keep 仅盘点。
"""

for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name
    bak = OUT / (name + '.before_eval_v3')
    if not bak.exists():
        shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8'))
    print('appended', name)

reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-09T19:35:00+08:00,离线评价v3+heldout合同,seed42_nc_eval_v3_20261109,'
        '纯离线:0训练;B测试正例need;显式trust/physical;正常身份恢复,seed42/1/2,hosts_bt31 trans,'
        '返回审计_离线评价v3与heldout合同_20261109.md,'
        'A@95+0.0604;B@95+0.0300;train def 11834/202206不变;合同不授权运行\n')
with reg.open('ab') as f:
    f.write(line.encode('utf-8'))
print('registry appended')
