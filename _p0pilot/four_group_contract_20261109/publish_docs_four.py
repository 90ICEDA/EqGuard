"""Byte-preserving append to master docs (backup first) + registry row."""
import shutil
from pathlib import Path

ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = ROOT / '_p0pilot/four_group_contract_20261109'

NOTE = """

### 2026-11-10 seed42 四组训练组成实验

- 审计：`10.15/00_说明/返回审计_四组seed42训练_20261110.md`；证据 `four_group_contract_20261109/`。
- 共同验证池：abc/id/opt val 39 视图、392,853 节点、312 辅助；A 组归一化；无训练/测试混入。
- 资产冻结：502 正例+8192 common+144 H；锥 A/B 各 11,187（558/10,629）；旧 264 锥方案作废。
- 四组训练完成：A-N/A-NC/B-N/B-NC best step 200/180/175/195；验证 AP 0.3043/0.2861/0.2352/0.2304。
- 测试（best）：基础池 AP A-N .2755、A-NC .2841、B-N .3057、B-NC .3382；aig/nand .1994/.1899/.2321/.1951；正常节点 FPR .3925/.4734/.2984/.3527。
- 交互差：基础池 +0.0240；aig/nand −0.0275；正常 FPR 两组 NC 均升高。单种子，不宣称稳定/因果。
- 待办：Top-5、实际召回/阈值迁移、逐源表、可信/全物理视图报警、深度 RF（null）；未补 seed1/2。
"""

for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name
    bak = OUT / (name + '.before_four_run')
    if not bak.exists():
        shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8'))
    print('appended', name)

reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-10T01:55:00+08:00,seed42四组训练组成,four_group_contract_20261109,'
        '训练:4组各200更新;0 SAT;0 EQ,seed42,hosts_bt31 trans+orig,'
        '返回审计_四组seed42训练_20261110.md,'
        'base A .2755/.2841 B .3057/.3382;add .1994/.1899/.2321/.1951;交互 +.0240/-.0275\n')
with reg.open('ab') as f:
    f.write(line.encode('utf-8'))
print('registry appended')
