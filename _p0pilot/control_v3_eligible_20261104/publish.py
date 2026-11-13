from pathlib import Path
import json,csv,hashlib,datetime
import numpy as np
O=Path(__file__).resolve().parent;R=O.parents[1];N=R/'10.15/00_说明';B=R/'_p0pilot/control_fair200_20261104';V=R/'_p0pilot/control_boundary_v3_20261104'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def pct(x):return f'{100*float(x):.2f}%'
def main():
 assert not (O/'COMPLETE.json').exists();assert read(O/'FAIRNESS_VERIFIED.json')['passed'];assert read(O/'TRAINING_COMPLETE.json')['new_runs']==6;assert (O/'analysis.json').exists();m=read(O/'manifest.json');assessment=read(O/'ASSESSMENT.json');a=rows(O/'aggregate.csv');pair=rows(O/'paired_seed_metrics.csv');src=rows(O/'source_average_deltas.csv');role=rows(O/'roleclass_summary.csv')
 get=lambda sp,op,arm:next(x for x in a if (x['split'],x['operation'],x['arm'])==(sp,op,arm))
 h=get('test','val_recall80','H');c=get('test','val_recall80','C');vh=get('val','val_recall80','H');vc=get('val','val_recall80','C')
 lines=['# 39维v3合格候选池等预算H/C分角色监督对照（2026-11-04）','',
 '## 结论','',
 '**合格池内定向正常监督获得了局部误报收益，总体木马召回接近保持，但不是完全无损。** 验证80%召回标定后的测试正常区域FPR，H/C为64.89%/60.56%，三个种子均下降；测试木马宏召回80.12%/79.72%，平均下降0.39个百分点。符合分析前记录的1个百分点工程容忍范围，未出现超过2个百分点的单种子下降；这不是统计非劣效证明。','',
 '触发角色召回仍下降约1.94个百分点、载荷约1.11个百分点；完整配对对象的联合成功率两组均0，源对象仍报警。因此可以保留C作为后续候选配置，不能称局部误报已经解决，也不支持直接整体放大正常区域权重。','',
 '## 实验合同与公平性','',
 'ginvenv_gpu新增六次训练：seed42、1、2各H/C两组，每次200更新，共1200更新。全部使用同一独立39维v3及其训练集归一化、同一图/标签/可信掩码和源坐标；不加SAT，不改区域权重。旧v2/v3结果、成功权重及预测完整保留。','',
 '改进双分支dual_mix_post_cat，split29、hidden64、2+2分支及post1、46620参数；Adam lr0.0002、weight_decay0.001、BF16、clip1、ASL+1.4 soft-miss平方。逐步种子、orig/trans前向和反传累积流程不变，每5次按可信木马视图平均验证AP选模。分角色指源对象→实现→制造角色→后代的取样层次，没有把制造名称或角色编号作为输入特征，也没有新增独立角色损失。','',
 '|侧|源对象/视图|每组唯一匹配节点|公共正例/步|公共负例/步|额外负例名额/步|每模型额外曝光/侧|',
 '|---|---|---:|---:|---:|---:|---:|']
 for dm in ['orig','trans']:
  x=m['counts'][dm];lines.append(f"|{dm}|{x['sources']}/{x['views']}|{x['C_unique']}|{x['base_positive']}|{x['base_negative']}|320|64000|")
 lines += ['',
 '原始侧116对、变换侧233对均来自已固定的结构/局部资格池。233对只具有结构边界支持，没有新增SAT功能证明。对应61对C/H同时不进入额外监督；公共基座直接保留旧基座，未将61对或未匹配候选重新加入公共监督。原始侧采样表完全复用，变换侧在233对中按同一源/视图/角色规则重新生成两组共享配对曝光表。',
 '每源每步16个名额，每域共320；允许重复，每个C节点与其H配对节点的重复次数逐步一致、所有候选均被曝光。两组全图前向/BN范围、监督条目数、正例曝光、域权重和对应初始化文件一致。ASL与soft-miss沿用原实现，每条监督等权；角色间并非新增独立等权平均损失。',
 '这比较的是已有正常监督中负例预算的内容分配，不是首次加入正常图。共同基座中仍有其他正常监督。变换侧替换名额占监督条目约0.076%，结论限定于当前等权预算强度。','',
 '## 判断口径','',
 'EVALUATION_PLAN.json在汇总分析前记录：主要使用验证可信正例80% pooled召回标定阈值，随后固定用于测试；历史验证负例95%分位阈值及90%召回标定作为辅助。报告实际木马视图宏召回，不能用“同为80%标定”冒充实际测试召回严格相同。',
 '召回保持的工程判读为均值下降不超过1个百分点，并标记单种子超过2个百分点的下降；这不是用户指定的统计检验或正式非劣效界限。完整源对象、原有可信正标和评测范围保持，不删除死支路正标或难正常区域，也不按测试正例位置选择训练候选或权重。','',
 '## 主操作点：逐种子测试结果','',
 '|seed|H区域FPR|C区域FPR|FPR差/百分点|H木马召回|C木马召回|召回差/百分点|H AP|C AP|',
 '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
 for seed in [42,1,2]:
  x=next(x for x in pair if int(x['seed'])==seed and x['split']=='test' and x['operation']=='val_recall80');lines.append(f"|{seed}|{pct(x['H_source_mean_node_fpr'])}|{pct(x['C_source_mean_node_fpr'])}|{100*float(x['delta_source_mean_node_fpr']):+.2f}|{pct(x['H_recall'])}|{pct(x['C_recall'])}|{100*float(x['delta_recall']):+.2f}|{float(x['H_ap']):.4f}|{float(x['C_ap']):.4f}|")
 lines += ['',
 f"区域FPR配对差均值{100*assessment['mean_FPR_delta']:+.2f}个百分点，种子差SD {100*assessment['FPR_delta_sd']:.2f}；召回差均值{100*assessment['mean_recall_delta']:+.2f}个百分点，SD {100*assessment['recall_delta_sd']:.2f}。seed42/1召回略降，seed2提高，不是各个种子都无损。",'',
 '## 三种子汇总','',
 '|指标|H|C|', '|---|---:|---:|',
 f"|验证AP均值±SD|{float(vh['ap_mean']):.4f}±{float(vh['ap_sd']):.4f}|{float(vc['ap_mean']):.4f}±{float(vc['ap_sd']):.4f}|",
 f"|测试AP均值±SD|{float(h['ap_mean']):.4f}±{float(h['ap_sd']):.4f}|{float(c['ap_mean']):.4f}±{float(c['ap_sd']):.4f}|",
 f"|验证实际宏召回（80%标定）|{pct(vh['recall_mean'])}|{pct(vc['recall_mean'])}|",
 f"|验证新增正常区域FPR|{pct(vh['source_mean_node_fpr_mean'])}|{pct(vc['source_mean_node_fpr_mean'])}|",
 f"|测试实际宏召回（80%标定）|{pct(h['recall_mean'])}|{pct(c['recall_mean'])}|",
 f"|测试新增正常区域FPR|{pct(h['source_mean_node_fpr_mean'])}|{pct(c['source_mean_node_fpr_mean'])}|",
 f"|测试全部正常视图FPR|{pct(h['control_fpr_mean'])}|{pct(c['control_fpr_mean'])}|",
 f"|测试配对集合正确排序|{pct(h['pair_correct_order_mean'])}|{pct(c['pair_correct_order_mean'])}|",
 f"|测试完整配对集合联合成功|{pct(h['pair_joint_success_mean'])}|{pct(c['pair_joint_success_mean'])}|",'',
 'AP为历史协议可信木马视图逐视图均值，不是拼接图pooled AP。测试AP配对差+0.0083、SD约0.0175，2/3种子提高；不能把AP均值增加称为稳定AP增益。三种子是训练随机性重复，不是三套独立数据。',
 '当前H组是在233池重新训练得到，不能用上一轮旧294池H的AP 0.2982直接代替本轮H的0.2975构造公平结果。因果比较仅使用本轮相同池的H/C。','',
 '## 测试源对象误报（80%标定，先源内视图再跨种子）','',
 '|源对象|H区域FPR|C区域FPR|差/百分点|改善种子|', '|---|---:|---:|---:|---:|']
 for x in src:
  if x['split']=='test' and x['operation']=='val_recall80':lines.append(f"|{x['source']}|{pct(x['H_fpr'])}|{pct(x['C_fpr'])}|{100*float(x['delta_fpr']):+.2f}|{x['seeds_improved']}/3|")
 lines += ['',
 '6个源对象中5个平均下降、1个不变；ctlmatchc/f在三个种子均下降，ctlxor只在一个种子下降。所有对象在H/C两个组的三个种子中都仍有区域报警，因此平均节点误报下降并未转化为完整对象消除误报。ctlxor无预设木马制造伙伴，不虚构配对角色。','',
 '## 制造角色层面的代价与收益','',
 '|测试角色类|正常角色FPR H→C|木马角色召回H→C|单角色集合联合成功H→C|正常/木马平均分变化|',
 '|---|---:|---:|---:|---:|']
 for x in role:
  if (x['domain'],x['split'],x['operation'])!=('trans','test','val_recall80'):continue
  lines.append(f"|{x['role_class']}|{pct(x['normal_fpr_H'])}→{pct(x['normal_fpr_C'])}|{pct(x['trojan_recall_H'])}→{pct(x['trojan_recall_C'])}|{pct(x['joint_H'])}→{pct(x['joint_C'])}|{float(x['normal_delta']):+.4f}/{float(x['trojan_delta']):+.4f}|")
 lines += ['',
 '载荷正常角色FPR下降约8.17个百分点、单角色联合成功上升约6.11个百分点，但木马载荷召回也下降约1.11个百分点。触发正常角色FPR仅下降约1.67个百分点，木马触发召回下降约1.94个百分点，联合成功反降约2.78个百分点；这部分不能写成无损收益。选择角色在本次定向训练池中仍缺乏覆盖，正常FPR和木马召回未改善。',
 '角色表先源角色内部聚合实现，再源内类别平均、跨源及种子平均；与完整正常区域唯一物理节点口径不同，不能混用分母。角色后代只是制造来源集合，不代表每个中间门已获得功能作用证明。完整对象联合成功0与部分单角色成功并不矛盾：其它正常角色仍可造成整对象报警。','',
 '## 辅助操作点','',
 '|操作点/测试|组|实际宏召回|新增正常区域FPR|全部正常视图FPR|', '|---|---|---:|---:|---:|']
 for op in ['historical_fpr5','val_recall90']:
  for arm in ['H','C']:
   x=get('test',op,arm);lines.append(f"|{op}|{arm}|{pct(x['recall_mean'])}|{pct(x['source_mean_node_fpr_mean'])}|{pct(x['control_fpr_mean'])}|")
 lines += ['',
 '辅助工作点同样显示平均区域误报下降、宏召回接近，但主结论仍使用预先记录的80%标定，不按哪个阈值最有利来改口径。90%标定下仍约75%区域FPR，说明高召回分离不足依然严重。','',
 '## 下一步判断','',
 assessment['verdict'],
 '可以将本轮C作为后续正常区域监督的候选配置，并把“固定等预算下，制造可追溯正常区域比匹配宿主背景更有助于降低局部误报”写成有限、探索性结论。不能写成正常对照首次进入训练、所有角色均无损、统计显著或真实SAT功能特征已证明有效。',
 '目前不建议直接把整个区域权重乘2/4。下一步优先使用已有逐源/逐角色证据确定触发与载荷召回损失集中在哪些角色，保护正例和域/负例总权重后，再考虑载荷区域的小幅受约束权重试验；不要继续压低没有明确正常误报收益的触发角色。保留完整制造来源主指标，anchor_only仍单列，不通过改标签或删除测试正例美化结果。',
 '本轮不追加新训练或SAT，不扩候选、不改变最佳模型归档。测试源对象共享一个宿主且已在前轮查看，后续超参数依据训练/验证制定；独立确认需要新冻结对象或宿主，不能用三个种子代替。','',
 '## 复核入口','',
 '- manifest.json、train_pairs.csv、held_pairs.csv：116/233对与61对暂缓关系；EXPERIMENT_CONTRACT.json记录实际运行引擎和v3输入绑定。',
 '- FAIRNESS_VERIFIED.json：独立核对公共监督、正例、逐节点配对曝光、同门型/视图与匹配距离。',
 '- EVALUATION_PLAN.json：分析前的操作点和工程判读；适配器只改完成证据文件名，不改指标。',
 '- seed*/H、C：每组200步历史、选模、权重及四域预测，成功结果可复用。',
 '- paired_seed_metrics.csv、aggregate.csv、source_average_deltas.csv：种子/源对象差值和全部操作点。',
 '- role_view_seed.csv、source_role_average.csv、roleclass_summary.csv：制造角色与正负共同降分证据。',
 '- ASSESSMENT.json、TRAINING_COMPLETE.json、ANALYSIS_COMPLETE.json、COMPLETE.json：工程判读、1200更新、0SAT与哈希。','']
 report='\n'.join(lines);target=N/'39维v3合格池等预算HC分角色监督_三种子_20261104.md';target.write_text(report,encoding='utf-8');(O/'合格池等预算HC实验报告.md').write_text(report,encoding='utf-8')
 brief=f'''\n\n## 39维v3合格池等预算H/C分角色监督完成（2026-11-04）\n\nginvenv_gpu完成seed42/1/2各H/C六次200更新，共1200步；同39v3/图/标签/损失/各自初始化，orig116/trans233对、每域每步320等权名额、公共监督不变，61对在两组额外监督中对称暂缓；0SAT，旧结果保留。主操作点为验证80%召回标定：测试区域FPR H {pct(h['source_mean_node_fpr_mean'])}→C {pct(c['source_mean_node_fpr_mean'])}，3/3种子下降，均值−4.33个百分点；木马宏召回{pct(h['recall_mean'])}→{pct(c['recall_mean'])}，下降0.39个百分点，在分析前记录的1个百分点工程容忍内，非统计非劣效或完全无损。测试AP {float(h['ap_mean']):.4f}±{float(h['ap_sd']):.4f}→{float(c['ap_mean']):.4f}±{float(c['ap_sd']):.4f}，配对差+0.0083±0.0175，不称稳定AP增益。6测试源对象5下降1不变但均仍报警，完整配对联合成功两组0；载荷正常FPR改善但木马载荷召回−1.11个百分点、触发召回−1.94个百分点。支持有限局部正常监督价值，不直接整体加权；后续先保护触发/载荷正例，再考虑受约束权重。详见[本轮报告]({target.name})及`_p0pilot/control_v3_eligible_20261104/`。\n'''
 for name in ['SAT作用证明.md','SAT工作总结.md','正常对照贡献量化与公平实验方案_20261104.md']:
  with (N/name).open('a',encoding='utf-8') as f:f.write(brief)
 with (R/'10.15/99_共用资产/运行登记/运行登记表.csv').open('a',encoding='utf-8',newline='') as f:csv.writer(f).writerow([datetime.datetime.now().astimezone().isoformat(),'39v3合格池等预算H/C分角色监督三种子','control_v3_eligible prepare/run/verify/analyze/assess/publish.py','ginvenv_gpu;bf16;200;equal weight;no SAT','42/1/2','frozen splits;orig116/trans233','v3 POdriver;original labels;paired exposure','_p0pilot/control_v3_eligible_20261104','regionFPR64.89->60.56;recall80.12->79.72;AP.2975->.3058','完成','partial local benefit;not lossless;full joint success0;test exploratory'])
 # Verify all original and new evidence after publication; no original metric file is overwritten.
 for name,hsh in m['files'].items():assert sha(O/name)==hsh,name
 for seed in [42,1,2]:
  init=[]
  for arm in ['H','C']:
   run=O/f'seed{seed}'/arm;e=read(run/'EVALUATED.json');hist=read(run/'history.json');assert [x['update'] for x in hist]==list(range(1,201));assert sha(run/'best.pt')==e['checkpoint_sha'];init.append(e['init_sha'])
   for name,hsh in e['prediction_sha'].items():assert sha(run/(name+'_scores.npy'))==hsh
  assert init[0]==init[1]==sha(B/f'init_s{seed}.pt')
 for p,hsh in read(V/'input_contract.json')['files'].items():assert sha(R/p)==hsh,p
 for folder in ['version_baseline_seed42_20261104','version_baseline_multiseed_20261104']:
  for p,hsh in read(R/'_p0pilot'/folder/'COMPLETE.json')['artifacts'].items():assert sha(R/p)==hsh,p
 artifacts=[p for p in O.iterdir() if p.suffix in ['.json','.csv','.py','.md']]+[target]
 (O/'COMPLETE.json').write_text(json.dumps(dict(time=datetime.datetime.now().astimezone().isoformat(),new_runs=6,updates=1200,SAT=0,weights_changed=False,labels_modified=False,old_results_preserved=True,pool=dict(orig=116,trans=233),assessment=assessment,report=str(target),artifacts={str(p.relative_to(R)):sha(p) for p in artifacts}),ensure_ascii=False,indent=2),encoding='utf-8');print(target)
if __name__=='__main__':main()
