from pathlib import Path
import csv,json,hashlib,datetime
import numpy as np
O=Path(__file__).resolve().parent;R=O.parents[1];N=R/'10.15/00_说明';B=R/'_p0pilot/control_fair200_20261104';S=R/'_p0pilot/version_baseline_seed42_20261104'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def pct(x):return f'{100*float(x):.2f}%'
def main():
 assert not (O/'COMPLETE.json').exists();c=read(O/'COMPARISON_COMPLETE.json');a=rows(O/'aggregate.csv');d=rows(O/'paired_global_deltas.csv');so=rows(O/'source_averages.csv');g=rows(O/'per_seed_metrics.csv')
 get=lambda sp,op,ver:next(x for x in a if (x['split'],x['operation'],x['version'])==(sp,op,ver))
 test2=get('test','historical_fpr5','v2');test3=get('test','historical_fpr5','v3');v2=get('val','historical_fpr5','v2');v3=get('val','historical_fpr5','v3');rec2=get('test','val_recall80','v2');rec3=get('test','val_recall80','v3')
 stability=c['stability'];lines=['# 39维v2/v3强双分支H基线：三种子配对结果（2026-11-04）','',
 '## 本轮执行和解释边界','',
 'ginvenv_gpu新增v3/H seed1、2各200次更新，共2次/400更新；复用先前v3/H seed42及全部已有v2/H seed42、1、2结果。没有追加SAT，没有调整区域权重，没有启用新233候选池。所有旧模型、预测、数据和seed42完成记录保持原样。','',
 '沿用dual_mix_post_cat/39维/split29/hidden64/2+2分支及post1/46620参数，Adam lr0.0002、weight_decay0.001、BF16、ASL+1.4 soft-miss平方、梯度裁剪1。每个种子的v2/v3使用各自相同初始化、原始/变换图、标签、监督基座、旧H采样表与200次预算，逐步随机种子相同；每5次按旧可信木马视图平均验证AP选模。','',
 '训练引擎与seed42 v3完全相同，仅新增种子和对应原初始化。特征版本差别仍只有PO距离列及配套训练集归一化；验证/测试不参与拟合。相同seed不宣称CUDA逐位确定，多种子用于检查这次版本收益的一致性。','',
 '## AP逐种子与稳定性','',
 '|seed|v2验证AP|v3验证AP|验证差值|v2测试AP|v3测试AP|测试差值|',
 '|---|---:|---:|---:|---:|---:|---:|']
 for seed in [42,1,2]:
  va=next(x for x in d if int(x['seed'])==seed and x['split']=='val' and x['operation']=='historical_fpr5');te=next(x for x in d if int(x['seed'])==seed and x['split']=='test' and x['operation']=='historical_fpr5');lines.append(f"|{seed}|{float(va['v2_ap']):.4f}|{float(va['v3_ap']):.4f}|{float(va['delta_ap']):+.4f}|{float(te['v2_ap']):.4f}|{float(te['v3_ap']):.4f}|{float(te['delta_ap']):+.4f}|")
 lines += ['', '|划分|v2 AP均值±种子SD|v3 AP均值±种子SD|配对差均值±SD|改善种子|','|---|---:|---:|---:|---:|']
 for sp,x,y in [('val',v2,v3),('test',test2,test3)]:
  z=stability[sp];lines.append(f"|{sp}|{float(x['ap_mean']):.4f}±{float(x['ap_sd']):.4f}|{float(y['ap_mean']):.4f}±{float(y['ap_sd']):.4f}|{z['AP_delta_mean']:+.4f}±{z['AP_delta_sd']:.4f}|{z['AP_improved_seeds']}/3|")
 lines += ['',
 'SD使用三个种子的样本标准差（ddof=1），配对差SD与两组各自SD分开报告。三个种子是同一划分下的训练随机性重复，不是三个独立数据集/宿主，不给节点级伪显著性。AP沿用可信木马视图逐视图均值，并非拼接全图pooled AP。','',
 '本轮“AP提升稳定”指逐种子配对增益方向一致，并非绝对表现波动更小：v3测试AP的种子SD约0.0263，大于v2约0.0194；验证SD也增加。不能写成v3降低了训练随机性。','',
 '## 三种操作点下的误报与召回','',
 '|划分/操作点|版本|实际木马宏召回|全部正常视图FPR|新增正常区域FPR（等源）|配对集合联合成功|',
 '|---|---|---:|---:|---:|---:|']
 for sp in ['val','test']:
  for op in ['historical_fpr5','val_recall80','val_recall90']:
   for ver in ['v2','v3']:
    x=get(sp,op,ver);lines.append(f"|{sp}/{op}|{ver}|{pct(x['recall_mean'])}|{pct(x['control_fpr_mean'])}|{pct(x['source_mean_node_fpr_mean'])}|{pct(x['pair_joint_success_mean'])}|")
 lines += ['',
 f"验证80% pooled正例召回标定后，测试实际木马视图宏召回v2/v3为{pct(rec2['recall_mean'])}/{pct(rec3['recall_mean'])}；新增正常区域FPR为{pct(rec2['source_mean_node_fpr_mean'])}/{pct(rec3['source_mean_node_fpr_mean'])}，全部正常视图FPR为{pct(rec2['control_fpr_mean'])}/{pct(rec3['control_fpr_mean'])}。两组实际召回并不由定义保证相同，须结合本表的实际值判断误报收益。",'',
 '历史fpr5阈值来自各自验证可信负例95%分位数，版本切换后校准和召回可能明显变化；不能直接将该操作点的局部FPR变化解释为等检出能力下的收益。80/90阈值仅使用验证正例，未在测试选阈值。','',
 '新增正常区域仍是单独难点；整图正常误报改善不能替代局部区域、同源角色联合成功和木马召回的检查。角色集合指标覆盖val/test各5源对象，完整正常区域各6源对象；集合最大分排序也不能证明每个中间门功能作用相同。','',
 '### 局部误报收益没有达到3/3种子稳定','',
 '|seed|v2实际测试召回|v3实际测试召回|v2区域FPR|v3区域FPR|', '|---|---:|---:|---:|---:|']
 for seed in [42,1,2]:
  x=next(x for x in d if int(x['seed'])==seed and x['split']=='test' and x['operation']=='val_recall80');lines.append(f"|{seed}|{pct(x['v2_recall'])}|{pct(x['v3_recall'])}|{pct(x['v2_source_mean_node_fpr'])}|{pct(x['v3_source_mean_node_fpr'])}|")
 lines += ['',
 'seed42和seed1的实际召回接近，区域误报均下降约4.5个百分点；seed2实际召回下降约2.68个百分点，区域误报却从70.21%略升至70.52%。因此只能支持平均局部误报小幅改善，不能宣称三个种子均改善。约80%操作点的配对集合联合成功两版均0，局部区分尚不充分。','',
 '## 测试源对象：验证80%召回标定，跨种子平均','',
 '|源对象|v2区域FPR|v3区域FPR|变化/百分点|改善种子数|', '|---|---:|---:|---:|---:|']
 for x in so:
  if x['split']=='test' and x['operation']=='val_recall80':lines.append(f"|{x['source']}|{pct(x['v2_fpr'])}|{pct(x['v3_fpr'])}|{100*float(x['delta_fpr']):+.2f}|{x['seeds_improved']}/3|")
 lines += ['',
 '先在每个源对象内汇总实现视图，再跨种子平均；详细逐种子、逐源和角色集合表均保留。当前测试源对象共享一个宿主，且本测试已被前轮检查，故这是探索性版本对照，不能扩大为新增独立宿主验证。','',
 '## 下一步是否进入分角色监督对照','']
 stable=stability['val']['AP_improved_seeds']==3 and stability['test']['AP_improved_seeds']==3
 if stable:
  decision='三种子下验证与测试AP均同向提高，支持在当前固定协议中将v3作为下一阶段特征基线，进入新资格池的分角色正常监督等预算H/C对照准备。该稳定性限定于本次三个种子和现有留出划分，不宣称所有宿主或功能场景均稳定。'
 else:
  decision='部分种子收益方向不一致，当前不宜直接将v3与新池/权重一起推进；应先结合验证选模和逐源分解说明版本波动。保留全部种子结果，不只挑选较好者。'
 lines += [decision,'',
 '后续先做同一v3、同一合格池的等权H/C，模型与200次预算保持，采用orig116/trans233对结构支持候选，61个死锚点关系在两组额外监督资格中对称暂缓。先冻结新池的公共监督、等额槽位、源/实现/角色采样与正例曝光，不能用旧294池H基线直接对比新233池C后把差异归因于正常内容。',
 '先检验同源角色召回、相似正常区域FPR和联合成功，再考虑固定总负例权重的小幅角色分配。源标签仍按制造归属保留；结构支持并不升级为SAT功能证明，局部同输入冲突不得通过加权强行解释成可分。',
 '本轮到此停止，没有启动C组、新资格池训练或权重搜索。所有下一轮参数与候选仅用训练/验证决定，测试不用于挑角色、倍率或最佳配置。','',
 '## 证据入口','',
 '- EXPERIMENT_CONTRACT.json：seed1/2与历史v2初始化、源码、图/监督、特征合同及旧H表绑定。',
 '- seed1/H、seed2/H：新200步历史、验证选模、权重和四域预测；seed42继续只读复用旧目录。',
 '- per_seed_metrics.csv、paired_global_deltas.csv、aggregate.csv：逐种子与配对均值/SD。',
 '- region_summary.csv、source_details.csv、source_averages.csv、role_pairs_per_source.csv：区域/源对象/配对集合分解。',
 '- COMPARISON_COMPLETE.json、TRAINING_COMPLETE.json、COMPLETE.json：两次新增训练/400更新、0SAT、旧结果保留与输入哈希。','']
 report='\n'.join(lines);target=N/'39维v2_v3单因素基线_三种子汇总_20261104.md';target.write_text(report,encoding='utf-8');(O/'三种子版本对照报告.md').write_text(report,encoding='utf-8')
 brief=f'''\n\n## 39维v2/v3单因素H基线三种子补齐（2026-11-04）\n\nginvenv_gpu新增v3/H seed1、2各200次，共400更新；v3 seed42及v2/H三个种子全部复用。模型/图/监督/损失/各自初始化/旧H采样表不变，不加SAT、不改区域权重、不启用新233池。验证AP v2 {float(v2['ap_mean']):.4f}±{float(v2['ap_sd']):.4f}→v3 {float(v3['ap_mean']):.4f}±{float(v3['ap_sd']):.4f}，{stability['val']['AP_improved_seeds']}/3改善；测试AP {float(test2['ap_mean']):.4f}±{float(test2['ap_sd']):.4f}→{float(test3['ap_mean']):.4f}±{float(test3['ap_sd']):.4f}，{stability['test']['AP_improved_seeds']}/3改善，配对差{stability['test']['AP_delta_mean']:+.4f}±{stability['test']['AP_delta_sd']:.4f}。验证80%校准下测试实际宏召回{pct(rec2['recall_mean'])}/{pct(rec3['recall_mean'])}，新增正常区域FPR{pct(rec2['source_mean_node_fpr_mean'])}/{pct(rec3['source_mean_node_fpr_mean'])}。AP配对增益同向不等于种子SD降低；局部误报仅2/3种子改善，seed2召回下降但误报略升，80%工作点两版集合联合成功仍0。{decision} 本轮未启动新池H/C或权重试验，旧结果全部保留。详见[三种子报告]({target.name})与`_p0pilot/version_baseline_multiseed_20261104/`。\n'''
 for name in ['SAT作用证明.md','SAT工作总结.md','正常对照贡献量化与公平实验方案_20261104.md']:
  with (N/name).open('a',encoding='utf-8') as f:f.write(brief)
 with (R/'10.15/99_共用资产/运行登记/运行登记表.csv').open('a',encoding='utf-8',newline='') as f:csv.writer(f).writerow([datetime.datetime.now().astimezone().isoformat(),'39v2/v3 H基线seed1/2补齐及三种子汇总','version_baseline_multiseed run_seeds12/compare/publish.py','ginvenv_gpu;bf16;200;old H;no SAT','1/2 new;42 reused','frozen orig/trans splits','v2 reused;v3 POdriver','_p0pilot/version_baseline_multiseed_20261104',f"testAP {float(test2['ap_mean']):.4f}->{float(test3['ap_mean']):.4f};{stability['test']['AP_improved_seeds']}/3 improved",'完成','no weights/pool change;test exploratory'])
 for p,h in c['prediction_bindings'].items():assert sha(R/p)==h,p
 for p,h in read(B/'manifest.json')['files'].items():assert sha(B/p)==sha(O/p)==h,p
 for p,h in read(S/'COMPLETE.json')['artifacts'].items():assert sha(R/p)==h,p
 artifacts=[p for p in O.iterdir() if p.suffix in ['.json','.csv','.py','.md']]+[target]
 (O/'COMPLETE.json').write_text(json.dumps(dict(time=datetime.datetime.now().astimezone().isoformat(),new_training_runs=2,new_updates=400,total_v3_seeds=[42,1,2],v2_all_reused=True,v3_seed42_reused=True,SAT=0,pool_changed=False,weights_changed=False,stable_AP_three_seeds=stable,decision=decision,report=str(target),artifacts={str(p.relative_to(R)):sha(p) for p in artifacts}),ensure_ascii=False,indent=2),encoding='utf-8');print(decision)
if __name__=='__main__':main()
