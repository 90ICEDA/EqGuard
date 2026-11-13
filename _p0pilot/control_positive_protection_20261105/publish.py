from pathlib import Path
import csv,json,hashlib,datetime,collections
import numpy as np
O=Path(__file__).resolve().parent;R=O.parents[1];B=R/'_p0pilot/control_v3_eligible_20261104';V=R/'_p0pilot/control_boundary_v3_20261104';N=R/'10.15/00_说明'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def pct(x):return f'{100*float(x):.2f}%'
def main():
 assert not (O/'COMPLETE.json').exists();audit=read(O/'AUDIT_COMPLETE.json');assert audit['all_stored_macro_recalls_reproduced'];cal=read(O/'CALIBRATION_COMPLETE.json');assert cal['thresholds_fit_on']=='validation only'
 for p,h in audit['inputs'].items():assert sha(R/p)==h,p
 node=rows(O/'positive_node_changes.csv');role=rows(O/'paired_source_role_average.csv');cl=rows(O/'paired_roleclass_average.csv');source=rows(O/'positive_source_average.csv');calib=rows(O/'calibration_summary.csv');thresholds=rows(O/'validation_guard_thresholds.csv');counts=rows(O/'positive_aux_eligibility_counts.csv');guard=rows(O/'guard_proposal_counts.csv')
 lost=[x for x in node if x['domain']=='trans' and x['split']=='test' and x['operation']=='val_recall80' and x['lost']=='1'];assert len(lost)==5
 lines=['# 正常区域收益、木马正例召回损失及分角色保护方案（2026-11-05）','',
 '## 回答当前两个问题','',
 '**v3与v2都是39维，差别只有“到PO的距离”这一列及其训练集归一化。** v2把任意引脚接触PO的门都当作距离0起点；v3只把库输出引脚真正驱动PO的门作为起点，再沿相同有向图求距离。v2已有的别名/向量拼接修复、其余38维、图边、标签和掩码均保留。v3不是新增SAT特征，也没有把原语21维编码混入本轮。','',
 '当前等预算H/C对照中，三个种子测试正常区域FPR为64.89%→60.56%，均同向下降；木马宏召回80.12%→79.72%，平均下降0.39个百分点；AP均值0.2975→0.3058，但AP不是3/3同向稳定提高。C说明针对木马相似正常区域的监督有局部价值，召回仍有小代价，完整配对对象联合成功率仍0。','',
 '本轮继续只读复用已有六组预测、映射和标签：0训练、0模型前向、0 SAT，未改标签、图、掩码或旧模型。新产生的是逐节点/源对象诊断、验证集校准探索和可审视的监督提案。','',
 '## 完整正标范围与统计单位','',
 '纳入orig/train 136、trans/train 829、val 215、test 243个可信物理正标坐标，合计1423个图内坐标。每个正标在每个模型种子和操作点只算一次；同源多实现和多个种子不能当作独立源对象。再利用既有制造关系把节点归到触发、载荷、选择、终端来源类，完整正标与原主指标召回逐项复现。',
 '配对制造角色仅覆盖部分变换视图；其均值先按源角色和实现聚合，分母不同于全部正标的逐视图宏召回。本文保留两套口径，避免把角色下降1.94个百分点误当作总体下降1.94个百分点。测试已被前轮查看，所有测试细分与后验校准均属探索性，不用于选训练节点或权重。','',
 '## 实际丢失和找回发生在哪里','',
 '约80%验证召回标定的三个种子中，测试合计5次由检出变漏检、2次由漏检变检出。它们是节点×种子事件，不是7个独立对象。5次损失来自4个源对象，其中2次终端事件是同一源对象、同一个DFF在id/opt实现中的表现。','',
 '|seed/源对象|制造角色/目标节点|H→C分数|H→C阈值|结构/血缘状态|描述|',
 '|---|---|---|---|---|---|']
 for x in lost:
  state='正常/木马源父类混合' if x['mixed_label_sources']=='True' else '输出不可达' if x['PO_reachable']=='False' else '输出可达、单一父类'
  lines.append(f"|{x['seed']}/{x['source']}|{x['manufacturing_roles']}/{x['instance']}|{float(x['H_score']):.4f}→{float(x['C_score']):.4f}|{float(x['threshold_H']):.4f}→{float(x['threshold_C']):.4f}|{state}|{x['loss_description']}|")
 lines += ['',
 'TM2略升分却漏检，主要表现为C的阈值上升；TN1同时降分且阈值上升；P1在C阈值降低后仍因分数下降而漏检，但它本来就在已核查的死支路中。两个HJ来源损失落在DFF_419_Q_reg上，映射父节点同时包含正常DFF_419_Q_reg和TrojanAHJ，不能当作纯HJ功能门的两次独立失败。原y仍为1，本轮不改；额外功能/角色保护需要把这种混合血缘单列。','',
 '2次找回均在seed2：injalpha/opt的DFF_419_Q_reg，以及injgamma/aig的DFF_982_Q_reg，也都是HJ制造来源与正常DFF混合映射。它们在原主指标中按既有正标计分，不代表新证实的木马终端功能。','',
 '## 按完整源对象汇总召回','',
 '|划分/木马源对象|H召回|C召回|差/百分点|分数参照分量/百分点|阈值参照分量/百分点|',
 '|---|---:|---:|---:|---:|---:|']
 for sp in ['val','test']:
  for x in source:
   if x['domain']=='trans' and x['split']==sp and x['operation']=='val_recall80':lines.append(f"|{sp}/{x['source']}|{pct(x['H_recall'])}|{pct(x['C_recall'])}|{100*float(x['recall_delta']):+.2f}|{100*float(x['score_component']):+.2f}|{100*float(x['threshold_component']):+.2f}|")
 lines += ['',
 '这里先源内实现平均，再跨种子平均；不同源对象视图数不同，不将这一表简单相加冒充全体宏召回差。逐节点宏召回贡献另行按每视图正例数和视图总数加权，触发/载荷/HJ来源对测试总体变化的贡献分别约−0.236/−0.082/−0.077个百分点，合计−0.395个百分点。','',
 '分量计算保留四个参考判断：H分数配H阈值、C分数配H阈值、H分数配C阈值、C分数配C阈值；对两种替换顺序取对称平均，分量之和精确还原召回差。概率刻度本身可能变化，所以这只是描述性阈值跨越核查，不是梯度冲突的因果分解。','',
 '测试总体的分数参照分量约−0.675个百分点，阈值参照分量约+0.280个百分点；种子间方向不同。seed42主要受阈值上升影响，seed1主要是真实分数跨线下降；seed2分数损失被更低阈值带来的找回抵消。不能用一个统一“阈值变高”解释全部召回变化。','',
 '## 是否与正常区域降分冲突','',
 '|配对角色类/测试|正常平均降分|木马平均降分|正常FPR差/百分点|木马召回差/百分点|分数/阈值参照分量（百分点）|',
 '|---|---:|---:|---:|---:|---:|']
 for x in cl:
  if (x['domain'],x['split'],x['operation'])==('trans','test','val_recall80'):lines.append(f"|{x['role_class']}|{float(x['normal_delta']):+.4f}|{float(x['trojan_delta']):+.4f}|{100*float(x['normal_fpr_delta']):+.2f}|{100*float(x['trojan_recall_delta']):+.2f}|{100*float(x['score_component']):+.2f}/{100*float(x['threshold_component']):+.2f}|")
 lines += ['',
 '载荷正常分数下降约0.0447，木马约0.0095，平均正负间隔反而扩大0.0352；约80.22%的源/角色/实现加权记录出现两侧都降分，但不能把它说成80.22%的独立节点。它表现出分离收益和共同抑制同时存在。',
 '触发正常分数下降0.0152，木马平均仅下降0.00023；角色召回下降约1.94个百分点中，描述性分数/阈值分量约−0.83/−1.11个百分点。因此部分触发损失来自工作点，而非所有触发门都被明显压分。选择角色没有得到正常FPR收益，且验证没有该制造角色的可靠覆盖，不能凭当前数据承诺保护效果。','',
 '### 训练/验证中已经可见的损失','',
 '训练侧35次丢失、13次找回；35次丢失中27次来自结构可达、无混合父类的正标，8次属于死支路。训练有7个配对源角色的平均召回下降，损失集中在s35932/injbeta载荷P0/P1/P2、s15850/A4形状1触发T2等；多数没有对应正常FPR改善。','',
 '验证侧4次丢失、4次找回，丢失全是结构可达、无混合父类的正标：seed42的injbeta/opt P0、T2，以及seed2的injalpha/id P2、injbeta/id T2。配对验证子集的平均角色召回没有下降角色，却漏掉这些id/opt损失，说明只看abc/nand配对区域会遗漏风险。正例保护应覆盖全部训练实现中的合格正标，不能只保护有正常伙伴的配对实现。','',
 '|训练源对象/角色|正常FPR差/百分点|木马召回差/百分点|解释|', '|---|---:|---:|---|']
 examples=[('s35932t200__ctlmatchb_d1_s42','P0'),('s35932t200__ctlmatchb_d1_s42','P1'),('s35932t200__ctlmatchb_d1_s42','P2'),('s15850t100__a4ctlequiv_s1_d1_s42','T2')]
 for src,ro in examples:
  x=next(x for x in role if x['domain']=='trans' and x['split']=='train' and x['operation']=='val_recall80' and x['source']==src and x['role']==ro);lines.append(f"|{src}/{ro}|{100*float(x['normal_fpr_delta']):+.2f}|{100*float(x['trojan_recall_delta']):+.2f}|源/角色平均，含多个实现和种子|")
 lines += ['',
 '测试TN1的正常FPR无改善而木马召回下降；TM2则正常FPR下降16.67个百分点、木马平均分略升，却受阈值影响失去检出。P1正常FPR两组均0，不能用“正常误报下降”解释其漏检代价；它又是死支路，不能简单提高纯功能正例权重。这些现象不支持统一扩大所有正常负例或所有木马正例的权重。','',
 '## 验证集单阈值保护：无需新训练的离线检查','',
 '只使用验证集已有标签与预测，为每个C模型求一个尽可能高的统一阈值，使其达到同seed H在验证集的宏召回；另给出同时满足验证支持的制造角色类召回下限的单阈值检查。所有阈值都在验证集确定后固定应用测试，部署形式是一个常数，不需要推理时读取真值角色、实例前缀或测试标签。选择类在验证缺失，不提供该类的保护保证。','',
 '|划分/模型及规则|实际木马宏召回|新增正常区域FPR|', '|---|---:|---:|']
 for x in calib:lines.append(f"|{x['split']}/{x['mode']}|{pct(x['actual_T_macro_recall'])}|{pct(x['normal_region_source_FPR'])}|")
 lines += ['',
 '仅匹配验证宏召回的C阈值，在当前测试上的平均召回由79.72%变为80.27%，区域FPR仍60.56%；角色下限单阈值同样约80.27%，区域FPR约61.16%。这说明部分检出代价可以通过校准修复，同时保留局部误报收益。','',
 '但这是对已检查模型的后验探索，不能覆盖或替代本轮原主表，不能据测试表现挑选两个校准规则中的“赢家”，也不能证明5个丢失事件全部恢复。校准不改变排序、AP或训练梯度；真实降分、死支路和混合血缘问题仍在。下一轮应只依据验证目标冻结统一规则，并在独立留出对象上确认。','',
 '## 正例保护的分角色监督方案','',
 '### 一、先明确保护资格，原监督保持','',
 '|范围|正标辅助资格|物理节点|', '|---|---|---:|']
 for x in counts:lines.append(f"|{x['key']}|{x['status']}|{x['physical_positive_nodes']}|")
 lines += ['',
 '原始侧训练136个正标均有结构支持；变换侧829个正标中750个结构可达且源父类不混合，7个存在正常/木马源父类混合，72个是其余纯死支路。7个混合中另含2个不可达，所以不可达总数仍74，不与此前数字矛盾。验证/测试同样保留所有215/243正标。',
 '这些是结构与来源资格，不是SAT功能证书。所有原始y、trusted、ASL和主指标继续保留全部正标；混合、死支路仅暂缓进入新的纯角色辅助项。HJ落到DFF等多对一对象，优先以清晰活动边界/对象集合讨论，不把每个后代当纯HJ功能门。','',
 '### 二、先保护触发与载荷，不统一放大正例','',
 '第一轮辅助项只考虑由训练/验证损失支持的trigger、payload；HJ和选择角色先保留全局来源监督，混合关系进一步审计。资格清单已给出orig/train 115、trans/train 624个触发/载荷候选，覆盖18个木马源对象；trans/val 169个仅作审计和验证，不进入训练。测试坐标没有进入训练提案。',
 '按源对象先平均，再按存在的角色类别平均，物理节点在同一组只算一次，避免多个实现或一对多后代重复增加权重。制造角色只作为训练监督分组，不加入特征，也不在测试推理时按真值角色使用不同阈值。','',
 '### 三、在现有预算内重分配漏检惩罚','',
 '可审视的后续损失形式为：','',
 '`L = L_ASL + 1.4 × [(1−η) × L_global_softmiss + η × L_source_role_softmiss]`','',
 'global_softmiss沿用当前全部可信正标的漏检平方；source_role_softmiss在合格训练触发/载荷组内计算相同形式，再源/角色归一化。η=0就是现有结果，可作为直接复用的基线；η=0.25可作为小幅方案示例，即全局1.05、分角色0.35，总系数仍1.4，尚未验证其最优性。保持ASL、负例总系数、正例唯一节点/曝光、更新次数和域权重，不额外对C单独堆正例损失。系数总和相同不等于梯度范数相同，应报告实际梯度/角色损失，不能声称梯度预算严格相等。','',
 '若将来授权训练，两组H/C都加入相同正例保护，复用现有η=0的六个结果；先seed42 H+guard/C+guard配对，再按验证结果决定是否补seed1/2。仍用同39维v3、orig116/trans233负例配对、200更新和对应初始化。不能只跑C+guard，再把其相对旧H的改善归因于正常对照。','',
 '### 四、选择与验收规则一并固定','',
 '维持每5步验证AP选模规则；角色召回作为配置接受/拒绝约束，不能为了让新损失显得有效而事后挑另一个检查点。统一阈值规则先在验证集冻结，所有条件使用同一校准原则；原80%协议结果仍保留，以便与历史可比。',
 '同时检查正常区域FPR、全体木马宏召回、触发/载荷召回、单源对象最差实现及集合联合成功。只有正常误报收益保持、关键角色召回不再系统下降，才接受新保护方案；若靠降低阈值让所有节点报警，不算解决。参数、资格和η仅用训练/验证，不根据本轮列出的测试门名设置权重。','',
 '当前建议先冻结并确认验证校准规则，暂不急于新训练；若仍需要学习层面的保护，再按上述对称H/C、小η、固定系数方案推进。本轮没有实施任何新损失或阈值部署，也没有改旧模型结果。','',
 '## 证据入口','',
 '- positive_node_changes.csv：所有正标的实际丢失/找回、分数/阈值、角色、可达性和混合父类。',
 '- positive_source_average.csv、role_unique_node_contributions.csv：完整源对象和不重复物理节点对宏召回差的贡献。',
 '- paired_source_role_average.csv、paired_roleclass_average.csv：正常区域收益与同源角色降分/阈值跨越。',
 '- global_recall_decomposition.csv：原指标精确复现和两顺序描述性分解。',
 '- validation_guard_thresholds.csv、calibration_diagnostic.csv、calibration_summary.csv：只用验证确定的统一阈值及全部结果。',
 '- positive_guard_proposal.csv、guard_proposal_counts.csv、POSITIVE_GUARD_PROPOSAL.json：未实施的训练/验证资格与损失方案。',
 '- AUDIT_COMPLETE.json、CALIBRATION_COMPLETE.json、COMPLETE.json：0训练/前向/SAT、原始预测/标签不变及完整哈希。','']
 report='\n'.join(lines);target=N/'正常对照召回损失定位与正例保护方案_20261105.md';target.write_text(report,encoding='utf-8');(O/'召回损失定位与正例保护报告.md').write_text(report,encoding='utf-8')
 brief=f'''\n\n## 正常对照召回损失定位与正例保护方案（2026-11-05）\n\n复用v3合格池H/C六组预测，0训练/0前向/0SAT，原标签图预测不改。v3相对v2仅修PO距离起点及该列归一化，其余38维和图/标签不变。当前C区域FPR64.89%→60.56%、召回80.12%→79.72%的5次测试丢失/2次找回已逐节点核实：TM2略升分但阈值升高，TN1分数和阈值同时跨线；P1在死支路降分；2个HJ丢失事件位于同时映射正常DFF与TrojanHJ的DFF节点，不能当纯功能角色。训练/验证已发现活动正例损失，不能只看abc/nand配对子集。只用验证集标定统一宏召回保护阈值，测试探索性结果为召回80.27%、区域FPR60.56%；不替代原主表、不改变AP、未部署。后续先冻结校准，再考虑对称H/C的正例保护：保留全部原监督，混合/死支路不进纯角色辅助；可提出orig115/trans624个可达、无混合父类的触发/载荷候选（验证169只作验证），将现有1.4 soft-miss系数在global/role间小幅分配（η示例0.25，未验证），负例预算及初始化/200步不变。详见[本轮报告]({target.name})及`_p0pilot/control_positive_protection_20261105/`。\n'''
 for name in ['SAT作用证明.md','SAT工作总结.md','正常对照贡献量化与公平实验方案_20261104.md']:
  with (N/name).open('a',encoding='utf-8') as f:f.write(brief)
 with (R/'10.15/99_共用资产/运行登记/运行登记表.csv').open('a',encoding='utf-8',newline='') as f:csv.writer(f).writerow([datetime.datetime.now().astimezone().isoformat(),'v3合格池召回损失与正例保护离线方案','control_positive_protection audit/calibration/propose/publish.py','CPU saved predictions;0 model calls','42/1/2 reused','orig train/trans train,val,test','H/C116/233 existing results','_p0pilot/control_positive_protection_20261105','5 lost/2 gained test events;validation guard80.27 recall/60.56 regionFPR','完成','no new training/SAT;no label edits;test exploratory;guard not deployed'])
 # Verify frozen runs and inputs remain unchanged after notes are written.
 for p,h in audit['inputs'].items():assert sha(R/p)==h,p
 for p,h in read(B/'COMPLETE.json')['artifacts'].items():assert sha(R/p)==h,p
 for p,h in read(V/'input_contract.json')['files'].items():assert sha(R/p)==h,p
 artifacts=[p for p in O.iterdir() if p.suffix in ['.json','.csv','.py','.md']]+[target]
 (O/'COMPLETE.json').write_text(json.dumps(dict(time=datetime.datetime.now().astimezone().isoformat(),training=0,SAT=0,model_forward=0,labels_graphs_masks_modified=False,saved_predictions_unchanged=True,calibration_validation_only=True,not_deployed=True,report=str(target),artifacts={str(p.relative_to(R)):sha(p) for p in artifacts}),ensure_ascii=False,indent=2),encoding='utf-8');print(target)
if __name__=='__main__':main()
