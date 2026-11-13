"""Publish the completed read-only mechanism audit, idempotent documentation append."""
from pathlib import Path
import csv,collections,hashlib,json
import numpy as np
from sklearn.metrics import roc_auc_score
O=Path(__file__).resolve().parent;R=O.parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(n):
 with (O/n).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def main():
 verified=read(O/'DIAGNOSTIC_VERIFIED.json');assert verified['independent_AUC_exact_match']
 panel=read(O/'panel_certificates.json');summary=rows('panel_evaluation_summary.csv');grad=rows('gradient_summary.csv');angles=rows('gradient_angles.csv');matching={r['certificate']:r for r in rows('panel_structural_matching.csv')};blocks=rows('panel_evaluation_blocks.csv')
 get=lambda split,tier,arm:next(r for r in summary if r['split']==split and r['tier']==tier and r['arm']==arm and r['space']=='root64')
 gradient=lambda arm,group:next(r for r in grad if r['checkpoint']==arm and r['group']==group)
 coverage=[]
 for split in ['train','val']:
  for tier in ['shallow_small','small_depth_control']:
   cc=[c for c in panel if c['split']==split and c['tier']==tier]
   coverage.append(f"|{split}|{'浅小' if tier=='shallow_small' else '同大小较深'}|{len(cc)}|{len({c['source'] for c in cc})}|{sum(c['has_mux'] for c in cc)}|")
 evaltable=[]
 for split in ['train','val']:
  for tier in ['shallow_small','small_depth_control']:
   rr=[get(split,tier,a) for a in ['Z','R','P']]
   evaltable.append(f"|{split}|{'浅小' if tier=='shallow_small' else '同大小较深'}|"+'|'.join(f"{float(r['cross_auc']):.6f}" for r in rr)+f"|{float(rr[1]['cross_auc'])-float(rr[2]['cross_auc']):+.6f}|")
 gradtable=[]
 for arm in ['R','P']:
  for group in ['backbone','pin_boundary','pin_internal','projection']:
   r=gradient(arm,group)
   gradtable.append(f"|{arm}|{group}|{float(r['real_norm_mean']):.4f}|{float(r['different_norm_mean']):.4f}|{float(r['real_permuted_cosine_mean']):.4f}|{float(r['real_different_cosine_mean']):.4f}|{float(r['R_P_total_cosine_mean']):.4f}|")
 matched=[]
 for tier in ['shallow_small','small_depth_control']:
  for arm in ['Z','R','P']:
   rr=[r for r in blocks if r['split']=='val' and r['tier']==tier and r['arm']==arm and r['space']=='root64' and all(matching[r['certificate']][k]=='True' for k in ['gates_matched','cut_counts_matched','size_bins_matched'])]
   aa=[float(r[k]) for r in rr for k in ['real0','real1']];bb=[float(r[k]) for r in rr for k in ['wrong0','wrong1']]
   matched.append(dict(tier=tier,arm=arm,blocks=len(rr),sources=len({r['source'] for r in rr}),auc=float(roc_auc_score([1]*len(aa)+[0]*len(bb),-np.array(aa+bb)))))
 with (O/'gate_cut_size_matched_metrics.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(matched[0]));w.writeheader();w.writerows(matched)
 report='''# 多源浅小等价锥面板与固定检查点梯度诊断

日期：2026-11-06。完成范围：复用既有证明与反例，重组离线面板，固定检查点和批次计算分项梯度。新增优化器更新0、SAT0、测试读取0；20次模型前向、56次损失向量-Jacobian积计算；这些反向计算不是训练。主模型及投影头参数、BN等缓冲区逐项保持，旧输入、证明与检查点哈希检查通过。GPU采用ginvenv_gpu，峰值分配约5.56GiB。

## 结论

本轮把“为什么R没有明显优于P”定位得更具体：**在当前检查点及批次上，真实关联与错误关联产生的拉近梯度高度同向；加上公共不同函数分离与方差项后，两套总梯度几乎同向。因此当前目标对关联真实性不够敏感，效果更接近一般紧致化/分离正则，而没有形成可靠的跨实现功能对应收益。**

这比“可能是数据少或锥太深”有更直接的机制证据，但仍是固定状态的局部诊断，不是对全部训练轨迹、Adam更新或所有宿主的因果定论。深锥表示和评价覆盖是并存限制；不能据此否定等价锥方向，也不能据此宣布已找到唯一原因。

## 1. 面板从哪里来，实际补齐了什么

只使用final_pairs/final_cones内已有CEC或完整枚举等价证据，复用保存的128组PI/物理Q输入。不产生新输入试验、不运行SAT/Yosys。所有10429个已有锥的引脚关联按保存输入重放，等价端点输出一致；不同函数只在已存输入下找到输出不同的位置作为存在性证书，绝不把128组相同输出当等价证明。

先按源对象、上下文、相同跨实现方向分组，将相同已观察签名保守合并后重组四端点块。相同观察签名合并可能漏掉不同函数，但不会制造新的等价证明。每源每层最多16块，同层每个端点最多曝光2次；按固定哈希选择，选择先于检查点评价，不读木马标签或预测分数。证明来源中可含历史标签辅助定位，功能接纳仍由已有证明决定；不能将整个来源池称作完全盲选。

浅小层要求四端均≤16门且边界到根的最大门级依赖深度≤4；对应根最多3次内部连线传播。同大小较深层也要求四端均≤16门，但至少一端深度>4。

|划分|层|四端证书块|独立源对象|含MUX块|
|---|---|---:|---:|---:|
'''+ '\n'.join(coverage)+'''

共250块，1000次端点出现；这些组合块不是250个独立布尔函数或250个新SAT证明。浅小训练覆盖rs232/s15850/s35932三个宿主的5源；验证仅s38417一个宿主的ctlmatchb和injalpha两源。浅小验证没有MUX，仍未补出多源浅MUX验证，不能用训练侧17个MUX块代替留出验证。

旧68块证书只有1块根三跳完整，与这次复用更多配对重组得到32块浅验证并不矛盾。门级最大依赖深度与最短图距离也不完全相同：重汇合捷径可能让全部成员位于根三跳内，但最长逻辑路径仍更深。本轮核对了“最大深度≤4必然三跳完整”，没有错误要求两者双向等价。

覆盖缺口明确保留：rs232 injalpha/injepsilon没有合格浅对；injzeta和s15850 ctlmatcha各仅1个浅对，不能组成不同函数的四端块；验证injbeta无浅对，injepsilon/injzeta各仅1个浅对，无法组成同源不同函数块。详见panel_coverage_denominators.csv，不拿重复曝光补齐这些源。

## 2. 固定模型评价：浅锥更容易区分，但真实关联仍无独有优势

复用正确角色Z/R/P各第50步检查点，BN冻结、dropout关闭，边界映射固定9000，输出根64维及整锥平均/拼接/投影表示。Z保留相同不同函数分离与方差项，是训练过的控制组，并非随机初始模型。下表为函数真/错跨实现距离AUC，不是木马检测AP。

|划分|层|Z|真实R|置换P|R-P|
|---|---|---:|---:|---:|---:|
'''+ '\n'.join(evaltable)+'''

验证浅小源等权AUC：Z/R/P=0.867676/0.864746/0.861816。R相对P有极小正差，但低于Z，且单种子、两源、同宿主，不能算真实等价学习收益。整锥平均、拼接和投影头也没有一致R优势。验证较深层R/P约0.5750/0.5806，明显难于浅层，但样本的边界、结构与功能难度同时变化，不能把浅/深差异全部归因于深度。

### 结构混杂与公平性边界

面板保证同源、同上下文、同实现方向、相同四端参与预算，不保证不同函数的门型、边界或大小分布完全相同。事后按两侧根门型、cut输入数及大小分箱同时匹配，浅验证剩12块/2源，Z/R/P AUC=0.89410/0.91493/0.91840，仍未发现R优于P；较深仅5块，不作泛化结论。

如果进一步要求两侧边界输入集合完全一致，当前已选面板没有合格块。对整个既有≤16门池再检查可用支持：浅层严格匹配为0；较深严格匹配仅训练rs232 ctldup与ctlmatcha各4条等价配对，验证为0。此处4条是等价配对数，不能说成4个独立源或4个独立函数类别。更严格的“结构相近但功能不同”留出评价仍有实质缺口，浅面板较高AUC不等于学会布尔功能。

## 3. 梯度诊断协议

固定Z/R/P各第50步参数，固定原schedule的update1、2、25、50四批，覆盖交替采样的全部10个训练源。每批在同一次前向图中，分别计算真实拉近、置换拉近、不同函数分离、0.1倍方差四项对参数的梯度；不创建优化器，不裁剪或施加更新，不选择新种子。主诊断关闭dropout，所有BN冻结；R的第1/2批另做相同种子dropout开启、BN仍冻结的敏感度检查。

按主干、共同边界、引脚边界、内部角色消息、投影头分组，报告梯度范数与方向。下表为四批算术平均，范数不是参数维度归一化的跨组重要性；不同组维度不同，详细grad_rms另存。余弦1表示同方向，-1表示相反方向；梯度下降方向也有相同的两两余弦。

|固定检查点|参数组|真实项范数|不同函数项范数|真实/置换项余弦|真实/不同项余弦|R/P总梯度余弦|
|---|---|---:|---:|---:|---:|---:|
'''+ '\n'.join(gradtable)+'''

R/P总梯度在**同一个固定检查点、同一批次**下构造：g_R=g_real+g_different+0.1g_variance，g_P=g_permuted+g_different+0.1g_variance；不是把不同权重位置的R/P梯度直接相比。

## 4. 原因判断及被排除的简单解释

1. **关联真实性的优化信号弱区分，有直接局部证据。** R检查点主干真实/置换项余弦0.9511，R/P总梯度0.9875；P检查点分别0.9413/0.9917。引脚边界、内部消息和投影头也呈相同趋势。将真实换成错误配对，并没有使局部优化方向发生足够明确的改变。
2. **紧致化与不同函数分离存在明显拉扯。** R主干真实项范数1.1774，不同函数项2.3715，二者余弦-0.8762。不同函数项约为真实项2倍，并非根据历史12.27%损失数值就推断梯度只有12%。MSE可能推动一般表示收缩，分离项推动一般展开；二者权衡可以同时出现在R和P里。不能仅靠增大真实项权重解决，因为错误关联也会被相似地放大，甚至压缩函数区分。
3. **不是接口未接通或只有投影头收到梯度。** 引脚和主干均有非零梯度，投影头之外也有优化信号；已有角色错位敏感度很弱，结合本轮更支持“未充分学到功能语义”，而不是“元数据没送进模型”。但梯度非零不等于有效功能学习。
4. **不能只怪深锥，也不能宣称加深就能修好。** 新浅验证已经有较高函数距离AUC，R仍未优于Z；较深层更难，但结构混杂未完全控制。全锥平均不是有序布尔组合运算，可能丢失输入到输出的逻辑组合。
5. **dropout不是目前唯一解释。** R两批打开dropout、BN冻结时R/P总梯度余弦约0.9739/0.9616，关闭时约0.9875/0.9889，仍高度同向。这是固定状态敏感度，不能替代重新训练的单因素因果实验，也不是本轮追加训练。
6. **当前轮不能归因于检测微调冲掉收益。** 本轮及最近引脚角色实验未做检测微调；无检测AP增益的结论不能从这些函数距离AUC推出。

## 5. 下一轮建议：先让目标区分真假关联

不建议立即增加步数、种子、SAT规模或追加200次检测微调。优先制定一个目标单因素合同：在固定语义接口、图、预算及初始化下，使同anchor跨实现的相对排序成为明确目标，并评估它是否让真实/置换梯度方向和函数排序产生差别。

设计时必须防止新的控制漏洞：如果把当前错误置换边直接加入所有组的跨实现负项，会与P的正项产生字面冲突，使P被额外惩罚，不能作为公平对照。可先核查每个既有源/上下文是否有第三个具有已存不同函数反例的函数，以第三函数提供所有组共有、且与R/P正边均不重合的负项；端点曝光、源预算和算子保持一致。先完成合同与离线支持/梯度预检，再决定是否训练。

严格结构匹配浅验证和留出浅MUX仍无法靠当前池补齐，应列为适用范围，不能把泛化结论做大。目标单因素若仍不能使R区别于P，再考虑独立的锥内有序拓扑递推编码；不要同轮一起改目标、深度和融合方式。

## 6. 核查与证据

- 面板250块全部经独立原始网表标量求值重放反例，和引脚关联位并行结果一致；等价性依据仍是原证明。
- 重查所用17条既有证明查询的model/script/log哈希与对应SUCCESS块，未重跑查询。
- 独立从落盘表示重算全部面板AUC，逐项精确吻合；各检查点主模型、投影头及BN状态计算前后完全一致。
- 文件：panel_certificates.json、panel_source_coverage.csv、panel_coverage_denominators.csv、panel_cone_depths.json、panel_evaluation_*.csv、panel_independent_metrics.csv、panel_structural_matching.csv、existing_structural_support.csv、gradient_norms.csv、gradient_angles.csv、gradient_summary.csv、proof_query_recheck.csv、DIAGNOSTIC_CONTRACT.json、GRADIENT_COMPLETE.json、DIAGNOSTIC_VERIFIED.json。均位于_p0pilot/cec_cause_audit_20261106。
- CPU准备阶段两次断言修订：11条已有完整枚举证明没有SAT proof_id，现明确接纳已有完整枚举证明；最长逻辑依赖路径与最短图距离不能双向等同，现仅检查有效的单向蕴含。修订均在模型诊断前，未依据模型分数修改候选。开发记录另存，未删除旧文件。
'''
 reportpath=R/'10.15/00_说明/等价锥浅小面板与分项梯度诊断_20261106.md';reportpath.write_text(report,encoding='utf-8')
 marker='### 2026-11-06 多源浅小面板与固定检查点分项梯度诊断（已完成）'
 appendix='\n\n'+marker+'''

本轮不训练、不追加SAT：重组250块已有证明/保存反例的评价面板；20次前向、56次分项向量-Jacobian积，优化器更新0、测试读取0。参数及BN缓冲区逐项保持，旧文件SHA保持，17条既有证明查询日志重查通过。详见《等价锥浅小面板与分项梯度诊断_20261106.md》。

- 浅小（四端≤16门、最大门级依赖深度≤4）：训练65块/5源/3宿主，其中MUX17块；验证32块/2源/同一宿主，MUX0。另有同大小较深训练121块/8源、验证32块/2源。组合块不是独立布尔函数或新增SAT证明；未补齐的源和浅MUX验证明确保留。
- 浅验证root64函数区分AUC Z/R/P=0.86621/0.86157/0.85913，R没有超过Z；较深=0.54565/0.57495/0.58057。门型/cut数/大小分箱匹配浅子集12块，Z/R/P=0.89410/0.91493/0.91840，仍无R优势。严格同边界输入集合匹配的浅留出支持为0，不能宣称已经隔离结构线索。
- 固定真实R第50步和原update1/2/25/50批：主干真实/置换拉近梯度余弦均值0.9511，R/P总梯度0.9875；真实拉近与不同函数分离余弦-0.8762、范数1.1774/2.3715。说明当前局部优化对关联真假不敏感，并有收缩/分离拉扯。是局部原始梯度诊断，不能当作完整训练轨迹的唯一因果证明，也不能用旧12.27%损失占比代替梯度占比。
- 主干、引脚及投影头均有非零梯度；dropout开启的两批仍高度同向；浅锥中R也未优于Z。因此不能仅归因于接口未接、投影头独占、锥太深或检测微调覆盖（本轮未微调）。
- 下一轮先准备同anchor跨实现相对排序目标的单因素合同。共用负项应与R/P正边均不重合，先核查已有第三函数反例支持，避免把P正边同时设为负边造成不公平。暂不直接扩SAT、补种子或做检测微调。

证据：`_p0pilot/cec_cause_audit_20261106/DIAGNOSTIC_VERIFIED.json`、panel_evaluation_summary.csv、gradient_summary.csv及对应逐块/逐项文件。
'''
 for n in ['SAT作用证明.md','SAT工作总结.md']:
  p=R/'10.15/00_说明'/n;old=p.read_text(encoding='utf-8-sig')
  if marker not in old:
   with p.open('a',encoding='utf-8') as f:f.write(appendix)
 outputs={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [reportpath,O/'gradient_summary.csv',O/'panel_evaluation_summary.csv',O/'DIAGNOSTIC_VERIFIED.json']}
 (O/'DIAGNOSTIC_PUBLISHED.json').write_text(json.dumps(dict(report=str(reportpath.relative_to(R)),outputs=outputs,docs_updated=['SAT作用证明.md','SAT工作总结.md'],optimizer_steps=0,SAT=0),ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(dict(report=str(reportpath),published=True),ensure_ascii=False))
if __name__=='__main__':main()
