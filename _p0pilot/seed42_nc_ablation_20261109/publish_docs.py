"""Byte-preserving append to master docs (backup first) + registry row."""
import shutil
from pathlib import Path

ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = ROOT / '_p0pilot/seed42_nc_ablation_20261109'

NOTE = """

### 2026-11-09 seed42 N/NC 统一监督消融执行（门禁后单种子探索）

- 审计：`10.15/00_说明/返回审计_seed42_NC执行_20261109.md`；证据 `_p0pilot/seed42_nc_ablation_20261109/`。
- 门禁：锥分数统一为 margin=logits[:,1]-logits[:,0]，每锥在 trusted 物理成员取 max 后再 BCEWithLogits；共同 logit 偏移不变性通过；训练模式无更新预检通过（节点/锥梯度范数 2.59/2.00，有限，0 step，参数/BN/RNG 恢复一致，5.82 GB，3.5 s）。
- 实际消费：仅 trans_train D 锥 11,834（891 正/10,943 负），可信成员 202,206，索引 sha 与预检一致；验证/PO/SI 不训练。
- 统计更正：675,726 是完整物理成员曝光，202,206 是可信聚合曝光；259 训练/65 验证视图。
- 运行：seed42 N/NC 各 200 更新，最佳步均 195，各约 308 s。
- 结果：节点 AP val N .2421/NC .2402，test N .2422/NC .2949；pooled test .1008/.1293；Top-1% test .4897/.5103；MIL D/PO val 均 1.0（饱和，不可当有效证据）；test MIL 缺缓存为 nan。
- 等召回 FPR（80/90/95%）：N .0582/.1186/.1633，NC .0661/.1921/.2786；角色召回 NC 略优 trigger/payload、略差 output_hijack。
- 结论：NC 在 test AP 上更好但 val 略低且高召回 FPR 更差；不扩 seed1/2，不作正式主表。
"""

for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name
    bak = OUT / (name + '.before_seed42_nc_run')
    if not bak.exists():
        shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8'))
    print('appended', name)

reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-09T18:20:00+08:00,seed42 N/NC统一监督消融,seed42_nc_ablation_20261109,'
        '实际训练:2次200更新;seed42;0 SAT;0 EQ,seed42,hosts_bt31 trans,'
        '返回审计_seed42_NC执行_20261109.md,'
        'N val/test .2421/.2422;NC val/test .2402/.2949;MIL val 1.0;test MIL nan;不扩seed1/2\n')
with reg.open('ab') as f:
    f.write(line.encode('utf-8'))
print('registry appended')
