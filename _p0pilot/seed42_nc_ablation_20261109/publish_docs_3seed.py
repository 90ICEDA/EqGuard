"""Byte-preserving append to master docs (backup first) + registry row."""
import shutil
from pathlib import Path

ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = ROOT / '_p0pilot/seed42_nc_ablation_20261109'

NOTE = """

### 2026-11-09 N/NC 三 seed 统一监督消融与离线评价

- 审计：`10.15/00_说明/返回审计_NC三seed离线评价_20261109.md`；证据 `_p0pilot/seed42_nc_ablation_20261109/`。
- 离线评价补充：orig/trans 双侧节点 AP、逐视图 Top-k（仅 trusted 物理节点、视图预算、稳定并列）、角色召回、正常视图报警与正常 D/PO 锥 FPR；验证阈值迁移与测试同召回诊断分列，测试诊断不用于调参；旧全图指标另列。
- 测试锥缓存：test 64 视图、184,832 锥（D 68 正/1,764 负、PO 29 正/873 负，unknown 排除并报告覆盖）；单类别 AP 记 NA；这是可信子集弱 MIL，不是独立功能 GT。
- seed1/2 训练：各 N/NC 200 更新；初始化哈希 seed1 16aa0fe8/seed2 15e499fa；同 seed N/NC 逐步索引哈希完全一致；最佳步 N_s1 185、NC_s1 155、N_s2 200、NC_s2 170。
- 三种子配对（n=3）：trans test AP 0.2658→0.2939（Δ+0.0281，SD 0.0297）；trans val AP +0.0141；orig val AP +0.0878；Top-1% test +0.0101；95% 召回测试 FPR +0.0604（SD 0.0476，代价）；D/PO 锥 AP 饱和 1.0，不能当功能影响证据；正常视图报警率 1.0。
- 结论：NC 的 AP 三种子平均正收益，但高召回误报代价明显，锥 AP 饱和、正常视图报警率 1.0 限制结论；不宣称显著，不扩其它种子。
"""

for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name
    bak = OUT / (name + '.before_nc_3seed')
    if not bak.exists():
        shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8'))
    print('appended', name)

reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-09T18:40:00+08:00,N/NC三seed统一监督消融+离线评价,seed42_nc_ablation_20261109,'
        '训练:seed1/2各N/NC 200更新;离线评价6检查点;0 SAT;0 EQ,seed42/1/2,hosts_bt31 orig+trans,'
        '返回审计_NC三seed离线评价_20261109.md,'
        'trans test AP 0.2658->0.2939 d+0.0281 sd0.0297;95%FPR+0.0604;锥AP 1.0饱和\n')
with reg.open('ab') as f:
    f.write(line.encode('utf-8'))
print('registry appended')
