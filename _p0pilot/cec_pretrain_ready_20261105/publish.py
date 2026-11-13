"""Publish certified controls, prepared runner and limits of unpaired test data."""
from pathlib import Path
import collections,csv,datetime,hashlib,json
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;J=R/'_p0pilot/cec_joint_expand_20261105';D=R/'10.15/00_说明'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def rows(p):return list(csv.DictReader(Path(p).open(encoding='utf-8-sig')))
def mt(rr,fields):return '\n'.join(['|'+'|'.join(fields)+'|','|'+'|'.join(['---']*len(fields))+'|']+['|'+'|'.join(str(r[k]) for k in fields)+'|' for r in rr])
def main():
 assert not (O/'PUBLISHED.json').exists();controls=read(O/'CONTROLS_COMPLETE.json');pre=read(O/'PREFLIGHT_COMPLETE.json');run=read(O/'RUN_CONTRACT.json');assert pre['optimizer_steps']==0 and pre['real_model_forward']==0 and not (O/'runs').exists()
 for path,h in run['frozen_files'].items():assert sha(R/path)==h,path
 for path,h in read(J/'PUBLISHED.json')['files'].items():assert sha(R/path)==h,path
 certificates=read(O/'negative_certificates.json');neg=set();false=set()
 for c in certificates:
  assert c['independent_scalar_verified']
  for a,b in c['certified_negatives']:neg.add((c['source'],c['context_id'],tuple(sorted([a,b]))))
  for a,b in c['certified_false_permuted_positives']:false.add((c['source'],c['context_id'],tuple(sorted([a,b]))))
 structural=rows(O/'structure_matching.csv');matches=[]
 for mode in ['main','strict']:
  row=dict(方案=mode)
  for field,label in [('left_gate_preserved','左根门型'),('right_gate_preserved','右根门型'),('left_cut_count_preserved','左边界规模'),('right_cut_count_preserved','右边界规模'),('left_boundary_set_preserved','左边界集合'),('right_boundary_set_preserved','右边界集合'),('size_bins_preserved','双侧规模档')]:
   rr=[r for r in structural if r['mode']==mode and r['field']==field];a=sum(int(r['passed']) for r in rr);b=sum(int(r['total']) for r in rr);row[label]=f'{a/b*100:.2f}%'
  matches.append(row)
 rawpairs={p['pair_id']:p for p in read(J/'final_pairs.json')};schedule=read(O/'schedule.json');statistics=[]
 for mode in ['main','strict']:
  for seed in [42,1,2]:
   rr=[r for r in schedule if r['mode']==mode and r['seed']==seed];ids={r[k] for r in rr for k in ['pair_a','pair_b']};positive={p for p in ids if all(e['trusted'] and e['label']==1 for e in rawpairs[p]['root_endpoints'])};u=next(r for r in controls['usage'] if r['mode']==mode and r['seed']==seed)
   statistics.append(dict(mode=mode,seed=seed,sources=u['sources'],pair_slots=u['positive_pair_slots'],unique_pairs=len(ids),positive_unique=len(positive),positive_sources=len({rawpairs[p]['source_object'] for p in positive}),max_pair_exposure=u['max_pair_exposure'],max_node_pooling_exposure=u['max_physical_node_pooling_exposure']))
 evaluation=dict(status='FROZEN_BEFORE_TRAINING',test_detection=dict(available=True,metrics=['trusted node AP/AUC','Recall@1%/5%','normal FPR at validation-calibrated thresholds','source/view aggregated detection'],condition='same held-out graph/labels/feature normalization; no test tuning; historically inspected test remains exploratory'),test_paired_stability=dict(available=False,metrics=['CEC cone embedding distance','same-root probability MAE','same-root threshold flip','paired both-correct rate'],report='NA:no qualified test pairs,not zero drift'),validation=dict(detection='all existing fixed validation graphs,not merely2273paired cones',functional='all2273proved/complete-enum pairs with source/component weights',positive_root='7pairs/4sources/onehost;report separately;not broad host generalization'),training_functional=dict(negative_certificates=len(certificates),scope='training only;in-sample function discrimination is not held-out functional generalization'),future_test_pair_creation='freeze label-blind PO/D+hash root rule before looking at new model scores;same-source explicit PI/Q CEC;no training use/no test-positive-position selection',pretrain_selection='fixed last50,no validation or test checkpoint selection',finetune_selection='existing trusted injection-view validation AP every5 updates;thresholds frozen from validation;test only after all arms fixed')
 (O/'EVALUATION_PLAN.json').write_text(json.dumps(evaluation,ensure_ascii=False,indent=2),encoding='utf-8')
 target=D/'等价锥函数负对证书_置换公平性及预训练准备_20261105.md';assert not target.exists()
 text='''# 等价锥函数负对证书、置换公平性及预训练准备

2026-11-05。本轮未启动训练或SAT，未创建训练队列，未对真实工程图做模型前向。完成数据证书、三组曝光检查、预训练/微调程序和CPU合成图数值检查。CPU合成图做了3次反向检查，无优化器更新；不能把这些检查写成真实实验训练。

## 1. 什么叫函数负对

函数负对不是“正常节点负样本”。它表示两锥在同名PI/物理Q自由上下文内实现不同布尔函数，既不决定哪边是木马，也不赋予任何安全标签。证明不同函数只需要找到一个明确共享输入，使两个根输出不同；不需要大规模SAT，也不能因为两段名字不同就当不同函数。

本轮为配对交换块生成666份证书，包含1324条去重的同视图函数负边和1332条去重的跨实现错误对应边。每块取两条真实等价边(aL,aR)、(bL,bR)，其中函数a≠b；共享输入下得到(a,a,b,b)，用于证明(aL,bL)、(aR,bR)不同，并同时证明置换(aL,bR)、(bL,aR)确实不等价。每个证书均保留同源对象、上下文、根bit、raw绑定、明确输入索引和预期输出，使用独立标量解释器回放全部666块通过。

128位并行模拟只定位反例，最终证书依赖其明确输入和标量输出；输入相同情况下根输出不同即足以否定函数等价。模拟未找到反例的候选不自动当负对，也不自动当等价。训练证书只使用训练侧，不读取测试标签或模型预测。

这些证书覆盖10个训练制造源，666不是666个独立电路。负边引用去重后仍保留按源、块和更新的使用次数，不能按出现次数夸大统计显著性。

## 2. 主置换对照的公平性

旧草案只保证全程端点次数，未保证加权端点曝光。本轮改为同一步、同源对象、同PI/Q上下文和同视图方向内交换两条真实边的右端点。

每步Z/R/P都编码完全相同的训练图、提取完全相同的锥表示，公共函数负对也相同。真实边(aL,aR)、(bL,bR)与置换边(aL,bR)、(bL,aR)使用相同权重；四个端点的数量与加权质量逐步一致，锥成员池化量也一致。Z同时计算真实/置换距离但将正等价项系数置0，不能跳过图前向或给Z空优化步骤。公共不同函数项和方差项使Z仍有实际学习目标。

主方案10源，每源在50步中的25步激活，每个激活步2条真实边、2条公共负边，另2条置换边供P使用。每源共50个正等价边名额，整体500个/seed；源交替激活使同一步可构造不同函数负对与交换。它替代此前“每源每步1对”的草案，保持总源曝光50不变。

主方案每seed实际覆盖382个不同真实配对，单对最多17次、物理节点锥池化最多50次。三种子各有独立冻结索引。每源累计损失权重相同，端点加权质量差严格为0；Z/R/P使用同一表，无按木马标签增权。所见可信正根为12对、4源（全训练池有13对、5源），是固定50步采样结果，未为了补标签覆盖反向改表。

源数、输入图、端点边际、损失条目和计算预算通过公平性检查，不代表置换仍保持配对双方的结构联合关系。主P是已证明错误的同源随机关系控制，结论仅为“真实对应与这种错误对应的差异”，不能直接称已排除门型或边界匹配线索。

## 3. 严格结构匹配子集与解释边界

额外要求两端完全相同的PI/Q边界集合、左右根门型、边界输入数、视图方向和双侧门数档后，只剩151对、7源、2宿主，且木马正根0。s35932和s15850 ctlmatcha均无此严格共同支持。主池5238对以及全部正根仍完整保留，没有因为控制组匹配失败删改数据或标签。

该子集只作为可选机制诊断，不能冒充全池三组训练，也不能用它验证木马正根稳定性。严格子集与主方案各自内部Z/R/P等预算，二者之间不直接比较AP来归因。

'''
 text+=mt(matches,['方案','左根门型','右根门型','左边界规模','右边界规模','左边界集合','右边界集合','双侧规模档'])
 text+='''

表中是交换块保留该配对结构属性的比例，端点边际在两方案内均100%一致。main的边界集合只保留约1.07%，因此必须保留上述解释限制。strict全通过，但只有151对背景共同支持；不把“严格匹配通过”写成全5238池都通过结构机制排除。

## 4. 已冻结的曝光统计

'''
 text+=mt(statistics,['mode','seed','sources','pair_slots','unique_pairs','positive_unique','positive_sources','max_pair_exposure','max_node_pooling_exposure'])
 text+='''

节点曝光上限是进入锥池化的次数。每次编码器完整图前向仍会访问训练图背景节点；三组前向次数相同，但不能将池化上限50写成全部图消息访问上限。公共负对和P关联只复用同一步已经编码的四个端点，不额外引入节点或反复重跑单锥图。

## 5. 预训练和下游具体实现

已准备engine.py，导入和默认执行均不训练，必须显式传--execute才允许运行；本轮没有使用该开关或创建runs目录。

- 预训练：当前较强改进双分支39维v3、hidden64、2+2+post1、29/10拆分，参数46620，与原模型保持。以分类头之前根64维和锥成员均值64维拼接，独立128→64ReLU→32投影。原分类头冻结，不参与功能目标。
- 输入：只加载trans_train的39v3与有向边，按原train-only归一化及±10裁剪；预训练阶段不读取y或可信mask，不加载验证/测试图。
- 损失：R为真实对应的每维均方距离，P为交换错误对应的同式距离，Z正等价项为0。三组共同使用证书负边的hinge(1−RMS距离)²与0.1倍方差不足0.5惩罚。所有组同时计算真实和置换两种距离，保持操作与端点一致。这些尺度是预注册起始设置，未声称最优。
- 预算：固定50次预训练，统一用第50次，不按验证单正根挑轮次。Adam lr0.0002、weight_decay0.001、clip1、ginvenv_gpu及bf16。每种子编码器与投影初始化相同，逐步随机种子相同；断点绑定文件哈希，成功结果直接复用。
- 微调：丢弃投影头，只迁移编码器及BN状态；分类头恢复同种子原始初值，优化器重新初始化。使用原H的两域图、标签、基础mask、200×320额外槽位、ASL+1.4soft-miss、200次更新和原验证AP每5步选模。预训练优化器状态不传给检测阶段。无SAT输入、不改区域权重。
- 主三组每个都50+200=250更新，原H200只能作历史参考。严格151子集是可选附加机制实验，本轮不排队或默认启动。

当前程序只自动完成预训练或微调所指定的一个阶段，不会在微调后自动读取测试分数。检测阈值及测试评价应在三组训练固定后统一进行。函数头的非坍缩与函数区分仍需实际运行后报告，不能由“负对证书存在”推断训练表示已经学会功能。

## 6. 已完成的预检与尚未验证部分

实际加载1275个三种子/双方案块索引，引用1436个训练锥，逐项核对物理成员、根坐标、39维有限性、训练隔离及原H监督槽位；300个方案×种子×更新的端点/权重/公共负对/前向预算检查通过。

CPU合成小图上验证：提取编码器后的分类logit与旧模型逐值相同；真实等价表示重合时R等价损失为0、置换为正；常量表示有函数区分与方差惩罚。Z/R/P均有有限的编码器和投影梯度，分类头无功能梯度；全程优化器步数0。seed42/1/2的旧检测初始化SHA与三组投影初始化指纹一致。所有原图、权重和既有结果未改。

ginvenv_gpu环境CUDA可用，但没有在真实全图执行前向/反向，所以完整GPU峰值显存、每步耗时和实际损失尺度尚未验证。数据/接口已达到可做seed42探索性启动的状态，不等于完整GPU实验已跑通；启动后先看首步显存、梯度、非坍缩和断点，再完成该组50步。若需改模型/采样/损失实现，更新合同并对三组同步，不能只修某一组。

## 7. 测试集没有配对的影响

| 评价内容 | 当前是否可做 | 结论边界 |
|---|---|---|
|固定测试图木马检测AP/AUC、预算召回|可以，沿用可信标签和固定划分|检验检测泛化，不需要节点CEC配对|
|正常FPR与源对象报警|可以，用同验证规则阈值|不能按测试结果调阈值或权重|
|同一个已证明等价锥的测试表示距离/概率MAE/翻转|不可以，报告NA|没有配对，不是漂移为0|
|学习到等价性可迁移到测试宿主|当前证据不足|验证仅1宿主，不能由检测AP单独推出|
|源对象跨视图检出差异|可作组级描述|不等同于逐锥CEC稳定性|

因此测试无配对不阻止本轮训练原型或检测AP对照，但会限制论文“测试侧功能等价稳定性”的闭环。应分别报告检测泛化与功能稳定性，不能把验证稳定性写成测试已证明稳定。

后续如补测试对应，应在查看本轮模型结果前冻结不依赖木马标签的PO/D根、实现组合和哈希抽样规则，按同源、明确PI/Q边界和CEC资格建评价池；不按测试正例位置或最高漂移位置挑样本，不把测试锥用于预训练或调参。历史测试已多轮被分析，后续固定留出结果仍需注明探索性，不能重新称从未观察的盲测。

## 8. 下一步与文件

下一步可先按main方案seed42运行Z/R/P三组的50步预训练及同200步下游；本轮只准备，没有启动。R−Z是主增量，R−P是错误对应控制；如要排除结构联合线索，还需严格151子集机制诊断，其结果适用背景范围。随后再决定是否补seed1/2，而不是现在自动提交所有队列。

目录`_p0pilot/cec_pretrain_ready_20261105/`：negative_certificates.json、scalar_negative_replay.csv、witness_contexts.json；support.csv、excluded_support.csv、schedule.json/csv、fairness_per_update.csv、structure_matching.csv、usage.csv；CONTROLS_COMPLETE.json；engine.py、RUN_CONTRACT.json、PREFLIGHT_COMPLETE.json、EVALUATION_PLAN.json。旧5238池和全部原证明继续保留。三个seed的数据表已准备不等于三种子实验已运行。
'''
 target.write_text(text,encoding='utf-8')
 brief='''

## 函数负对证书、置换公平性与预训练准备（2026-11-05）

完成666份块级函数不同反例证书并独立标量回放（1324去重同视图函数负边、1332去重错误跨实现边），不是木马负标签；0训练更新/0新SAT/0真实图前向，CPU合成图做3次梯度检查、0优化器步。主Z/R/P同一步交换两条边右端，逐步端点次数及加权质量完全一致、同公共负边与完整图前向预算；10源每源50名额、500真实边名额/seed、382唯一配对、单对≤17、节点池化≤50，采到12正根4源（总池13/5不变）。主对照只满足来源/端点/预算公平，配对结构联合关系未保持，不能称排除门型/边界线索；严格边界/门型/cut/规模档全匹配仅151对7源2宿主、0正根，另作机制诊断，不冒充全池。300逐步检查通过，三种子初始化/旧H200监督槽位冻结；准备engine.py与RUN_CONTRACT，默认不执行，50预训练+200微调、迁移编码器、恢复原分类头、重置Adam、不加SAT/不改区域权重。ginvenv_gpu CUDA可用但全图显存/损失尺度尚未试跑，无队列。测试无CEC配对不妨碍固定图检测AP/召回/FPR，但测试配对MAE/翻转/功能稳定性须NA，不能由验证1宿主外推；后续补测试应提前冻结标签无关规则、不按测试正例或漂移筛选、不用于训练。详见[本轮报告](等价锥函数负对证书_置换公平性及预训练准备_20261105.md)及`_p0pilot/cec_pretrain_ready_20261105/`。
'''
 for n in ['SAT作用证明.md','SAT工作总结.md']:
  path=D/n;assert '## 函数负对证书、置换公平性与预训练准备' not in path.read_text(encoding='utf-8')
  with path.open('a',encoding='utf-8') as f:f.write(brief)
 with (R/'10.15/99_共用资产/运行登记/运行登记表.csv').open('a',encoding='utf-8',newline='') as f:csv.writer(f).writerow([datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),'函数负对证书和置换公平性及预训练准备','cec_pretrain_ready inventory/build_controls/preflight/publish','ginvenv_gpu;CPU synthetic backward3;optimizer0;realforward0;SAT0','42/1/2 frozen indices/inits;not trained','train only;val/test policy frozen','39v3;strongdual;H200;50pre+200fine prepared',str(O.relative_to(R)),'666cert;1324negative;endpoint weighted delta0;main10sources;strict151 background','完成准备未启动','main structural joint mismatch disclosed;full GPU memory/loss scale pending;test paired metrics NA'])
 files={str(p.relative_to(R)):sha(p) for p in O.iterdir() if p.is_file() and p.suffix in ['.json','.csv','.py']};files[str(target.relative_to(R))]=sha(target)
 (O/'PUBLISHED.json').write_text(json.dumps(dict(report=str(target.relative_to(R)),files=files,training_updates=0,optimizer_steps=0,real_model_forward=0,synthetic_backward_calls=3,new_SAT_queries=0,status='PREPARED_NOT_STARTED'),ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(dict(report=str(target.relative_to(R)),negative_certificates=len(certificates),unique_negative_edges=len(neg),training_started=False),ensure_ascii=False),flush=True)
if __name__=='__main__':main()
