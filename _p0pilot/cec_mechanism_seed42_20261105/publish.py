"""Publish evidence-bounded diagnosis without modifying any training artifact."""
from pathlib import Path
import collections,csv,datetime,hashlib,json
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;PRE=R/'_p0pilot/cec_pretrain_ready_20261105';RUN=R/'_p0pilot/cec_pretrain_seed42_20261105';J=R/'_p0pilot/cec_joint_expand_20261105';D=R/'10.15/00_说明'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def mt(rr,fields):return '\n'.join(['|'+'|'.join(fields)+'|','|'+'|'.join(['---']*len(fields))+'|']+['|'+'|'.join(str(r[k]) for k in fields)+'|' for r in rr])
def main():
 assert not (O/'PUBLISHED.json').exists();a=read(O/'DIAGNOSIS_COMPLETE.json');decomp=read(O/'DECOMPOSITION.json');collision=read(O/'INPUT_COLLISIONS.json');plan=read(O/'PREPARED.json');done=read(O/'EMBEDDINGS_COMPLETE.json');old=read(RUN/'ANALYSIS_COMPLETE.json')
 for path,h in plan['frozen'].items():assert sha(R/path)==h,path
 for path,h in plan['inputs'].items():assert sha(R/path)==h,path
 assert a['training_updates']==a['optimizer_steps']==a['backward_calls']==a['new_SAT_queries']==0 and all(c['state_unchanged'] for c in done['model_state_checks'])
 def metric(stage,layer,split='val',cohort=None):return next(r for r in a['function_metrics'] if r['stage']==stage and r['layer']==layer and r['split']==split and r['cohort']==(cohort or ('main' if split=='train' else 'val_negative')))
 def spec(stage,layer):return next(r for r in a['spectra'] if r['stage']==stage and r['layer']==layer and r['split']=='val')
 def row(arm,stage,layer):
  z=metric(stage,layer);return dict(组=arm,阶段=stage,表示=layer,同函数RMS=f"{z['real_rms']:.4f}",不同函数RMS=f"{z['negative_rms']:.4f}",同异距离比=f"{z['real_over_negative']:.4f}",同异排序AUC=f"{z['same_vs_negative_AUC']:.4f}",真实置换排序AUC=f"{z['same_vs_fake_AUC']:.4f}")
 function_table=[row(arm,arm+'_pre',layer) for arm in ['Z','R','P'] for layer in ['root64','concat128','projection32_'+arm]]
 head_table=[]
 for arm in ['Z','R','P']:
  for label in ['initial',arm]:
   z=metric(arm+'_pre','projection32_'+label);head_table.append(dict(编码器=arm+'_pre',投影头=label,同异排序AUC=f"{z['same_vs_negative_AUC']:.4f}",真实置换排序AUC=f"{z['same_vs_fake_AUC']:.4f}"))
 spectrum_table=[]
 for arm in ['Z','R','P']:
  for layer in ['concat128','projection32_'+arm]:
   z=spec(arm+'_pre',layer);spectrum_table.append(dict(组=arm,表示=layer,源等权标准差=f"{z['source_balanced_std']:.4f}",有效秩=f"{z['effective_rank']:.3f}",首主成分能量=f"{100*z['top1_energy']:.2f}%",源内有效秩=f"{z['within_source_effective_rank']:.3f}"))
 fine_table=[row(arm,arm+'_'+stage,'projection32_'+arm) for arm in ['Z','R','P'] for stage in ['pre','best','last']]
 bn_table=[]
 for arm in ['R','P']:
  for suffix in ['pre','best','preW_fineBN','fineW_preBN']:
   z=metric(arm+'_'+suffix,'projection32_'+arm);dr=next((r for r in a['drift'] if r['arm']==arm and r['split']=='val' and r['comparison']==suffix+'_vs_pre'),None);bn_table.append(dict(组=arm,组合=suffix,同异排序AUC=f"{z['same_vs_negative_AUC']:.4f}",源内CKA相对预训练=f"{dr['within_source_CKA']:.4f}" if dr else '1.0000'))
 noise_table=[]
 for arm in ['Z','R','P']:
  clean=next(z for z in a['noise'] if z['arm']==arm and z['mode']=='eval_running' and z['layer']=='projection32');drop=next(z for z in a['noise_self'] if z['arm']==arm and z['BN']=='runningBN' and z['layer']=='projection32');batch=next(z for z in a['noise'] if z['arm']==arm and z['mode']=='dropout_batchBN101' and z['layer']=='projection32');noise_table.append(dict(组=arm,干净不同函数RMS=f"{clean['negative_rms']:.4f}",同锥两次dropout距离=f"{drop['same_cone_dropout_RMS']:.4f}",噪声相对不同函数距离=f"{drop['same_cone_dropout_RMS']/clean['negative_rms']:.3f}",训练模式不同函数RMS=f"{batch['negative_rms']:.4f}",训练模式同函数RMS=f"{batch['real_rms']:.4f}"))
 # Cross-arm CKA removes each source's centroid before comparing feature geometry.
 pairs=read(J/'final_pairs.json');source={p[k]:p['source_object'] for p in pairs for k in ['left_cone','right_cone']};ids=plan['val_cones'];ss=[source[c] for c in ids]
 def center(x):
  x=x.astype(float).copy()
  for src in set(ss):
   ii=np.array([s==src for s in ss]);x[ii]-=x[ii].mean(0);x[ii]/=np.sqrt(sum(ii))
  return x
 def cka(x,y):
  x,y=center(x),center(y);return float(np.linalg.norm(x.T@y)**2/max(np.linalg.norm(x.T@x)*np.linalg.norm(y.T@y),1e-30))
 similarity=[]
 for stage in ['pre','best']:
  vv={arm:np.load(O/'embeddings'/(arm+'_'+stage)/'val_eval_running.npy') for arm in ['Z','R','P']};similarity.append(dict(stage=stage,R_P=cka(vv['R'],vv['P']),R_Z=cka(vv['R'],vv['Z']),P_Z=cka(vv['P'],vv['Z'])))
 (O/'cross_arm_CKA.json').write_text(json.dumps(similarity,indent=2),encoding='utf-8')
 protocol=read(R/'_p0pilot/control_boundary_v3_20261104/input_contract.json');features=[dict(column_1based=i+1,name=name,branch='structure29' if i<29 else 'topology10',normalization='raw onehot' if i<25 else 'train pooled orig/trans zscore clipped+-10') for i,name in enumerate(protocol['columns39'])]
 with (O/'feature_columns.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(features[0]));w.writeheader();w.writerows(features)
 target=D/'等价锥预训练失效机制_函数区分投影头与微调覆盖_20261105.md';assert not target.exists()
 text='''# 等价锥预训练失效机制：函数区分、投影头与微调覆盖

2026-11-05。复用seed42 Z/R/P全部检查点及已保存预测。无新增训练、优化器、反向或SAT；新增47次训练/验证图的评估前向，所有参数及BN缓冲逐次校验不变；未重新前向测试图，没有改旧分数、阈值、选模或标签。下述为单种子的事后机制诊断，不是新独立确认实验。

## 1. 当前训练配置和监督协议

当前采用改进双分支S-GIN，39维输入、hidden64、前29/后10维拆分，各2层GIN，融合后1层GIN，即根表示的3次消息传递；模型46620参数。先39→39共享残差混合，再分支、融合、post层和dropout，检测分类头只读取根节点64维表示。预训练另用root64与整个组合锥mean64拼接的128维向量，经128→64ReLU→32投影。

GIN各层及post输出使用dropout0.2，含BatchNorm。输入为冻结有向全图，包含所有既定引脚连接；模型仅消费edge_index，未消费edge_roles。CEC语义边界是同名PI与自由物理Q，QN为反相；编码器仍读取完整图上下文，不能当成在该PI/Q输入下精确计算布尔值的求值器。

Z/R/P各50次预训练，统一末步：共同函数不同负对＋方差项，Z关闭正等价项，R真实对应，P已被明确反例否定的同源交换对应。主三组每步端点、权重、公共负对、前向预算和初始化相同，源平衡；主P配对结构联合关系不受控，严格151背景配对仅用于本轮离线诊断，未训练。

预训练只读trans_train图和39维，不以安全标签作为损失或输入。原10源/2965训练配对池中，固定50步采500真实边名额、382唯一配对，覆盖12个可信正根、4个正根源；不是所有训练配对都被优化目标使用。数据池按源/连通锥/边等权，实际50步按冻结源平衡索引执行。

随后丢弃投影头，迁移编码器含BN，分类头恢复原seed42初始状态，重置Adam，沿用旧H监督微调200步，损失为ASL＋1.4soft-miss平方，无新增区域损失或等价辅助项。每步原始侧基础136正/109910负＋320个H负名额；变换侧829正/420045负＋320个H负名额。名额允许按旧H索引重复，不能当成独立节点数；预训练池化的曝光上限不能套到检测监督上。

统一Adam lr0.0002、weight_decay0.001、clip1，ginvenv_gpu、bf16。检测每5步按验证可信木马视图macro AP选模（Z185、R200、P195），阈值仅验证标定。三组共750次更新。检测AP为验证25/测试24个木马视图的可信节点逐视图宏平均；完整正常视图FPR另报，不是新增区域FPR。历史已分析测试结果维持探索性，不作为新盲测。

## 2. 当前实际特征选取

使用39维v3，没有使用原语21维，也没有拼接18维SAT摘要。CEC证据通过关系损失使用，不是数值SAT特征输入。39维的精确字段见feature_columns.csv。

|1基列号|内容|分支|
|---|---|---|
|1—25|25类库单元/合成门类别one-hot|前29维|
|26—27|log1p输入端口数、log1p关联连接数|前29维|
|28—29|是否触及PI、是否触及PO|前29维|
|30—31|有向PI距离、到PO输出驱动单元距离|后10维|
|32—33|log1p精确二跳fanin、fanout|后10维|
|34—35|以寄存器边界重置的输入/输出侧距离|后10维|
|36—37|相同寄存器边界处理后的二跳fanin、fanout|后10维|
|38—39|组合SCC标记、log1p组合SCC规模|后10维|

“register_reset”指在寄存器处重置图遍历边界，不是复位引脚信号特征。门型列保留原one-hot，结构14列使用冻结的训练orig/trans统计z-score并裁剪±10；v3相对v2仅修PO距离起点与该列统计，其他38列和图保持。模型输入不含PI/Q信号身份、逐输入真值/变化向量或引脚角色编码，因此有CEC关系监督不等于输入已包含完整功能语义。

## 3. 本轮如何区分三种机制

分开读取初始编码器、预训练50步、微调选中点及微调200末点的root64、mean64、concat128；对同一编码器分别接初始/训练后投影头，另把训练头接初始编码器。这样可检查头压缩，不能当成“单独训练投影头”的因果消融。

另准备20份验证不同函数证书，来自5个已有验证制造源；按固定哈希、每源最多8块，从现有等价池选择两种函数，不按标签或模型分数筛选。共享PI/Q输入使输出不同，独立标量回放20块全部通过；不是新增SAT，也未进入训练。

诊断“同函数vs不同函数AUC”用距离越小越同函数的排序定义，先各源内计算再宏平均；不是木马分类AUC。另报真实跨实现边vs错误跨实现边AUC，区分两种负对。真同函数和同视图不同函数可能存在实现域组成差异，不能把该AUC当纯功能可辨性定论。验证仅20块/5源/1宿主，全部属于事后诊断。

谱以源等权协方差计算，同时看去掉各源均值后的有效秩；CPU投影统一float32重算便于头交换，与上轮bf16、节点等权谱的绝对数不直接相减。旧分类分数和检测AP没有重算或修改。

## 4. 函数区分是否被压缩

'''
 text+=mt(function_table,['组','表示','同函数RMS','不同函数RMS','同异距离比','同异排序AUC','真实置换排序AUC'])
 text+='''

R/P比Z同时缩小同函数与不同函数距离，说明确有整体尺度压缩；但不能据此说相对函数区分全面消失。验证投影同异AUC由Z的0.3484提高到R0.5977、P0.6055，R/P均有一定相对区分，问题是R并未独有地优于P。同异距离比是先按源求比再平均，不能直接用表内两个宏平均RMS相除。

尤其下游实际分类只用root64：预训练时root64同异AUC为Z0.6453、R0.5805、P0.5820，R没有给检测头入口提供优于两对照的功能区分。mean与MLP上的某种改善不保证能传给只看root64的检测头。这是当前预训练目标与下游接口不完全一致的直接证据，但不是其独立导致AP变化的已验证因果结论。

严格同边界/门型/规模匹配的151个训练背景配对上，投影同异AUC仅Z0.3134/R0.3327/P0.3457，真实vs错误跨实现AUC约0.56；这种条件下，不同函数在同实现中反而常比相同函数跨实现更近。它支持当前表示还受到实现差异影响，不能由宽松主池的距离改善宣布已学会功能等价。

## 5. 投影头是否吸收了约束

'''
 text+=mt(spectrum_table,['组','表示','源等权标准差','有效秩','首主成分能量','源内有效秩'])
 text+='''

R的concat128有效秩3.56，投影后1.75，首主成分约87.35%能量；Z投影更集中，首主成分约97.01%。因此低秩并非R独有，投影头明显进一步压缩了表示。

'''
 text+=mt(head_table,['编码器','投影头','同异排序AUC','真实置换排序AUC'])
 text+='''

固定R预训练编码器，初始头同异AUC0.6156，训练头0.5977，训练头并未保住更多不同函数信息；但真实vs错误对应AUC只从0.6859到0.6945，小幅变化。把训练头接回初始编码器也不能复现预训练效果。R编码器两个分支参数相对初值各变化约2.3%，共享mix约7.8%，投影第一/第二层约7.9%/5.6%，分类头预训练变化0。

结论是：投影头承担了明显压缩，编码器也确实学习了，不能归为“只有头吸收、编码器完全没动”。交换头会造成分布失配，不能把交换前后差值直接当可加的因果贡献百分比。

## 6. 为什么真实对应与错误对应这么接近

源内中心化后，R/P预训练concat128的验证CKA为0.99695，R/Z为0.91151；微调后R/P仍0.98826。两种约束在预训练阶段就已得到非常相似的编码器，因此不能仅把失败归咎于后续微调。

用同一交换块的四个向量可精确分解：两条真实边平均平方距离=两实现函数集合的共同中心偏移＋相对函数差；置换边有相同的共同中心偏移，只把相对函数差改成相对函数和。实际R预训练投影的共同中心项占真实MSE约57.5%，P约57.1%，两组都在压制这部分共同偏移。

预训练历史中，R正等价项占均值总损失约7.58%，P约7.18%，其余主要为共同不同函数项和方差项。这里是损失数值份额，不是编码器梯度贡献份额。解析计算的表示层正项梯度cos约0.44，两种正约束仍有明显方向差，不能说梯度完全相同。共同目标和共同偏移能够解释泛化正则化趋势，但没有单独训练消融来分配各因素的因果贡献。

因此更准确的说法是：当前目标所得到的主要变化并不特异于真实等价边；即使错误边被严格证明不同函数，也可以通过类似的尺度/实现差异压缩改变表示。

## 7. dropout是否干扰了函数区分

在同一预训练检查点上，只改变dropout/BN模式，不改权重或统计缓冲。BN运行统计固定时比较两次不同dropout掩码，对同一锥得到的距离如下：

'''
 text+=mt(noise_table,['组','干净不同函数RMS','同锥两次dropout距离','噪声相对不同函数距离','训练模式不同函数RMS','训练模式同函数RMS'])
 text+='''

R同锥随机噪声距离约0.0928，是干净不同函数距离0.1506的约62%；P约66%。训练样式batch-BN＋dropout时，R同函数/不同函数距离约0.204/0.214，二者很接近；关闭dropout的batch-BN约0.189/0.217，差别更明显。说明随机噪声确实占据了函数距离的一部分，不能把训练中距离非零全算成功能区分。

这不证明关闭dropout重训一定提高AP。当前只是同检查点评估模式切换；batch-BN没有更新running统计、没有优化器，不能等同于从头采用另一种噪声配置训练。

## 8. 微调是否覆盖了预训练效果

以下均重新挂回同一个预训练投影头，检测模型实际没有使用该头。

'''
 text+=mt(fine_table,['组','阶段','同函数RMS','不同函数RMS','同异排序AUC','真实置换排序AUC'])
 text+='''

R验证投影同异AUC从0.5977降到0.4148；concat128从0.5820降到0.4719；root64从0.5805降到0.4555。P也出现类似下降。R源内CKA（微调相对预训练）约0.359，说明表征明显重组；真实vs错误跨实现AUC仍约0.66，不能说全部预训练信息彻底消失。

R预训练分支参数变化约2.3%，微调相对预训练又变化约10%，共享mix约26.6%，变化量明显更大；下游没有任何继续保持功能目标的损失。Z也发生变化，但Z的该验证同异排序反而提升，说明微调并不是单向擦除所有表示，而是按检测监督重组织，可能覆盖或旋转预训练功能分量。

### BN与参数互换

'''
 text+=mt(bn_table,['组','组合','同异排序AUC','源内CKA相对预训练'])
 text+='''

R固定预训练参数、只换微调BN，CKA仍约0.955但距离尺度变化大；固定预训练BN、换微调参数，CKA约0.501；两者一起变化后约0.359。说明不只是BN统计，参数更新也造成了表征重组；也不能把BN互换后的失配结果当可部署模型效果。

固定旧头表现下降可能来自信息丢失，也可能是坐标旋转或头失配。本轮没有训练线性探针，因此不能断言预训练功能信息已全部不可恢复。但微调前R本就未优于P，加之root入口无独特优势，恢复微调保持约束并不是已被证明足够的单一修复。

## 9. 是否存在“证书函数不同，但当前输入必然相同”的硬冲突

对本轮负边作保守3轮前驱多重集颜色审计：若规范化39维初始颜色、3轮根颜色、锥成员颜色袋完全相同，当前确定性评估编码器的root＋mean将不可区分。main500次负边引用/394去重边、strict350/165、验证40/40均未检出这种充分不可区分条件。不能把失败直接归为这些样本的完全同输入或错误证书；未检出也不证明当前模型表达充分。

模型没有显式输入引脚角色或PI/Q查询赋值，3跳编码＋全锥均值并非完整函数求值；其可学习功能能力仍需实验证据，不能因CEC证书正确就假设模型必然能学到对应关系。本轮不改39维、不改标签，也不据此草率加入信号名字等宿主线索。

## 10. 原检测结果保持与下一步建议

原验证AP Z/R/P=0.21934/0.23480/0.24263，测试AP=0.29479/0.27749/0.28005，全部复用原预测及选模，不更新任何阈值。测试没有CEC配对，本轮也没有新测试前向，不能输出测试功能稳定性。

本轮可确认的链条是：R/P预训练编码器非常相似；真实与不同函数一起缩距，投影进一步低秩化，主变化并不特异于真实边；dropout噪声相对函数距离不可忽视；下游只用root而预训练用root＋mean＋头，微调又对编码器作较大重组。它们共同解释当前设置为什么没有建立“真实对应优于置换”的证据，不能声称已经确定某一个唯一根因。

建议先冻结训练/验证上的机制验收，再选择一个单因素修复：

1. 优先检查在功能预训练阶段关闭dropout、检测微调仍保持0.2是否能减少噪声干扰；三组同步、同预算，不据测试调参。这是建议，不是本轮已运行结论。
2. 单独检验把函数间相对区分及去相关/有效秩约束落实到可迁移编码器或root入口，不能只对投影输出求近；先确定与检测所用表示的接口一致。不要一次同时改特征、模型、损失和预算。
3. 预训练阶段真正出现R相对P的函数区分优势后，再以独立因素检验微调保留小权重功能项或限制功能分量漂移，不能先认定只冻结BN或延长训练就够。

暂不建议扩大SAT或直接追加seed1/2来掩盖该机制缺口。后续改法先用训练/验证指标和证书队列确定，固定后才统一看测试；不把本轮事后20验证负块当独立确认集。

## 11. 复核文件

目录`_p0pilot/cec_mechanism_seed42_20261105/`：PREPARED.json、validation_negative_certificates.json及输入见证；embeddings/*含初始、预训练、选中微调、末步和BN/dropout互换的只读评估表示及SHA绑定；EMBEDDINGS_COMPLETE.json记录47次前向且模型状态均未变；function_distances.csv、spectra.csv、encoder_drift.csv、dropout_BN_modes.csv、dropout_same_cone_noise.csv、weight_deltas.json、cross_arm_CKA.json、loss_decomposition.csv、DECOMPOSITION.json、INPUT_COLLISIONS.json及逐边表、feature_columns.csv、DIAGNOSIS_COMPLETE.json。旧750次训练检查点和预测均保留。
'''
 target.write_text(text,encoding='utf-8')
 brief='''

## 等价预训练未优于置换的离线机制诊断（2026-11-05）

复用seed42检查点/原预测，0新增训练/反向/优化器/SAT，47次train/val评估前向逐次校验参数与BN不变，0测试新前向。当前协议为39v3（25门型+14拓扑、29/10双分支、2+2+post1），50功能预训root64+mean64投影32，丢头后H200检测仅用root64；不加18维SAT/原语21，微调ASL+1.4softmiss不含功能项。新增20份验证不同函数证书（5源、固定哈希、独立标量反例），不是木马负标签。R/P验证编码器源内CKA=.99695，预训阶段已相似；R投影同/异函数RMS=.1218/.1190，P=.1151/.1162，尺度都收缩但相对区分不全消失，同异AUC R.5977/P.6055（Z.3484），无R独有优势；检测root入口AUC Z.6453/R.5805/P.5820。R concat秩3.56→投影1.75、首主成分87.35%，头压缩明显但编码器分支也更新2.3%，不能归为仅头吸收。正项占平均总损失R7.58%/P7.18%，共同中心项约57%，解析正项z梯度cos约.44并非相同梯度。R同锥dropout噪声.0928约为干净异函数距离.1506的62%，噪声不可忽略。R微调后固定旧头同异AUC .5977→.4148，编码器concat .5820→.4719，源内CKA .359，参数更新约10%；BN单换CKA .955、权重单换 .501，存在重组/部分覆盖但非全信息消失。负边3轮颜色审计未找到必然同输入冲突，不能怪证书错误或已证明表达不可能。原AP和阈值不变、测试功能配对仍NA。建议先单因素检验预训dropout/编码器功能区分与头接口，再考虑微调保持项，不扩大SAT或机械补种子。详见[本轮报告](等价锥预训练失效机制_函数区分投影头与微调覆盖_20261105.md)及`_p0pilot/cec_mechanism_seed42_20261105/`；均为事后小样本诊断，不用于测试调参。
'''
 for name in ['SAT作用证明.md','SAT工作总结.md']:
  path=D/name;assert '## 等价预训练未优于置换的离线机制诊断' not in path.read_text(encoding='utf-8')
  with path.open('a',encoding='utf-8') as f:f.write(brief)
 with (R/'10.15/99_共用资产/运行登记/运行登记表.csv').open('a',encoding='utf-8',newline='') as f:csv.writer(f).writerow([datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),'等价预训练函数区分_投影头_微调覆盖机制','cec_mechanism prepare/evaluate/analyze/decompose/audit_input_collisions/publish','ginvenv_gpu inference only47;0train/backward/SAT;no test forward','42 existing checkpoints','train/val20negative witness blocks;test saved predictions only','same39v3/old checkpoints;no labels/features changed',str(O.relative_to(R)),'RPencoderCKA.99695;RvalfunctionAUC.5977->.4148;headrank1.75;drop noise62%','完成离线机制诊断','single-seed posthoc20blocks;counterfactual head/BN swaps not training causal ablation'])
 files={str(p.relative_to(R)):sha(p) for p in O.rglob('*') if p.is_file() and '__pycache__' not in p.parts};files[str(target.relative_to(R))]=sha(target)
 (O/'PUBLISHED.json').write_text(json.dumps(dict(report=str(target.relative_to(R)),files=files,training_updates=0,backward_calls=0,optimizer_steps=0,new_SAT_queries=0,new_evaluation_forwards=47,new_test_forwards=0,status='POSTHOC_MECHANISM_DIAGNOSIS_COMPLETE'),ensure_ascii=False,indent=2),encoding='utf-8');print('Published mechanism diagnosis and updated both notes',flush=True)
if __name__=='__main__':main()
