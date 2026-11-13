from pathlib import Path
import csv,hashlib,json
import numpy as np
O=Path(__file__).resolve().parent;R=O.parents[1];D=R/'10.15/00_说明'
def read(n):return json.loads((O/n).read_text(encoding='utf-8-sig'))
def rows(n):
 with (O/n).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert read('VERIFIED.json')['passed']
rr=rows('six_code_metrics.csv')
def score(domain,group,arm,tag=None):
 return float(np.mean([float(r['family_macro_win']) for r in rr if r['domain']==domain and r['group']==group and r['arm']==arm and (tag is None or int(r['tag'])==tag)]))*100
name='修订等价锥编码敏感性与迁移缺口审计_20261107.md'
text='''# 修订等价锥：编码敏感性与训练/留出差距

2026-11-07。复用上一轮INIT、Z/R/P末步32检查点及9000/9001表示，补充9002—9005四套共享重编码的冻结前向；144次额外模型前向，0反向、0优化器、0更新、0新增SAT、0检测微调、0测试集读取。全部旧资产哈希不变。本轮约26秒冻结推理，后处理另计。

结论：真实目标训练内有效，但“训练内改善却未迁移”要拆开看——非MUX已较容易，MUX训练内就没有稳定学好；留出难源与容易源差距远大于整体平均。边界编码造成的排序波动足以掩盖当前微弱的关联收益，但没有证明它是唯一原因。

## 1. 编码敏感性：输入正确，关系排序仍不稳定

|编码|INIT|Z|R真实|P置换|R−P（百分点）|
|---|---:|---:|---:|---:|---:|
'''
for tag in range(9000,9006):
 vals=[score('val','all',a,tag) for a in ['INIT','Z','R','P']]
 text+=f'|{tag}|'+ '|'.join(f'{x:.2f}%' for x in vals)+f'|{vals[2]-vals[3]:+.2f}|\n'
text+='''
六编码留出均值INIT/Z/R/P=73.52/72.60/73.63/72.91%。R在5/6优于Z和P，但只在3/6优于INIT；R均值仅高于INIT约0.11个百分点。相较只看原两编码，补充诊断出现微弱正向迹象，应如实保留；这4套是事后诊断，不得替换9000主指标、挑最优编码，或当成6个独立种子/宿主来宣称显著收益。

9000→9001，R留出真假逐对比较按单元等权的翻转率27.17%，初始化已有29.79%；R的余量变化RMS=0.1949，而同编码R−P余量差RMS=0.0691，约2.82倍。这里余量=错误候选距离−真实候选距离。训练对应比值仅0.71，说明在留出数据上编码波动相对学习差异更突出；不是归因百分比。

独立检查确认6套编码仅改变16个边界身份通道，9个节点类型通道、图边、引脚角色、相位及节点顺序均不变。相同上下文跨实现共享同一编码，没有发现错配接口。输入坐标变化仍会改变神经模型计算，不能把这个现象解释为CEC证明出错。

原两编码R−P总差从−4.00变为+0.57个百分点：ctlmatchb含MUX贡献+2.63、同源非MUX贡献−0.11、injalpha贡献+2.05个百分点（按73单元等权可加）。排名反转由MUX和容易源共同推动，不能只归因一个对象。

## 2. 哪些真的学好了，哪些没有

|子集/口径|INIT|Z|R|P|
|---|---:|---:|---:|---:|
'''
for domain,group,label,tag in [('train','all','训练全体/6编码家族宏平均',None),('train','nonMUX','训练非MUX/9000家族宏平均',9000),('train','MUX','训练MUX/9000（3单元）',9000),('val','s38417t100__ctlmatchb_d1_s42/all','留出ctlmatchb/6编码均值（34单元）',None),('val','s38417t100__injalpha_d1_s42/all','留出injalpha/6编码均值（39单元）',None),('val','MUX','留出MUX/6编码均值（23单元）',None)]:
 text+=f'|{label}|'+ '|'.join(f'{score(domain,group,a,tag):.2f}%' for a in ['INIT','Z','R','P'])+'|\n'
text+='''
训练非MUX与全体行采用家族等权，不能用上述两行直接反推单元等权总体。R训练全体在6/6编码都优于Z和P，说明真实关联学习并非完全没发生。但是训练MUX主编码从INIT63.89%降到R52.78%；9001为55.56%→52.78%，不支持“MUX训练已经学会”。不能只通过加宿主泛化项来解释或解决它。

留出injalpha初始化约95.80%，R约96.65%，接近上限；ctlmatchb初始化约47.96%，R约47.22%，困难集中于此源。同一ctlmatchb、同一abc/aig流程内，9000的R在MUX为40.22%，非MUX为56.82%；9001为50.72%、50.76%。非MUX也不稳定，故难点涉及abc/aig跨结构对应，不能断言只要修MUX即可。所有胜率是功能真假配对比较，不是木马召回/AP。

## 3. 训练支持为何不足以解释为单纯宿主偏差

|来源|单元/函数类|实现流程|含MUX单元|最大端点门数中位/深度中位/边界数中位|
|---|---|---|---:|---|
|训练rs232 ctldup|1/3|abc/opt|0|24/10/7|
|训练rs232 injalpha|1/3|abc/id|0|30/15/12|
|训练s15850 ctldup|2/6|id/opt|0|637/58.5/182.5|
|训练s15850 injepsilon|3/9|abc/aig|3|1076/70/182|
|留出s38417 ctlmatchb|34/88|abc/aig|23|160.5/32/34|
|留出s38417 injalpha|39/94|id/opt|0|183/21/59|

同一训练源的3个MUX单元共享上下文，9个函数类不是9个独立宿主；全部原生MUX在一侧、另一侧展开，留出23个MUX也同样单侧。MUX引脚矩阵仅在19/32批有实际更新，三组一致；不能当成程序漏训练。虽然32步不断换边界编码，但支持只有3个大MUX单元、一个制造源。训练MUX反而更大更深，不符合“验证比训练深”这一解释。

来源、宿主、流程、大小和功能类型互相混杂。仅凭训练vs留出差异不能证明模型依赖宿主身份，也不能证明缺失某种门型是唯一原因。当前更有证据的解释是：小而偏的功能支持、组合关系尚未学会、神经表示对任意身份编码的关系排序不稳定共同存在。高整体分数含易源的初始化先验，不能全部算作功能学习成果。

## 4. 下一轮单因素方案（只准备，未执行）

先检查并冻结“同一上下文共享重编码下，候选相对分布一致”的目标。它约束同一真实函数问题换输入身份坐标后的排序，不要求两个不同函数向量相同，也不把边界输入身份全部抹掉。不要同时换模型、训练池、损失负项、种子、曝光或加入检测微调。

采用Z/R/P × 一致性关闭/开启，共6组，各32步，seed42共同原初始化。为了隔离一致性这一因素，6组全部使用每步两个共享编码（tag=t和10000+t），消费相同两个图批次；原Z/R/P基础损失均取两编码平均。相较旧单编码协议，这是新预算，不能直接以旧R充当公平基线。

对每个查询在3个候选上的分布p=softmax(−RMS距离/1)，计算两编码分布的Jensen–Shannon散度，按原查询权重平均Lcons。开启组加同一冻结系数λ，关闭组λ=0。JS不读取真实/置换目标，因此在P内不会再偷偷增加真实正配对；两编码的P仍用同一冻结逆置换规则，保留原公共负项。标记0=关闭，1=开启，形成Z0/Z1、R0/R1、P0/P1。

λ在下一轮无更新预检时仅用训练批1/2/16/32和共同初始化确定：令中位数λ||∇Lcons||/||∇Lbase_R||约0.25，六组共用一个λ；记录公式、实际比值及与真实项的方向，随后冻结，不看验证成绩调节。若JS梯度近零、无效或引起强制相等/目标冲突，先停止制定训练执行，不用虚构大系数补救。本轮没有做这项梯度标定。

各组每32步仍64逻辑单元名额/384查询身份，但每查询消费两编码，实际为128编码单元输入、768编码查询、2304候选距离、768公共负项计算；开启/关闭组都计算JS并以λ开关纳入同一次反向，确保前向预算相同。功能曝光身份次数16不变，编码输入次数翻倍；两者分别记账。

评价仍固定末步32、73个H3，以9000为预定主诊断，保留9001—9005；额外冻结9006—9011作未用于本轮诊断的新编码。所有编码都报告，不选择最佳映射或检查点；它们仍不是新的独立电路。检查R1是否优于R0、P1和Z1，是否降低逐对翻转，以及ctlmatchb/MUX是否改善。只稳定容易源或只令分布更均匀而无真实排序改善，均不能视作功能迁移成功。若MUX训练内仍接近随机，下一步应回到组合表示与已有证明的训练支持设计，而非直接加种子或扩大SAT。

首先只完成这6组的实际双编码加载和无更新梯度预检，再决定是否训练。当前已揭示的验证子集只能继续用于诊断，不能通过反复调整后仍将其包装为未触及的确认性评估。

## 证据与复核

目录`_p0pilot/cec_repaired_transfer_audit_20261107/`：AUDIT_CONTRACT.json、COMPLETE.json、VERIFIED.json、six_code_metrics.csv、unit_metrics.csv、encoding_sensitivity.csv、code_vs_training_effect_scale.csv、source_MUX_gap_decomposition.csv、source_support.csv、within_source_flow_MUX.csv和新增冻结表示。CPU独立复算600组指标（最大误差3e-15以内）、8组敏感性、10组输入不变性检查。首次敏感性复核对FP32余量RMS误设1e-10容差，修正为1e-6后通过；排序翻转仍要求1e-10一致，原日志保留，未重跑冻结推理。
'''
(D/name).write_text(text,encoding='utf-8')
entry='''

### 2026-11-07 修订等价锥编码敏感性与迁移缺口审计（未训练）

复用本轮检查点与两编码表示，补9002—9005冻结前向144次，0反向/0优化器/0训练/0SAT/0测试读取。六编码留出INIT/Z/R/P均值73.52/72.60/73.63/72.91%，R在5/6胜Z和P但只3/6胜INIT；有微弱正向诊断迹象，不能替换原9000失败主结果或当独立种子。R留出真假排序两原编码翻转27.17%；编码余量变化约为R−P差异的2.82倍，输入检查仅16边界通道变化，未发现坐标错配。

关键修正：训练整体R改善不代表MUX已学好。训练MUX仅s15850 injepsilon的3单元/9函数类，9000 INIT63.89%→R52.78%；训练非MUX81.25%→95.83%（家族宏平均）。留出六编码R在ctlmatchb47.22%、injalpha96.65%、MUX47.10%，难源/流程与MUX混杂；同源非MUX也不稳。训练MUX更大更深，不能归因验证深度更大，也不能单独归因为宿主偏差。

下一轮建议先冻结并预检“相对候选分布的共享重编码JS一致性”单因素：Z/R/P各设开/关，6组均消费相同两编码、基础损失取均值，仅JS系数开关不同；系数仅用训练初始化梯度标定，不用验证调节。保持原7单元/初始化/模型/负项/32步，分别记逻辑曝光及双编码实际计算预算；禁止直接单锥向量身份重排不变。先加载及无更新梯度预检，尚未训练或标定。独立复算600组指标、8组敏感性和10组输入检查通过，旧文件保持。

详见[编码敏感性与迁移缺口审计](修订等价锥编码敏感性与迁移缺口审计_20261107.md)，证据`_p0pilot/cec_repaired_transfer_audit_20261107/`。
'''
for n in ['SAT作用证明.md','SAT工作总结.md']:
 p=D/n;b=p.read_bytes();old=b.decode('utf-8-sig');assert '修订等价锥编码敏感性与迁移缺口审计（未训练）' not in old
 (O/(n+'.before')).write_bytes(b);p.write_text(old+entry,encoding='utf-8')
manifest={p.name:sha(p) for p in O.iterdir() if p.is_file() and p.suffix in ['.py','.json','.csv','.npz'] and p.name not in ['OUTPUT_MANIFEST.json','PUBLISHED.json']}
(O/'OUTPUT_MANIFEST.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
(O/'PUBLISHED.json').write_text(json.dumps(dict(report=str(D/name),report_sha=sha(D/name),summaries_updated=True,training=0,SAT=0),ensure_ascii=False,indent=2),encoding='utf-8')
print('Published audit and updated both summaries.')
