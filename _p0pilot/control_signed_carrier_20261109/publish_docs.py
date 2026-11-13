"""Byte-preserving append to the two master docs (backup first)."""
import shutil
from pathlib import Path

ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train\_p0pilot\control_signed_carrier_20261109')

NOTE = """

### 2026-11-09 带相位功能承载对应（只读审计，0 训练 / 0 新增 SAT）

- 新目录 `_p0pilot/control_signed_carrier_20261109/`；报告 `10.15/00_说明/返回审计_带相位功能承载对应_20261109.md`。
- 三例固化为 6 条关系：R1 alpha P2→`_0384_`（−1，活跃）、R2 alpha T→`_0383_`（−1，活跃）、R3 alpha H→`_0001_`（−1，活跃）、R4/R5 delta DP0/DP2 命名副本（+1，**悬空**）、R6 delta 输出吸收（`g10801 = H OR T`，x 依赖消失，不产生节点配对）。
- 关键事实：被监督为正的命名副本（delta 8957/8958、934/935；alpha 983350）悬空；真正活跃的载体是**未标记的反相门**（983349 等）。`trusted=False` 的 0 是未标记，不是受监督负例。
- 反例全部通过：去相位 32/32 不匹配；边界错位 32/32 不匹配；只看名字会接受死副本（函数匹配但用途 dead）；自由 Q 与固定 Q 混用会改变输出（1/4）。
- 有界扩展：12 个源门对象（train 6 / val 6，10 个独立源），得到 5 条签名关系（全为 +1，4 活跃 1 悬空），7 条未确认（全部边界未对齐）；模式预算 20/65536；**未自动恢复任何 −1 承载**。
- 校验：`VERIFIED.json`、`VERIFY_EXTENSION.json`、`UNTOUCHED.json`（72 个标签/图/网表文件哈希核对通过）；0 SAT/CEC/Yosys、0 模型前向。
- 结论：接口可解释“降误报同时压低正例”的一部分机制，但增量集中在三例；暂不作为训练目标，不改标签；下一步先补反相桥接与扩大源覆盖。
"""

for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name
    bak = OUT / (name + '.before_signed_carrier')
    if not bak.exists():
        shutil.copy2(p, bak)
    data = p.read_bytes()
    assert data.endswith(b'\n') or True
    p.write_bytes(data + NOTE.encode('utf-8'))
    print('appended', name, 'bytes', len(NOTE.encode('utf-8')))

# registry
reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-09T15:05:00+08:00,带相位功能承载对应审计,control_signed_carrier_20261109,'
        '只读:三例6关系+12对象扩展;0训练/0SAT,seed42,hosts_bt31 orig+trans,'
        'control_signed_carrier_20261109;返回审计_带相位功能承载对应_20261109.md,'
        '局部真值54+20模式,6关系(5签名3负2正+1吸收);扩展5签名7未确认;72文件哈希未变\n')
with reg.open('ab') as f:
    f.write(line.encode('utf-8'))
print('registry appended')
