"""Audit all750 optimizer steps and publish the completed seed42 exploration."""
from pathlib import Path
import collections,csv,datetime,hashlib,json,sys
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;PRE=R/'_p0pilot/cec_pretrain_ready_20261105';J=R/'_p0pilot/cec_joint_expand_20261105';D=R/'10.15/00_说明'
sys.path.insert(0,str(PRE));import engine as E
torch=E.torch
def mt(rr,fields):return '\n'.join(['|'+'|'.join(fields)+'|','|'+'|'.join(['---']*len(fields))+'|']+['|'+'|'.join(str(r[k]) for k in fields)+'|' for r in rr])
def main():
 assert not (O/'PUBLISHED.json').exists();a=E.read(O/'ANALYSIS_COMPLETE.json');assert a['total_updates']==750 and a['test_paired_metrics'] is None
 for path,h in E.read(PRE/'RUN_CONTRACT.json')['frozen_files'].items():assert E.sha(R/path)==h,path
 for root in [PRE,J]:
  for path,h in E.read(root/'PUBLISHED.json')['files'].items():assert E.sha(R/path)==h,path
 audits=[];first=[];prestats=[]
 for arm in ['Z','R','P']:
  b=PRE/'runs/main/seed42'/arm
  for stage,updates in [('pretrain',50),('finetune',200)]:
   folder=b/stage;done=E.read(folder/'COMPLETE.json');assert done['updates']==updates;binding=E.read(folder/'binding.json');assert binding['seed']==42 and binding['mode']=='main' and binding['arm']==arm and binding['init_sha']==E.sha(E.H/'init_s42.pt') and binding['execution_contract_sha']==E.sha(O/'EXECUTION_CONTRACT.json') and binding['controller_sha']==E.sha(O/'run_controlled.py')
   saved=torch.load(folder/'resume.pt',map_location='cpu',weights_only=False);assert saved['completed']==updates and saved['binding']==binding;steps={int(v['step']) for v in saved['optimizer']['state'].values() if 'step' in v};assert steps=={updates},(arm,stage,steps)
   for group in saved['optimizer']['param_groups']:assert group['lr']==.0002 and group['weight_decay']==.001
   assert all(torch.isfinite(v).all() for v in saved['model'].values() if v.is_floating_point());assert len(saved['history'])==updates
   audits.append(dict(arm=arm,stage=stage,updates=updates,optimizer_steps=updates,same_detector_initialization=True,finite_weights=True,checkpoint_sha=E.sha(folder/'resume.pt')))
   gate=E.read(O/f'FIRST_{stage}_{arm}.json');assert gate['passed'];first.append(dict(arm=arm,stage=stage,peak_allocated_GiB=f"{gate['peak_allocated_bytes']/2**30:.3f}",peak_reserved_GiB=f"{gate['peak_reserved_bytes']/2**30:.3f}",passed=True))
  assert E.read(b/'pretrain/COMPLETE.json')['classifier_unchanged']
  ph=E.read(b/'pretrain/history.json');h=next(h for h in a['histories'] if h['arm']==arm);prestats.append(dict(组=arm,预训练末步标准差=f"{ph[-1]['representation_std']:.4f}",验证投影标准差=f"{h['validation_projection']['std_mean']:.4f}",验证有效秩=f"{h['validation_projection']['effective_rank']:.3f}",预热后步耗时中位秒=f"{np.median([r['seconds'] for r in ph[4:]]):.3f}"))
 detection=[];comparison={}
 for arm in ['Z','R','P']:
  val=next(z for z in a['detection'] if z['arm']==arm and z['split']=='val' and z['operation']=='val_recall80');test=next(z for z in a['detection'] if z['arm']==arm and z['split']=='test' and z['operation']=='val_recall80');comparison[arm]=dict(val=val,test=test)
  detection.append(dict(组=arm,验证AP=f"{val['ap']:.4f}",测试AP=f"{test['ap']:.4f}",测试AUC=f"{test['auc']:.4f}",测试Recall1=f"{test['r1']*100:.2f}%",测试Recall5=f"{test['r5']*100:.2f}%",测试召回=f"{test['recall']*100:.2f}%",正常FPR=f"{test['control_fpr']*100:.2f}%",选中微调步=val['selected_update']))
 delta={key:comparison['R']['test'][key]-comparison['Z']['test'][key] for key in ['ap','auc','r1','r5','recall','control_fpr']};delta['R_minus_P_test_AP']=comparison['R']['test']['ap']-comparison['P']['test']['ap'];delta['R_minus_Z_val_AP']=comparison['R']['val']['ap']-comparison['Z']['val']['ap'];delta['R_minus_P_val_AP']=comparison['R']['val']['ap']-comparison['P']['val']['ap']
 pairtable=[];functable=[]
 for arm in ['Z','R','P']:
  for cls in ['all','0','1']:
   p=next(z for z in a['paired'] if z['arm']==arm and z['split']=='val' and z['stratum']==cls);pairtable.append(dict(组=arm,根类别=cls,源=p['sources'],配对=p['pairs'],概率MAE=f"{p['MAE']:.5f}",翻转=f"{p['flip']*100:.2f}%",两侧均正确=f"{p['both_correct']*100:.2f}%",两侧均错=f"{p['both_wrong']*100:.2f}%"))
  f=next(z for z in a['functional_validation'] if z['arm']==arm and z['stratum']=='all');t=next(z for z in a['functional_train'] if z['arm']==arm);functable.append(dict(组=arm,验证等价RMS=f"{f['rms']:.4f}",按源尺度归一RMS=f"{f['normalized_rms']:.4f}",训练真实RMS=f"{t['real_rms']:.4f}",训练置换RMS=f"{t['permuted_rms']:.4f}",训练不同函数RMS=f"{t['negative_rms']:.4f}"))
 pairs=E.read(J/'final_pairs.json');skipped=[p for p in pairs if p['split']=='train' and not p['detection_stability_diagnostic_eligible']]
 # Raw per-root outcomes retained; do not change labels or thresholds to improve them.
 rootrows=list(csv.DictReader((O/'pair_predictions.csv').open(encoding='utf-8-sig')));positive_rows=[]
 for arm in ['Z','R','P']:
  for source in sorted({r['source'] for r in rootrows if r['split']=='val' and r['label']=='1'}):
   rr=[r for r in rootrows if r['arm']==arm and r['split']=='val' and r['label']=='1' and r['source']==source];w=np.asarray([float(r['weight']) for r in rr]);w/=w.sum();positive_rows.append(dict(组=arm,制造源=source,正根数=len(rr),MAE=f"{np.dot(w,[float(r['MAE']) for r in rr]):.4f}",翻转=f"{np.dot(w,[int(r['flip']) for r in rr])*100:.2f}%",两侧均正确=f"{np.dot(w,[int(r['both_correct']) for r in rr])*100:.2f}%",两侧均错=f"{np.dot(w,[int(r['both_wrong']) for r in rr])*100:.2f}%"))
 target=D/'等价锥ZRP探索性预训练及检测微调_seed42_20261105.md';assert not target.exists()
 text='''# 等价锥Z/R/P探索性预训练及200次检测微调（seed42）

2026-11-05。按用户授权使用ginvenv_gpu执行main方案seed42三组，完成每组50次预训练及200次检测微调，共750次优化器更新。未追加SAT，旧实验、图、标签、特征、证明、训练初始化和成功批次均保留。未执行seed1/2或严格151子集训练。

## 1. 结论

首步显存、有限损失与非全常量检查均通过，三组完整运行，无OOM或失败训练批次。**本轮未证明真实等价约束的独立检测增益**：R验证AP高于Z，但低于P；测试AP低于Z和P。R在验证功能表示原始距离上比Z小，但P同样小，尺度归一化后优势有限；不应把这写成模型已经学会可迁移电路等价。

三组表示均非全常量，然而32维验证功能投影有效秩仅约1.18—2.03，存在明显低秩/维度退化风险。首步不坍缩不等于训练结束后表达充分，不能以首步检查代替最终表征检查。

## 2. 固定协议与实际实现

Z仅关闭正等价项，三组都保留证书不同函数负对和方差项；Z并非完全没有功能信息的从头训练组。R使用真实等价边，P使用已证明错误的同源交换边。三组同完整trans_train图、39维v3、相同归一化、原改进双分支2+2+post1、hidden64、同编码器/投影初值和逐步随机种子。

预训练共50步，固定末步，不按验证指标选预训练轮次；10源每源50真实边名额、500名额、382唯一配对，公共负边与逐步端点/权重完全一致。未加18维SAT摘要输入；使用的是CEC/枚举证明提供的训练对应关系。

为避免对同一完整隐藏张量重复做多次大规模反向scatter，运行控制器将锥池化改为单次批量gather/index_add求均值，随后恢复原隐藏dtype。根节点及成员不变，CPU前向与梯度等价检查通过；三个组同步使用。模型、损失、监督预算不变。CUDA并行归约存在小量数值波动，相同初始化不代表不同进程输出逐bit完全一致。

50步后丢弃投影头，只迁移编码器及BN状态；分类头恢复同种子原初值，重置Adam。原H200两域基础监督、额外200×320槽位、ASL+1.4soft-miss、图/标签/归一化与初始化保持。三组均每5步验证AP选检测检查点，不根据测试结果选择。原H200只作历史参照，不充当250步公平主对照。

主P保持端点/来源/预算，但改变配对结构联合关系；其比较不能排除门型/边界关系线索。严格151对背景子集未运行。本轮不将未运行的机制对照写入结果。

## 3. 首步检查与运行预算

'''
 text+=mt(first,['arm','stage','peak_allocated_GiB','peak_reserved_GiB','passed'])
 text+='''

预训练首步原始表示标准差约0.049、有效秩约4.66，不同函数RMS约0.066；三个组的总损失约0.918、0.924、0.924，梯度有限。先分别保存第1步检查点，三组均通过后续跑剩余49步，第1步没有重算。微调首步两域损失约0.69—0.73，权重有限。

表中显存是首步实际最大已分配/保留量，不冒充整个微调阶段的最大值。后续全程没有OOM；预训练阶段也记录完整峰值，微调后续未额外保存全程峰值。每个预训练检查点的Adam step=50，每个微调检查点step=200，历史更新索引完整无重复；模型参数和权重均有限，预训练分类头未改。

'''
 text+=mt(prestats,['组','预训练末步标准差','验证投影标准差','验证有效秩','预热后步耗时中位秒'])
 text+='''

训练预热后预训练约0.23秒/步，首次初始化及加载时间另计。两域检测微调及验证选模仍按原预算执行，速度不靠减少更新或监督量获得。

## 4. 检测结果

以下AP/AUC/预算召回均为可信木马视图的逐视图宏平均（验证25视图、测试24视图），不是把正常对照混入后的全图池化AP。正常FPR为完整正常对照视图的可信负节点FPR逐视图宏平均（验证40视图、测试40视图），不是新增区域FPR。阈值操作点沿用验证正例分数分位数标定的val_recall80，实际按视图汇总的召回不保证恰好80%；这些口径不能与历史区域FPR表混比。

'''
 text+=mt(detection,['组','验证AP','测试AP','测试AUC','测试Recall1','测试Recall5','测试召回','正常FPR','选中微调步'])
 text+=f'''

R−Z验证AP={delta['R_minus_Z_val_AP']:+.5f}，R−P验证AP={delta['R_minus_P_val_AP']:+.5f}；R−Z测试AP={delta['ap']:+.5f}，R−P测试AP={delta['R_minus_P_test_AP']:+.5f}。R测试正常FPR相对Z下降{abs(delta['control_fpr'])*100:.2f}个百分点，但召回也下降{abs(delta['recall'])*100:.2f}个百分点；Recall@5%提高{delta['r5']*100:.2f}个百分点，Recall@1%下降{abs(delta['r1'])*100:.2f}个百分点。排序与阈值指标方向不同，不能只选有利指标宣布成功。

本轮仅一个种子，不作显著性或稳定增益判断。历史测试已被多轮分析，当前检测结果为固定留出探索性结果，不能重新称完全未见的盲测。

## 5. 检测概率的跨实现诊断

同源/连通锥/观测边权重先在各源内归一，再对源等权；正负根分层只在有该类的源内汇总。all不是节点数量加权平均，不能与分层表按节点数直接拼接。训练2965对中1对因根标签资格不满足而不进入检测概率诊断，仍保留功能训练资格；验证2273对均可诊断。

'''
 text+=mt(pairtable,['组','根类别','源','配对','概率MAE','翻转','两侧均正确','两侧均错'])
 text+='''

R/P的验证负根MAE低于Z，正根却没有同步改善。正根7对/4源的R、P翻转25%，高于Z的8.33%；但两侧均正确率三组都是50%，R/P两侧均错减少。这意味着部分原本两边都漏检的案例变成一边检出，不能简单把Z低翻转解释为更正确，也不能把R更多单侧检出解释为跨实现一致性已改善。

'''
 text+=mt(positive_rows,['组','制造源','正根数','MAE','翻转','两侧均正确','两侧均错'])
 text+='''

验证正根仅1个宿主的4个制造源，源数量小且角色有限。测试仍无可靠锥配对，测试配对MAE/翻转报告NA；不填0，不由验证漂移外推测试稳定性。

## 6. 功能表示是否真正改善

RMS为独立功能投影头的表示距离，不是检测概率。验证使用全部2273已证等价边，先源内按既定权重再源等权；source-normalized RMS为每对距离除以该源所有锥表示的每维标准差尺度，可辅助识别仅把所有表示整体缩小的情况。该归一化分析是描述性机制诊断，不用于选模。

'''
 text+=mt(functable,['组','验证等价RMS','按源尺度归一RMS','训练真实RMS','训练置换RMS','训练不同函数RMS'])
 text+='''

真实等价R比Z原始距离小，但P更小；按源尺度归一后R与P差别仍小，不能认定真实对应有独特的功能收益。R/P不同函数的训练RMS也明显缩小，且低于目标间隔1，说明当前目标并没有充分保住函数间区分。所有源表示标准差都非0，但有效秩很低，方差惩罚尚不足以保证多维信息充分。

这些结果提示：当前预训练可能主要改变表示尺度或产生一般正则化，真实等价结构的增量尚未分离。投影头是否吸收了约束、dropout噪声是否代替了函数区分、以及微调是否覆盖了预训练效果，均是待验证假设，本轮不把它们写成已确定原因。

训练不同函数证书属于训练内诊断，不是验证/测试函数区分泛化证据。没有构造验证不同函数负对，也没有测试CEC配对；验证等价距离小并不证明能区分验证中不同函数。

## 7. 下一步判断

暂不建议直接扩大SAT或机械补齐seed1/2。优先复用本轮检查点和已保存预测，离线检查投影/编码器谱、同函数/不同函数距离及微调前后变化，确认降低等价距离没有同时抹掉函数区分；再判断是否需要修改防退化目标、噪声设置或功能头。若修改，Z/R/P同步，不能只调整R或按测试AP调参数。

本轮证明了数据/证书和三组训练可以按同预算跑通，也记录了未获得独立增益的负结果；没有证明SAT特征输入有效，也没有否定CEC对应证据本身的正确性。

## 8. 可复核文件

训练检查点：`_p0pilot/cec_pretrain_ready_20261105/runs/main/seed42/{Z,R,P}/pretrain/`和`finetune/`，包含binding、resume、COMPLETE、历史及最佳模型。冻结RUN_CONTRACT保留开跑前状态以维持哈希，不回写；实际完成状态看本轮TRAINING_COMPLETE和ANALYSIS_COMPLETE。

本轮目录`_p0pilot/cec_pretrain_seed42_20261105/`：EXECUTION_CONTRACT、POOL_SANITY、FIRST_pretrain_*/FIRST_finetune_*、TRAINING_COMPLETE、ANALYSIS_COMPLETE；detection_metrics.csv、pair_predictions.csv、pair_diagnostic_summary.csv、functional_val_pairs.csv、functional_val_summary.csv、functional_train_blocks.csv、functional_train_summary.csv、scores/*及绑定；gate/finish/analysis日志全部保留。优化器与冻结输入审计见VERIFIED.json。
'''
 target.write_text(text,encoding='utf-8')
 E.write(O/'VERIFIED.json',dict(optimizer_audits=audits,total_updates=750,all_frozen_inputs_unchanged=True,first_gates_pass=True,new_SAT_queries=0,old_results_preserved=True,strict_subset_training_run=False,training_seed42_only=True,delta=delta,excluded_prediction_diagnostic_pair_ids=[p['pair_id'] for p in skipped]))
 brief='''

## 等价锥Z/R/P探索性预训练与检测微调seed42（2026-11-05）

ginvenv_gpu完成main三组各50预训练+200微调共750更新，Adam steps逐检查点核验50/200；0新SAT，旧结果/图/标签/监督/初始化保留，未跑seed1/2或严格151子集。三组首步预训练峰值4.73GiB、微调4.80GiB，损失/梯度有限，初始有效秩约4.66，先保存第1步再续跑无重复；同成员批量池化CPU前向/梯度等价，预热约0.23秒/步。验证AP Z/R/P=.21934/.23480/.24263；测试AP=.29479/.27749/.28005，R未优于Z/P。val_recall80标定下测试召回80.57/79.87/80.09%，完整正常视图FPR6.07/5.31/5.53%，非新增区域FPR。验证功能RMS .2997/.1369/.1277，按源尺度归一1.3898/1.2990/1.2846；R缩距但P也同样，不能认定真实等价独立增益。验证功能投影标准差.344/.153/.140、有效秩1.18/1.87/2.03，非全常量但明显低秩风险；不同函数训练RMS .602/.151/.142，函数区分未充分保持。7正根/4源两侧均正确三组50%，翻转Z8.33%/R25%/P25%，R/P部分从两侧漏检变单侧检出，不能单看漂移宣称成功。测试配对指标NA，检测固定留出结果探索性。Z只关闭正等价项，公共函数负对/方差仍保留；未加18维SAT特征输入。建议先复用检查点离线查谱、噪声和微调覆盖，暂不扩大SAT或机械追加种子。详见[本轮报告](等价锥ZRP探索性预训练及检测微调_seed42_20261105.md)及`_p0pilot/cec_pretrain_seed42_20261105/`。
'''
 for name in ['SAT作用证明.md','SAT工作总结.md']:
  path=D/name;assert '## 等价锥Z/R/P探索性预训练与检测微调seed42' not in path.read_text(encoding='utf-8')
  with path.open('a',encoding='utf-8') as f:f.write(brief)
 with (R/'10.15/99_共用资产/运行登记/运行登记表.csv').open('a',encoding='utf-8',newline='') as f:csv.writer(f).writerow([datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),'等价锥ZRP seed42预训练50和检测微调200','cec_pretrain_seed42 run_controlled/analyze/publish','ginvenv_gpu CUDA bf16;3x250 updates;SAT0','42 only','main10sources;val2273pairs;test detection only','39v3 samegraph/Hsupervision/init;packed mean allarms',str(O.relative_to(R)),'testAP Z.29479 R.27749 P.28005;rank1.18/1.87/2.03','完成探索性三组实验','real equivalence no unique AP gain;low-rank risk;single seed;test pair metricsNA'])
 files={str(p.relative_to(R)):E.sha(p) for p in O.iterdir() if p.is_file() and p.suffix in ['.json','.csv','.py']};files[str(target.relative_to(R))]=E.sha(target)
 for p in (PRE/'runs/main/seed42').rglob('*'):
  if p.is_file() and p.suffix in ['.json','.pt','.npy']:files[str(p.relative_to(R))]=E.sha(p)
 E.write(O/'PUBLISHED.json',dict(report=str(target.relative_to(R)),files=files,seed=42,arms=['Z','R','P'],pretrain_updates=150,finetune_updates=600,new_SAT_queries=0,status='COMPLETED_EXPLORATORY_NO_UNIQUE_REAL_EQUIVALENCE_GAIN'))
 print(json.dumps(dict(report=str(target.relative_to(R)),total_updates=750,delta=delta),ensure_ascii=False),flush=True)
if __name__=='__main__':main()
