"""Publish coverage recovery and a concrete unexecuted pretraining protocol."""
from pathlib import Path
import collections,csv,datetime,json,sys
import numpy as np
from pool_adapter import FunctionalConePool,read,sha
O=Path(__file__).resolve().parent;R=O.parents[1];D=R/'10.15/00_说明'
def table(rr,fields):return '\n'.join(['|'+'|'.join(fields)+'|','|'+'|'.join(['---']*len(fields))+'|']+['|'+'|'.join(str(r[k]) for k in fields)+'|' for r in rr])
def csvrows(n):return list(csv.DictReader((O/n).open(encoding='utf-8-sig')))
def main():
 assert not (O/'PUBLISHED.json').exists()
 result=read(O/'POOL_COMPLETE.json');pairs=read(O/'pool_pairs.json');cones={c['cone_id']:c for c in read(O/'pool_cones.json')};old=read(R/'_p0pilot/cec_cone_expand_20261105/final_pairs.json');oldids={p['pair_id'] for p in old};meta={v['view']:v for v in csvrows_external(R/'generate_trans/folds/hosts_bt31/views_meta.csv')}
 audit=[]
 for split,n in [('train',391),('val',96),('test',0)]:
  ds=FunctionalConePool(split);assert len(ds)==n;assert np.isclose(sum(ds[i]['weight'] for i in range(n)),1 if n else 0)
  for z in ds:
   assert z['functional_training_data_eligible']==(split=='train') and 'root_endpoints' not in z
   for side in ['left','right']:assert not z[side]['members'].flags.writeable
   audit.append(dict(pair_id=z['pair_id'],split=split,proof_method=z['proof_method'],weight=z['weight']))
 for bad in ['all',None,'']:
  try:FunctionalConePool(bad)
  except ValueError:pass
  else:raise AssertionError('mixed split accepted')
 flows=[];positive=[]
 for split in ['train','val','test']:
  for p in pairs:
   if p['split']!=split:continue
   if all(e['trusted'] and e['label']==1 for e in p['root_endpoints']):
    aa,bb=[cones[p[k]] for k in ['left_cone','right_cone']]
    positive.append(dict(split=split,source=p['source_object'],pair_id=p['pair_id'],flow='/'.join(sorted([meta[aa['view']]['op'],meta[bb['view']]['op']])),proof='native_CEC' if p['proof_ids'] else 'complete_enum',left_cells=len(aa['members']),right_cells=len(bb['members']),inputs=len({tuple(l[:3]) for c in [aa,bb] for l in c['leaves']}),new_vs_all_previous=p['pair_id'] not in oldids))
  for a,b in sorted({tuple(sorted([meta[cones[p['left_cone']]['view']]['op'],meta[cones[p['right_cone']]['view']]['op']])) for p in pairs if p['split']==split}):
   rr=[p for p in pairs if p['split']==split and sorted([meta[cones[p['left_cone']]['view']]['op'],meta[cones[p['right_cone']]['view']]['op']])==[a,b]]
   flows.append(dict(split=split,op_a=a,op_b=b,pairs=len(rr),sources=len({p['source_object'] for p in rr}),positive_pairs=sum(all(e['trusted'] and e['label']==1 for e in p['root_endpoints']) for p in rr)))
 # Quantify why endpoint-count matching alone is not a frozen weighted control.
 weights=read(O/'POOL_CONTRACT.json')['weights'];byid={p['pair_id']:p for p in pairs};perm=csvrows('permutation_draft.csv');true_mass=collections.defaultdict(float);fake_mass=collections.defaultdict(float)
 for p in perm:true_mass[p['true_right_cone']]+=weights[p['true_pair_id']];fake_mass[p['permuted_right_cone']]+=weights[p['true_pair_id']]
 maxdelta=max(abs(true_mass[k]-fake_mass[k]) for k in set(true_mass)|set(fake_mass))
 # Audit negative/different-function certificates and final permutation matching
 # are deliberately prerequisites; this file never launches the proposed protocol.
 protocol=dict(status='PROPOSAL_NOT_RUNNER_NOT_TRAINING_READY',python='ginvenv_gpu',model='dual_mix_post_cat 39v3 split29 hidden64 2+2+post1',features='same frozen39v3; no SAT feature inputs',seeds=[42,1,2],initial_phase_seed=42,pretrain_updates=50,finetune_updates=200,total_updates_each_main_arm=250,optimizer=dict(type='Adam',lr=0.0002,weight_decay=0.001,clip_grad_norm=1.0),arms=['Z:no_positive_equivalence_term','R:real_positive_equivalence_term','P:grouped_permuted_equivalence_term'],common_pretrain_terms=['certified_function_different_negative_margin','weighted_noncollapse_variance'],functional_projection=dict(input='concat(root hidden,mean hidden of combo cone)',hidden_dim=64,output_dim=32,normalization='none on z; weighted variance regularizer'),loss=dict(real_positive='weighted squared distance, coefficient1',negative='weighted max(0,1-L2distance)^2, coefficient1',variance='weighted mean relu(0.5-std(z)), coefficient0.1'),fine_tuning='discard projection head; transfer encoder only; identical frozen detector head initial weights; fresh identical Adam state; original H supervision and loss for200 updates',selection='pretrain fixed last50; fine tuning old validation trusted injection AP every5; never select by test or single positive pair',historical_reference='old200-update H is context only, not equal-budget main control',proposal_hyperparameters_not_validated=True,paired_exposure='freeze common endpoint/node/source schedules before running; equal weighted endpoint marginals required',permutation_draft_rows=len(perm),permutation_draft_max_weighted_right_endpoint_delta=maxdelta,remaining=['certify function-different negatives by explicit PI/Q output-difference witnesses','filter accidental equal functions in permutation; apply gate/cut strata','freeze common-pool source/component weights and exact exposure including repeat limits','implement frozen training runner; loss-scale and memory preflight without optimizer updates'],test_pair_policy='do not select using test positive locations; no test pair census this round',training_started=False,SAT_queries=0)
 (O/'PRETRAIN_PROTOCOL.json').write_text(json.dumps(protocol,ensure_ascii=False,indent=2),encoding='utf-8')
 target=D/'等价锥覆盖缺口补证与等预算预训练方案_20261105.md';assert not target.exists()
 text='''# 等价锥覆盖缺口补证与等预算预训练方案

2026-11-05。本轮0训练、0模型前向、0新增SAT；复用旧证明，并对少量旧候选进行完整二值枚举和独立标量回放。旧文件、图、特征、标签、预测和证明均不改，不移动或删除文件。

## 1. 正根到底有多少，验证是否需要扩充

“双侧可信正根配对”指两个根各自都有可信正标签，不由一侧复制标签。它是根输出配对数，不是正例节点总数，也不是独立木马数量。锥内其他节点不因此获得正标签。

| 划分 | 上轮原生CEC主池正根 | 本轮原生CEC正根 | 完整枚举补充正根 | 当前可靠正根合计 | 正根源对象 |
|---|---:|---:|---:|---:|---:|
|训练|8|8|2|10|4|
|验证|1|1|1|2|2|
|测试|0|0|0|0|0|

上轮训练还保存了1对仅枚举补充，故上轮若把两种合格证据一起计数应为训练9/验证1，而此前说8/1明确指原生CEC主池。本轮枚举训练2对中有1对是该旧补充的重新核验，真正新增正根配对为训练1、验证1；没有将它再算成新配对。测试0表示未建立本项目合同下的配对，绝不表示测试图没有正例。

验证确实需要扩充，优先增加源对象与实现变化。本轮从injalpha的id/opt一对，增加到injalpha的id/opt和injzeta的abc/aig两对；验证正根源从1增至2。但仍只有s38417一个宿主，不能称已解决跨宿主验证或正例统计充分问题。

## 2. 当前按宿主的覆盖与缺口

分母为当前变换侧数据；原始侧没有自动纳入本轮锥合同。一个制造源的多个视图不能当多个独立源。

'''
 text+=table(csvrows('coverage_after.csv'),['split','host','total_sources','paired_sources','pairs','positive_pairs','positive_sources'])
 text+='''

训练3/3宿主有配对，但源覆盖只有9/50；验证1/1宿主有配对，源覆盖3/13；测试0/13。s35932只有一个正常制造源的56对、没有木马正根，是训练侧的明显缺口。s15850正根仅1个制造源。验证13个源中，仅3个有任意可靠锥、2个有正根。当前缺口是覆盖范围与独立性，不能靠继续从同一源投影更多负根解决。

## 3. 实现流程覆盖

'''
 text+=table(flows,['split','op_a','op_b','pairs','sources','positive_pairs'])
 text+='''

训练可用流程有abc、aig、id、nand、opt及极少rt，但已配对仅覆盖abc/aig、abc/id、abc/nand、abc/opt、id/opt五类。训练aig/id、aig/nand、aig/opt、id/nand、nand/opt仍无可靠边，rt相关也未覆盖。验证仅abc/aig与id/opt两类，所有nand相关配对均缺失。不同源在某流程有视图，不等于已经证明该流程对的锥等价；可选共同源分母完整记录在flow_gaps_before.csv。

## 4. 这轮如何优先复用证据

先穷查11个已绑定PO/D实现对的7454个观察位，不再使用旧first64或正根first4上限；没有找到新的双侧可信正根。随后核查第10/11/12轮累计表中127个不同的无条件proved查询，按源网表、raw、完整模型重生成、共享env、精确SAT命令及SUCCESS日志绑定。得到8个此前未加载的非平凡负根配对（训练7、验证1），其中新增s15850 ctlmatcha制造源。没有用增加负根数量来冒充正根覆盖改善。

18个review查询无法与原计划推断的当前raw严格绑定，单列excluded_model_not_equal_to_current_planned_raw，不自动接受，也不宣称旧证明错误。可能是复核候选/模型上下文与原plan不同，后续若恢复精确映射可再审；本轮不靠放宽检查补数。

再把974004行旧sweep仅用作定位，限定现有raw、同源、训练/验证侧和双侧独立可信正根。得到25个去重当前候选；按验证优先、未覆盖正根源优先、可完整枚举边界优先和固定哈希，最多24个/每源4个，实际取17个。3对用完整二值PI/Q枚举通过，另14个边界过大暂缓；旧proved没有直接当作新证明。3对中1对为旧枚举补充，新增2对。

| 划分 | 来源 | 实现 | 自由PI/Q输入 | 完整输入数 | 两侧门数 | 是否新增 |
|---|---|---|---:|---:|---|---|
|训练|rs232 injzeta|abc/aig|8|256|18/30|旧补充重核验|
|训练|rs232 injzeta|abc/nand|8|256|18/39|新增|
|验证|s38417 injzeta|abc/aig|10|1024|14/29|新增|

三对另用独立标量解释器逐输入回放，共1536组，两侧全部相等且非恒定，完整真值表哈希一致。证书保留语义叶顺序、Q/QN极性、raw哈希和根bit。新增8个源绑定配对也独立回放并核查非恒定，最多13输入，未调用求解器。它们仍以旧CEC投影为原始证明，不把抽样当作等价证明。

最终功能池487对=train391+val96，447个连通锥对象=train351+val96；484对有旧源绑定CEC、3对有完整枚举证书。较旧全部477候选净增10对（8负根、2正根）。不把487都写成原始SAT证明。权重按源/上下文连通锥/已观测边分级等权重算；训练9源、验证3源隔离。新pool_adapter逐项加载487对，保留根bit/pin和只读成员，不给功能训练payload附上安全标签；原FINAL476版本及旧475接口保留。

## 5. 锥级等价预训练的具体设计

目标是检验编码器能否利用功能等价证据减少实现变化带来的表示与检测波动，而不是让CEC直接判木马。以当前较强改进双分支为基础：39维v3、29/10拆分、hidden64、2+2+post1、原图/归一化。SAT摘要不作输入，正常对照监督和区域权重不同时改。

编码器仍读取完整训练视图及现有图边，避免把深锥截成小邻域而改变证明对象；从分类头之前的节点隐藏表示取根向量和该组合锥成员均值，拼接后经独立MLP（hidden64，输出32）得到z。锥成员有重叠，需缓存节点隐藏表示后池化，不能逐锥重跑整图。这个z是拟学习的功能表示，必须通过函数区分诊断后才能认为具有功能意义。

仅训练391对进入预训练，验证96对只评价。木马标签可辅助此前选样和分层诊断，但不进入预训练损失、特征或边界，也不把锥内节点标签互相复制。

预训练拟50次更新，不按验证单正根挑最佳预训练轮次，统一用第50次。共同Adam参数lr=0.0002、weight_decay=0.001、梯度裁剪1，优先ginvenv_gpu和bf16。先seed42，之后再决定seed1/2，不现在提交队列。这些是待验证的起始参数，不是已有最优结论。

拟议损失：

- 等价项L_eq为按源/连通锥/观测边权重汇总的两侧z平方距离。
- 不同功能项L_diff为max(0,1−两z距离)的平方。只能对同名PI/Q可对齐、且至少有一个明确输入反例使输出不同的函数对使用；未知或仅采样相同的函数对不能当负对。
- 防坍缩项L_var为每维加权标准差不足0.5的惩罚，建议系数0.1。非恒定函数本身不保证表示不坍缩，所以仍需同时监测z方差、有效秩、不同函数区分与真实配对距离。

不同功能证书优先利用已有完整真值表；不足时在同源PI/Q上下文做小批CPU布尔回放，发现一个两侧输出不同的输入即可提供不同功能见证，不需SAT。无反例不等于等价。证书生成、函数负对数量和难度匹配尚待预检，不在本轮宣称完成。

## 6. 等预算主对照

| 组别 | 预训练50更新 | 下游检测200更新 | 要回答的问题 |
|---|---|---|---|
|Z 零等价约束|共同L_diff+0.1L_var，计算等价距离但系数0|共同监督、损失、采样和预算|功能差异训练之外，真实等价约束是否有增量|
|R 真实对应|Z共同项+真实L_eq|与Z完全相同|真实对应的效果|
|P 置换对应|Z共同项+分组置换L_eq|与Z完全相同|收益是否来自真实对应关系|

三个主组都做50+200=250次更新，同功能投影头与参数、同端点曝光、同不同功能负对、同优化器与数据前向次数。Z不是“完全不预训练”，而是“没有正等价约束”的预训练对照。旧H200仅作历史参照，不能作为250更新的公平主基线。

预训练后丢弃投影头，只迁移编码器；检测分类头均恢复同一种子原初始权重，使用相同新Adam状态，执行原H监督200更新。所有组原始侧/变换侧正负监督、H采样表、ASL+1.4 soft-miss、阈值标定和每5步验证AP选模规则保持。若下游新增功能头、监督或区域损失变化，必须重做全部主对照。

另可增加预算上界参考S250：相同图上纯检测监督250更新。它有更多标签曝光，只能检验“预训练能否胜过额外监督更新”的替代方案，不能宣称与主三组标签曝光完全一致。若预算紧张，先不跑该参考组。

### 置换与曝光的预检结果

当前391个训练边均可在同源、同PI/Q上下文和同视图方向内构造闭合置换，已排除已知同功能连通分量，未增加端点重复次数。但这仅证明端点次数可匹配：不同连通分量仍可能实现相同函数，门型/cut难度也需继续匹配，而且当前草案的加权端点曝光并未证明一致。

'''
 text+=f'本轮实际计算的右端点加权质量最大差为{maxdelta:.8f}。因此permutation_draft.csv明确为草案，不可直接当作合格公平组。最终需按权重层/门型/cut共同支持构造闭合置换，或三组共同缩小到合格池并重新计算源/连通锥/边权重。无法匹配的边三组共同暂缓，单列覆盖损失，不只缩小P组。\n'
 text+='''
训练前还要冻结每源和单节点的预训练重复曝光上限，三组共用相同端点及图前向计划。比较更新数与监督曝光，同时实报耗时、总节点前向/反向量和显存峰值，不能靠把零损失组跳过计算而声称预算相等。不同功能项和方差项本身保持Z组有实际更新，避免把空优化步骤当额外训练对照。

## 7. 验收标准及仍未补齐的地方

先检验加载、损失有限、梯度路径及非坍缩，再用全验证检测AP、Recall@1%/5%、正常FPR和各源配对MAE/翻转/两侧均正确率共同评价。正负根分开，所有配对按制造源先汇总；测试不得用于选样、权重或阈值。低漂移伴随木马召回下降不能算成功。三种子波动不是跨宿主置信区间。

验证正根2对仍少，尤其只有一个宿主，能展示案例与机制，不能独立支持广泛泛化结论。s35932训练正根、s15850的更多机制、验证更多源/流程和独立测试配对仍需后续补齐。本轮没有现成合格证明的部分未伪造为covered。后续应先恢复18个review查询的精确源/模型映射、检查现有宽边界候选；若仍缺证据，再另定小规模逐锥CEC预算。测试配对应按预先冻结的标签无关根规则建立，不能按测试正例位置补样。

本轮数据层完成，训练方案已有具体定义，但负函数证书、最终匹配置换、曝光合同及runner未实现。当前不建议直接开训，更不把本轮新增配对当作已经得到的预训练增益。

## 8. 文件入口

`_p0pilot/cec_coverage_pretrain_20261105/`：coverage_before/after.csv、flow_gaps_before.csv、query_audit.csv、candidate_projections.csv；bounded_positive_pairs/cones.json、bounded_positive_ledger.json、ENUM_CERTIFICATES.json、scalar_replay.csv；pool_pairs/cones.json、pool_weights.csv、POOL_CONTRACT.json、pool_adapter.py、POOL_COMPLETE.json；permutation_draft.csv、PRETRAIN_PROTOCOL.json。旧476主池和证明均保持原样。
'''
 target.write_text(text,encoding='utf-8')
 with (O/'positive_root_inventory.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(positive[0]));w.writeheader();w.writerows(positive)
 with (O/'adapter_preflight.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(audit[0]));w.writeheader();w.writerows(audit)
 with (O/'flow_coverage_after.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(flows[0]));w.writeheader();w.writerows(flows)
 brief='''

## 等价锥覆盖补证与等预算预训练方案（2026-11-05）

0训练/0前向/0新增SAT。穷查11个旧PO/D实现对7454观察位与127个精确无条件查询，新增8个源绑定负根（train7/val1），训练新增s15850 ctlmatcha源；18个review模型未与原plan/raw绑定，单列暂缓不改旧证明。974004旧sweep仅定位，25个当前双侧可信正根候选中固定规则选17个，3对完整PI/Q枚举1536输入并独立标量复核（含1条旧补充），净新增正根train1/val1。最终可靠功能池487=train391/val96，447分量，训练9源/验证3源；484对源绑定CEC+3对完整枚举单列。可信正根train10来自4源、val2来自2源，test0不是无木马；验证新增s38417 injzeta abc/aig10输入14/29门，仍仅1验证宿主。s35932无正根、验证nand及多流程未覆盖，不能称补齐全部。新pool_adapter487对加载通过，旧476版本不改。提出同强双分支39v3、50预训练+200检测的Z/R/P三组同预算：共同函数不同负对与防坍缩，只改零/真实/置换等价项；旧H200非公平主基线。391边置换端点次数可保，但未知同功能碰撞、门型/cut和加权曝光未过最终审计，负函数证书、最终合同与runner待实现，不开训。详见[本轮方案](等价锥覆盖缺口补证与等预算预训练方案_20261105.md)及`_p0pilot/cec_coverage_pretrain_20261105/`。
'''
 for n in ['SAT作用证明.md','SAT工作总结.md']:
  assert '## 等价锥覆盖补证与等预算预训练方案' not in (D/n).read_text(encoding='utf-8')
  with (D/n).open('a',encoding='utf-8') as f:f.write(brief)
 with (R/'10.15/99_共用资产/运行登记/运行登记表.csv').open('a',encoding='utf-8',newline='') as f:csv.writer(f).writerow([datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),'等价锥缺口补证与预训练合同方案','cec_coverage_pretrain coverage_reuse/bounded_positive_reuse/freeze_pool/publish','CPU ginvenv_gpu;0model/train/SAT','no new seeds;future42/1/2','train391/val96;test0','39v3;native484+enum3;old476 preserved',str(O.relative_to(R)),'positive10/2;9/3sources;447components;18review deferred','完成离线补证和方案','negative-function/permutation-weight audit and runner pending;one val host'])
 files={str(p.relative_to(R)):sha(p) for p in O.iterdir() if p.is_file() and p.suffix in ['.json','.csv','.py']};files[str(target.relative_to(R))]=sha(target)
 (O/'PUBLISHED.json').write_text(json.dumps(dict(report=str(target.relative_to(R)),files=files,training=0,model_forward=0,new_SAT_queries=0,adapter_loaded=487,pretraining_started=False),ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(dict(report=str(target.relative_to(R)),positive_roots={s:z['positive_pairs'] for s,z in result['by_split'].items()},permutation_weight_delta=maxdelta),ensure_ascii=False),flush=True)
def csvrows_external(path):return list(csv.DictReader(path.open(encoding='utf-8-sig')))
if __name__=='__main__':main()
