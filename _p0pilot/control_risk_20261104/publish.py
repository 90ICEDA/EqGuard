from pathlib import Path
import csv,json,collections,datetime,shutil
import numpy as np
ROOT=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent
def rows(n):return list(csv.DictReader((O/n).open(encoding='utf-8-sig')))
def dump(n,a):
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(a[0]));w.writeheader();w.writerows(a)
ob=rows('per_source_object.csv');vs=rows('region_per_view.csv');ps=rows('trojan_control_pairs.csv');su=rows('summary.csv')
co=list(csv.DictReader((O.parent/'control_retention_20261104/cohort_candidates.csv').open(encoding='utf-8-sig')))
coverage=[]
for sp in ['train','val','test']:
 for src in sorted({r['source_view'] for r in co if r['split']==sp and r['proposed_cohort']=='primary_candidate'}):
  a=[r for r in co if r['source_view']==src and r['proposed_cohort']=='primary_candidate']
  coverage.append(dict(split=sp,source_view=src,candidate_views=len(a),target_node_occurrences=sum(int(x['target_nodes']) for x in a),prediction_status='missing_train_predictions' if sp=='train' else 'available_6_model_seed_configs',reason='No inference recomputation; train score file absent' if sp=='train' else 'saved arrays checked against per-view metrics'))
dump('source_coverage.csv',coverage)
source_summary=[]
for sp in ['val','test']:
 for src in sorted({r['source_view'] for r in ob if r['split']==sp}):
  a=[r for r in ob if r['source_view']==src]
  byview=[r for r in vs if r['source_view']==src]
  source_summary.append(dict(split=sp,source_view=src,model_seed_configs=len(a),configs_with_alarm=sum(int(x['source_any_alarm']) for x in a),mean_region_node_fpr=float(np.mean([float(x['view_macro_node_fpr']) for x in a])),mean_best_rank_fraction=float(np.mean([float(x['view_macro_best_rank_fraction']) for x in a])),configs_top1_guaranteed=sum(int(x['top1_guaranteed_views'])>0 for x in a),mean_background_fpr=float(np.mean([float(x['background_fpr']) for x in byview]))))
dump('source_overview.csv',source_summary)
report='''# 可追溯新增正常区域的已有预测离线诊断

2026-11-04。本轮只使用已保存分数，0训练、0模型前向、0SAT，没有加载权重重新预测。

## 证据范围和坐标

模型固定为最新p2b_main_20261031/runs的A单分支、B双分支，各seed42/1/2，共6配置；不因测试成绩挑模型，旧掩码、SAT增强或其他架构实验不混入。

对应SELECTED.json与seed*_AB.json的模型路径一致。保存的val/test分数长度、有限性检查通过，按原阈值重算所有保存的trusted per-view FPR，与原表一致。未重算权重前向，因此结论绑定于现存分数和元数据；不是重新认证历史整个训练管线。

物理节点由冻结ordered node_names_trans、old_start/old_stop映射到split start；逐个新增门检查实际节点存在、physical=true、y=0。全部130个验证及142个测试候选正常节点均在new可信评价掩码中。排序在所在视图所有物理节点上计算，与“只在可信子集排序”分开；未知背景参与检查队列，但没有被认证为正常。

两种聚合：先同一源对象内对实现等权，再对源对象等权；6个模型配置仅作重复诊断，不当作6个独立数据样本。val与test各6个源对照变体，分别来自单个宿主，同宿主对象也不完全统计独立。

训练侧50候选视图、23个源对象没有本版本保存的train_scores.npy，全部标NA，不借用其他模型预测，不把缺失当低风险。详见source_coverage.csv。

## 源对象逐项报告

下表每行一个源对象，含其2个完整可追溯且无共享落点的实现。报警配置数表示6个A/B×seed配置中，至少一个实现新增区域有节点达到该模型原阈值的次数；不是独立实验成功率。FPR先对实现平均；风险排名为区域最高风险节点的最好名次占全物理视图节点数的比例，再平均。排名比例越小越靠前。跨模型分数尺度不同，不平均原始风险分数作为优劣指标；具体risk_max、threshold保留在逐配置表。

|划分|源对象|报警配置数/6|区域节点FPR均值|区域最高风险平均排名比例|进入前1%的配置数/6|同视图背景FPR均值|
|---|---|---:|---:|---:|---:|---:|
'''
for r in source_summary:
 report+=f"|{r['split']}|{r['source_view']}|{r['configs_with_alarm']}|{r['mean_region_node_fpr']:.2%}|{r['mean_best_rank_fraction']:.2%}|{r['configs_top1_guaranteed']}|{r['mean_background_fpr']:.2%}|\n"
report+='''
全部12个验证/测试源对象均至少有一次报警。测试6个对象中4个在全部6配置报警，另2个分别4/6、5/6。不能据此宣称所有正常对照都难：本结果限定于既有完整可追溯主候选，且不含消除、不明及混合对象。

## 按模型与种子分开

报警源数为同一源任一实现报警。FPR按源等权，不池化全部节点。

|划分|模型|seed|报警源数/6|区域节点FPR|源平均最高风险排名比例|前1%源数/6|
|---|---|---:|---:|---:|---:|---:|
'''
for r in su:
 report+=f"|{r['split']}|{r['arm']}|{r['seed']}|{r['source_any_alarm']}|{float(r['source_macro_node_fpr']):.2%}|{float(r['source_macro_best_rank_fraction']):.2%}|{r['sources_top1_guaranteed']}|\n"
report+='''
阈值原本由验证集全部可信负节点的95%分位确定；不是“正常对照区域固定5% FPR”阈值，也没有按本轮测试区域重调。除区域告警外，前1%风险排名说明部分误报不只是阈值偏移；但只有离线关联证据，不能证明正常监督训练一定改善。

## 与木马区域的严格受限对比

按预设ctlmatcha/b/c/d/e/f→injalpha/beta/gamma/delta/epsilon/zeta匹配同宿主、同源模板、同实现配方；A4按形状匹配。ctlxor无严格模板木马伙伴，不制造配对。原生成器匹配随机种子提供模板关系，不代表两区域功能等价或门级严格一一对应。

木马新增区域须全部源新增门有实际图落点，且所有落点都为new可信正例；否则整对排除，不只挑高分/正例子集。不新做SAT验证，不补造对应。配对的max聚合受区域规模影响，节点数保存在表中，只作诊断，不宣称因果安全区分已认证。

验证仅5个源对照有可用木马区域伙伴；测试仅3个源（见下面明细）。先按源内实现平均，再按源等权。

|划分|模型|seed|可用配对源数|木马高于正常的排序率|木马报警且正常不报警|两区域均低于阈值|
|---|---|---:|---:|---:|---:|---:|
'''
for r in su:
 report+=f"|{r['split']}|{r['arm']}|{r['seed']}|{r['paired_sources']}|{float(r['pair_correct_order']):.2%}|{float(r['pair_joint_success']):.2%}|{float(r['pair_both_low']):.2%}|\n"
report+='\n可用配对源对象：\n\n'
for sp in ['val','test']:
 report+='- '+sp+'：'+ '；'.join(sorted({r['control_source'] for r in ps if r['split']==sp}))+'。\n'
report+='''
测试排序率跨配置33.33%—100%，联合成功0—50%，配对仅3源、种子波动明显；不能宣称模型已可靠区分。正常风险降下来但木马同时漏检，不是成功。详见trojan_control_pairs.csv，保留每个源、实现、配置的风险、命中、双低与双高。

## 判断与实验修订

存在值得解决的新增正常区域误报，不应因只有数百节点而认定问题不重要。但目前证据支持的是一个受限、可定位的误报问题，尚不是“正常监督可提升全图泛化”的因果结论。

1. 优先把已冻结的完整/无共享对象定义为困难区域池，训练仅使用既有23个训练源对象；不能按本轮测试误报大小筛选训练家族、改负例权重或确定超参数。
2. 离线诊断已看测试，后续在该测试集上的研究应明确为既有测试上的探索性验证；要给出独立确认结论，需要新冻结的独立源对象/机制/宿主评测。不要再称现有测试为完全未触碰。
3. 主实验C-H区域等预算替换仍适用：相同木马正例和公共背景监督，仅替换困难正常区域与匹配普通背景区域。两侧规则统一；固定源对象、实现、节点曝光和权重，按训练实际支持确定预算，不扩大普通负例数掩盖区域收益。
4. 验证集可检查阈值稳定性，但不要只以本区域误报最低选模，必须同时保护木马AP/召回。参数网格及选择规则事先冻结，样本小不做大规模调参。
5. 将“新增正常区域前1%告警、区域FPR、木马检出保持及配对联合成功”作为共同指标；整图背景FPR和总体AP辅助报告。消除对象不以0风险算成功。
6. 第一轮宜小规模源对象分层的可行性实验，而非预先铺满18次大训练；先验证采样合同与梯度预算，待另行授权再训练。本轮不发起训练、SAT或推理。
7. 当前A4 equiv没有独立验证/测试候选，现有dead类普通对照上的发现不能代表可达等价控制的泛化。ys_aig映射缺口也仍未解决。

## 文件与缺失说明

- per_source_object.csv：每个源对象、每模型、每种子分开（72行），主交付。
- source_overview.csv：12源对象描述性总览；source_coverage.csv：所有35候选源对象及训练预测缺失。
- region_per_view.csv：144条区域评价；region_nodes.csv：1632条节点×配置记录，标签/可信/风险/名次/报警。
- trojan_control_pairs.csv：严格合格伙伴逐对结果；pair_exclusions.csv：每个候选未配对原因（含训练候选，不能误计为已评价配对）。
- summary.csv：逐seed/模型/划分源等权汇总；prediction_prechecks.csv：保存分数与原指标一致性。
- audit.json：输入哈希、坐标合同、范围限制及零训练/前向/SAT声明；analyze.py为离线复现代码。

只使用已保存预测，未调用任何训练、模型前向或SAT。当前原始侧k4历史部分成果仍未确认，当前增强加载orig补零的事实保持；本轮与SAT增益无关。
'''
(O/'离线诊断报告.md').write_text(report,encoding='utf-8')
public=ROOT/'10.15/00_说明/新增正常对照区域离线误报诊断_20261104.md'
public.write_text(report,encoding='utf-8')
plan=ROOT/'10.15/00_说明/正常对照贡献量化与公平实验方案_20261104.md'
backup=O/'方案_离线诊断修订前.md'
if not backup.exists():shutil.copy2(plan,backup)
section='''
## 离线预测诊断后的修订（2026-11-04）

详见[新增正常对照区域离线误报诊断_20261104.md](新增正常对照区域离线误报诊断_20261104.md)。最新new-mask A/B各3seed的既有预测证实：验证/测试各6个源对照对象均至少出现一次区域误报。测试各配置4—6/6对象报警，区域节点FPR14.64%—40.25%；部分区域进入视图物理节点风险前1%，存在明确的局部误报问题。主候选272个验证/测试节点全部已有可信正常标签。

严格伙伴条件下验证5源、测试3源可做木马区域比较，联合成功仍不稳定；不扩大为全部配对。训练23源/50视图无本版本保存预测，标NA；不重新前向、不借用旧模型分数。

继续采用等源对象/区域预算C-H替换，而非从整图随机采负例。训练对象只按训练侧冻结池选取，不依测试难例挑对象或权重。先小规模验证预算、损失及源级泛化，预算值在训练/验证支持范围内确定，待用户另行授权后实施。多种子不能补偿独立源对象少，测试只有一宿主且已被本轮诊断查看，后续该测试上的结果属探索性验证；独立确认需新冻结对象或留出。区域误报改善必须同时报告木马检出保持和配对联合成功。A4可达等价对照与ys_aig仍缺当前主评价支持，不夸大结论。本轮0训练、0模型前向、0SAT。
'''
old=plan.read_text(encoding='utf-8')
if '离线预测诊断后的修订（2026-11-04）' not in old:plan.write_text(old+'\n'+section,encoding='utf-8')
note='\n\n### 新增正常对照区域已有预测离线诊断（2026-11-04）\n\n报告：[新增正常对照区域离线误报诊断_20261104.md](新增正常对照区域离线误报诊断_20261104.md)。最新new-mask A/B各seed42/1/2，只读取既有val/test分数并复核原per-view FPR。独立源对象各6个、每对象2实现，测试4—6/6源对象在各配置报警；正常新增区域节点FPR14.64%—40.25%，全部272个候选节点可信正常。验证5源/测试3源有严格标签合格的木马区域伙伴，联合成功不稳定；训练23源缺保存预测，NA，不重前向。明细、输入绑定、源级表、排除表在_p0pilot/control_risk_20261104；已修订公平实验方案为冻结困难区域与背景区域等预算替换，保护木马检出，明确既有测试已被诊断使用，不据测试挑训练对象。0训练、0模型前向、0SAT，未修改生产入口。\n'
for name in ['SAT作用证明.md','SAT工作总结.md']:
 p=ROOT/'10.15/00_说明'/name
 if '新增正常对照区域已有预测离线诊断（2026-11-04）' not in p.read_text(encoding='utf-8-sig'):
  with p.open('a',encoding='utf-8') as f:f.write(note)
p=ROOT/'10.15/99_共用资产/运行登记/运行登记表.csv';tag='新增正常对照区域已有预测离线诊断'
if tag not in p.read_text(encoding='utf-8-sig'):
 with p.open('a',encoding='utf-8',newline='') as f:csv.writer(f).writerow([datetime.datetime.now().astimezone().isoformat(),tag,'analyze.py;publish.py','numpy offline;no torch forward','42/1/2','val/test existing frozen sources','new-mask A/B existing scores','_p0pilot/control_risk_20261104','test 4-6/6 sources alarm;14.64-40.25% region FPR','离线诊断完成','train scores absent;no training/forward/SAT'])
assert len(ob)==72 and len(vs)==144 and len(source_summary)==12
assert all(int(x['new_eval_nodes'])==int(x['region_nodes']) for x in vs)
assert len({(x['split'],x['view'],x['split_row']) for x in rows('region_nodes.csv')})==272
(O/'COMPLETE.json').write_text(json.dumps(dict(time=datetime.datetime.now().astimezone().isoformat(),sources_evaluated=12,regions=24,physical_nodes=272,model_configs=6,per_source_rows=72,train_sources_missing=23,new_training=0,new_forward=0,new_sat=0,report=str(public)),ensure_ascii=False,indent=2),encoding='utf-8')
print(public)
print('Strict pairs',len(ps),'rows. Report and plan updated. No training, inference or SAT.')
