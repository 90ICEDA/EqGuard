from pathlib import Path
import csv,json,hashlib,datetime
O=Path(__file__).resolve().parent;R=O.parents[1];N=R/'10.15/00_说明';B=R/'_p0pilot/control_fair200_20261104';V=R/'_p0pilot/control_boundary_v3_20261104'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def pct(x):return f'{100*float(x):.2f}%'
def main():
 assert (O/'COMPARISON_COMPLETE.json').exists() and not (O/'COMPLETE.json').exists();c=read(O/'COMPARISON_COMPLETE.json');g=rows(O/'global_metrics.csv');reg=rows(O/'region_summary.csv');src=rows(O/'source_deltas.csv');old=read(B/'seed42/H/EVALUATED.json');new=read(O/'seed42/H/EVALUATED.json')
 def gm(ver,sp,op='historical_fpr5'):return next(x for x in g if x['version']==ver and x['split']==sp and x['operation']==op)
 def rr(ver,sp,op='historical_fpr5'):return next(x for x in reg if x['version']==ver and x['domain']=='trans' and x['split']==sp and x['operation']==op)
 lines=['# 39维v2/v3单因素强双分支基线：seed42（2026-11-04）','',
 '**seed42下，v3验证和测试节点AP均提高，建议下一轮补齐seed1、2确认稳定性；当前尚未补跑。正常区域在约80%召回工作点只有部分改善，不能据此宣布相似正常逻辑问题已解决。**','',
 '## 复用与单因素协议','',
 '直接复用已有v2/H seed42的200次训练结果，没有重新训练v2。本轮仅新增v3/H seed42一次200更新，使用ginvenv_gpu；未加SAT、未调整区域权重、未清理候选、未改标签。输入仍为原始侧+变换侧完整图。','',
 'dual_mix_post_cat、39维、split29、hidden64、2+2分支及1层融合后GIN、46620参数；Adam lr0.0002、weight_decay0.001、BF16、梯度裁剪1；ASL+1.4 soft-miss平方，逐步随机种子、orig/trans前向和梯度累计方式均复用原训练体。200次更新不变，每5次按可信木马视图平均验证AP选模。',
 '使用与v2/H完全相同的初始化文件（含BN状态）、公共监督基座及旧H名额表；每域每步320个H负例名额，唯一节点与重复曝光次序相同。没有启用新审计后的233对池，仍是旧池对应H采样，61个暂缓候选没有在本轮进行任何过滤。',
 '唯一改动是PO距离列及该列配套训练集归一化。其余38维、图边、边角色、标签、可信掩码和坐标字节一致。原始GPU加载代码与损失实现保持同一哈希，仅进程内指定独立v3合同及归一化；未改旧加载脚本文件。','',
 '已有seed42首版训练脚本和本轮复用训练体前缀一致；历史末尾异常日志处理的修正不涉及训练循环。相同随机种子与初始化不等于承诺CUDA聚合逐位确定，因此本轮仍需多种子确认。','',
 '## 主结果','',
 '|指标|v2/H seed42|v3/H seed42|变化|', '|---|---:|---:|---:|']
 metrics=[('验证节点AP','val','ap'),('测试节点AP','test','ap'),('验证节点AUC','val','auc'),('测试节点AUC','test','auc'),('测试R@1%','test','r1'),('测试R@5%','test','r5')]
 for name,sp,key in metrics:
  a,b=float(gm('v2',sp)[key]),float(gm('v3',sp)[key]);lines.append(f'|{name}|{a:.4f}|{b:.4f}|{b-a:+.4f}|')
 lines += ['',
 f"两版最佳验证检查点分别为第{c['selected_v2']['epoch']}、{c['selected_v3']['epoch']}次更新；两版都完整训练到200次，选模规则相同。测试AP绝对提升{c['v3_test_AP']-c['v2_test_AP']:.4f}，相对约{100*(c['v3_test_AP']/c['v2_test_AP']-1):.2f}%。AP为沿用历史协议的木马视图逐视图AP平均，不是拼接图pooled AP。",'',
 '## 工作点与正常区域','',
 '|划分/操作点|版本|实际木马宏召回|全部正常视图FPR|新增正常区域FPR（等源）|配对集合联合成功|',
 '|---|---|---:|---:|---:|---:|']
 for sp in ['val','test']:
  for op in ['historical_fpr5','val_recall80','val_recall90']:
   for ver in ['v2','v3']:
    x,y=gm(ver,sp,op),rr(ver,sp,op);lines.append(f"|{sp}/{op}|{ver}|{pct(x['recall'])}|{pct(x['control_fpr'])}|{pct(y['source_mean_node_fpr'])}|{pct(y['pair_joint_success'])}|")
 lines += ['',
 'historical_fpr5阈值分别为v2 0.82446、v3 0.59808，都仅由对应验证可信负例的95%分位数确定。在这个工作点，测试召回54.49%→80.89%，正常区域FPR26.31%→61.18%，整区域联合成功40%→0；召回跨度太大，不能把这两行直接解释为同等检出能力下正常识别退化或改善。','',
 '**更接近公平工作点的是验证80% pooled召回校准：测试实际宏召回80.70%→80.89%，正常区域FPR64.98%→60.49%，全部正常视图FPR12.90%→4.98%。** 验证同操作点的实际宏召回78.39%→78.66%，新增正常区域FPR77.24%→61.51%，亦有改善。阈值均未使用测试选择。','',
 '不过测试新增正常区域仍有约60%节点误报，两版6/6源对象仍报警，配对集合联合成功均0。v3的正常区域最高风险平均排名分位从约2.40%变为0.91%（越小越靠前），说明相似正常区域仍是突出难例。该排名与阈值无关，不能用整体正常视图FPR下降掩盖局部高风险。','',
 '90%校准下，测试实际宏召回91.70%→87.40%，区域FPR82.75%→77.68%；因召回差约4.30个百分点，不能将FPR差直接称为等测试召回收益。','',
 '## 测试逐源对象：80%验证召回校准','',
 '|源对象|v2区域FPR|v3区域FPR|变化/百分点|', '|---|---:|---:|---:|']
 for x in src:
  if (x['domain'],x['split'],x['operation'])==('trans','test','val_recall80'):lines.append(f"|{x['source']}|{pct(x['v2_fpr'])}|{pct(x['v3_fpr'])}|{100*float(x['delta_fpr']):+.2f}|")
 lines += ['',
 '4个源对象改善、1个不变、1个退化；ctlmatchc误报增加约20.98个百分点。源对象共享同一测试宿主，不是6个独立宿主；本测试已在此前工作中查看，结果为探索性。逐源与实现记录均保留，不只报告总体均值。','',
 '## 是否补齐seed1、2','',
 '**建议补齐，但本轮只完成seed42，没有自动追加。** 理由首先来自验证AP由0.1531增至0.2225，以及相近验证召回下正常区域FPR下降；这些改善幅度值得检验随机种子稳定性。测试AP同向增加是补充描述，不能用已查看测试选择下一轮阈值或权重。','',
 '下一轮继续保持本轮v3/H、200次、旧H名额表及对应seed1/2原初始化，直接复用已有v2/H seed1/2结果，最多新增两次v3训练。若多种子提升稳定，再冻结v3为后续版本；若分歧大，分析种子/选模波动，不能仅保留本次较好的seed42。','',
 '在版本稳定性确认前，不加入新233池或分角色加权。后续研究正常监督时，两组应共同使用同一v3和同一新资格池，先等权H/C，再检验固定总负例权重的分角色分配。当前AP提升只支持PO边界修正的单种子价值，不能归因于SAT、新标签、候选清理或区域权重。','',
 '## 可靠性和证据入口','',
 '- EXPERIMENT_CONTRACT.json：旧结果绑定、初始化、单因素变化、软件环境及六输入一致性检查。',
 '- seed42/H/config.json、binding.json、history.json、SELECTED.json：200步、初始化/源文件哈希和验证选模。',
 '- seed42/H/：新权重及orig_train、trans_train、trans_val、trans_test四组预测；v2预测只读复用。',
 '- global_metrics.csv、region_summary.csv、per_source.csv、role_pairs_per_source.csv、source_deltas.csv：三个预先定义操作点、完整源对象和集合角色结果。',
 '- COMPARISON_COMPLETE.json、TRAINING_COMPLETE.json、COMPLETE.json：新训练仅1次/200更新、0 SAT、未启动seed1/2及完整哈希记录。','']
 report='\n'.join(lines);target=N/'39维v2_v3单因素基线_seed42_20261104.md';target.write_text(report,encoding='utf-8');(O/'单因素基线报告.md').write_text(report,encoding='utf-8')
 brief=f'''\n\n## 39维v2/v3单因素基线seed42完成（2026-11-04）\n\nginvenv_gpu新增v3/H seed42一次200更新，复用已有v2/H；强dual_mix_post_cat、图/监督/损失/初始化/旧H采样表及每步320槽均一致，不加SAT、不改区域权重、不启用新233池。验证AP0.1531→0.2225，测试AP0.2221→0.2696；最佳验证选模150→195步但两版都200更新。验证80%召回校准下测试实际宏召回80.70%→80.89%，正常区域FPR64.98%→60.49%，全部正常视图FPR12.90%→4.98%；相似正常区域仍高误报、集合联合成功两版均0，ctlmatchc局部退化。历史操作点召回54.49%→80.89%，对应区域FPR26.31%→61.18%，不能当作同等召回比较。建议下一轮仅补v3/H seed1、2并复用既有v2/H，先确认版本稳定性，再进入新资格池/权重对照。本轮未启动seed1/2，旧结果均保留。详见[本轮报告]({target.name})及`_p0pilot/version_baseline_seed42_20261104/`。\n'''
 for name in ['SAT作用证明.md','SAT工作总结.md','正常对照贡献量化与公平实验方案_20261104.md']:
  with (N/name).open('a',encoding='utf-8') as f:f.write(brief)
 with (R/'10.15/99_共用资产/运行登记/运行登记表.csv').open('a',encoding='utf-8',newline='') as f:csv.writer(f).writerow([datetime.datetime.now().astimezone().isoformat(),'39v2-v3单因素H基线seed42','version_baseline_seed42 run_seed42/compare/publish.py','ginvenv_gpu;bf16;200;old H slots;no SAT','42','frozen orig/trans splits','v2 reused;v3 only POdistance+norm','_p0pilot/version_baseline_seed42_20261104','valAP .1531->.2225;testAP .2221->.2696','完成','seed1/2 not started;single seed;test exploratory;region FPR remains high'])
 # Frozen originals, checkpoint and prediction evidence must still match after writing notes.
 for p,h in read(B/'manifest.json')['files'].items():assert sha(B/p)==sha(O/p)==h
 for ver,run in [('v2',B/'seed42/H'),('v3',O/'seed42/H')]:
  ev=read(run/'EVALUATED.json');assert ev['checkpoint_sha']==sha(run/'best.pt')
  for name,h in ev['prediction_sha'].items():assert sha(run/(name+'_scores.npy'))==h
 artifacts=[p for p in O.iterdir() if p.suffix in ['.json','.csv','.py','.md']]+[target]
 (O/'COMPLETE.json').write_text(json.dumps(dict(time=datetime.datetime.now().astimezone().isoformat(),new_training_runs=1,new_updates=200,v2_reused=True,SAT=0,region_weight_changed=False,old_H_sampling_retained=True,seed1_2_started=False,report=str(target),artifacts={str(p.relative_to(R)):sha(p) for p in artifacts}),ensure_ascii=False,indent=2),encoding='utf-8');print(target)
if __name__=='__main__':main()
