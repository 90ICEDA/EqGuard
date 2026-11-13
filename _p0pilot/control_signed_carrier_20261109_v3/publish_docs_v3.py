"""Byte-preserving append to the two master docs (backup first) + registry row."""
import shutil
from pathlib import Path

ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = ROOT / '_p0pilot/control_signed_carrier_20261109_v3'

NOTE = """

### 2026-11-09 主实验合同与相位接口 v3（只读）

- 主实验合同：`10.15/00_说明/三项主实验合同_v1_20261109.md`；返回审计 `10.15/00_说明/返回审计_主实验合同与相位v3_20261109.md`。
- 合同要点：A 节点 vs 节点+锥（N/NC × seed42/1/2 = 6 次）；B 严格 no-keep（3 对象 × 3 配方 × 2 变体 = 18 综合 + 18 CEC，未授权）；C held-out recipe abc/aig/nand（2 组 × 3 seed × 3 折 = 18 次）。
- 锥定义：历史区域是 DFF 正向扇出区 / touches_PO 反向；拟用端点锥是 D 引脚反向 fanin / PO 驱动门输入反向，二者不可混称。
- keep 面板实测作废：30 个 keep 变体组中 14 组四方案文件完全相同；30 个 keep 文件模块名与后缀不一致；128/317 个 plain 文件模块名含 keep；injalpha ys_abc 的 plain/keepbnd/keepcur/keepfull/keepnone 五文件 sha256 相同（模块名 keepbnd）。B 需重新综合/CEC（未授权）。
- LRO 3 seed × 5 recipe 表在，但 `results/hosts_bt31_seed*_lro_*` 无 best.pt/预测分数，只能复用表与配置；正常对照五组 × 3 seed 的 best.pt 与分数可离线复用做等召回—误报评价。
- 相位 v3：新目录 `_p0pilot/control_signed_carrier_20261109_v3/`，只处理原 8 条关系；修复精确别名 invert、source_signal 绑定、结构化上下文（free/fixed/state）、吸收双端表达式；12 项篡改全部被加载器拒绝；对象级统计修正为 train 3 对象/10 尝试/1 未检查、val 4 对象/9 尝试/2 提前接受。
- 仍未确认：端点锥实际收益、严格 no-keep 的 CEC 与 GT、−1 承载自动恢复。
"""

for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name
    bak = OUT / (name + '.before_main_contract_v3')
    if not bak.exists():
        shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8'))
    print('appended', name)

reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-09T16:45:00+08:00,主实验合同+相位接口v3,control_signed_carrier_20261109_v3,'
        '只读:三项合同;keep面板核查;v3加载器12篡改拒绝,seed42,hosts_bt31 orig+trans,'
        '三项主实验合同_v1_20261109;返回审计_主实验合同与相位v3_20261109.md,'
        '8关系验证;12拒绝;对象级覆盖train3/val4;0训练/0SAT\n')
with reg.open('ab') as f:
    f.write(line.encode('utf-8'))
print('registry appended')
