"""Correct handoff and publish audit; snapshot originals before document edits."""
from pathlib import Path
import csv,hashlib,json
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;D=R/'10.15/00_说明'
def rd(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def snapshot(p):
 dest=O/'document_snapshots'/p.name;dest.parent.mkdir(exist_ok=True)
 if not dest.exists():dest.write_bytes(p.read_bytes())
 return dest
def table(rows,keys):
 text='|'+'|'.join(keys)+'|\n|'+'|'.join(['---']*len(keys))+'|\n'
 for r in rows:
  vv=[]
  for k in keys:
   v=r[k]
   if k not in ['family','arm','stage','space','source','value','stratum','split']:
    try:v=f'{float(v):.4f}'
    except (ValueError,TypeError):pass
   vv.append(str(v))
  text+='|'+'|'.join(vv)+'|\n'
 return text
def main():
 assert rd(O/'COMPLETE.json')['model_forwards']==0
 path=D/'交接_等价锥现状_20261105.md';backup=snapshot(path);text=backup.read_text(encoding='utf-8-sig')
 def replace(a,b):
  nonlocal text
  assert a in text,a;text=text.replace(a,b)
 replace('## 1. 一句话现状\n\n**等价锥的“数据、配对、证明”已经打通并做了系统审计，但“用等价关系做预训练能否提升检测/函数区分”目前是否定结果**：\n在 4 种目标（原 MSE+铰链、源内排序、逐视图中心化、节点对派生锥）下，\n真实对应 R 都没有稳定优于置换对应 P，预训练表示的同/不同函数区分在 0.50 左右。',
 '## 1. 一句话现状\n\n**现有有效探索实验尚未证明真实等价预训练具有稳定独立检测增益；不能据此否定功能预训练或扩池方向。**原MSE、dropout消融、排序和逐视图中心化均已执行，但只有seed42。节点对派生锥试点存在错误监督及训练/评测重叠，已标为无效，排除出方法结论。\n\n本轮复用缓存表示，按同源、同上下文、相同实现方向比较真实/错误跨实现对：原MSE预训练root64的合并AUC为Z/R/P=0.5975/0.6059/0.6075。R未显示独特收益，但不能再笼统说所有表示AUC都在0.50左右。逐源/逐实现差异须分别报告。\n\n2026-11-05本轮已修订统计与结论。原文快照和无效试点证据清单保存在`_p0pilot/cec_fair_audit_20261105/`，完整结果见《等价锥交接修正与公平离线评价_20261105.md》。')
 replace('### 3.2 锥规模（关键：小锥灌水）','### 3.2 锥规模（含大量小锥，需分层）')
 replace('训练池 77% 是 abc↔opt','训练池 62.1%（1842/2965）是 abc↔opt')
 replace('### 3.3 木马正根（12 条）','### 3.3 实际抽到的木马正根（12条；总训练池13条/5源）')
 replace('- 排除 aig/nand 后正根 **6 条**','- 总训练池还包括s15850/injepsilon的1条正根，本次50步未抽中。下表12条是实际采样配对，不是总池规模，也不是12个独立函数。\n- 排除 aig/nand 后正根 **6 条**')
 replace('→ 去掉 aig/nand 后，预训练实际学的是“通用功能不变性”，不是木马函数。','→ 这是未执行的过滤方案的池结构，而非当前实际训练分布；若采用该方案，将主要研究普通逻辑的功能不变性。普通逻辑等价监督也可能帮助检测，但其贡献需要对照验证。')
 replace('### 4.1 原 Z/R/P（dropout 0.2，100 次微调）','### 4.1 原 Z/R/P（dropout 0.2，50次预训练＋200次检测更新）')
 replace('关 dropout 三组 val 都升，但 R 仍不优于 P；函数区分反而下降','关 dropout 三组 val 都升，R的验证/测试AP略高于P，但测试仍低于Z，且没有多种子稳定性证据；旧20块判据的函数区分反而下降')
 replace('结论：dropout 不是函数区分弱的原因。','结论：移除dropout未解决功能区分弱，不能认定dropout是唯一或主要原因，也不能断言它完全没有影响。')
 replace('排序损失 50 次内维持 0.19–0.21（下限 0.2）','排序损失 50 次内约为0.19–0.21（0.2为各距离相等时两个margin项之和，不是理论下限）')
 replace('结论：排序约束被“所有锥表示接近相同”的退化解吸收。','现象与低方差、距离区分不足相容；仅凭平均损失不能断定唯一机制是全部表示相同。排序版Z只有方差项，与原MSE版Z的公共负项不同，跨目标Z并非相同干预。')
 replace('原 20 块上的“R 0.58 vs P 0.58”和“R 0.48 vs P 0.40”都是小样本噪声。','原20块结论受小源样本和汇总口径影响，不能据此确认R优于P或证明差异完全属于噪声。所谓block-balanced实际为合并全部距离后的AUC；源内AUC等权与合并AUC回答不同问题，应同时报告。')
 replace('对照反向不是“对照角色”的问题，是 **aig 配方** 的问题（见 4.9）。','角色、源和配方严重混杂；反向还受到“跨视图同函数”对比“同视图不同函数”的条件差异影响。不能单独归因于对照角色或AIG配方。公平跨视图比较后，原MSE的ctlmatchb R/P AUC约0.529/0.525。')
 replace('### 4.8 训练侧角色×配方间隔（R 组）','### 4.8 训练侧角色×配方间隔（dropout=0的R组投影距离）')
 replace('训练集里**没有 control × abc↔aig 配对**；aig 只以注入角色出现且间隔≈0；','本次固定采样块没有control×abc↔aig，所列间隔取自dropout=0的functional_train_blocks.csv；不能与dropout=0.2验证距离直接拼成因果证据。')
 replace('验证集“对照 = aig、注入 = id/opt”与角色完全共线，不能把反向归因于角色。','验证证书中对照32块全为abc↔aig，注入主要为id↔opt但还含少量aig/nand；属于严重混杂，并非完全共线，不能独立归因角色或配方。')
 replace('所有配方 DFF 数完全一致；','这两个实测网表的各配方DFF数完全一致，未检查全部工程网表；')
 replace('做法：每个更新内，池化锥表示先减该视图均值，再算原距离；','做法：每个更新内，投影后的32维锥表示减去当前采样中同视图的均值，再算原距离；方差项仍使用未中心化表示；')
 replace('结论：aig 反向不是视图偏移，距离归一化路线无效。','结论：这一具体中心化实现未显示收益；不能排除其他视图偏移机制，也不能否定所有归一化/域对齐路线。')
 start=text.index('### 4.11 节点对派生锥');end=text.index('## 5. 已确认的结论')
 text=text[:start]+'''### 4.11 节点对派生锥试点：已标为无效，原始证据保留

- 原试点建立1000块/2000条名义配对/4000锥，只有预训练，没有200次检测微调；不是与前三项同协议的第四种目标。
- 每块pair_a来自proved、pair_b来自differ，未修改engine却把二者均当作真实等价边拉近。实际1000条differ边进入R的拉近项；派生负边/交换边也不具备原合同的函数不同证书。
- 评测按候选列表截取后3000条，没有按实际训练清单去重；3000 proved中726条、3000 differ中486条实际参与过训练。
- 原AUC 0.4981/0.5245/0.5067作为错误试点的历史输出保留，不支持方法成败、留出泛化或“扩池无效”。
- 2000条名义配对相对旧实际382条约5.2倍，相对2965总训练池反而更少；“扩大两个数量级”没有相同单位的依据。
- 证据：原目录新增`INVALIDATED_20261105.json`；详见`_p0pilot/cec_fair_audit_20261105/NODEPAIR_INVALIDATION.json`中的原文件哈希与原因。原脚本、检查点和结果未修改或删除。

'''+text[end:]
 start=text.index('## 5. 已确认的结论');end=text.index('## 9. 证据索引')
 text=text[:start]+'''## 5. 目前可以确认的结论

1. 有效seed42探索实验尚未证明真实R有稳定独立检测增益；单seed不能断言差异在统计噪声内。
2. 公平跨实现评价存在源与配方异质性，R通常接近P。不能写成所有预训练表示都没有任何函数信息。
3. AIG与结构变化是待检验机制，原同/不同函数AUC混入视图条件差异，尚不能确定AIG为根因。
4. +0.16训练内间隔属于dropout=0投影诊断，不证明这些源对下游检测产生因果贡献。
5. 直接删除aig/nand会显著收缩配对、正根与验证覆盖，不推荐作为默认主路线，但不是逻辑上不可做。
6. 节点对试点无效，不能用于否定扩池；原CEC数据池不因这个试点而失效。

## 6. 解释边界

- Z的定义随目标族不同：原MSE/去dropout/中心化包含公共函数不同项；排序Z只有方差项。不能混称未经预训练的检测基线。
- 同/不同函数距离、真实/错误跨实现距离、节点检测AP分别回答不同问题；源内等权和合并AUC同时报告。
- 小源只有1–2证书块，重复配对或锥不是独立样本，不据此作显著性宣称。
- 测试配对稳定性为NA；历史多轮检查的测试不再称全新盲测，不按测试结果调配置。
- dropout=0只是机制对照，没有确立为新最优；单次中心化失败不能否定整类方法。

## 7. 已核查的信息缺口

39v3已有寄存器门型、touches_PI/PO、PI/PO距离和寄存器侧拓扑线索，不能说模型完全不知道PI/Q相关信息。但引脚角色、边界变量身份、物理Q/QN极性和查询边界映射未进入当前输入/池化接口；edge_roles仅为元数据，且组合引脚全部角色1。

本轮用实际v3生成器构造了两个不需SAT的反例：交换MUX选择/数据引脚，以及NOT(a)改为NOT(b)，分别在8个输入组合中2个、4个输出不同；其x39、edge_index、现有edge_roles却完全相同。这证明当前表示可丢失这些信息，不代表已证明真实数据中有多少精确碰撞。

## 8. 下一步建议

先使用本轮公平离线评价及信息缺口报告审视输入表示，不追加SAT、seed或训练。优先明确引脚角色和边界变量对齐的最小接口合同，分别处理，避免一次同时加多类信息。边界变量只在同源查询上下文中对齐，禁止把宿主/信号名字直接编码为检测捷径。

若后续用户授权训练，再一次只改一个因素，保持模型、初始化、特征其余列、监督与预算可比，Z/R/P同步修改；先验证root64及同条件真实/错误配对区分，再考虑微调保持项。不使用已经无效的节点对试点作为继续或停止某方向的依据。

'''+text[end:]
 replace('7. 任何“一致性/保持项”都要等预训练先在验证函数区分上站住（R 稳定高于 P）再谈。','7. 微调保持项先以预训练存在可用功能信息为前提；R/P判断使用条件一致的验证配对，并保留单seed及小源限制。')
 text+='\n本轮审计入口：`_p0pilot/cec_fair_audit_20261105/`；原文快照：`document_snapshots/交接_等价锥现状_20261105.md`。\n'
 path.write_text(text,encoding='utf-8')
 pilot=D/'等价锥扩充C_节点对试点_20261105.md';pb=snapshot(pilot)
 pilot.write_text('> **2026-11-05审计：本试点无效。** 存在differ误作等价监督和训练/评测配对重叠，以下原文仅为历史证据，不作为有效结论。原文快照及原实验文件哈希保存在`_p0pilot/cec_fair_audit_20261105/`；未重跑或删除实验。\n\n'+pb.read_text(encoding='utf-8-sig'),encoding='utf-8')
 summary=list(csv.DictReader((O/'fair_cross_summary.csv').open(encoding='utf-8-sig')));strata=list(csv.DictReader((O/'fair_cross_strata.csv').open(encoding='utf-8-sig')));info=rd(O/'INPUT_INFORMATION_AUDIT.json')
 report='''# 等价锥交接修正、公平离线评价与输入信息核查（2026-11-05）

## 执行范围

0次训练更新、0次优化器步、0次模型前向、0次新增SAT/Yosys，仅CPU读取已有表示/检查点、证书和冻结网表，执行向量运算及8组合小例枚举。使用ginvenv_gpu的Python，但没有调用GPU模型。旧节点对试点脚本、日志、模型、结果已按哈希确认未变；新增INVALIDATED标记保留历史输出。文档改写前快照保存在document_snapshots。

## 文档纠正与无效试点

原实验是50次预训练+200次检测更新；abc↔opt为1842/2965=62.1%；训练池正根13/5源，实际抽到12/4源。排序的0.2是等距离时两margin项之和，不是损失下界。训练间隔表来自dropout0，原验证分层来自dropout0.2，不再拼成因果链。移除dropout、单次中心化失败均不支持否定整类机制。

节点对试点1000块中1000条proved与1000条differ都进入R的等价拉近项；错误交换边/负边没有原合同证书。所谓3000+3000留出中有726条proved及486条differ参与过训练。本轮没有修复并重跑，只标无效且保留证据。2000条名义配对相对382约5.2倍，不是100倍扩池。不能据此下“扩池无效”的结论。

## 公平离线评价合同

复用已有68块验证函数不同证书（5源/1宿主，源内块数32/32/2/1/1），全部独立标量回放通过。每块由aL=aR、bL=bR及一个a≠b反例构成，故aL↔bR、bL↔aR均为已证错误配对。

真实对(aL,aR)/(bL,bR)与错误对(aL,bR)/(bL,aR)共享源、PI/Q上下文、左/右视图、端点和名额，避免原“同函数跨视图/不同函数同视图”的视图条件混杂。对每个左端anchor比较正确/错误右端；另报块均值胜率、无量纲相对间隔与合并AUC、源内AUC等权。AUC和胜率不是同一统计。

本轮评价mse/dropout0/rank三个已有目标族的Z/R/P，预训练第50步与检测验证最优步，root64/concat128/projection32。微调后投影是冻结预训练头读出探针，不是实际检测输入。中心化没有全锥表示缓存，未为补齐它增加模型前向，记作本轮未复评。

68块并非68个独立源对象，少量锥重复；大源证书不等于额外制造对象。锥大小分层以每块四个锥的最小成员数为共同分层，未实现逐门型/规模联合精确匹配，公平性限于上述端点/上下文/方向条件。本轮没有以分数筛选或新增候选。

## 预训练root64结果

cross_auc为合并真实/错误跨实现距离AUC，source_macro_cross_auc为每源AUC等权。不能直接将其中一种当作唯一正确指标。

'''
 report+=table([r for r in summary if r['stage']=='pre' and r['space']=='root64'],['family','arm','cross_auc','source_macro_cross_auc','anchor_win','source_macro_anchor_win'])
 report+='\n## 主要源与实现方向分层\n\n以下均为pre/root64，两个大源各32块。ctlmatchb对应abc↔aig，injalpha对应id↔opt；其余三源样本少，不据此作源泛化宣称。\n\n'
 report+=table([r for r in strata if r['stage']=='pre' and r['space']=='root64' and r['stratum']=='source' and ('ctlmatchb' in r['value'] or 'injalpha' in r['value'])],['family','arm','value','cross_auc','anchor_win','relative_gap'])
 report+='''
原MSE ctlmatchb R的同函数跨视图/不同函数同视图AUC约0.222；改为真实/错误均跨视图后0.529。原反向包含比较条件差异，不能直接解释为功能排序本身反转。injalpha真实/错误跨实现R约0.788，但P约0.813，仍无真实预训练独立优势。大源上Z本身已有区分，必须看R相对Z/P的变化而非仅看R是否大于0.5。

公平判据下MSE/dropout0/rank的pre/root64合并R-P差均不为正，但单seed不能作显著性宣称；源内等权值受2/1/1小块源影响，也不能忽略。当前结论是“未确立独立收益”，不是“表示不含任何函数信息”。全阶段、全空间及锥大小分层见CSV，不能只挑某一数值宣称成功。

## 输入信息缺口：现有内容与实际丢失

已有：25维门型含寄存器类别、touches_PI/PO、PI/PO有向距离、寄存器侧距离和二跳上下文、有向单元连接。

未进入当前网络接口：组合单元输入引脚身份（如MUX选择端S0、数据A/B）、消费者对应的具体PI索引、物理Q身份及Q/QN极性、锥查询的边界变量对应。现有edge_roles对组合输入统一为1，DFF有D/时钟/扫描/复位等粗角色，但加载器只传x39和edge_index，未将edge_roles交给GIN。证明端leaves/context确实保存了更完整信息，投影端只读取root和成员均值，没有读取这些边界token。

### 当前生成器的确定性反例

1. 四单元BUF+MUX电路，交换选择端S0与数据端A，39维特征、edge_index和现有edge_roles逐元素相同，但8组输入有2组输出不同。
2. 相同PI集合下NOT(a)与NOT(b)，上述输入同样逐元素相同，8组输入有4组输出不同。

这些是用实际v3生成器生成的合成信息丢失反例，不是新SAT查询，不代表测得真实池中精确碰撞的发生率。相同输入使当前确定性推理无法区分这两种情况，但不意味着所有函数任务都需全局信号名字，也不意味着新增信息必然提高木马AP。

### 已有锥涉及范围与感受野代理统计

'''
 report+=table(info['cone_summary'],['split','unique_cones','cones_with_mux','cones_with_PI','cones_with_Q','cones_with_members_outside_root_3hop','median_root_3hop_member_fraction'])
 report+='''
本表以唯一锥去重，不是配对或训练实际曝光数。3跳仅统计原始组合逻辑锥内根的祖先距离，作为2分支层+1post层的范围代理，不是完整图上精确的模型依赖掩码；均值池化仍访问全锥成员，不能据此说根看不到的成员完全没有参与预训练。训练/验证边界支持和锥尺度差异明显，应在解释泛化时保留。

## 下一步建议

先形成两个独立候选合同，选其一执行，避免把引脚角色、边界对齐、池化和损失同时修改：

1. 引脚角色：先定义MUX选择/数据、DFF输出Q/QN及控制端的语义，确认有向边及合并多引脚边能完整保存；这是关系信息，不能简单给节点多加一个is_PI位来替代。若后续调整模型消费引脚角色，Z/R/P须同步、同预算，先看公平配对指标及root64。
2. 边界输入对齐：使用同源查询的对应token定义局部角色/端点锚点，不把宿主或任意信号名嵌入为全局特征；明确PI/Q、极性、共享/不同支持怎样进入表示。PI/Q信息不充分与池化损失要分开检验。

首选先针对已证实丢失的引脚语义制定最小方案，再决定是否训练。公平离线指标保留真实/错误跨实现对比及同视图区分两个任务；函数区分有改善之后再单因素考虑微调保持项。节点对扩充可以作为后续候选，但须先纠正证明资格和实际集合去重；本轮没有修复数据再训练。

## 证据

`_p0pilot/cec_fair_audit_20261105/`：audit.py、COMPLETE.json、CERTIFICATES_VERIFIED.json、NODEPAIR_INVALIDATION.json、fair_cross_blocks.csv、fair_cross_summary.csv、fair_cross_strata.csv、INPUT_INFORMATION_AUDIT.json、boundary_cone_inventory.csv、fixtures及document_snapshots。COMPLETE包含读取输入哈希和旧试点文件未变核验。所有原始SAT/图/标签/检查点继续保留。
'''
 reportpath=D/'等价锥交接修正与公平离线评价_20261105.md';reportpath.write_text(report,encoding='utf-8')
 note='''\n\n### 2026-11-05 交接纠错、公平跨实现评价与输入信息缺口（已完成）

纠正《交接_等价锥现状》中的62.1%比例、200次微调、总池13/实际12正根、排序0.2非理论下界及配置混用；收回“AIG根因/扩池无效/所有表示随机”的过强结论。节点对试点1000条differ误作等价拉近，且评测3000 proved/3000 differ与训练重叠726/486，已标无效，原实验文件哈希确认未变，未删除旧结果。68块证书独立回放全部通过，复用mse/dropout0/rank缓存做真实/错误均跨相同实现方向的评价：pre/root64合并Z/R/P AUC分别0.5975/0.6059/0.6075、0.5929/0.6040/0.6064、0.6277/0.6211/0.6443，仍未确立R独立优势。原MSE ctlmatchb R反向0.222在公平条件下为0.529，不能直接归因AIG。用实际v3生成器证实MUX引脚交换、PI身份交换可使不同函数具有完全相同x39/边/现有edge_roles；现有PI/寄存器拓扑线索保留，缺的是引脚语义与具体边界对应进入模型接口。0训练/0模型前向/0新增SAT/Yosys；下一步先定单因素输入接口方案，再考虑训练及微调保持。详见[本轮报告](等价锥交接修正与公平离线评价_20261105.md)，证据`_p0pilot/cec_fair_audit_20261105/`。
'''
 for name in ['SAT作用证明.md','SAT工作总结.md']:
  f=D/name
  if '### 2026-11-05 交接纠错、公平跨实现评价与输入信息缺口' not in f.read_text(encoding='utf-8-sig'):
   with f.open('a',encoding='utf-8') as out:out.write(note)
 manifest=rd(O/'NODEPAIR_INVALIDATION.json')['original_files_sha256'];assert all(sha(R/p)==h for p,h in manifest.items())
 (O/'PUBLISHED.json').write_text(json.dumps(dict(report=str(reportpath.relative_to(R)),corrected_handoff=str(path.relative_to(R)),snapshots_preserved=True,original_experiment_files_unchanged=True,training_updates=0,new_SAT=0),ensure_ascii=False,indent=2),encoding='utf-8')
 print('PUBLISHED',reportpath,flush=True)
if __name__=='__main__':main()
