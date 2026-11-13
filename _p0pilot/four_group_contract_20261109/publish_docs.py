"""Byte-preserving append to master docs (backup first) + registry row."""
import shutil
from pathlib import Path

ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = ROOT / '_p0pilot/four_group_contract_20261109'

NOTE = """

### 2026-11-09 展开边界修正与四组合同（不训练）

- 审计：`10.15/00_说明/返回审计_展开修正与四组合同_20261109.md`；证据 `_p0pilot/four_group_contract_20261109/MANIFEST.json`。
- 统计改名：旧 max_size=可信聚合成员、shared_exposure=平均全成员；修正：abc/aig/nand/id/opt 平均完整成员 20.6/41.9/41.2/48.1/22.4，平均可信聚合 1.19/12.22/1.34/31.46/12.19，成员最大跨锥曝光 568/924/785/1018/922。
- 正常 FPR：消费 seed1/2 已保存全测试预测（24 npz）与 seed42 CLOSURE；95% 目标下 abc N/NC 0.173/0.285、aig 0.323/0.287；40 ctl 视图口径，A/B 保留实际召回。
- 四组合同清单：A=171 视图/66 源（abc,id,opt），B=255/66（+aig,nand），ys_rt 两组排除；按源最小正例配额合计 502/步；8192 common+144 extra；共同归一化用 A 组 orig+trans；锥预算按源分层、正负锥同数量；主分析交互差 [NC−N]_B−[NC−N]_A。
- 未完成：真实路径深度/RF 覆盖、四组索引与锥抽样索引、共同归一化落盘哈希、加载预检——因此未通过门禁、未训练。
"""

for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name
    bak = OUT / (name + '.before_four_group')
    if not bak.exists():
        shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8'))
    print('appended', name)

reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-09T23:55:00+08:00,展开修正与四组合同,four_group_contract_20261109,'
        '只读:统计改名;正常FPR补算;四组清单;0训练,seed42/1/2,hosts_bt31 trans_test,'
        '返回审计_展开修正与四组合同_20261109.md,'
        'A171/B255;66源;配额502;未生成索引/未预检\n')
with reg.open('ab') as f:
    f.write(line.encode('utf-8'))
print('registry appended')
