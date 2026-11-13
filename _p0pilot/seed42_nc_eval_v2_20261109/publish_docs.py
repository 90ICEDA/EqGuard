"""Byte-preserving append to master docs (backup first) + registry row."""
import shutil
from pathlib import Path

ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = ROOT / '_p0pilot/seed42_nc_eval_v2_20261109'

NOTE = """

### 2026-11-09 离线评价 v2 与三 seed 收益/代价（纯离线）

- 审计：`10.15/00_说明/返回审计_离线评价v2与三seed收益代价_20261109.md`；证据 `_p0pilot/seed42_nc_eval_v2_20261109/`；旧评价保留。
- 口径：锥聚合仅 trusted physical 且每锥 ≥2 实际成员；D/PO 分列 pos/neg/unknown/AP/FPR，单类别 AP 记 NA；旧完整成员评价不再沿用。
- A（验证阈值迁移）与 B（测试同召回诊断）分列：A 95% 召回 FPR +0.0604（SD 0.0476），B 同召回 +0.0110（SD 0.0277）→ 代价主要来自阈值迁移而非排序尾部退化。
- 角色 Top-k 修正为视图内 trusted 物理预算、稳定并列；旧全图 Top-k 数值作废。
- 正常视图按制造身份（ctl*/inj*）判定：val 35 正常（5 NA），整图报警 1.0；test 64 视图身份缺失全部 NA，旧 test 1.0 结论作废。
- AP：trans test +0.0281（SD 0.0297）、trans val +0.0141、orig val +0.0878；逐 seed 不一致（seed1 test −0.0049），此前“三种子方向一致”作废。
- 训练证据：仅每 5 步记录 trans 单侧索引哈希，无每步双侧索引/梯度记录；不补造。
- 建议：暂不进入 no-keep/held-out 主线，先补 test 身份/锥 GT 与非饱和标签、稳定阈值；不扩种子、不改 λ/pw。
"""

for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name
    bak = OUT / (name + '.before_eval_v2')
    if not bak.exists():
        shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8'))
    print('appended', name)

reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-09T19:05:00+08:00,离线评价v2+三seed收益代价,seed42_nc_eval_v2_20261109,'
        '纯离线:0训练;A/B分离;锥trusted physical>=2;身份正常视图,seed42/1/2,hosts_bt31 trans,'
        '返回审计_离线评价v2与三seed收益代价_20261109.md,'
        'A@95 +0.0604; B@95 +0.0110; AP test +0.0281 sd0.0297; 暂不进入主线\n')
with reg.open('ab') as f:
    f.write(line.encode('utf-8'))
print('registry appended')
