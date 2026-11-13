from pathlib import Path
import csv,json,collections,datetime,shutil,hashlib
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent
def read(n):return list(csv.DictReader((O/n).open(encoding='utf-8-sig')))
su=read('summary.csv');ob=read('per_source.csv');pa=read('role_pairs_per_source.csv');rv=read('region_per_view.csv');nr=read('region_nodes.csv')
overview=[]
for domain,split in [('orig','train'),('trans','train'),('trans','val'),('trans','test')]:
 for src in sorted({x['source_view'] for x in ob if (x['domain'],x['split'])==(domain,split)}):
  a=[x for x in ob if (x['domain'],x['split'],x['source_view'])==(domain,split,src)]
  d=dict(domain=domain,split=split,source_view=src)
  for seed in [1,2]:
   x=next(x for x in a if int(x['seed'])==seed)
   for key in ['views','region_node_occurrences','alarm_views','any_alarm','view_mean_node_fpr','view_mean_best_rank_fraction','top1_views','view_mean_background_fpr']:d[f'seed{seed}_{key}']=x[key]
  overview.append(d)
with (O/'source_overview.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(overview[0]));w.writeheader();w.writerows(overview)
text='''# 改进双分支200次模型：新增正常区域离线复核

2026-11-04。使用既有seed1/2的dual_mix_post_cat非SAT39维v2、split29、hidden64、两分支各2层、输入mix、concat融合及融合后1层GIN，46620参数。只做eval/inference_mode前向：2权重×orig_train/trans_train/val/test共8份预测；0训练、0反传、0优化器step、0SAT。不调用训练入口main。全部原生产脚本、图、掩码、权重保持不变。

## 复现检查

严格load_state_dict，参数数目及SELECTED路径检查通过；使用历史train_ab.load的原输入、旧可信掩码、归一化及BF16，预测后逐项检查权重与BN运行状态未改变。val/test AP、AUC、R@1/5%、正常FPR复现历史报告，AP容差1e-6，其他指标容差1e-5；差值原样记录在evaluation.json，不能声称全部字节一致。seed1测试AUC差约1.07e-6。原验证负例95%分位阈值也复核通过，未按本轮困难区域或测试重新调阈值。

SELECTED为200次预算内验证最优权重：seed1 epoch180、seed2 epoch200。测试AP约0.2514/0.2513，仅作模型绑定，不能据两种子认定全局最优。输入合同、归一化、loader与权重摘要另存COMPLETE.json和evaluation.json。

## 评价对象与口径

正常区域沿前轮完整且无宿主共享落点候选定位：trans训练23源/50视图450节点、验证6源/12视图130节点、测试6源/12视图142节点。orig训练对这23源的158新增正常实例也作拟合诊断。全部实际物理节点、旧可信正常标签已逐一核查。

排序在所在视图全部物理节点上计算，边界外未知背景只参与检查队列，不认证为正常。对分数并列保留最好/最差名次；前1%/5%使用最差名次也在预算内的保证命中。源对象先对实现等权，再按源等权，不把一源多实现当独立设计。val/test各6源变体分别共用一个宿主，不支持跨多个独立测试宿主的显著性结论。

orig训练的阈值沿用trans验证阈值，只作同模型诊断，不声称原始侧独立校准。训练侧表现是拟合检查，不能证明泛化。

## 汇总

|域/划分|seed|源对象|至少一实现报警的源数|区域节点FPR（源等权）|区域最高风险平均排名比例|有区域进入前1%的源数|
|---|---:|---:|---:|---:|---:|---:|
'''
for x in su:text+=f"|{x['domain']}/{x['split']}|{x['seed']}|{x['sources']}|{x['alarm_sources']}|{float(x['source_mean_node_fpr']):.2%}|{float(x['source_mean_best_rank_fraction']):.2%}|{x['sources_top1']}|\n"
text+='''
测试6个源对象两个种子全部至少有一个实现报警；两种子分别5/6、4/6源对象有区域进入前1%，且6/6都有区域进入前5%。并非仅在低风险尾部越过阈值。全视图正常FPR约1.81%/1.77%不能代表新增困难区域误报很低。

## 按源对象分开报告

每行一个源对象，报警视图数分母为该对象合格实现数量；两个种子分别列出。排名比例是每实现区域最高风险名次占该视图物理节点数的比例，再在源内平均，越低越靠前。具体风险分数与阈值保留在region_per_view.csv，不跨种子混平均分数。

'''
for domain,split in [('trans','val'),('trans','test'),('trans','train'),('orig','train')]:
 text+='\n### '+domain+'/'+split+'\n\n|源对象|实现数|seed1报警视图|seed2报警视图|seed1区域FPR|seed2区域FPR|seed1排名比例|seed2排名比例|\n|---|---:|---:|---:|---:|---:|---:|---:|\n'
 for x in overview:
  if (x['domain'],x['split'])!=(domain,split):continue
  text+=f"|{x['source_view']}|{x['seed1_views']}|{x['seed1_alarm_views']}|{x['seed2_alarm_views']}|{float(x['seed1_view_mean_node_fpr']):.2%}|{float(x['seed2_view_mean_node_fpr']):.2%}|{float(x['seed1_view_mean_best_rank_fraction']):.2%}|{float(x['seed2_view_mean_best_rank_fraction']):.2%}|\n"
text+='''
## 与木马制造角色区分

使用source_node_pairs中明确的同角色同门型源对应，以及实际目标门/旧可信正负标签合格的后代集合。再与完整正常区域主候选相交：trans训练20源/44视图、验证5源/10视图、测试5源/10视图；正常角色节点329/94/105。它与全新增正常区域450/130/142不是同一集合：ctlxor等无明确模板伙伴，末端PD/HJ也不强造角色对。

这里比较的是匹配角色集合，不要求整个木马新增区域都完整；因此测试能覆盖5源，前轮要求整个木马区域完整的评价仅3源。两种口径不同，不得混池报覆盖提升或性能提升。后代门集合不是笛卡尔积一一节点对，也不是SAT功能等价。

区域风险取max；大小不等带来的偏差未完全控制，记录双方节点数，只作探索性角色区分诊断。正确排序给相等分数半分；联合成功要求木马max>=阈值且正常max<阈值，双低另报。逐源先平均实现，再平均源。

|划分|seed|配对源|木马风险高于正常的排序率|木马报警且正常不报警|两侧同时低于阈值|匹配木马角色节点召回|
|---|---:|---:|---:|---:|---:|---:|
'''
for x in su:
 if x['domain']!='trans':continue
 text+=f"|{x['split']}|{x['seed']}|{x['pair_sources']}|{float(x['pair_correct_order']):.2%}|{float(x['pair_joint_success']):.2%}|{float(x['pair_both_low']):.2%}|{float(x['pair_trojan_recall']):.2%}|\n"
text+='\n逐源角色结果（每源含2个实现，训练中有的含更多keep视图）：\n\n|划分|源对象|seed|木马较高排序率|联合成功|匹配木马角色召回|\n|---|---|---:|---:|---:|---:|\n'
for x in pa:
 if x['split']=='train':continue
 text+=f"|{x['split']}|{x['control_source']}|{x['seed']}|{float(x['correct_order']):.2%}|{float(x['joint_success']):.2%}|{float(x['trojan_node_recall']):.2%}|\n"
text+='''
## 是否值得做等预算正常对照训练

值得进行受控、小规模的等预算正常角色监督实验，但现有证据只证明问题存在，不证明训练必有效。

- 强模型仍在全部测试源对象上发生局部误报；排名也靠前，不能因整图FPR较低或AP较高而否认问题。
- 模板角色的排序较好（测试90%—100%），但联合成功只有20%—40%，说明已有分离能力尚未转化为可靠的报警决策。单纯降低所有风险可能同时降低木马召回。
- 训练侧困难正常区域也有误报（trans18—20/23源），而这些节点原本已被旧掩码监督。实验应检验“监督预算分配到困难角色是否有效”，不是再次添加相同负标签或仅扩展全图负例数量。
- 失败可能涉及监督稀释、特征重叠、优化或阈值校准，离线观察不能归因到某一项。可在验证侧做阈值—木马召回权衡诊断作为无训练参照，但本轮未新增阈值搜索，也未按测试选择参数。

## 方案修订

1. 正式比较固定该非SAT改进双分支200次，不换回较弱单分支100次。各组同种子、初始化、前向、归一化、优化器与预算。200次仅2个历史种子，后续成对实验至少统一42/1/2；不把历史不同损失或不同预算结果拼成公平基线。
2. 先冻结完整区域交集中的角色C与可匹配背景角色H。公共监督从旧可信掩码排除C/H并集，再以相同槽位和曝光补回C或H。正例集合、重复次数、负例总量、唯一节点支持及两侧域权重相同，保持原ASL/soft-miss形式，不通过稀释正例或额外放大C权重制造增益。
3. 按源对象→实现→角色采样，原始和变换侧一致；对照节点不是随机取整张正常图背景。不能根据此次测试高分对象筛选训练家族或设预算。训练池仍来自冻结训练划分。
4. 小规模成对可行性优先；区域FPR/告警率下降必须同时保护木马AP、召回及角色联合成功。既有测试已多次查看，后续其结果属探索性验证，独立确认仍需新冻结对象或评测。
5. 本轮只复核强基线，不启动后续训练；SAT保持不运行。原始侧k4历史部分成果尚未确认，当前加载orig SAT补零，不把本分析解释成双侧SAT已完成。
6. A4 equiv不在现有独立验证/测试中，ys_aig映射缺口仍在；不宣称全部正常对照、全部流程或多个测试宿主的泛化均获验证。

## 交付

- source_overview.csv：每个源对象两种子并列；per_source.csv：116条源对象×域/划分×seed。
- region_per_view.csv与region_nodes.csv：正常区域/逐节点风险、阈值、排名及标签，训练与评价分开。
- role_pairs_per_source.csv、role_pairs_per_view.csv：匹配角色区分，含双低/双高、召回与联合成功。
- summary.csv：每种子、域、划分源等权汇总。
- seed1/seed2：独立新增评分数组、原权重摘要、输入绑定、历史指标复现差值及状态未变检查。
- evaluate.py、analyze.py、publish.py：可复现评估分析程序；没有启动优化器或SAT。
'''
(O/'复核报告.md').write_text(text,encoding='utf-8')
p=R/'10.15/00_说明/改进双分支200次_正常区域离线复核_20261104.md';p.write_text(text,encoding='utf-8')
plan=R/'10.15/00_说明/正常对照贡献量化与公平实验方案_20261104.md';backup=O/'方案_强模型复核前.md'
if not backup.exists():shutil.copy2(plan,backup)
tag='200次强基线离线复核后的决定（2026-11-04）'
old=plan.read_text(encoding='utf-8')
if tag not in old:plan.write_text(old+'\n\n## '+tag+'\n\n详见[改进双分支200次_正常区域离线复核_20261104.md](改进双分支200次_正常区域离线复核_20261104.md)。已复核seed1/2的200次既有权重，8份eval预测，历史AP/AUC等指标在记录容差内复现，权重与BN状态不变。测试6/6源对象两个种子均有区域报警，区域FPR17.97%/19.84%，5/6和4/6源有区域进入前1%。匹配角色测试5源，排序100%/90%，联合成功40%/20%。训练侧也有误报，不是新增标签缺失，支持小规模等预算C-H角色监督分配实验；尚未证明训练一定改善，需同时保护木马召回及考虑阈值权衡。未来各组统一强架构200次、原损失和域权重，在公共掩码排除C/H并集后等额替换，按源对象/实现/角色采样，不能简单加减负例。已查看测试只作探索性，不能依其筛训练对象。0训练/0反传/0SAT，本轮只完成推理和离线分析，后续训练待授权。\n',encoding='utf-8')
note='\n\n### '+tag+'\n\n新增[改进双分支200次_正常区域离线复核_20261104.md](改进双分支200次_正常区域离线复核_20261104.md)。严格加载dual_mix_post_cat/39维/split29/46620参数seed1/2既有200次权重，8份eval预测，未训练。复现历史指标并记录数值容差，权重/BN状态未变。原始训练23源、新增158节点；变换训练23源450节点、验证6源130节点、测试6源142节点全部可信正常。测试6/6源两种子均报警，区域FPR17.97%/19.84%，前1%源数5/6、4/6；角色配对测试5源排序100%/90%、联合成功40%/20%。训练侧也误报，建议受控的小规模等预算C-H区域角色监督分配实验，非简单增加负标签；不能证明因果有效，测试探索性限制保留。逐源表、角色表、分数与绑定在_p0pilot/control_best200_20261104。已修订实验方案。0训练、0反传、0优化器step、0SAT。\n'
for name in ['SAT作用证明.md','SAT工作总结.md']:
 q=R/'10.15/00_说明'/name
 if tag not in q.read_text(encoding='utf-8-sig'):
  with q.open('a',encoding='utf-8') as f:f.write(note)
q=R/'10.15/99_共用资产/运行登记/运行登记表.csv'
if tag not in q.read_text(encoding='utf-8-sig'):
 with q.open('a',encoding='utf-8',newline='') as f:csv.writer(f).writerow([datetime.datetime.now().astimezone().isoformat(),tag,'evaluate.py;analyze.py;publish.py','ginvenv_gpu eval/inference_mode;strict checkpoint','1/2','frozen existing sources','old mask +39v2','_p0pilot/control_best200_20261104','test6/6 source alarms;17.97/19.84% region FPR','复核完成；未训练','8 unique predictions;0 backward/optimizer/SAT'])
assert len(ob)==116 and all(x['all_normal_labels_verified']=='True' for x in rv)
for seed in [1,2]:
 ev=json.loads((O/f'seed{seed}/evaluation.json').read_text());assert ev['state_unchanged'] and ev['historical_metrics_reproduced']
info=dict(time=datetime.datetime.now().astimezone().isoformat(),models=2,unique_eval_arrays=8,training=0,backward=0,optimizer_steps=0,SAT=0,normal_region_source_rows=len(ob),report=str(p),files={str(x.relative_to(R)):hashlib.sha256(x.read_bytes()).hexdigest() for x in [R/'_p0pilot/round32_20261029/input_contract.json',R/'_p0pilot/round32_20261029/normalization.npz',R/'_p0pilot/p2b_main_20261031/train_ab.py',O/'evaluate.py',O/'analyze.py']})
(O/'COMPLETE.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8');print(p)
