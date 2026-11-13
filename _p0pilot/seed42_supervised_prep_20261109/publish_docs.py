"""Byte-preserving append to master docs (backup first) + registry row."""
import shutil
from pathlib import Path

ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = ROOT / '_p0pilot/seed42_supervised_prep_20261109'

NOTE = """

### 2026-11-09 seed42 统一监督消融预检（只读，0 optimizer.step）

- 合同：`10.15/00_说明/SEED42_NC冻结合同_20261109.md`；审计 `10.15/00_说明/返回审计_seed42监督预检_20261109.md`；证据 `_p0pilot/seed42_supervised_prep_20261109/`。
- 修复虚拟 assign 节点映射：`__v2_assign_*` 是 39v3 辅助行（virtual_node_map.jsonl，global id 3220146+），不是缺失；物理 1,928,967（unique）、辅助 554、真正缺失 0（上一版误报 1,956）。
- 缓存分离：完整结构成员与 MIL 可信物理成员分列；辅助节点 mask 全 false、无标签资格；标签只由物理成员决定，混合 unknown 保持 −1，不暗中升负。
- 预算：训练分母 = train D 可训练锥 11,834（891 正 / 10,943 负），可信成员 202,206；14,106 是 train+val、D+PO+SI 总数，不是训练分母。
- 冻结合同：N/NC 同节点索引/初始化/Adam/200 更新/选模/阈值；L_cone 仅 trans_train 合格 D 锥；λ=1、pw=10 固定；双侧锥需另建 orig 缓存。
- GPU 预检（ginvenv_gpu）：11,834 锥、202,206 聚合成员；节点/锥损失 0.4963/1.1705，梯度有限；0 optimizer.step，参数/BN 前后一致；峰值 4.45 GB，单步 3.73 s。
- 通过审计后再启动 seed42 N/NC 两次探索；本轮不排队训练。
"""

for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name
    bak = OUT / (name + '.before_seed42_supervision')
    if not bak.exists():
        shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8'))
    print('appended', name)

reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-09T17:55:00+08:00,seed42统一监督消融预检,seed42_supervised_prep_20261109,'
        '只读:辅助节点映射;缓存分离;预算重算;GPU无更新预检,seed42,hosts_bt31 trans_train,'
        'SEED42_NC冻结合同_20261109;返回审计_seed42监督预检_20261109.md,'
        '训练分母11834(891/10943);0step;参数未变;4.45GB;0训练\n')
with reg.open('ab') as f:
    f.write(line.encode('utf-8'))
print('registry appended')
