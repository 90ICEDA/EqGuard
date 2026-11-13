"""Append completed freeQ hookup/no-update preflight to both research logs."""
from pathlib import Path
import hashlib,json,shutil
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;S=R/'10.15/00_说明'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert read(O/'VERIFIED.json')['passed'] and read(O/'VERIFIED.json')['training_updates']==0
for n,h in read(O/'OUTPUT_MANIFEST.json').items():assert sha(O/n)==h,n
for p,h in read(O/'EXECUTION_CONTRACT.json')['protected_files'].items():assert sha(R/p)==h,p
report=S/'等价锥自由Q模型接入与无更新梯度预检_20261106.md'
heading='### 2026-11-06 自由Q模型接入与实际加载无更新梯度预检（已通过，未训练）'
block='''

### 2026-11-06 自由Q模型接入与实际加载无更新梯度预检（已通过，未训练）

ginvenv_gpu/CUDA FP32按冻结自由Q合同完成模型接入、全部32批实际加载和固定批次无更新梯度预检；合计44次前向、32次自动微分调用，优化器对象/参数更新/SAT/新真实输入模式/测试读取均0。旧合同、索引、图、标签、证明与检查点SHA保持，新初始模型参数与缓冲区保持，没有训练队列。

- 实际47360参数与合同一致：输入1664、角色20480、相位128、GRU24960、LayerNorm128。输入为25维局部语义加角色/极性，Q处截断；无39维权重、PO位置、BN、dropout、投影头或分类头。共同完整初始化已保存，Z/R/P独立实例加载后状态与根输出一致。
- 实际32批每批3家族/3单元/18端点；累计96单元名额、576查询、1728候选距离、576公共负项完全对齐合同。局部节点105—4839、引脚边90—6156，最大组合深度66。每节点/引脚均被消费，所有节点均为锥根祖先；主验证4双函数/16端点实际加载，无虚构第三候选。
- 实际模型保留MUX端口、具体输入、Q/QN、重复脚、常量等反例的区分信息；对称AND交换和Q上游D变化表示均不变。单锥/合批差7.15e-7；六级链Q身份到根梯度非零，范数约12.16。只证明初始化信息通路和计算能力，不是已学会功能等价。
- 独立方程复算首批4059节点，最大状态差1.95e-6；32批输入哈希及实际目标索引逐项复核，224损失值最大误差1.38e-7。R真实、P双射错误且逆向用逆置换、Z关联0；公共同实现不同函数项/方差项与加权端点相同，无旧第三函数项冲突。
- 更新索引1/2/16/32只是检查批次，不是训练更新。R/P关联梯度余弦分别-0.9512/-0.9400/-0.9535/-0.8957，总梯度0.9089/0.7161/0.8387/0.9015；目标方向不同，但公共项仍使总梯度同向。输入、五类角色、相位、GRU、LayerNorm在首批有有限非零梯度，总梯度与分项和相对误差最大约6.7e-7。未改变权重或按梯度配平。
- 同一初始化在32批的root64逐维std均值0.704—0.863、有效秩4.00—6.18，无完全坍缩；不是训练曲线，也不能与旧架构/面板作单因素收益比较。主预检约14.4秒，峰值PyTorch已分配显存约84MiB（不含上下文等开销）。
- 接入与预检门槛通过，可准备下一轮按原seed42、Z/R/P各32次更新的探索训练，使用保存的共同初始化。先看训练内拟合，再看严格留出及逐源R-P/R-Z；主验证仅4单元/2制造源/1宿主，不作充分泛化或检测AP结论。本轮未训练、不追加SAT。

详见[自由Q模型接入与预检汇报](等价锥自由Q模型接入与无更新梯度预检_20261106.md)。证据`_p0pilot/cec_freeq_preflight_20261106/`：model_interface.py、INITIAL_STATE.pt、actual_loading_budget.csv、FIXTURES_VERIFIED.json、gradient_vectors.npz、INDEPENDENT_CHECKS.json和VERIFIED.json。原冻结合同未改写，前一轮“尚未接入”的状态由本轮完成记录承接。
'''
changes=[]
for name in ['SAT作用证明.md','SAT工作总结.md']:
 p=S/name;old=p.read_text(encoding='utf-8-sig');assert heading not in old
 backup=O/(name+'.before_round.bak');assert not backup.exists();shutil.copy2(p,backup)
 p.write_text(old.rstrip()+block+'\n',encoding='utf-8');new=p.read_text(encoding='utf-8');assert new.startswith(old.rstrip()) and new.count(heading)==1
 changes.append(dict(path=str(p.relative_to(R)),before_sha=sha(backup),after_sha=sha(p),append_only=True))
for p,h in read(O/'EXECUTION_CONTRACT.json')['protected_files'].items():assert sha(R/p)==h,p
(O/'PUBLISHED.json').write_text(json.dumps(dict(report=str(report.relative_to(R)),report_sha=sha(report),model_code_sha=sha(O/'model_interface.py'),initial_state_sha=sha(O/'INITIAL_STATE.pt'),verified_sha=sha(O/'VERIFIED.json'),docs=changes,training=0,SAT=0,model_forwards=44,autograd_calls=32,old_experimental_files_unchanged=True),ensure_ascii=False,indent=2),encoding='utf-8')
print('FREEQ_PREFLIGHT_REPORT_AND_TWO_LOGS_UPDATED')
