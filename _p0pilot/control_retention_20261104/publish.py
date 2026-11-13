from pathlib import Path
import json,csv,collections,datetime,shutil,re
from audit import cells,sha,F,ROOT,OUT
rows=list(csv.DictReader((OUT/'per_view.csv').open(encoding='utf-8-sig')))
summ=list(csv.DictReader((OUT/'summary.csv').open(encoding='utf-8-sig')))
assert len(rows)==231 and len({r['view'] for r in rows})==231
nodes=list(csv.DictReader((OUT/'per_source_node.csv').open(encoding='utf-8-sig')))
for r in rows:
    a=[x for x in nodes if x['view']==r['view']]
    assert len(a)==int(r['source_added_nodes'])
    assert sum(x['status']=='mapped' for x in a)==int(r['traced_source_nodes'])
    assert int(r['traced_source_nodes'])+int(r['unresolved_source_nodes'])==len(a)
    # Independent single-line instance parser, separate from audit's block regex.
    text=(F/'trans'/(r['view']+'.v')).read_text(encoding='utf-8')
    line_names={m.group(1).lstrip('\\') for m in re.finditer(r'^\s*[\w$]+\s+(\\[^\s]+|[\w.$\[\]/]+)\s*\(\s*\.',text,re.M)}
    assert set(filter(None,r['target_instances'].split('|'))) <= line_names

co=[]
for r in rows:
    role=('primary_candidate' if r['status']=='完整保留' else 'partial_secondary') if int(r['shared_target_nodes'])==0 and r['status'] in ('完整保留','部分保留') else 'excluded_from_matched_main'
    co.append({**r,'proposed_cohort':role,'training_started':False})
with (OUT/'cohort_candidates.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(co[0]));w.writeheader();w.writerows(co)
def table(a,key):
    s='|'+key+'|视图数|完整保留*|部分保留*|消除|映射不明|\n|---|---:|---:|---:|---:|---:|\n'
    for r in a:s+='|'+ '|'.join(str(r[x]) for x in ['group','views','完整保留','部分保留','消除','映射不明'])+'|\n'
    return s
report='''# 新增正常对照节点的变换保留与映射审计

2026-11-04。离线核查48份源对照及冻结划分中的231个变换视图；0训练、0SAT，没有改写原网表或旧映射。

## 判据与证据边界

源对象依据provenance.new_gates，48/48源文件均找到全部新增实例；多处生成记录如给出不同新增实例集合则拒绝。逐视图核对mapping.src_view/rw_view和实际目标实例，已存在映射无悬空目标、表头无错配。源/目标/映射/provenance/clean参考SHA保存在audit.json。

*“完整保留”是全部源新增实例都有现存目标门的溯源/同名落点；“部分保留”是仅一部分有落点。不是逐门函数等价证明，不代表保持相同门数、完整功能边界或一一对应。现有映射本身未逐项重新做SAT认证，候选区域不可据此直接用于跨实现功能一致性。

“消除”要求无新增对象落点，并且当前门实例/类型/逐引脚连接、模块端口列表及全部assign，与已有同宿主同配方clean参考逐项完全相同。该结论是独立新增门对象已消失，不是重新证明整电路时序等价。仅前缀或映射缺失不判消除。

“映射不明”包括无法排除优化消除、改名、重写或旧映射漏项的情况；不把它们全部当成保留或消除。尤其40个ys_aig仍是映射不明。

## 按划分

'''
report+=table([r for r in summ if r['group_by']=='split'],'划分')
report+='\n合计：231视图，完整90、部分17、消除80、映射不明44。\n\n## 按实现流程\n\n'+table([r for r in summ if r['group_by']=='recipe'],'流程')
report+='\n## 按对照族\n\n'+table([r for r in summ if r['group_by']=='family'],'对照族')
report+='''
## 共享落点风险

18个视图的新增对象映射到了也被宿主源门映射的目标门。这是当前映射的角色混合信号，不自动证明物理合并机制。包括ctldup全部10个有映射视图，以及部分ctlmatchd、ctlmatchf、a4ctlequiv。不能将这些门当独立新增正常区域无限重复计样。

剔除共享落点、并要求完整溯源后：

|划分|主实验候选视图|唯一源对照实例数|候选目标节点次数|
|---|---:|---:|---:|
'''
for sp in ['train','val','test']:
    a=[r for r in co if r['split']==sp and r['proposed_cohort']=='primary_candidate']
    report+=f"|{sp}|{len(a)}|{len({r['source_view'] for r in a})}|{sum(int(r['target_nodes']) for r in a)}|\n"
report+='''
训练50候选视图约450个目标节点，而不是812166个正常图物理节点；多实现不独立，不能把50视图当50独立源设计。候选主集还需节点坐标、可信负标签和边界检查后才可训练；本轮没有将这些候选写入训练掩码。

部分保留且无共享落点：训练11、验证2、测试2，单列补充组。训练14/验证2/测试2视图存在共享落点，退出主匹配区域实验。四类统计与训练准入是不同维度，不能因共享而篡改原溯源覆盖。

## 交付与后续

- per_view.csv：231视图完整清单、四类状态、源新增实例数、已映射/未映射数、目标门名单、共享落点、clean参考及摘要。
- per_source_node.csv：1746个“源新增节点×视图”记录，每个目标门类型和落点依据；不是1746独立源节点。
- summary.csv：划分/对照族/流程汇总。
- cohort_candidates.csv：拟议候选准入，不是已经监督的节点。
- audit.py与audit.json：可复现审计和输入绑定。

当前全部映射不明有44个：40个ys_aig与4个A4 dead/ys_id。当前消除80个为普通对照的ys_id/ys_opt各40个。不能把这些视图的低风险计为模型识别新增困难逻辑成功；它们仍可作为整图正常或clean一致性诊断，但不承担“新增区域区分”主结论。

不重新生成数据、不重跑综合或SAT；先使用可审计候选设计实验。A4 equiv在验证/测试没有独立视图，因此其作用只能训练侧分析或未来另设独立留出，不声称现有跨宿主验证已覆盖。
'''
(OUT/'审计报告.md').write_text(report,encoding='utf-8')

revision='''
## 2026-11-04修订：基于实际保留情况的主实验对象与预算

本节优先于前文按“整张正常对照视图随机抽负节点”的粗方案。审计报告见 `_p0pilot/control_retention_20261104/审计报告.md`，逐视图见per_view.csv。

1. 原始侧48源对照均有明确新增实例列表。变换侧231视图只有90完整溯源、17部分、80确认消除、44映射不明。完整溯源不是功能等价或独立安全角色证明。
2. 18个视图共享宿主落点，主实验排除整个混合对象，不重复当作新增正常区域。主候选只取完整溯源且无共享者：训练50视图450目标节点、验证12视图130节点、测试12视图142节点；都是候选，须再核对实际图坐标、负标签及边界，未启动训练。部分区域另报，消除及不明不进入困难新增区域主指标。
3. 原始/变换侧使用同一源对象资格原则。主域对照优先取能在两侧可靠定位的共同源对象；orig-only其余对象可作独立补充，不能让两侧对象家族不同而解释成域效应。源/宿主/划分不重排，不能为扩大样本把val/test送入训练。
4. 实验主问题改为“等额区域负例预算，匹配新增正常区域是否优于普通背景”。固定木马监督和公共背景监督；替换槽分别来自困难对照区域C与普通背景区域H。H尽量匹配同宿主、门型、规模、PI/PO粗位置；匹配特征在训练/验证预先固定，报告共同支持及丢失对象。不根据测试正例位置选训练负例。
5. 先按源对象采样，再选实现，最后在已定位新增区域内采节点，绝不从整图随机挑选。相同源的多个实现按固定权重；小区域全用，大区域按固定角色层次抽样。背景组使用相同区域/节点次数、唯一节点预算及重用次数。无合格背景匹配则剔除两组对应对象并报告，不能静默选容易背景。
6. 预算低/高两档应由450个训练候选目标的真实可用数量和去重源数决定，不能照百万节点规模指定。高档通过改变固定采样次数/覆盖范围时，记录唯一节点数和重复次数；源对象相同反复采样不是新增信息。先冻结具体对象清单、共同支持及采样manifest，暂不预设18次训练或固定N，以免数据不支持。
7. 损失公共项固定，额外负例项独立归一化，权重相同；正例集合、累计正例曝光、优化步数、orig/trans权重、初始化、全图前向和BN范围均固定。C与H对照使用同一槽位预算。额外不监督组可保留，但仅作“是否增加监督”参照，不能作为等预算内容贡献的唯一依据。
8. 特征先固定39维v2、模型先固定同一单分支，不加入SAT/等价一致性/区域辅助模块。SAT原始侧未补、双侧同合同输入尚未完成；当前既有trans覆盖不能写成双侧SAT完成。本轮0训练、0SAT。
9. 主评价在冻结且独立留出的新增正常区域，报告C区域FPR、区域告警、木马AP/召回、T-C排序/联合成功；增加区域保留率、映射覆盖和有效源数。消除区域无风险分数，不填0当正确识别。部分区域只报告已定位子集，不与完整区域混池。
10. A4 equiv是更严格的结构可达对照，但现有验证/测试没有独立A4对象；不能用普通dead类测试代替该机制泛化验证。当前完整候选偏向abc/nand，不能声称跨全部流程。ys_aig缺映射为后续静态追踪任务，本轮不启动SAT补证。

预期结论：只有等预算C优于H、困难区域误报减少且木马检出保持，才支持新增木马样正常区域的额外贡献；整图背景改善或被消除对象低风险均不足以支持这一结论。
'''
plan=ROOT/'10.15/00_说明/正常对照贡献量化与公平实验方案_20261104.md'
backup=OUT/'正常对照贡献量化方案_本轮修订前.md'
if not backup.exists():shutil.copy2(plan,backup)
old=plan.read_text(encoding='utf-8')
if '基于实际保留情况的主实验对象与预算' not in old:
    plan.write_text(old+'\n'+revision,encoding='utf-8')
(OUT/'方案修订.md').write_text(revision,encoding='utf-8')
note='\n\n### 正常对照新增区域保留审计与方案修订（2026-11-04）\n\n离线核查48源对照、231变换视图：完整溯源90、部分17、确认独立新增结构消除80、映射不明44；消除由同配方clean门/引脚/端口/assign完全一致支持，非仅名称缺失。18视图共享宿主落点，主匹配区域实验排除。完整且无共享候选train50/val12/test12，目标节点次数450/130/142，尚需图坐标及标签预检；不是已训练或功能已证。审计及CSV在_p0pilot/control_retention_20261104；已修订正常对照贡献量化方案为源对象/区域内等预算C-H替换，单列部分/消除/不明，不从整图随机采负节点。原始侧SAT未补齐，双侧合同未完成。0训练、0SAT，保留生产数据与旧映射。\n'
for name in ['SAT作用证明.md','SAT工作总结.md']:
    p=ROOT/'10.15/00_说明'/name
    if '正常对照新增区域保留审计与方案修订（2026-11-04）' not in p.read_text(encoding='utf-8-sig'):
        with p.open('a',encoding='utf-8') as f:f.write(note)
with (OUT/'validation.json').open('w',encoding='utf-8') as f:json.dump(dict(passed=True,views=len(rows),source_node_records=len(nodes),target_name_independent_check=True,new_training=0,new_sat=0),f,indent=2)
print('Published audit, cohort table and plan revision; 0 training/0 SAT')
