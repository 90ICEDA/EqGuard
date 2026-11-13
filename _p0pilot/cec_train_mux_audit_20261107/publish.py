from pathlib import Path
import csv,gzip,hashlib,json
import numpy as np
O=Path(__file__).resolve().parent;R=O.parents[1];D=R/'10.15/00_说明'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(n):
 with (O/n).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert read(O/'VERIFIED.json')['passed'];us=read(O/'SELECTED_UNITS.json');center=rows('IMPLEMENTATION_CENTER_DIAGNOSTIC.csv')
# Explicit truncated root formulas;Cn denotes an existing internal subcone,never a new free boundary.
with gzip.open(R/'_p0pilot/cec_boundary_panel_expand_20261107/local_graphs.json.gz','rt',encoding='utf-8') as f:z=json.load(f)
graphs=dict(zip(z['cone_ids'],z['graphs']));formula=[]
for u in us:
 for f,c in enumerate(u['cones'][::2]):
  g=graphs[c];inc={n:[] for n in range(len(g['op']))}
  for s,d,r,p in g['edge']:inc[d].append((s,r,p))
  def expr(n,depth):
   op=g['op'][n]
   if op<2:return ('PI' if op==0 else 'Q')+str(g['slot'][n])
   if op<4:return str(op-2)
   if depth==0:return 'C'+str(n)
   return ['AND','OR','XOR','NOT','MUX'][op-4]+'('+','.join(('~' if p else '')+expr(s,depth-1) for s,r,p in sorted(inc[n],key=lambda e:e[1]))+')'
  formula.append(dict(unit_id=u['unit_id'],function=f,cone_id=c,near_root_formula=expr(g['root'],3),note='Cn is the unchanged internal subcone,not a new independent input;MUX args=A,B,S'))
(O/'NEAR_ROOT_FUNCTIONS.json').write_text(json.dumps(formula,indent=2),encoding='utf-8')
plan=dict(status='proposal_only;no new model/interface/training executed',factor='nativeMUX vs fixedBoolean-equivalent4gate AND/NOT expansion at isolated cone-loader interface only',formula='U=AND(S,B);V=AND(NOT(S),A);W=AND(NOT(U),NOT(V));Y=NOT(W);NOT on edges encoded byexisting phasebits except output NOTnode',inherit='all original input/consumer phase bits preserved;orderedpins A,B,S decodedbeforeexpansion;fulloriginal PI/Qboundary preserved',baseline='current two-code Z0/R0/P0,JSdisabled;reuse only ifcommonpool/schedule/inputs/initialization unchanged',new_arms='expanded Z0/R0/P0 same32steps seed42 oldINITIAL_STATE,25d,Adam,logicalexposure,2codes perstep;do not reuse oldsingle-code arms',eligibility_gate='before any training recheck encoderforcedties/positive-negative feasibility under BOTHrepresentations;commonmask required;ifchanged rebuildmatchednativebaseline too,never silently reuse mismatched oldbaseline',capacity_caveat='nominal47360params unchanged;3MUX-specific4096matrices becomeunused ifallMUXexpanded,activeparameterusagechanges;mustreport,not puresemantics proof',budget='same logicalsamples/2code exposures/updates;actualDAGnodes andcomputeincrease,reportseparately ratherthanclaimidenticalFLOPs',preflight_only_next='losslessroot/PIQbinding,8localBooleanassignments pertemplate,replayexisting128patterns,alias/phase/root consumers,actualloading,noncollapse,no-updateVJPs,commoneligibility;noSAT needed',evaluation='same73H3fixedmain9000,all12tagsdiagnostic,per-source/MUX/rootMUX-vsinternalMUX;INIT separate;new forcedties notcountedaslearnedgain',training_authorized=False,training=0,SAT=0)
(O/'NEXT_SINGLE_FACTOR_PLAN.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
name='训练MUX真假函数与原生展开对应审计_20261107.md'
text='''# 3个训练MUX单元：真假函数、实现对应和引脚审计

2026-11-07。结论：没有发现这9条真实配对、9条不同函数反例或MUX引脚角色错误。现有失败不能解释为“错误配对/无梯度/所有区分信息穿过70层”。更具体的困难是：只有一个源的少数函数变体，原生MUX与展开门网络走不同神经计算路径，共同实现偏移与组合关系尚未对齐；这些是证据支持的机制线索，不是排他的因果证明。

## 1. 3个单元究竟包含什么

全部来自训练源s15850t100__injepsilon_d1_s42、ys_abc→ys_aig、同一native物理Q上下文；没有新候选、验证正例选样或新SAT。

|单元前缀|函数对|abc侧|aig侧|门数/最大深度|
|---|---:|---|---|---|
|d7a3bddd|3|3个根MUX|3个NOT根，MUX已展开|481/22 → 1076/70|
|6d3ac3fe|3|3个根MUX|3个NOT根，MUX已展开|481/22 → 1076/70|
|65058cd2|3|均AND根；其中2个内部含MUX，1个不含MUX|均NOT根，无原生MUX|423—426/25 → 896—905/72—73|

修正统计口径：是3个“含MUX的候选集合”、9个函数对、18端点、8个原生MUX实例，绝非9个独立MUX实例或3个独立制造源。旧“训练MUX”单元指标包含第三组内那个不含MUX的函数；旧结果不删除，本轮明确这一边界。

前6个函数可具体写为`F_i=S ? Q_Bi : Q_Ai`：

|单元|函数|A（S=0数据端）|B（S=1数据端）|
|---|---:|---:|---:|
|d7a3bddd|0|Q421|Q320|
|d7a3bddd|1|Q443|Q417|
|d7a3bddd|2|Q247|Q356|
|6d3ac3fe|0|Q311|Q370|
|6d3ac3fe|1|Q348|Q96|
|6d3ac3fe|2|Q372|Q175|

编号是固定上下文的物理Q槽位，不是木马标签。六者共享同一个复杂选择器S：abc侧480/481门相同，aig侧1070/1076门相同；它们是相同选择网络的数据端变体，并非6种独立组合拓扑。已有128输入中S有112次为1，但这不是精确输入概率或全真值表。

第三单元的原生侧近根公式如下，保留现有内部锥Cn，不把它们当自由新输入；MUX参数顺序为A/B/S：

'''
for f in formula[-3:]:text+=f"- F{f['function']}：`{f['near_root_formula']}`\n"
text+='''
该组三个根共享部分使能/屏蔽逻辑，不能把它们都描述为根MUX选择Q信号。精确根、引脚及完整图保留在FUNCTION_PAIRS.csv、CONE_STRUCTURE.csv及原始接口中。

## 2. 真实配对和错误候选是否可靠

9个真函数对复用**同一条联合PO/D CEC成功查询**，其不同obs分量分别对应9个根。检查model.v、run.ys、run.log哈希、精确查询和SUCCESS块，再核对obs拼接向量索引→根bit→两实现。不能将其写成9次独立SAT证明。

进一步把18个锥的原始门表达式及PI/Q/反相绑定逐项与该证明模型的left_design/right_design赋值核对，重建18个实际加载图，全部一致。因此不是只凭root名字或以前的proved标记认定等价。

9条不同函数证书全部在原保存输入上重放：每条均真对应两侧一致、不同函数之间输出不同。前两单元的不同候选在已有128输入上相差59—68位，第三组相差12—27位；负对不是仅靠一个脆弱样本猜出来，也不存在把等价函数错当负对的当前证据。128模式只证明这些负对确实不等，不能用来替代真对CEC全输入等价证明。

## 3. 引脚角色与展开实现

8个原生MX2X1_RS的24条输入边全部核对：role2=A、role3=B、role4=S0，符号相位与raw连接一致。布尔语义为`(~S & A) | (S & B)`，未发现数据端/选择端交换。

前6个aig输出可精确分解为：

`Y = (Q_B & T) | (Q_A & ~T)`（展开图由AND/NOT实现）

T和NOT(T)在原aig图中有明确的直接NOT连接，不是按相似嵌入猜出的对应；对局部A/B/T的8种赋值验证该尾部恰好是MUX(A,B,T)。这是代数/局部结构检查，未追加SAT或真实电路输入。完整原生/展开输出仍由上述既有CEC覆盖；此处不把T与另一实现S的内部信号映射额外包装成已独立完成的新CEC。

关键区别：原生根通过3个专用角色矩阵直接聚合A/B/S，而展开侧通过AND/NOT及通用角色矩阵计算。正确引脚进入模型，并不自动赋予这两个神经计算式相同的组合含义。

## 4. 为什么训练内仍难

### 不是所有判别信号都穿过70层

前6个函数的A/B数据端为物理Q：原生到输出距离1条边，aig侧均4条边。70层最大深度主要位于共同选择/上下文网络；不能据此推断数据端身份必然因70次传播全部消失。另一些边界路径确实更长，但这不是已证明的唯一瓶颈。

冻结INIT/R0/R1检查点，在9000/9001对3个单元求真实候选CE梯度，共18次前向/18次autograd，0优化器、0更新。R0三类MUX角色矩阵梯度范数分别约0.088—0.360、0.090—0.343、0.044—0.104，边界身份梯度范数约0.166—0.269，均非零。排除了这些检查点“角色参数没参与/梯度全断”的说法；非零梯度不等于已经学会正确运算。

### 共同实现偏移明显，但去掉它仍不足

对每个3函数集合，分别减去该侧3个根表示均值，仅作冻结候选集合诊断。该操作不读真/假对应标签，但依赖完整候选集合，不能直接当作通用单节点部署接口或新的主要评价。

|单元|R0原始胜率，12编码均值|去两侧均值后|实现均值偏移/侧内离散RMS|
|---|---:|---:|---:|
'''
for u in us:
 rr=[r for r in center if r['arm']=='R0' and r['unit_id']==u['unit_id']];mean=lambda k:float(np.mean([float(r[k]) for r in rr]));text+=f"|{u['unit_id'][:8]}|{mean('raw_win')*100:.2f}%|{mean('centered_win')*100:.2f}%|{mean('offset_over_within'):.2f}|\n"
text+='''
实现偏移大于侧内函数差异，但中心化后仍只有约56%—60%，R1约57%—62%；不是简单平移校正就能解决。证据更支持“实现通道不一致、候选之间相对功能几何也未对齐”，而非只缺一个宿主去偏步骤。

## 5. 下一轮单因素方案：只检验MUX局部规范展开

优先准备**原生MUX vs 固定AND/NOT模板**的接口单因素预检，暂不训练。保留完整PI/Q边界、原函数/候选/负证书和全锥，不截成未经证明的自由内部边界。模板：

`U=S & B; V=(~S) & A; W=(~U) & (~V); Y=~W`

使用现有相位位表示输入/内部反相，生成3个AND及1个NOT；所有输入和消费者原相位必须继承，MUX旧节点映射到Y。这样利用已知原语代数先验，避免仅靠极少样本学会“一个MUX”和“一组AND/NOT”的表示对应；不输入真值表、SAT标签或真实配对答案。其余OR/XOR/NOT/AND编码不变，不同时做全门型规范化、改深度、改池或调整损失。

拟比较同一双编码协议下Z/R/P三组的原生版本与展开版本，JS均关闭，seed42/32步/原初始化/Adam/逻辑曝光不变。只有在候选准入、采样索引和预算完全未变时，才复用本轮原生Z0/R0/P0，未来只新增展开侧三组；当前不执行。

**必须先重新检查双方编码器强制相等和P目标可实现性。**若规范展开使某些真配对成为参数无关的完全相同计算图，就不能让P把错误候选严格排在其前，重犯历史控制缺陷。采用两种表示共同合格掩码；如果需要剔除/改采样，则原生基线也要按新共同合同重建，不能直接沿用旧结果。新增确定性相等只记代数先验，不算新学习收益；验证子集也须标出，不静默删除困难或改主要指标。

模型名义参数仍47,360，但全部MUX展开后，三个专用4096参数矩阵不再被使用；有效参数使用/共享路径发生变化，这是该表示因素的组成部分，必须明报，不能声称全部有效容量不变。逻辑样本与更新预算相同，DAG门数增加，实际节点计算量不完全相同，也须单列。

下一轮先完成模板局部8赋值恒等式、已有128模式重放、raw/根/消费者/相位与别名对齐、共同准入和实际加载/无更新梯度预检；不需新SAT。若通过，再决定是否训练展开侧Z/R/P。评估保持原73个H3、9000主诊断及12编码，分根MUX/内部MUX/不含MUX函数、源与流程报告。当前不继续加JS系数、补种子或检测微调。

## 证据与复核

目录`_p0pilot/cec_train_mux_audit_20261107/`：PROOF_BINDING_AUDIT.csv、PROOF_DESIGN_RAW_GATE_BINDING.csv、FUNCTION_PAIRS.csv、NEGATIVE_CERTIFICATE_REPLAY.csv、RAW_PIN_ROLE_AUDIT.csv、EXACT_LOCAL_AIG_MUX_TAILS.csv、CONE_STRUCTURE.csv、FUNCTION_QUERY_ERRORS.csv、IMPLEMENTATION_CENTER_DIAGNOSTIC.csv、FROZEN_TRUE_CE_GRADIENTS.csv、LEAF_GRADIENT_PATHS.csv、VERIFIED.json、NEXT_SINGLE_FACTOR_PLAN.json。独立复算252组原始/中心化指标、1512条查询、18条梯度向量范数及18个原始/证明模型锥绑定；48个局部代数赋值不是新增真实电路模式。

两次准备检查分别因证明obs为拼接向量（而非逐位赋值）、JSON将tuple存为list触发严格断言；已修正解析和序列化比较，保留失败日志。它们不是电路证据错误，没有重跑训练。所有既有证明、检查点、图、标签和受保护文件保持不变。
'''
(D/name).write_text(text,encoding='utf-8')
entry='''

### 2026-11-07 训练MUX真假函数/展开对应/引脚审计（通过，未训练）

3训练单元来自同一s15850 injepsilon源/abc-aig流程，含9函数对、18端点、8原生MUX实例；第三单元1个函数不含MUX，旧“训练MUX”是含MUX候选集合口径。9真对共复用1条联合PO/D CEC查询的9个obs投影，模型/脚本/日志与raw门表达式、PI/Q相位绑定通过；9负证书重放均不同，前两单元不同函数差59—68/128位、第三12—27位，不是仅靠covered或一个稀有样本认定。

24引脚边role2=A/3=B/4=S0全部正确。前6原生根MUX共享480门选择器，aig共享1070门，数据端仅更换物理Q；展开6条尾部是准确MUX恒等式。A/B到输出原生1边、aig4边，不能直接以最大深度70断言判别信息全消失。INIT/R0/R1两编码18次冻结前向/18次梯度均角色/边界梯度非零，0优化器/0训练/0新增SAT/0测试读取。

实现公共偏移明显，R0偏移/侧内离散约1.79—2.05；候选侧中心化后3单元胜率约56%—60%，仍不足，未只靠平移解决。下一轮建议只预检MUX的固定4门AND/NOT规范展开，其余特征/损失/池不变，JS关闭；必须重审两表示共同准入和P强制相等冲突，若改池则不能复用旧原生基线。名义参数相同但专用角色矩阵可能不再使用、节点计算量增加，须明报；确定性代数相同不算学习收益。先接口/重放/加载/无更新梯度，不训练或SAT。

详见[训练MUX审计与下一轮方案](训练MUX真假函数与原生展开对应审计_20261107.md)，证据`_p0pilot/cec_train_mux_audit_20261107/`。独立复算252组指标、1512查询、18梯度及18原始/证明锥绑定通过，旧资产保持。
'''
for n in ['SAT作用证明.md','SAT工作总结.md']:
 p=D/n;b=p.read_bytes();old=b.decode('utf-8-sig');assert '训练MUX真假函数/展开对应/引脚审计（通过' not in old
 (O/(n+'.before')).write_bytes(b);p.write_text(old+entry,encoding='utf-8')
manifest={p.name:sha(p) for p in O.iterdir() if p.is_file() and p.suffix in ['.py','.json','.csv','.npz'] and p.name not in ['OUTPUT_MANIFEST.json','PUBLISHED.json']}
(O/'OUTPUT_MANIFEST.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
(O/'PUBLISHED.json').write_text(json.dumps(dict(report=str(D/name),report_sha=sha(D/name),summaries_updated=True,training=0,SAT=0),ensure_ascii=False,indent=2),encoding='utf-8')
print('MUX audit report and both summaries updated.')
