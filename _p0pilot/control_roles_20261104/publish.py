from pathlib import Path
import csv,json,datetime,hashlib
import numpy as np
O=Path(__file__).resolve().parent;R=O.parents[1];B=R/'_p0pilot/control_fair200_20261104';N=R/'10.15/00_说明'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def pct(x):return f'{100*float(x):.2f}%'
def fmt(x):return f'{float(x):+.4f}'
def main():
 assert not (O/'COMPLETE.json').exists()
 a=read(O/'analysis.json');assert read(O/'context.json')['training']==read(O/'mechanism.json')['training']==0
 for p,h in a['score_bindings'].items():assert sha(R/p)==h,p
 for p,h in read(B/'manifest.json')['inputs'].items():assert sha(R/p)==h,p
 for seed in [42,1,2]:
  for arm in ['H','C']:
   p=B/f'seed{seed}'/arm;assert sha(p/'best.pt')==read(p/'EVALUATED.json')['checkpoint_sha']
 normal=rows(O/'normal_source_average.csv');classes=rows(O/'roleclass_summary.csv');source=rows(O/'source_role_average.csv');context=rows(O/'role_context.csv');reach=rows(O/'reach_audit.csv');exposure=rows(O/'role_exposure.csv')
 lines=['# 等预算正常监督的制造角色、分数重叠与权重诊断（2026-11-04）','',
 '## 结论','',
 '**不建议直接整体提高正常区域监督权重。** 正常载荷和终端确实降分，但对应木马角色也受到抑制；低分木马触发/选择角色与高分正常载荷之间存在交叉排序问题。局部输入不可区分、制造来源标签与单节点输出作用不同、定向角色覆盖不全，也都无法靠统一加大负例权重解决。后续值得考虑的是保持总负例权重的受约束分角色权重对照，不能据本轮离线结果宣布已有最优权重。','',
 '本轮只读取六组已有H/C预测、标签、图和制造映射：0训练、0模型前向、0 SAT。仅建立新的离线分析文件；原图、预测、标签、权重及已有成功结果哈希核对通过。本轮模型输入为39维v2，没有SAT列，不能把本轮重叠直接解释成SAT功能证据无效。','',
 '## 对象、角色与统计口径','',
 '完整正常区域：orig/train 23源对象158节点；trans/train 23源对象450节点；val/test各6源对象，130/142节点。配对分析在同一主候选中取制造同名角色且原可信标签一致的关系：orig/train 20源121角色记录；trans/train 20源260记录、329正常/293木马唯一节点；val 5源70记录、94/86节点；test 5源80记录、105/106节点。此处记录数是源角色×实现，不是独立物理节点数。','',
 '先在源对象的每个制造角色内部汇总实现视图，再报告源对象和种子；角色类别先源内平均再跨源平均。多个角色共享后代节点时不当作独立样本。完整正常区域按唯一物理节点计算；跨类别共享后代原计划单列mixed_lineage，本轮主区域中未出现跨类别共享。','',
 'T/TN/TI/TM等为触发角色；P数字为载荷；S数字为载荷选择/辅助门；HJ为输出劫持/等价终端；PD等为正常死端终端；X数字为深XOR。名称仅用于制造溯源、监督诊断，未加入模型输入。制造对应不是SAT等价证明，后代集合不表示每个中间门都实现源门函数。ctldup/ctlxor没有预设木马伙伴，相关木马指标保持缺失。','',
 '以下历史操作点阈值均沿用每模型自己的验证可信负例95%分位数；高召回操作点也仅在验证正例上标定。测试已被此前查看，所有测试分解属于探索性，不用于选择下一轮训练对象或权重。源对象彼此仍可能共享宿主，不能称独立宿主泛化证明。','',
 '## 哪些完整正常源对象改善','',
 '|测试源对象|H区域FPR|C区域FPR|变化/百分点|平均风险变化C−H|木马制造伙伴|',
 '|---|---:|---:|---:|---:|---|']
 for x in normal:
  if (x['operation'],x['domain'],x['split'])!=('historical_fpr5','trans','test'):continue
  partner='无预设伙伴' if '__ctlxor_' in x['source'] else '有，按制造角色单列'
  lines.append(f"|{x['source']}|{pct(x['fpr_H'])}|{pct(x['fpr_C'])}|{100*(float(x['fpr_C'])-float(x['fpr_H'])):+.2f}|{fmt(x['score_delta'])}|{partner}|")
 lines += ['',
 '全部6源对象跨种子平均均改善，但不是每个对象在每个种子都改善；正常风险确实下降，并非单纯把阈值提高。历史阈值平均C比H低约0.0057，反而会抵消部分FPR收益。normal_source_average.csv另列H分数配C阈值、C分数配H阈值，供区分分数与阈值效应；这些交叉阈值只作描述，不能视为校准不变的因果分解。','',
 '未配对角色也有贡献：正常终端类FPR44.44%→34.72%，深XOR内部角色41.67%→34.82%；完整ctlxor对象含终端，因此其整区域46.67%→41.30%，分母不同。正常触发角色在测试主区域的历史阈值下已为0%误报，继续压低它的收益很有限。','',
 '## 哪些木马角色同时降分','',
 '|测试制造角色类|正常风险变化|木马风险变化|正常角色FPR H→C|木马角色召回H→C|同角色集合联合成功H→C|',
 '|---|---:|---:|---:|---:|---:|']
 for x in classes:
  if (x['operation'],x['domain'],x['split'])!=('historical_fpr5','trans','test'):continue
  lines.append(f"|{x['role_class']}|{fmt(x['normal_delta'])}|{fmt(x['trojan_delta'])}|{pct(x['normal_fpr_H'])}→{pct(x['normal_fpr_C'])}|{pct(x['trojan_recall_H'])}→{pct(x['trojan_recall_C'])}|{pct(x['joint_H'])}→{pct(x['joint_C'])}|")
 lines += ['',
 '配对载荷正常风险下降约0.0386，木马也下降0.0118；正负平均间隔仍增加0.0268，说明同时存在局部分离收益和共同抑制。按源对象、角色和视图等层汇总，载荷类正负同时降分比例约87.28%，不是87.28%的独立节点。触发类正负也有共同下降，测试正常误报已0%，木马召回反降15.00%→14.17%。选择类木马风险比正常风险降得更多，间隔变窄；两组历史阈值下木马召回均0，不能把其正常FPR下降解释成成功区分。','',
 '### 具体角色：同时降分并不总有收益','',
 '|划分/源对象|角色|正常FPR H→C|木马召回H→C|正常/木马风险变化|',
 '|---|---|---:|---:|---:|']
 wanted=[('val','ctlmatchb','P2'),('val','ctlmatchc','TI3'),('val','ctlmatchf','P0'),('test','ctlmatcha','P2'),('test','ctlmatchd','P0'),('test','ctlmatchd','S1')]
 for sp,fam,role in wanted:
  x=next(x for x in source if x['domain']=='trans' and x['split']==sp and x['operation']=='historical_fpr5' and '__'+fam+'_' in x['source'] and x['role']==role)
  lines.append(f"|{sp}/{x['source']}|{role}|{pct(x['normal_fpr_H'])}→{pct(x['normal_fpr_C'])}|{pct(x['trojan_recall_H'])}→{pct(x['trojan_recall_C'])}|{fmt(x['normal_delta'])}/{fmt(x['trojan_delta'])}|")
 lines += ['',
 '例如验证ctlmatchb/P2、ctlmatchc/TI3、ctlmatchf/P0均出现正常FPR未改善而木马召回下降，表明正例保护问题并非只在测试发现。测试ctlmatchd/P0、P2共享部分正常后代，不能当两条独立成功/失败证据。逐角色明细见source_role_average.csv；跨种子平均可能掩盖个别种子的方向，source_role_seed.csv保留种子明细。','',
 '## 高召回为何仍难区分','',
 '### 1. 跨角色排序不统一','',
 'C组测试正常载荷平均分0.6720，高于木马触发0.6114和木马选择0.4801；H组也有同样次序。在同源同实现内部比较全部“木马触发—正常载荷”制造角色均分组合，正确排序率验证H 43.72%→C 46.64%，测试35.42%→39.57%；木马载荷—正常载荷测试则83.47%→85.92%。这些是描述性两两排序，不是新增独立样本的分类AUC。','',
 '因此“木马区域最大分高于正常区域最大分”可能只是高分木马载荷/终端胜出，掩盖低分触发门漏检。为保住触发/选择门召回而降低统一阈值，就重新放出高分正常载荷。验证校准80%召回的测试实际宏召回H/C为80.64%/80.03%，正常区域FPR仍67.52%/64.87%；90%校准下FPR82.58%/81.89%，改善进一步缩小。整对象联合成功在80/90操作点均0，但部分单角色集合仍可成功，两种粒度不可混淆。','',
 '![验证标定的召回与正常区域误报曲线](C:/Users/91344/Desktop/GraphSAINT/GIN_train/_p0pilot/control_roles_20261104/recall_fpr_curve.png)','',
 '曲线横轴为各自实际木马视图宏召回；阈值来自验证pooled正例。不同组横坐标不完全相同，不宣称严格等测试召回下的因果改善。','',
 '### 2. 单节点特征重叠与局部上下文边界','',
 '重新用39维归一化输入及edge_index构建三跳入边计算树指纹。三跳来自两层分支GIN和一层融合后GIN；输入混合层不增加图传播距离。指纹相同是局部输入不可区分的充分条件，指纹不同不证明模型已经学会分离。测试配对有少量单节点39维完全相同的后代，但没有三跳指纹完全相同的配对，所以不能把全部测试失败归为表示必然不可能。','',
 '训练侧有3条ctlmatche/TM1/ys_nand的源角色×视图记录包含三跳输入相同的正负后代，来自rs232、s15850、s35932；对应预测在六个模型中分差均为0。它们没有下游输出用途信息进入局部消息，单靠调权不能使确定性模型对相同输入给出不同结果。这里说的是具体后代子集，不是整个角色集合或整个数据集都不可区分。','',
 '当前边由驱动门指向消费门，GIN聚合输入侧消息；下游载荷用途不会通过该方向自动传回触发门。39维包含到PO距离等全局摘要，因此不能说模型完全没有下游信息，但它没有显式利用边的引脚角色元数据，也没有真实功能证据输入。源门角色在综合后的中间门间会拆分、合并，制造谱系不能替代每节点的真实功能作用。','',
 '### 3. 正标节点与输出功能相关性并不等价','',
 '|范围|可信正标节点|到PO不可达|配对木马唯一节点/其中不可达|',
 '|---|---:|---:|---:|']
 for x in reach:lines.append(f"|{x['key']}|{x['all_trusted_positive']}|{x['all_trusted_positive_PO_unreachable']}|{x['paired_unique_T_nodes']}/{x['paired_T_unreachable']}|")
 lines += ['',
 '用独立稀疏图反向遍历验证了全部图节点的PO可达标志与39维距离列一致，不是仅按名称猜测。测试243个可信正标节点中34个（13.99%）无到PO的路径；配对木马子集中为34/106。这是“当前图中的结构可达性”，不是SAT功能影响判定；不能直接断言标签错误，也不能因此自动删标签。其标签可能表达植入来源/对象归属，而非每个中间门都对异常输出有独立影响。要求这类节点全部高召回，会与同样局部形态的正常逻辑发生更强冲突。','',
 '正标不可达现象只是高召回困难的一个因素；可达木马触发/选择角色也存在漏检，不能将全部问题归因于34个节点。下一轮若深入，应先分开报告制造对象定位与输出功能作用，不在本轮改图、改标签或补SAT。','',
 '### 4. 本轮角色曝光不均，不能解释成单纯权重不足','',
 '|侧|定向角色|唯一C节点|额外曝光/64000|',
 '|---|---|---:|---:|']
 for x in exposure:lines.append(f"|{x['domain']}|{x['role_class']}|{x['unique_C_nodes']}|{x['extra_C_exposures']}|")
 lines += ['',
 '本轮定向池没有payload_select；这不表示历史训练没有该角色的正例或负例。s15850训练中存在injdelta/ctlmatchd，但未满足此次变换侧主候选资格，因此未纳入双侧共同定向池。不能仅给现有池加权就补出缺失角色。orig/trans每步320槽占监督条目约0.290%/0.076%，确实偏小；同时训练侧已观察到共同抑制和输入冲突，故加权不应成为唯一解释。','',
 '## 是否调整区域监督权重','',
 '当前决定：**不直接扩大整体正常区域权重，也不自动追加训练。** 现有证据支持下一次经过授权的小范围“分角色、固定总负例权重、保护正例”的对照，但不支持直接选一个大权重投入主模型。','',
 '1. 先把输入局部不可区分的训练后代和映射歧义单独登记；角色集合定位与单节点功能相关性分开评价，保留原标签和原主指标。不要将疑难正例静默移除以提高分数。',
 '2. 若做权重试验，优先考虑训练/验证已显示局部分离收益的载荷区域，触发区域不统一加大负例抑制；选择角色先解决可用候选覆盖和正例漏检。终端/深XOR无同角色木马伙伴时，不冒充配对证据。',
 '3. 在相同H/C两组中同时设置相同的小倍率（可预先冻结为当前有效角色权重的2倍、4倍），将公共负例权重等额转移到候选区域，使每域总负例权重、正例权重和soft-miss项不变。不是加权后再隐式稀释正例或增加总梯度预算。两个倍率只是假设待检验，没有在本轮计算新模型。',
 '4. 选权重只看训练/验证：正常区域FPR、同源角色联合成功、木马触发/载荷/选择分层召回同时满足预先约定的容忍范围；不能以测试某角色误报的位置或测试最佳权重决定下一轮对象。若仍主要共同降分，优先改进边界/引脚语义、下游上下文或区域集合目标，而非继续加大负例权重。',
 '5. 本轮对象数和宿主覆盖有限，不给节点级显著性或最优权重结论。后续应复用已有对应、区域监督及实现一致性思路，但逐项加入，维持可归因的对照。','',
 '## 复核入口','',
 '- normal_source_average.csv、normal_nodes_with_roles.csv：完整正常源对象及未配对角色变化，唯一节点口径。',
 '- source_role_average.csv、source_role_seed.csv：同源制造角色、种子与实现汇总；source_role_view证据在role_view_seed.csv。',
 '- cross_role_source.csv：正常载荷与不同木马角色的交叉排序。',
 '- role_context.csv、context_source_class.csv：特征/入边三跳指纹、距离与同分证据。',
 '- reach_audit.csv、positive_reach_strata.csv：独立可达性与正标分层，未改标签。',
 '- validation_calibrated_curve.csv、recall_fpr_curve.png：只用验证标定的操作点曲线。',
 '- role_exposure.csv、unique_support.csv、analysis.json、COMPLETE.json：实际支持数、曝光预算、预测来源哈希与无训练/SAT记录。','']
 report='\n'.join(lines);target=N/'正常对照制造角色与高召回重叠诊断_20261104.md';target.write_text(report,encoding='utf-8');(O/'分析报告.md').write_text(report,encoding='utf-8')
 brief=f'''\n\n## 正常对照制造角色与高召回重叠诊断（2026-11-04）\n\n复用H/C六组200次模型已有预测完成离线角色分析，0训练/0前向/0 SAT。测试6个完整正常源对象跨种子平均误报均下降；配对载荷正常风险−0.0386、木马−0.0118，正常FPR26.22%→17.53%，木马召回71.89%→69.11%。触发正常FPR已0，木马召回15.00%→14.17%；选择木马召回两组均0。验证b/P2、c/TI3、f/P0存在正常误报不降而木马召回下降。高召回难点包括正常载荷分数高于木马触发/选择、三条训练角色×视图存在相同三跳输入且六模型同分、定向池缺选择角色；变换测试243可信正标中34个图上PO不可达（独立遍历核验，非标签错误或SAT判定）。不建议整体加大正常监督；后续经授权可小范围分角色调权、保持总负例权重并保护正例，先隔离解释局部输入冲突及制造来源/功能作用区别。详细逐源/角色与曲线见[本轮报告]({target.name})及`_p0pilot/control_roles_20261104/`。测试仅探索性，权重方案只据训练/验证决定。\n'''
 for name in ['SAT作用证明.md','SAT工作总结.md','正常对照贡献量化与公平实验方案_20261104.md']:
  with (N/name).open('a',encoding='utf-8') as f:f.write(brief)
 with (R/'10.15/99_共用资产/运行登记/运行登记表.csv').open('a',encoding='utf-8',newline='') as f:
  csv.writer(f).writerow([datetime.datetime.now().astimezone().isoformat(),'正常对照源对象-制造角色与高召回机制离线诊断','control_roles analyze/context/mechanism/normal_roles/publish.py','CPU offline only;0 forward/train/SAT','42/1/2','frozen orig/train +trans/train/val/test','H/C200 saved predictions and source roles','_p0pilot/control_roles_20261104','payload FPR down;T also down;cross-role inversion;3 train context collisions','完成','no new training/SAT;test exploratory;no label edits'])
 artifacts=[p for p in O.iterdir() if p.suffix in ['.csv','.json','.py','.png','.md']]+[target]
 (O/'COMPLETE.json').write_text(json.dumps(dict(time=datetime.datetime.now().astimezone().isoformat(),training=0,model_forward=0,SAT=0,predictions_unchanged=True,training_inputs_unchanged=True,checkpoint_unchanged=True,graph_and_labels_modified=False,source_objects_not_independent_hosts=True,report=str(target),artifacts={str(p.relative_to(R)):sha(p) for p in artifacts}),ensure_ascii=False,indent=2),encoding='utf-8')
 print(target)
if __name__=='__main__':main()
