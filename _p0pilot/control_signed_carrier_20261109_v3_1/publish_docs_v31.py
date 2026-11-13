"""Byte-preserving append to master docs (backup first) + registry row."""
import shutil
from pathlib import Path

ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = ROOT / '_p0pilot/control_signed_carrier_20261109_v3_1'

NOTE = """

### 2026-11-09 合同 v2、端点锥离线预检与相位 v3.1（只读）

- 合同：`10.15/00_说明/三项主实验合同_v2_20261109.md`；审计 `10.15/00_说明/返回审计_合同v2与端点锥预检_20261109.md`。
- 修订：29/10 是特征分支维度不是数据划分；实际划分 train 259 / val 65 / test 64 视图（宿主 rs232 113、s15850 86、s35932 60；s38417 65；s38584 64）。
- 端点锥：D 锥含 D 的组合驱动、止于 PI/Q、排除寄存器本体；PO 锥含实际驱动门；单点/直接 PI/直接 Q/空组合锥全部保留分类。预检小图 rs232 injalpha：70 锥（D58/PO12）、347 成员、direct_pi 1、direct_q 27、empty 28、D 锥重叠 201/1653、导出→重载成员逐一相等（`_p0pilot/endpoint_cone_precheck_20261109/PRECHECK.json`）。
- 标签：role_region（制造来源）与 impact_cone（独立影响 GT）分名；unknown 不记 0、不进分母；不得把节点正标 OR 成 cone GT。缺口表 `ENDPOINT_GT_GAPS.csv`。
- 预算：N/NC 同节点预算/初始化/200 更新/选模/阈值；L=L_node+λ·L_cone，区域均值归一化；锥索引预计算；λ=1.0、pw=10 仅验证集预选。
- no-keep：现有面板不能证明严格 no-keep（≠旧网表全部无效）；3 源小面板 = 12 次综合 + 12 次 CEC（待授权）；LRO 折内重拟合归一化。
- 支线 v3.1：吸收关系 target_observation 与 target_signal/驱动/引脚/坐标严格绑定并验宿主端点；候选集合减尝试集合统计未检查后代，train 1 / val 4；14 项拒绝测试全部通过。
"""

for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    p = ROOT / '10.15/00_说明' / name
    bak = OUT / (name + '.before_contract_v2_v31')
    if not bak.exists():
        shutil.copy2(p, bak)
    p.write_bytes(p.read_bytes() + NOTE.encode('utf-8'))
    print('appended', name)

reg = ROOT / '10.15/99_共用资产/运行登记/运行登记表.csv'
line = ('2026-11-09T17:10:00+08:00,合同v2+端点锥预检+相位v3.1,control_signed_carrier_20261109_v3_1;endpoint_cone_precheck_20261109,'
        '只读:锥定义纠正;小图预检;unknown规则;v3.1绑定与计数,seed42,hosts_bt31 orig,'
        '三项主实验合同_v2_20261109;返回审计_合同v2与端点锥预检_20261109.md,'
        '70锥347成员一致;14拒绝;未检查train1/val4;0训练/0SAT\n')
with reg.open('ab') as f:
    f.write(line.encode('utf-8'))
print('registry appended')
