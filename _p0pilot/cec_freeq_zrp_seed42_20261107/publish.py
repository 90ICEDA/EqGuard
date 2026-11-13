"""Publish authorized fixed32 seed42 training results to the two research logs."""
from pathlib import Path
import hashlib,json,shutil
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;S=R/'10.15/00_说明'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert read(O/'VERIFIED.json')['passed'] and read(O/'VERIFIED.json')['actual_optimizer_updates']==96
for n,h in read(O/'OUTPUT_MANIFEST.json').items():assert sha(O/n)==h,n
for p,h in read(O/'EXECUTION_CONTRACT.json')['protected_files'].items():assert sha(R/p)==h,p
report=S/'自由Q等价锥ZRP探索训练_seed42_32步_20261107.md';heading='### 2026-11-07 自由Q ZRP各32步探索训练与85单元H3主评价（已完成，收益未稳定）'
block='''

### 2026-11-07 自由Q ZRP各32步探索训练与85单元H3主评价（已完成，收益未稳定）

按用户明确授权，用ginvenv_gpu/CUDA FP32完成seed42的Z/R/P各32次参数更新，共96次；绑定新85H3主要评价合同，原训练池、共同初始化、模型、损失和预算保持。96次训练前向、160次初始/末次固定评价前向，未检测微调/新增SAT/测试读取；旧资产SHA保持，全部旧结果保留。

- 三组完整初始化文件与预检逐字节一致，47360参数；旧21三函数/63观测函数类/3家族/126端点及32步采样表未替换。每组96单元名额、576查询、1728候选距离、576公共负项。全部14参数实际Adam步数均32，无失败、缺步或重复更新；首步损失与预检一致，梯度和参数有限，固定末次而非验证选模。
- 主指标为85H3、root64、家族等权真实对更近胜率，9000为主编码。INIT/Z/R/P=78.04/77.94/78.33/77.16%；R-P+1.18个百分点、R-Z+0.39、R-INIT+0.29。主函数AUC=0.6354/0.6397/0.6388/0.6389，未同步呈现R独有优势，不能混作检测AP。
- 预定敏感性编码9001的INIT/Z/R/P=80.49/79.02/79.12/79.71%；R-P-0.59个百分点、R-Z+0.10、R-INIT-1.37。电路/对应/样本不变，只变共享中性输入编码，真实优于置换的方向未保持。因此主编码的小领先尚不足以证明稳定功能收益；本合同没有预先设定+2个百分点等数值门槛，未套用旧轮门槛或择优编码。
- 主编码逐源R/Z/P：ctlmatchb的34单元49.02/48.28/47.06%，injalpha的51单元97.88/97.71/97.22%。前者INIT50%、后者INIT96.73%，总体高分主要来自本来较容易的injalpha；源与流程abc-aig/id-opt耦合，不作单一因素归因。主编码两源R-P/R-Z同向，但9001的injalpha方向反转。
- 23个H3含MUX单元，9000 INIT/Z/R/P=48.19/46.38/47.83/46.01%，9001 R=50%，仍接近随机且仅一个源。41双函数与44三函数分别报告top1，不混合不同候选数的准确率。
- 严格PO旧4单元四状态均源等权75%（家族内单元等权87.5%），新主面板内7单元四状态胜率均100%，两套编码均如此；高分在初始化已存在，小子集未提供真实组独有收益。旧4/新7不相加，也不作为额外样本加入主要85单元。
- 冻结训练池21单元在9000的INIT/Z/R/P胜率79.96/78.77/79.17/79.56%，9001为76.39/80.56/83.33/75.60%。训练内提升也依赖中性编码，不能简单说训练已学会而只有留出失败。最后8更新前相对同批初始R真实CE下降0.0747、Z也下降0.0671；P指定错误CE反而升0.0280，共同不同函数项大幅下降，P未明显拟合错误目标。这不是固定批完整收敛试验，未改权重。
- 无明显坍缩：H3 root64有效秩INIT/Z/R/P约13.84/17.58/17.09/17.72，变宽不是R独有。主执行训练+评价约53.3秒，训练阶段峰值PyTorch已分配显存约90MiB，不含上下文等开销；保存共同初始、三组可恢复检查点及16份表示缓存。
- CPU独立复核检查点/真实优化器步数/预算和216组距离、手工加权AUC等通过。结论限单seed、2制造源、1验证宿主，85单元不是85独立电路；不宣称木马检测增益。
- 下一步优先复用本轮缓存和检查点分析中性编码敏感性及公共项/关联项作用，不自动追加训练、种子、检测微调或SAT。

详见[自由Q ZRP探索训练结果](自由Q等价锥ZRP探索训练_seed42_32步_20261107.md)。证据`_p0pilot/cec_freeq_zrp_seed42_20261107/`：EXECUTION_CONTRACT.json、Z/R/P/resume.pt、PRIMARY_METRICS.csv、PRIMARY_DIFFERENCES.csv、PRIMARY_SOURCE_DIFFERENCES.csv、training_target_diagnostics.csv、representation_geometry.csv及VERIFIED.json。
'''
changes=[]
for name in ['SAT作用证明.md','SAT工作总结.md']:
 p=S/name;old=p.read_text(encoding='utf-8-sig');assert heading not in old
 backup=O/(name+'.before_round.bak');assert not backup.exists();shutil.copy2(p,backup)
 p.write_text(old.rstrip()+block+'\n',encoding='utf-8');new=p.read_text(encoding='utf-8');assert new.startswith(old.rstrip()) and new.count(heading)==1
 changes.append(dict(path=str(p.relative_to(R)),before_sha=sha(backup),after_sha=sha(p),append_only=True))
for p,h in read(O/'EXECUTION_CONTRACT.json')['protected_files'].items():assert sha(R/p)==h,p
(O/'PUBLISHED.json').write_text(json.dumps(dict(report=str(report.relative_to(R)),report_sha=sha(report),verified_sha=sha(O/'VERIFIED.json'),execution_contract_sha=sha(O/'EXECUTION_CONTRACT.json'),primary_result_sha=sha(O/'PRIMARY_RESULT.json'),docs=changes,actual_optimizer_updates=96,finetune=0,SAT=0,test_reads=0,old_files_unchanged=True),ensure_ascii=False,indent=2),encoding='utf-8')
print('ZRP32_RESULT_REPORT_AND_TWO_LOGS_UPDATED')
