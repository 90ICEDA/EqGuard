"""Publish the completed support audit and proposed contract to research logs."""
from pathlib import Path
import hashlib,json,shutil
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;S=R/'10.15/00_说明'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
assert read(O/'VERIFIED.json')['passed']
for name,h in read(O/'OUTPUT_MANIFEST.json').items():assert sha(O/name)==h,name
for p,h in read(O/'AUDIT_COMPLETE.json')['protected_files'].items():assert sha(R/p)==h,p
report=S/'等价锥PO匹配范围与自由Q公平模型合同_20261106.md'
heading='### 2026-11-06 等价锥PO精确匹配范围与自由Q公平模型合同（已完成，未训练）'
block='''

### 2026-11-06 等价锥PO精确匹配范围与自由Q公平模型合同（已完成，未训练）

仅在既有105困难单元/310配对内核查PO位置和重组证据；没有搜索更大池。未训练、反向、新模型前向、SAT、新真实输入模式或测试读取；旧资产哈希保持。先固定位置规则，后复用旧表示评价，不按预测或木马标签选样。

- 精确PO匹配要求候选函数在左、右两实现分别有相同坐标，不要求两侧距离相等。原整单元训练11/73、验证0/32满足；原单元内裁出训练6三函数+23双函数、验证4双函数。粗分层可保留16/21整单元，但层内仍有位置线索，不替代精确匹配。
- 在310条既有配对内按同源/查询/视图对和相同结构轮廓重组：T2+精确PO训练32三函数+16双函数、验证7双函数；T3再要求相同物理边界后仅训练4双函数/2源、验证4双函数/2源，无三函数。严格训练8函数名额实际6个上下文内观测类，验证8个；训练/验证各仅1宿主、各1含MUX、无浅小单元。T3暂不纳入训练206、验证88条配对，清单保留。
- 严格子集PO单列控制胜率50%/AUC0.5；复用旧root64表示，验证INIT62.5%，Z/A_R/A_P/S_R/S_P均75%。Z/S_R/S_P均为ctlmatchb1单元50%、injalpha3单元100%，再按源等权；仍无真实组独有收益，也不能把小子集结果视作因果提升。没有新的模型前向。
- 重组不同函数关系完成127条保存输入回放记录，实际119条唯一配对边；跨面板重复分开计，不是新增SAT或等价证明。
- 已制定新25维自由Q编码器Z/R/P合同：只用锥内操作、输入身份、角色和极性，完整拓扑消费；预计47360参数的64维拓扑GRU消息编码器、LayerNorm，无BN/dropout/投影头。它是新架构内真实目标对照，不能与旧39全图模型作单因素因果比较；模型尚未实现或加载，预计参数量待实际核验。
- PO匹配训练候选32三函数先合并跨制造源相同观测组合为24个，再按上下文内观测函数不重复的最大组合保留21个/63类/126端点，覆盖3上下文家族、5制造源、3宿主。各组同seed42新初始化、FP32、32次更新的方案；每步每家族1单元，共96单元名额/576查询/1728候选距离/576公共负项。单函数最多16次，重叠组合门最多67次、共享Q/PI边界引用最多192次，后者不计作独立证据。
- P的三函数循环置换在反方向用逆映射；公共不同函数项只用同实现内部关系，避免旧跨实现第三函数负项与P目标冲突。端点加权曝光、直接/传递正负冲突、采样预算和最大不重复组合独立检查通过。严格4个双函数留出只作探索诊断，不补第三候选、不宣称充分泛化。
- 下一步先做新模型接入及实际加载/无更新梯度预检，再决定是否按合同训练；本轮没有训练授权或自动队列，不追加SAT、检测微调或种子。

详见[PO匹配与模型合同汇报](等价锥PO匹配范围与自由Q公平模型合同_20261106.md)。证据`_p0pilot/cec_po_contract_20261106/`：matching_by_source.csv、T2/T3_PO_exact_units.json、FAIR_MODEL_CONTRACT.json、SCHEDULE_SEED42.json、SUPERVISION_BUDGET.json、FROZEN_INDICES.json及VERIFIED.json。首次准备的子集字段名错误已修复，日志保留，未涉及训练/SAT失败。
'''
changes=[]
for name in ['SAT作用证明.md','SAT工作总结.md']:
 p=S/name;old=p.read_text(encoding='utf-8-sig');assert heading not in old
 backup=O/(name+'.before_round.bak');assert not backup.exists();shutil.copy2(p,backup)
 p.write_text(old.rstrip()+block+'\n',encoding='utf-8');new=p.read_text(encoding='utf-8');assert new.startswith(old.rstrip()) and new.count(heading)==1
 changes.append(dict(path=str(p.relative_to(R)),before_sha=sha(backup),after_sha=sha(p),append_only=True))
for p,h in read(O/'AUDIT_COMPLETE.json')['protected_files'].items():assert sha(R/p)==h,p
(O/'PUBLISHED.json').write_text(json.dumps(dict(report=str(report.relative_to(R)),report_sha=sha(report),model_contract_sha=sha(O/'FAIR_MODEL_CONTRACT.json'),verified_sha=sha(O/'VERIFIED.json'),docs=changes,training=0,SAT=0,new_model_forwards=0,old_experimental_files_unchanged=True),ensure_ascii=False,indent=2),encoding='utf-8')
print('PO_REPORT_CONTRACT_AND_TWO_LOGS_UPDATED')
