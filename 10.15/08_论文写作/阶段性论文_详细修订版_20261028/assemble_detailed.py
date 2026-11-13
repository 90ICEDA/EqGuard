"""Build a comprehensive research manuscript from audited staged evidence."""
import csv,hashlib,json,re,shutil,datetime
from pathlib import Path
import numpy as np
H=Path(__file__).resolve().parent;ROOT=H.parents[2];B=H/'构建与核验';A=H/'assets'
old=(B/'上一版全文.md').read_text(encoding='utf-8')
def read(p):return list(csv.DictReader(Path(p).open(encoding='utf-8-sig')))
def section(start,end=None):
    a=old.index(start);b=old.index(end,a+len(start)) if end else len(old)
    return old[a:b].strip()
def subheads(text,chapter):
    n=0
    def rep(m):
        nonlocal n;n+=1;return f'### {chapter}.{n} '+m[1]
    return re.sub(r'^### \d+\.\d+ (.+)$',rep,text,flags=re.M)
def table(caption,head,rows):
    return caption+'\n\n| '+' | '.join(head)+' |\n|'+ '|'.join(['---']*len(head))+'|\n'+'\n'.join('| '+' | '.join(str(v) for v in r)+' |' for r in rows)+'\n'
history=(H/'历史章节.md').read_text(encoding='utf-8')
probe=read('D:/GIN训练/10.5/results/phase2/audit/single_to_composed_d2_probe_metrics.csv')
lookup={(r['model'],r['probe'],r['cv']):float(r['acc']) for r in probe}
history=history.replace('{{PROBE_TABLE}}',table('表F 表示中可线性读取的信息',['模型','电路ID随机','深度跨电路','算子跨电路','强度跨电路'],[[g]+[f'{lookup[(g,p,c)]:.4f}' for p,c in [('circuit','random'),('depth','circuit_heldout'),('operator','circuit_heldout'),('strength','circuit_heldout')]] for g in ['G1','G2','G3','G4']]))
history=history.replace('{{M0_TABLE}}',section('表5 历史LOCO','M1提高了').replace('表5','表H'))
history=history.replace('{{PRIMITIVE_TABLE}}',section('表6 历史rs232','门类型归并').replace('表6','表P'))
ab=read(ROOT/'10.10/results/summary_methods_ab.csv');wanted=['random','heur_dag_dist_po','gnn_loco(M0)','logreg_39','mlp_39']
history=history.replace('{{AB_METHOD_TABLE}}',table('表L A/B对照中的模型与特征表现',['方法','A型AP','B型AP','A型对照AUC','B型对照AUC'],[[m]+[next(r[k] for r in ab if r['数据']==d and r['方法']==m) for k,d in [('木马AP','A 型'),('木马AP','B 型'),('木马对合法对照的AUC','A 型'),('木马对合法对照的AUC','B 型')]] for m in wanted]))
train=read(ROOT/'10.12/results/stage4_3seed.csv');agg=[]
for cfg in ['c1_lr1e3_ep100_b16','c7_lr3e3_ep100_b16','c8_lr1e3_ep100_b32']:
    rows=[r for r in train if r['配置']==cfg];vals=[float(r['AP_T']) for r in rows];assert len(vals)==3
    agg.append(dict(config=cfg,mean=float(np.mean(vals)),sd=float(np.std(vals,ddof=1))))
history=history.replace('{{TRAIN_TABLE}}',table('表M 训练预算与学习率的三种子复核',['配置','seed42','seed43','seed44','均值与样本标准差'],[[a['config'].replace('_ep100','')]+[next(r['AP_T'] for r in train if r['配置']==a['config'] and r['seed']==str(seed)) for seed in [42,43,44]]+[f"{a['mean']:.4f}±{a['sd']:.4f}"] for a in agg]))
budgets=read('D:/GIN训练/9.26/GIN_train/results/single_to_composed_d2_budget_sweep.csv')
budget_table=table('表Y 视图预算扫描的三种子平均AP',['每轮视图预算','G1','G2','G3','G4'],[[b]+[next(r['AP_mean'] for r in budgets if r['Budget']==str(b) and r['Group']==g) for g in ['G1_OrigOnly','G2_EqAug','G3_RandCons','G4_PredHard']] for b in [1,2,4,8]])
history=history.replace('该阶段还绘制了按edit_ratio分箱的鲁棒性边界：',budget_table+'\n该阶段还绘制了按edit_ratio分箱的鲁棒性边界：')
history=history.replace('### 5.1 表示探针的设计','''### 5.1 早期困难变体与修改对象

9月13日已经按原始对象聚合一对多目标，而不只是比较两张图的总体指标。在当时15个变体的分组表中，正常未修改对象平均配对MAE为0.0176，正常修改对象为0.0689；木马未修改对象为0.0135，木马修改对象为0.0476。两类对象都在结构被改写后更不稳定，说明漂移并非木马独有。表中配对数与区域数为跨视图平均量，不应四舍五入后当成独立总样本数。[H2]

困难变体报告将AP下降、配对漂移与改写次数并列，发现部分编辑较多的随机变体更难。它为后续按预测困难度选择训练视图提供动机，但测试困难分析不能直接变成训练候选选择。9月早期对固定困难网表的观察，与后来fold内合法pred-hard实现应区分：后者要求每轮候选只来自训练集合。

### 5.2 表示探针的设计''')
history=history.replace('若原指标AnyMiss表示“至少漏掉一个正例”，它与“预算内一个木马都没找到”含义不同，后续统一评测应以公式或计算代码明确，不能按列名猜测。','本文检查phase2/p2common.py确认，AnyMiss@K为first_hit_rank>K，表示预算内没有命中任何正例，不是“至少漏掉一个正例”。10.10部分汇总解释与实现不一致，此处按实际计算解释；无正例时为NaN。')
lio=[]
for label,name in [('39维','lio_summary_g5_3seed.csv'),('合并特征','lio_summary_3seed.csv')]:
    rr=read(ROOT/'10.13'/name);assert len(rr)==6
    vals=np.array([[float(r[s]) for s in ['s42','s43','s44']] for r in rr]).mean(axis=0)
    lio.append([label]+[f'{v:.4f}' for v in vals]+[f'{vals.mean():.4f}±{vals.std(ddof=1):.4f}'])
mixed='''### 8.6 合并表示与未见实例的相反结果

原语编码之外，g10_mixed尝试结合局部与区域比例信息。它在实现变化诊断上缓解部分分数排名差异，却没有在未见实例方向获得平均提升。表Z对每个种子先等权平均6个留出实例，再计算种子均值和样本标准差，直接使用归档三种子CSV。[H7]

'''+table('表Z 特征改造在历史LIO协议下的三种子结果',['特征','seed42','seed43','seed44','种子均值与标准差'],lio)+'''
这组LIO为30轮、每轮预算4，与100轮预算16的跨实现编码实验不同，不能把两个协议的绝对AP放在同一排行榜。相同压缩协议内，39维配置均值约0.2112，合并配置约0.1632，方向与部分未见实现诊断相反。它表明抑制库单元词汇表差异可能同时损失某些实例的区分线索，不能用一个泛化维度的收益代表所有维度。

逐实例效果也不是同向：合并表示对epsilon有利，对beta等实例不利。单种子跨实例标准差较小，只能说明该次结果在实例间更接近，不能称为跨随机种子稳定性已提高。三种子汇总反而显示合并配置的种子标准差更大，必须保留这一后续修正。

另一个负面结果来自视图均值级对照剩余：先按每host的原始注入视图均值与标准差形成参考，再分别计算正常对照和木马视图漂移，发现部分改写两类漂移接近。这不证明节点级安全信息不存在，因为参考不是完全独立干净基底、统计粒度也是视图均值；它只说明全局漂移不能直接作为木马特异性证据。

### 8.7 与10.15阶段的衔接'''
history=history.replace('### 8.6 与10.15阶段的衔接',mixed)
for ch in range(3,9):
    a=history.index(f'## {ch} ');b=history.find('\n## ',a+1)
    if b<0:b=len(history)
    history=history[:a]+subheads(history[a:b],ch)+history[b:]
intro='''# 面向等价网表的图神经网络硬件木马检测模型研究

阶段性论文详细修订版　2026年10月28日

研究范围　早期S-GIN与多视图实验至10.15阶段模型及SAT功能验证

## 摘要

门级硬件木马检测不仅需要区分正常与恶意逻辑，还需要在逻辑等价但结构不同的实现之间保持有效。本文沿用原始课题“面向等价网表变体鲁棒的GNN木马检测”的研究目标，系统整理5月至10月的连续研究：从S-GIN阈值校准、困难负例挖掘和误报分析，发展到600视图等价矩阵、十划分三种子增广对照、结构捷径探针、对象级对应、A/B载荷控制、训练配置修正、原语特征编码，以及10.15阶段的双分支和区域监督模型。各阶段以独立数据版本与评测协议报告，并结合已撤回结论说明证据边界。

历史实验显示，等价增广的部分AP收益同样出现在恒等训练对照中；跨实现预测一致性改善也未必提高木马检出。死线载荷与真实输出劫持的受控比较进一步揭示，结构痕迹可能夸大检测能力。三种子训练修正将特定B型五电路LOCO配置的AP提高到0.2604±0.0053，同时推翻了根据单次欠训练结果作出的部分模型归因。原语编码在rs232开发诊断上缓解了门词汇表漂移，但仍受节点粒度、辅助损失坐标和重复使用开发集的限制。

在10.15正式数据折上，388视图包含约322万个变换侧节点。三种子结果中，双分支配置相对可信掩码单分支将逐视图节点AP从0.0693提高到0.1425；在加入逻辑锥代理的基线上，区域监督将节点AP从0.1410提高到0.1850，PO边界区域AP从0.2854提高到0.3968。模型结构和参数量仍存在配置差异，尚不能将提升完全归因于功能不变性。进一步的原生物理Q上下文SAT提取在8个小网表达到94.09%有效覆盖，但真实内容尚未显示稳定优于置换内容的跨插入检测收益。本文据此形成“可信对应—结构与功能代理—区域监督—功能证据对照”的研究路线，并将未完成的完整对比学习与全量SAT检测验证保留为后续工作。

关键词　硬件木马　等价网表　图神经网络　多视图学习　区域监督　功能特征

## Abstract

This staged study investigates graph neural network based hardware Trojan detection across logically equivalent gate-level implementations. It consolidates the research from early S-GIN threshold calibration and hard negative mining to a 600-view rewrite benchmark, controlled multi-view learning, representation probes, object correspondence, observable-payload controls, training configuration repair, primitive feature encoding, dual-branch GIN models and region supervision. Historical experiments show that identity-view training can explain a substantial part of augmentation gains, while stronger prediction consistency does not necessarily improve security detection. A three-seed configuration study obtains AP 0.2604±0.0053 under its historical five-circuit protocol, correcting conclusions drawn from undertrained models. On the current 388-view dataset, dual-branch encoding improves per-view node AP from 0.0693 to 0.1425, and region supervision improves node AP from 0.1410 to 0.1850 and output-boundary AP from 0.2854 to 0.3968. These results are reported within their own data versions and do not establish a cross-stage performance ranking. Native physical-state SAT extraction reaches 94.09 percent effective coverage on eight small netlists, but stable cross-insertion gains from correctly attached functional content remain unproven. The study distinguishes functional equivalence, security roles and prediction consistency, and provides traceable evidence for both improvements and limitations.

## 1 引言

门级网表将电路表示为逻辑单元与连接关系，适合图神经网络建模。然而，同一功能可以由大量结构不同的网表实现，综合、门分解和资源复用会改变门类型、邻域、路径深度甚至节点数量。模型若只记住某种实现中的局部外观，就可能把正常改写视为异常，也可能在真实木马被重新综合后失去检出能力。

原始课题《原论文.docx》将目标明确为：学习对等价变体鲁棒的表示，同时保持对恶意修改的敏感性，并以未见变体、泛化差距、检测稳定性和模块消融验证。本文以这一原始目标为主线，梳理研究为何从节点级阈值问题走向多视图表示、对象对应、区域监督和SAT功能证据，而不是将近期SAT工作当作全部研究内容。[D20]

本工程早期首先处理高召回下误报较多的问题，通过阈值扫描、困难负例和局部结构分析发现分数重叠。随后使用多机制等价矩阵检验实现变化，发现增广和一致性可改善某些改写测试，但跨宿主仍明显失效。表示探针和对象拆分统计进一步揭示，实现信息可被模型读取，而一对多关系不满足简单逐门一致性假设。

10月初建立更严格的安全对照，发现载荷不可观察会制造强烈结构伪信号；随后修正训练预算，避免将欠训练误判为模型结构失败。10.13的原语编码与绑定研究缓解部分跨实现差异，却没有解决全部粒度和安全语义问题。10.15阶段据此形成可信监督、双分支和区域级检测，10.22以后才进一步引入真实SAT功能关系与内容对照。各阶段既相互衔接，也有不同的任务与数据边界。

本文贡献包括：建立可追踪的等价变换与分组评测体系；通过恒等、正常匹配及A/B载荷对照分析检测收益来源；验证训练配置、原语表示、双分支及区域监督在各自协议下的作用；建立具有明确上下文和坐标合同的SAT功能证据，并保留无增益、绑定失败和协议修正等负面结果。尚未统一完成的GraphSAINT随机游走采样、SAGPool、多头注意力及完整功能正负对比学习，不写为当前已验证主模型。

## 2 研究基础与任务定义

'''
related=section('### 2.1 图学习','## 3 任务定义')
problem=section('### 3.1 等价视图','### 3.2 数据规模')
metrics=section('### 6.2 AP','### 6.3 跨宿主')
body2=subheads(related+'\n\n'+problem+'\n\n'+metrics,2)
body2+='''

### 2.6 本文的证据组织

历史文档、CSV和检查点具有不同证据强度。原始混淆矩阵可以重算工作点，却未必能恢复完整训练；多种子CSV可以核对聚合，却不能代替独立宿主测试；形式日志可以证明指定命题，却不提供完整安全标签。本文分别标明历史诊断、开发探索和当前正式折结果。

旧文档中“显著”“已闭环”“全域绑定”等表述不直接继承。新稿优先使用机读CSV和可重放证据；存在冲突时报告选定来源、保留冲突与解释限制。代码与数据均不为写作重新训练或扩大SAT搜索，后台全量任务与本文完成结果分开冻结。[H9]
'''
current_data=section('### 3.2 数据规模','### 3.5 历史数据')
current_data=current_data.replace('表1','表T').replace('表2','表U')
model=section('## 4 面向等价网表','## 5 真实SAT')
model=re.sub(r'^## 4 .+\n','',model,flags=re.M)
model=re.sub(r'公式（([1-4])）',lambda m:'公式（'+str(int(m[1])+1)+'）',model)
model=model.replace('图1','图B').replace('assets/图1_模型流程.png','assets/图1_模型流程.png')
results=section('### 7.4 双分支','### 7.8 高覆盖')
for n,label in [(7,'Q'),(8,'R'),(9,'S')]:results=results.replace('表'+str(n),'表'+label)
results=results.replace('图2','图C').replace('图3','图D')
intro9='''## 9 双分支与区域监督的阶段性模型

### 9.1 从前期研究到正式数据

10.15阶段将此前分散的绑定、误报、模型和泛化问题组织为数据标签、弱监督、特征模型、ABC/AIG专项、家族扩展和统一协议等工作包。它并非在10.22以后才产生：可信掩码、DFF/PO区域、双分支和区域损失均已有独立实验。后续N1至N4主要补充对照审计、三种子复核及统一评测。[H8]

前期600视图矩阵、10.10的180视图A/B数据、10.13开发诊断和当前388视图正式折各有来源。下文当前结果以hosts_bt31为主，不把历史最高AP作为同一基线。SAT扩展也使用单独的小网表和开发协议，不改变既有主表的定义。

### 9.2 keep与实例来源

none、cur、bnd与full分别代表不同的信号保护集合。全网keep可以保住更多名字和中间对象，却削弱改写自由度；只保留某些攻击相关线也可能让正常与恶意视图受到不同保护。可信性应依赖实例来源与端点关系，而不是只看名字存活率。

A3早期单例发现bnd与cur在部分绑定指标上相同，后续跨样本表则报告不同的区域与负例覆盖；这并不构成一条普适的“bnd总是更优”结论。论文采用其有限作用：保留必要状态或输出边界，检查标签是否有真实来源，同时报告保护策略对变换强度和对照的影响。

真实综合中，新中间单元可能没有原始实例祖先；assign展开与别名也可能改变节点顺序。实例级对齐器因而区分显式出处、端点驱动、身份回落及无法绑定，不将所有新节点自动判为正常。部分视图的payload被折叠或不再可观察时，不能仍把旧标签当作已验证安全角色。

### 9.3 新配方与边界存活

D2在rs232两个视图上比较五种ABC配方并执行CEC。有限试验显示锚点存活约0.472，而实例存活约0.280。它证明这组配方与保护策略下边界可以比实例更稳定，不是跨全部宿主、全部配方的硬上限。E类家族和新电路工作也应分别报告生成、形式验证与模型外推，不能因新增网表通过CEC就宣称模型泛化已经提高。[H8]

'''
chapter9=subheads(intro9+'\n\n'+current_data+'\n\n'+model+'\n\n'+results,9)
satmethod=section('## 5 真实SAT','## 6 实验设置')
satmethod=re.sub(r'^## 5 .+\n','',satmethod,flags=re.M).replace('表3','表V')
satmethod=re.sub(r'公式（([56])）',lambda m:'公式（'+str(int(m[1])+1)+'）',satmethod)
satmethod=satmethod.replace('附录B','附录C')
satresult=section('### 7.8 高覆盖','## 8 讨论')
satresult=satresult.replace('表10','表W').replace('表11','表X')
chapter10=subheads('''## 10 SAT功能证据与检测价值验证

### 10.1 功能特征研究的进一步收紧

前期信号概率、SCOAP、结构可达和局部真值表已为功能信息提供候选，但它们依赖输入独立性、边界自由度或结构代理。真实SAT阶段进一步区分候选命题、可行前提、形式状态、可靠对应和训练附着，目标是检验功能内容是否提供结构代理之外的信息。

早期脚本曾将influence限定在MUX等局部模板，后续逐节点cut表避免按测试正例或门型候选人为挑选。尽管如此，条件表行间变化仍不是对内部线施加强制干预的因果影响。物理Q、QN、输出极性与DFF数据输入必须按合同解释，不能仅凭同名网络复用旧proved。

'''+satmethod+'\n\n'+satresult,10)
discussion=section('## 8 讨论','## 10 结论')
discussion=re.sub(r'^## [89] .+\n','',discussion,flags=re.M)
chapter11=subheads('''## 11 综合讨论与后续研究

### 11.1 各阶段回答了什么

阈值与HNM回答分数重叠如何影响召回和误报；600视图回答训练策略能否缓解有限改写分布变化；恒等对照揭示增广收益来源；对象统计回答逐门一致性在哪些关系上失效；A/B载荷控制揭示不可观察逻辑的伪信号；训练扫描排除欠训练归因；原语编码处理门词汇表差异；区域监督处理定位粒度；SAT最后检验更严格功能内容的增量。它们共同支撑原始课题，不能只保留近期主表。

### 11.2 跨阶段不能建立单一性能排行榜

早期约0.6的改写AP、hosts_beta约0.26的LOCO、rs232原语约0.38的ys_rt AP与当前0.185的正式折AP，使用不同数据、正例覆盖、聚合方式和测试难度。数值高低不能表示研究时间上的进退。真正可比较的提升来自同一阶段固定合同中的配对配置，例如相同折上的A1到A2、A3到A5。

''' +discussion,11)
conclusion='''## 12 结论

本文按原始课题的研究目标，完整连接了早期S-GIN、等价增广、捷径与对象分析、安全对照、训练修正、原语表示、10.15阶段模型以及真实SAT验证。研究表明，面向等价网表的木马检测同时受到输入表示、对象对应、监督来源、训练充分性和安全上下文的限制，单一一致性指标或某次高AP无法覆盖这些因素。

历史实验获得了具有持续价值的结论：恒等训练可以解释部分增广收益；一对多对象不宜强制逐门相等；死线载荷会造成结构伪信号；严重欠训练足以改变模型比较；原语编码可缓解实现词汇表漂移。10.15阶段在更明确的折与三种子条件下验证了双分支配置和区域监督，构成当前模型侧的主要改进。SAT进一步提供可重放功能证据，但覆盖、信息量和安全检测增益仍须分开验证。

本阶段未完成原方案中所有模块的统一、独立确认。后续优先冻结可靠功能边界与安全角色，使用重新生成的折内置换和零内容控制检验SAT增量，补充参数量匹配与独立宿主测试；若功能内容不能产生稳定收益，则保留SAT作为验证与解释工具。研究目标仍是让模型对等价实现变化保持有效、对真实恶意修改保持敏感，而不是为加入某个模块寻找单一有利指标。

'''
references=section('## 参考文献','## 附录A')
appendix_sources=section('## 附录C 实验来源','## 附录D')
appendix_sources=appendix_sources.replace('## 附录C','## 附录B')
appendix_sources=appendix_sources.replace('以下路径相对工程根目录。','以下路径相对工程根目录；SAT段落中以tables/开头的简写统一指向10.15/06_统一评测协议/N4_三向泛化/tables/。')
appendix_contract=section('## 附录B SAT摘要','## 附录C').replace('## 附录B','## 附录C')
appendix_origin=section('## 附录E 原始方案').replace('## 附录E','## 附录D')
appendix_claim=section('## 附录D 结论','## 附录E').replace('## 附录D','## 附录E')
appendix_contract=appendix_contract.replace('表B1','表C1')
appendix_origin=appendix_origin.replace('表E1','表D1')
appendix_claim=appendix_claim.replace('表D1','表E1')
appendix_new='''## 附录A 历史研究覆盖索引

表A1 研究阶段与本文章节

| 范围 | 纳入内容及证据 |
|---|---|
| 5月24日与31日 | 第3章阈值曲线、混淆矩阵、HNM、BCE/Focal/ASL与子图位置探索 |
| 6月7日与14日 | 第3章误判门、不可达逻辑、标签问题及标量一致性探索 |
| 6月21日与28日 | 第3章LOCO、模型选择与阈值目标变化；TrojanSAINT初步复现不列正式比较 |
| 8月30日与9月6日 | 第3–4章规则修正、训练验证划分错误、早期变体与区域思想 |
| 9月13日 | 第4–5章困难变体挖掘、修改与未修改对象的漂移 |
| 9月26日 | 第4章600视图、CEC、120次主运行、恒等与label-free对照、预算与LOCO |
| 10月5日 | 第5章表示probe、对象类别、双干预、M0–M3与inspection-hard |
| 10月10日 | 第6章A/B载荷、功能与cut代理、简单模型、匹配对照及旧结论更正 |
| 10月12日 | 第7章欠训练修正、三种子学习率预算选择、损失扫描与配对激活 |
| 10月13日至14日 | 第8章真实综合、特征保持率、原语编码、邻域区域、保名与别名失败 |
| 10月15日至19日 | 第9章keep、实例来源、可信掩码、区域构造、双分支与区域损失 |
| 10月19日至22日 | 第9章N1–N4补充对照、三种子复核及正式折体检 |
| 10月22日至28日 | 第10章功能语义修正、边界配对、覆盖与内容对照、全量任务边界 |

本索引按研究内容覆盖阶段，不以目录数量代替结论。没有复核全部原始预测或不具备同口径对照的旧结果，在正文明确作为历史记录或探索证据。

'''
h_sources='''

[H1] 早期S-GIN：D:/GIN训练/S-GIN训练2026-5-24.docx、5-31、6-7、6-14、6-21、6-28同系列文档。新稿保存原图、文本、原始文件哈希及混淆矩阵重算。

[H2] 早期改写与诊断：D:/GIN训练/8.30/日志2.txt、9.6/日志3.txt、9.13/日志4.txt、9.13/pairwise_by_group.csv及hard_view_mining_report.csv。历史日志中的经验推断不直接作为形式结论。

[H3] 等价基准：STAGE_REPORT.md、TASK4_D2_GROUPS_REPORT.md、generate_trans/matrix/cec/{cec_results.csv,negative_control_results.csv}；D:/GIN训练/9.26/GIN_train/results/下的120运行主表、预算、恒等及label-free控制CSV。

[H4] 捷径与对象：D:/GIN训练/10.5/report/task1至task6各报告及results/phase2/下audit、object_stats、counterfactual、task4_methods、task5_viewpolicy、loco的CSV。表F和表I使用机读CSV，相关性不作因果与显著性证明。

[H5] 安全对照：10.10/最终说明.md、第三块_执行记录.md及results/summary_*.csv、beta/simple_models_macro.csv。文字与表冲突时以正文明确指定的机读表为准；欠训练结论由H6修正。

[H6] 训练配置：10.12/说明.md、执行记录.md、results/stage0至stage5各CSV；三种子统计重新计算。lambda局部扫描不等于全局最优或零权重消融。

[H7] 跨实现表示：10.13/第四步_四组对比.md、特征筛选对比.md、10.14.md、step4_four_groups.csv、step4_3seed_compare.csv、feature_retention_g5.csv、control_residual.csv及rank_pct系列CSV。

[H8] 10.15前期模型：00_说明/10.15至今完成情况.md、10.19至今完成情况.md，以及A3_keep三方案、D2_新abc配置和07_论文图表/TABLES.md。旧进度文档中“显著、全域、硬上限”等措辞不自动继承，最终主表以D3至D5为准。

[H9] 新稿取证：构建与核验/详细修订取证.json保存本次输入哈希、历史CEC计数、早期混淆矩阵重算、训练三种子统计与冲突说明。构建只涉及写作产物，不导入训练入口或启动SAT。
'''
manuscript='\n\n'.join([intro.strip(),body2,history,chapter9,chapter10,chapter11,conclusion,references,appendix_new,appendix_sources+h_sources,appendix_contract,appendix_origin,appendix_claim])+'\n'
# Uniquely named interim captions become sequential paper table numbers.
labels=re.findall(r'^表([A-Z])\s',manuscript,re.M)
assert len(labels)==len(set(labels)),labels
mapping={v:str(i+1) for i,v in enumerate(labels)}
manuscript=re.sub(r'表([A-Z])(?![A-Z0-9])',lambda m:'表'+mapping[m[1]],manuscript)
figurelabels=re.findall(r'^图([A-Z])\s',manuscript,re.M)
fm={v:str(i+1) for i,v in enumerate(figurelabels)}
manuscript=re.sub(r'图([A-Z])(?![A-Z0-9])',lambda m:'图'+fm[m[1]] if m[1] in fm else m[0],manuscript)
manuscript=re.sub(r'assets/图\d+_模型流程.png','assets/图1_模型流程.png',manuscript)
manuscript=re.sub(r'assets/图\d+_主模型消融.png','assets/图2_主模型消融.png',manuscript)
manuscript=re.sub(r'assets/图\d+_区域监督.png','assets/图3_区域监督.png',manuscript)
# Historical figures are imported unchanged. All current figures are generated
# by the copied deterministic builder from their original audited sources.
shutil.copy2(B/'早期原始插图/S-GIN训练2026-5-24/image1.png',A/'历史图_阈值扫描.png')
assert '{{' not in manuscript
(H/'面向等价网表的图神经网络硬件木马检测模型研究.md').write_text(manuscript,encoding='utf-8')
sources=[ROOT/'10.15/原论文.docx',ROOT/'STAGE_REPORT.md',ROOT/'TASK4_D2_GROUPS_REPORT.md',ROOT/'generate_trans/matrix/cec/cec_results.csv',ROOT/'generate_trans/matrix/cec/negative_control_results.csv']
sources+=list(Path('D:/GIN训练').glob('S-GIN*.docx'))
sources +=[Path('D:/GIN训练')/p for p in ['8.30/日志2.txt','9.6/日志3.txt','9.13/日志4.txt','9.13/pairwise_by_group.csv','9.13/hard_view_mining_report.csv']]
sources +=list(Path('D:/GIN训练/10.5/report').glob('*.md'))
sources +=[Path('D:/GIN训练/10.5/results/phase2')/p for p in ['audit/single_to_composed_d2_probe_metrics.csv','object_stats/single_to_composed_d2_summary.csv','object_stats/single_to_composed_d2_drift_by_category.csv','counterfactual/dual_intervention_sensitivity.csv','task5_viewpolicy/single_to_composed_d2_model_summary.csv','loco/loco_summary_ckpt.csv']]
sources +=[Path('D:/GIN训练/9.26/GIN_train/results')/p for p in ['ALLFOLDS_groups_macro_amp.csv','single_to_composed_d2_budget_sweep.csv','identity_control_vs_real_transform.csv','labelgated_vs_labelfree.csv']]
sources +=[ROOT/'10.10'/p for p in ['最终说明.md','第三块_执行记录.md']]+list((ROOT/'10.10/results').glob('summary_*.csv'))
sources +=[ROOT/'10.12'/p for p in ['说明.md','执行记录.md']]+list((ROOT/'10.12/results').glob('*.csv'))
sources +=[ROOT/'10.13'/p for p in ['第四步_四组对比.md','特征筛选对比.md','10.14.md','step4_four_groups.csv','step4_3seed_compare.csv','feature_retention_g5.csv','control_residual.csv']]
sources +=[ROOT/'10.13'/p for p in ['lio_summary_g5_3seed.csv','lio_summary_3seed.csv','rank_pct_g10_3seed.csv']]+[ROOT/'phase2/p2common.py']
sources +=[ROOT/'10.15'/p for p in ['00_说明/10.15至今完成情况.md','00_说明/10.19至今完成情况.md','01_数据与标签/A3_keep三方案/说明.md','04_ABC_AIG专项/D2_新abc配置/说明.md','07_论文图表/TABLES.md']]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
records=[dict(path=str(p.resolve()),sha256=sha(p),bytes=p.stat().st_size) for p in sources]
cec=read(ROOT/'generate_trans/matrix/cec/cec_results.csv');neg=read(ROOT/'generate_trans/matrix/cec/negative_control_results.csv')
assert len(cec)==600 and all(r['status']=='PASS' and int(r['proven'])>0 and int(r['unproven'])==0 for r in cec)
negcounts={k:sum(r['kind']==k for r in neg) for k in {r['kind'] for r in neg}}
report=dict(time=datetime.datetime.now().astimezone().isoformat(),inputs=records,main_tables=len(labels),figures=len(figurelabels),chinese_chars=len(re.findall(r'[\u4e00-\u9fff]',manuscript)),cec_rows=len(cec),cec_status_counts={k:sum(r['status']==k for r in cec) for k in {r['status'] for r in cec}},negative_control_counts=negcounts,negative_control_status_counts={k:sum(r['status']==k for r in neg) for k in {r['status'] for r in neg}},training_aggregates=agg,early_confusion_recomputed=[dict(TP=t,FP=f,TN=tn,FN=fn,recall=t/(t+fn),fpr=f/(f+tn)) for t,f,tn,fn in [(24,589,1567,2),(23,421,1735,3),(22,280,1876,4)]],conflicts=['October10 prose gives different A/B method metrics; manuscript uses summary_methods_ab.csv and flags discrepancy.','Probe prose differs in some random operator accuracy values; table generated directly from CSV.','Early AP source calls PR-AUC; no blanket AP reinterpretation.','Standardized feature residual is not raw Trojan-minus-control difference.','Budget and historical train run totals vary by report; only the 120 main runs are treated as the verified sweep.'],new_training_runs=0,new_sat_searches=0,errors=[])
(B/'详细修订取证.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
# In the new folder, rendering and frozen inputs include this complete review.
b=H/'build_paper.py';bs=(H.parent/'阶段性论文_20261028/build_paper.py').read_text(encoding='utf-8')
bs=bs.replace("records=[]\n", "records=[]\n    detail=json.loads((BUILD/'详细修订取证.json').read_text(encoding='utf-8'))\n    assert not detail['errors']\n    for row in detail['inputs']:\n        assert sha(row['path'])==row['sha256']\n        records.append(row)\n")
bs=bs.replace("(?:表(?:\\d+|[A-Z]\\d+)|图\\d+)","(?:表(?:\\d+|[A-Z]\\d+)|图\\d+)")
bs=bs.replace("if line.startswith('阶段性论文'):p.alignment", "if line.startswith(('研究范围','研究依据')):p.paragraph_format.first_line_indent=Pt(0);p.alignment=WD_ALIGN_PARAGRAPH.CENTER\n        if line.startswith('阶段性论文'):p.alignment")
bs=bs.replace("if line.startswith('[D'):","if line.startswith(('[D','[H')):")
bs=bs.replace("iscaption or line.startswith('[D')", "iscaption or line.startswith(('[D','[H'))")
b.write_text(bs,encoding='utf-8')
r=H/'render_with_native_word.py';rs=r.read_text(encoding='utf-8').replace('版式预览_v3','版式预览_v1');r.write_text(rs,encoding='utf-8')
print(json.dumps({k:report[k] for k in ['chinese_chars','main_tables','figures','errors']},ensure_ascii=False))
