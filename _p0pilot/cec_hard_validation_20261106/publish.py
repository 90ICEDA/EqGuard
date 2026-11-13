"""Append this completed offline round to the two research logs."""
from pathlib import Path
import hashlib,json,shutil
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;S=R/'10.15/00_说明'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
assert read(O/'VERIFIED.json')['passed']
for p,h in read(O/'INTERFACE_VERIFIED.json')['protected_files'].items():assert sha(R/p)==h,p
report=S/'等价锥自由Q接口验证与105单元离线评价_20261106.md'
heading='### 2026-11-06 自由Q边界接口验证与105单元困难面板离线评价（已完成，未训练）'
block='''

### 2026-11-06 自由Q边界接口验证与105单元困难面板离线评价（已完成，未训练）

ginvenv_gpu完成自由PI/Q接口的加载和反例验证，再以原初始化及五组固定50步检查点评价既有105困难单元。新增13次冻结模型前向（含1次重复核验）；反向/优化器/SAT/新增真实输入模式/测试读取均0。175项冻结资产SHA保持，模型参数及BN缓冲区不变。

- 自由Q接口：620锥/20视图，161322局部节点/207401引脚边；原128模式共79360根比特比较一致，305已有不同函数见证/1220输出复现通过；18项MUX角色、输入身份、Q/QN、重复脚、常量、六级拓扑及错误拒绝检查通过。保存重载、单锥/批量及上下文改名一致。所有真实锥含Q，无真实常量节点；常量由合成反例覆盖。回放不替代原CEC，也未新增证明。
- 新25维局部语义接口已验证，但未接入旧39维模型；本轮模型评价仍使用旧全图39v3和原边界/引脚适配器，不能写成新接口收益。旧缓存覆盖训练196/428、验证6/192端点，因此补做12次正常前向和1次重复；没有重训练。
- 三函数主评价：训练68单元/8源，root64源等权胜率INIT/Z/A_R/A_P/S_R/S_P=55.99/57.36/57.16/57.29/56.77/56.45%；留出32单元/2源/同宿主=66.67/68.23/66.93/68.75/69.01/70.05%。S_R仍未优于S_P；A_R也未优于A_P。训练侧另5个双函数单元单列，不并入三候选主表。
- 留出分源S_R/S_P：ctlmatchb48.96/50.52%，injalpha89.06/89.58%；含MUX6单元仅一个源，为48.61/50.00%。留出没有浅小单元。成员均值与投影读出同样没有真实组优势；不能只据合并指标宣称功能迁移。
- 固定结构控制：根门型和成员门型均值均50%，但根14维结构距离留出84.38%；逐列PO距离（0起始列30）单列84.38%/AUC0.7910，二跳扇出55.21%，其他12列50%。面板虽匹配规模/深度/操作统计/同边界，仍有锥外位置线索；此结果不证明GNN因果上只依赖PO，也不支持直接删除检测PO特征。
- 新面板每函数、双向、全部错误候选等权，再按源汇总，与旧59单元的四锚查询不同，不能直接将旧76.59%与新69.01%视作单因素下降。下一步先审视位置共同支持及25维接口的公平模型接入合同，暂不补种子、扩SAT或检测微调。

详见[本轮报告](等价锥自由Q接口验证与105单元离线评价_20261106.md)。证据`_p0pilot/cec_hard_validation_20261106/`：INTERFACE_VERIFIED.json、function_metrics.csv、metrics_by_source.csv、additional_structure_controls.csv及VERIFIED.json。独立CPU重算120组指标及手工加权AUC通过。
'''
changes=[]
for name in ['SAT作用证明.md','SAT工作总结.md']:
 p=S/name;old=p.read_text(encoding='utf-8-sig')
 assert heading not in old,'Do not append the round twice'
 backup=O/(name+'.before_round.bak');assert not backup.exists();shutil.copy2(p,backup)
 p.write_text(old.rstrip()+block+'\n',encoding='utf-8')
 assert p.read_text(encoding='utf-8').startswith(old.rstrip()) and p.read_text(encoding='utf-8').count(heading)==1
 changes.append(dict(path=str(p.relative_to(R)),before_sha=sha(backup),after_sha=sha(p),append_only=True))
for p,h in read(O/'INTERFACE_VERIFIED.json')['protected_files'].items():assert sha(R/p)==h,p
(O/'PUBLISHED.json').write_text(json.dumps(dict(report=str(report.relative_to(R)),report_sha=sha(report),docs=changes,verified_sha=sha(O/'VERIFIED.json'),training=0,SAT=0,old_experimental_files_unchanged=True),ensure_ascii=False,indent=2),encoding='utf-8')
print('REPORT_AND_TWO_LOGS_UPDATED')
