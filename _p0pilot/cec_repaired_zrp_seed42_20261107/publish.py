from pathlib import Path
import csv,hashlib,json
O=Path(__file__).resolve().parent;R=O.parents[1];D=R/'10.15/00_说明'
def read(n):return json.loads((O/n).read_text(encoding='utf-8-sig'))
def rows(n):
 with (O/n).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert read('VERIFIED.json')['passed']
primary=rows('PRIMARY_METRICS.csv');metrics=rows('evaluation_metrics.csv')
def score(tag,arm,group='val_H3_primary'):
 r=next(r for r in metrics if int(r['tag'])==tag and r['arm']==arm and r['group']==group and r['space']=='root64')
 return 100*float(r['family_macro_win'])
name='修订等价锥ZRP探索训练_seed42_32步_20261107.md'
text='''# 修订等价锥Z/R/P探索训练（seed42，各32步）

2026-11-07。结论：真实关联项学到了训练池内的排序方向，但留出宿主上仍未显示稳定优于公共项基线Z和置换P；编码敏感性仍会反转R/P排名。暂不进入检测微调，也不把本轮作为检测收益证据。

## 协议和完成情况

- 使用ginvenv_gpu/CUDA、FP32，禁用AMP/TF32；共96次实际优化更新。原模型、初始化、图、损失与修订后的采样计划冻结，保留全部历史结果；未追加SAT、未读取测试集。
- 25维接口（9维节点类型及16维中性边界身份编码），自由Q截断、完整有向锥、5种引脚角色和相位；47,360参数，共享GRU/LayerNorm，无dropout、投影头或检测分类器。本轮不是39维检测训练。
- 训练7个三函数单元、21个上下文函数类、4个制造源、2个家族（rs232、s15850），含MUX单元3个。每步每家族抽1单元，各组累计64单元名额、384查询、1152候选距离、384公共负项；最大函数曝光16。
- Z=同实现不同函数负项+方差项；R=Z+真实跨实现候选分类；P=Z+固定规则置换目标分类。三组同批输入、相同正负项权重及初始化；Adam lr=0.0002、weight_decay=0.001、梯度裁剪1。训练边界共享重编码tag=步数；评价9000主编码、9001预定敏感性编码，未按结果选编码或检查点。
- 固定末步32评价，另报未训练INIT。主要73个H3单元：37个双函数、36个三函数、2个制造源、1个上下文/宿主s38417；共364个唯一端点。单元并非73个独立电路，不能据此作大样本显著性或广泛泛化声明。
- 训练及两套编码评价共约40.85秒（不含后处理/独立核验）；峰值已分配显存约95.29 MiB，是小规模锥编码任务，不能类比200轮检测训练耗时。

## 主要结果

指标为root64真实候选比错误候选更近的逐对胜率，距离相同计0.5，先单元平均再上下文家族平均。当前验证仅1家族；不是木马检测AP。双/三候选不混报top1。两组编码中的数值越大越好。

|编码|INIT|Z|R真实|P置换|R−Z|R−P|
|---|---:|---:|---:|---:|---:|---:|
'''
for tag in [9000,9001]:
 vals=[score(tag,a) for a in ['INIT','Z','R','P']]
 text+=f"|{tag}|"+'|'.join(f'{x:.2f}%' for x in vals)+f'|{vals[2]-vals[1]:+.2f}个百分点|{vals[2]-vals[3]:+.2f}个百分点|\n'
text+='''
主编码R低于INIT约2.05个百分点；敏感性编码低于INIT约1.03个百分点。R/P优势方向仍反转，因此9001的小幅领先不构成可靠收益。主编码下，ctlmatchb的R−P为−7.11、R−Z为−2.94个百分点；injalpha为−1.28、+0.43个百分点。9001中ctlmatchb的R−P仍为−1.72，而injalpha为+2.56个百分点，源对象上也不一致。

## 训练内与MUX诊断

|评价子集/编码|INIT|Z|R真实|P置换|
|---|---:|---:|---:|---:|
'''
for group,label in [('train_frozen_pool','训练池（家族宏平均）'),('val_H3_MUX','H3含MUX验证')]:
 for tag in [9000,9001]:text+=f'|{label}/{tag}|'+ '|'.join(f'{score(tag,a,group):.2f}%' for a in ['INIT','Z','R','P'])+'|\n'
text+='''
含MUX验证23单元，均属ctlmatchb；它与源对象/实现流程混杂，不能把退化唯一归因MUX。主编码R约40.22%，敏感性编码约50.72%，仍未形成稳定的跨实现组合功能区分。未修改旧PO诊断：旧4单元和新7单元独立报告，不能并入主指标；初始化已很高，不宜凭该小子集宣称学习收益。

最后8步相对相同批次/编码的冻结初始化：R真实CE下降0.0605、P真实CE上升0.0202；P置换CE下降0.0284、R置换CE上升0.0419。结合训练池排序方向，说明两组确实在响应各自目标，而非三组没有发生有效更新；但P的CE下降不证明其最终可完全拟合。

主编码验证表示有效秩INIT/Z/R/P约13.58/17.14/16.35/15.96，R逐维平均标准差约0.855；没有整体坍缩证据，有效秩上升也不等于功能信息增加。训练内改善而留出未改善，更符合有限训练支持下的泛化不足及边界编码敏感；这不是已完成的因果分解。此前输入集合捷径及已知编码器强制相等冲突已按合同排除，本轮仍无稳定收益，说明仅修复这两点不足以解决问题。

## 核验与限制

独立CPU复算168组胜率/AUC汇总；检查三组初始文件、检查点哈希、96次连续更新、目标损失公式、相同特征/参数使用及预算。各组11个参数张量实际Adam步数32；MUX三角色矩阵各19，按实际角色出现批次数计算，三组一致，不是漏训练。沿用旧审计器的“所有参数必须32步”断言首次失败，已按原始图中引脚出现次数修正，保留verify_attempt1.log，未重跑成功训练。全部受保护旧文件哈希不变。

下一步建议先复用本轮检查点做共享边界重编码下的逐单元排序稳定性及MUX/非MUX、源对象分层，定位训练内到留出的差距；据此再冻结“关系排序一致性”的单因素合同，而非直接约束单锥向量对任意输入身份置换不变。暂不追加种子、检测微调或SAT。新池与旧三家族训练预算不同，不将新旧绝对分数差作为候选修复的单因素效果。

证据目录：`_p0pilot/cec_repaired_zrp_seed42_20261107/`。主要文件为EXECUTION_CONTRACT.json、TRAINING_COMPLETE.json、VERIFIED.json、PRIMARY_METRICS.csv、PRIMARY_DIFFERENCES.csv、PRIMARY_SOURCE_DIFFERENCES.csv、evaluation_metrics.csv、training_target_diagnostics.csv、representation_geometry.csv、三组resume.pt及history.json、INIT/三组的两套编码表示。完整指标、分候选数及PO诊断均在evaluation_metrics.csv，不能以诊断替换主结果。
'''
(D/name).write_text(text,encoding='utf-8')
entry='''

### 2026-11-07 修订等价锥Z/R/P各32步探索（已完成，无稳定收益）

ginvenv_gpu按修订合同seed42完成三组各32步，共96实际更新；同47,360参数/原初始化/损失/图与批次，训练7三函数单元、21函数类、4制造源、2家族。各组预算64单元名额、384查询、1152候选距离、384公共负项。固定末步，主评价73个H3（37双函数/36三函数、2源/1验证宿主）；0检测微调/0新增SAT/0测试读取，旧资产保留。

root64家族宏平均逐对胜率：9000下INIT/Z/R/P=74.43/73.52/72.37/76.37%；R−Z=−1.14、R−P=−4.00个百分点。9001为77.28/74.54/76.26/75.68%；R−Z=+1.71、R−P=+0.57，编码更换仍反转排名，R两编码均低于INIT。训练池9000为70.42/74.58/81.67/66.25%，说明真实目标训练内有效、留出无稳定迁移；含MUX验证R=40.22/50.72%（两编码），与ctlmatchb来源混杂，不能单独归因MUX。整体表示未坍缩，不等于功能充分。

独立复核168组指标及检查点/损失/预算通过；MUX角色矩阵实际19步，其余11参数张量32步，三组按图角色曝光一致。初次审计旧断言误要求所有参数32步，已修正并保留日志，无需重跑训练。建议先复用冻结表示分析关系排序的编码稳定性与泛化缺口，再制定单因素稳定性目标；不直接进入检测微调。新旧训练支持/预算不同，不能直接归因修复收益。

详见[修订合同训练结果](修订等价锥ZRP探索训练_seed42_32步_20261107.md)，证据`_p0pilot/cec_repaired_zrp_seed42_20261107/`。
'''
for n in ['SAT作用证明.md','SAT工作总结.md']:
 p=D/n;before=p.read_bytes();old=before.decode('utf-8-sig');assert '修订等价锥Z/R/P各32步探索（已完成' not in old
 (O/(n+'.before')).write_bytes(before);p.write_text(old+entry,encoding='utf-8')
manifest={str(p.relative_to(O)):sha(p) for p in O.rglob('*') if p.is_file() and p.suffix in ['.py','.json','.csv','.npz','.pt'] and '__pycache__' not in p.parts and p.name not in ['OUTPUT_MANIFEST.json','VERIFIED.json','PUBLISHED.json']}
(O/'OUTPUT_MANIFEST.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
v=read('VERIFIED.json');v['output_manifest_sha']=sha(O/'OUTPUT_MANIFEST.json');(O/'VERIFIED.json').write_text(json.dumps(v,indent=2),encoding='utf-8')
(O/'PUBLISHED.json').write_text(json.dumps(dict(report=str(D/name),report_sha=sha(D/name),summaries_updated=True,old_results_retained=True),ensure_ascii=False,indent=2),encoding='utf-8')
print('Report and both summaries updated.')
