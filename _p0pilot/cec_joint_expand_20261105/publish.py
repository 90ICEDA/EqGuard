"""Publish recovered evidence, expanded coverage and actual bounded exposure."""
from common import *
import datetime
import importlib.util
adapter_spec=importlib.util.spec_from_file_location('cec_joint_expanded_adapter',O/'pair_adapter.py')
adapter=importlib.util.module_from_spec(adapter_spec);adapter_spec.loader.exec_module(adapter)
ExpandedConePairs=adapter.ExpandedConePairs
def mt(rr,fields):return '\n'.join(['|'+'|'.join(fields)+'|','|'+'|'.join(['---']*len(fields))+'|']+['|'+'|'.join(str(r[k]) for k in fields)+'|' for r in rr])
def main():
 assert not (O/'PUBLISHED.json').exists();report=read(O/'FINAL_COMPLETE.json');sc=read(O/'SCHEDULE_VERIFIED.json');positive=rows(O/'positive_roots.csv');summary=rows(O/'source_summary.csv');flows=rows(O/'flow_summary.csv');pairs=read(O/'final_pairs.json');cc={c['cone_id']:c for c in read(O/'final_cones.json')};before=read(PRE/'POOL_COMPLETE.json');oldids={p['pair_id'] for p in read(PRE/'pool_pairs.json')};load=[]
 for split,n in [('train',2965),('val',2273),('test',0)]:
  ds=ExpandedConePairs(split);assert len(ds)==n;assert np.isclose(sum(ds[i]['weight'] for i in range(n)),1 if n else 0)
  for z in ds:
   assert z['functional_training_data_eligible']==(split=='train') and 'root_endpoints' not in z
   for side in ['left','right']:assert not z[side]['members'].flags.writeable
   load.append(dict(pair_id=z['pair_id'],split=split,proof_method=z['proof_method'],root_pin_retained=True))
 for bad in ['all',None,'']:
  try:ExpandedConePairs(bad)
  except ValueError:pass
  else:raise AssertionError('Mixed split accepted')
 table('adapter_preflight.csv',load)
 bysplit=[]
 for sp,v in report['by_split'].items():
  prev=before['by_split'][sp];bysplit.append(dict(划分=sp,配对=f"{prev['pairs']} → {v['pairs']}",源对象=f"{prev['sources']} → {v['sources']}",可信正根=f"{prev['positive_pairs']} → {v['positive_pairs']}",正根源=f"{prev['positive_sources']} → {v['positive_sources']}",宿主=v['hosts']))
 newpos=[]
 for p in read(O/'bounded_pairs.json'):
  cs=[cc[p[k]] for k in ['left_cone','right_cone']];newpos.append(dict(划分=p['split'],来源=p['source_object'],实现='/'.join(c['view'].split('__')[-1] for c in cs),输入=p['enum']['inputs'],枚举输入数=p['enum']['patterns'],两侧门数='/'.join(str(len(c['members'])) for c in cs)))
 target=R/'10.15/00_说明/等价锥联合证明扩充_review恢复与小范围补证_20261105.md';assert not target.exists()
 text='''# 等价锥联合证明扩充、review恢复与小范围补证

2026-11-05。本轮按用户要求扩充可用等价锥，优先复用已有PO/D联合证明，恢复18个review查询，补s35932正根及验证集不同来源和流程。没有训练、模型前向或新SAT求解。小范围补证最终采用已有结构快照上的完整二值枚举，保留失败日志和旧全部结果。

## 1. 最终数量和覆盖变化

'''
 text+=mt(bysplit,['划分','配对','源对象','可信正根','正根源','宿主'])
 text+='''

合计487→5238对，净增4751对。其中4743对是从已有联合证明补齐的同源观察点，8对是限定三个实现对后新完成的正根枚举证明。5227对有源绑定CEC，11对有完整PI/Q枚举证书；不把完整枚举混写成新运行的SAT。旧487版本、476主池和475阶段接口全部保留。

按输出单元、引脚、源网表SHA、同源对象及PI/Q上下文去重；最终5191个已观测连通锥分量（训练2923、验证2268），不展开传递闭包制造边。5191不是已证明5191种不同布尔函数，也不是5191个独立电路。不同根仍可能实现同函数，锥内成员也可高度重叠，统计优先以制造源为单位。

训练宿主rs232、s15850、s35932都有正根，修复了此前s35932正根空缺。验证正根覆盖injalpha、injzeta、injepsilon、injbeta四个制造源，增加了abc/nand正根配对；但仍全部来自s38417一个验证宿主。测试仍没有本合同下的配对，未读取测试标签或按测试正例位置选择。

## 2. 已有PO/D联合证明扩充

对已绑定的11个实现对，不再沿用每对64个观察点上限，扫描7454个PO/物理D观察位。核对证明模型、脚本、日志哈希、准确query_id、SUCCESS块、共享env和观察向量顺序；原生模型由各自raw重新生成比对，第8轮机制模型明确使用intervention=0自然电路，不混用干预证明。

联合证明OR-of-XOR=0只能投影到实际包含的对应观察位；本轮没有推断任意内部网相等。现存图中可落点、两侧非平凡且已找到输出0/1见证的观察点才入池。新增4743对：训练2571、验证2172。标签不用于这一批的接受或根选择。

2034个观察引用为PI/Q或常量锚，90个不能形成当前图完整映射的非平凡双锥，12个在固定128组输入中未显示非恒定，分别暂缓。这里是观察引用次数，包含不同实现对引用，不能相加当独立对象数。128组输入只用于找到非恒定的两见证，不替代旧联合CEC。未发现变化的12个不能直接称恒定函数。

对每个新增联合证明配对保存输出0/1的明确输入索引和共享输入位图，并用另一个标量解释器逐一回放两见证，共9486组配对输入，全部两侧一致。位图算法、完整PI/Q语义标识、上下文及源快照哈希均保留，可复核。

## 3. 18个review为何恢复，是否增加独立证据

已全部恢复，去重后新增配对0。上一轮coverage_reuse脚本仅识别路径中的pairs_batch2/3，未识别reviews_batch2/3，导致复核查询错误读取第一批计划，进而模型不匹配。这是审计索引错误，不是这18个证明实际失败。

本轮改为先按model SHA和准确prove参数找到唯一原始查询，再读取该原查询的批次计划与pair_index；同时核验review和原model逐字一致、各自脚本/日志SHA、对应SUCCESS块、根bit以及当前raw重新生成结果。review目录末尾编号只是复核顺序，不是源实现对编号。18条都对应已有查询重复执行，其中不合格的PI/Q锚仍不计锥，对已有锥的引用不另加样本、不另加权。

review_recovery.csv保留每条review、原folder/query、批次、源/伙伴视图、根bit、SHA与参数，替代上一轮暂缓结论；旧表不改，说明追加纠正。

## 4. 优先缺口的小范围补证

固定三个实现对：s35932 injalpha abc/aig、验证s38417 injepsilon abc/aig、验证s38417 injbeta abc/nand。按当前两侧独立可信正根、同名信号候选、较小PI/Q边界及固定哈希，最多每对3个根、总9根；不读取预测或测试信息。候选同名仅定位，不能作为证明。

原拟短时CEC，但WSL在第一个结构准备步骤返回Wsl/E_ACCESSDENIED，未导出新raw，更没有执行SAT查询。prepare.log/prepare.ys与失败small.log原样保留；未重复调用失败任务或修改系统设置。

随后从已有k4成功批次的snapshots.json找到原结构raw，核对当前source SHA与raw SHA、当前图成员落点、PI/Q布局、全模型单驱动、无组合环、无被消费的悬空/X/Z；直接复用，没有修改k4记录。转为最多18输入、总1048576输入组合的完整二值枚举。实际只做8根、132080种输入组合，全部等价且非恒定，再用独立标量解释器逐输入回放、核对完整真值表哈希，全部通过。

'''
 text+=mt(newpos,['划分','来源','实现','输入','枚举输入数','两侧门数'])
 text+='''

因此新增正根为训练3、验证5。它们是当前自由命名PI/物理Q上下文内的完整组合函数等价，不涉及复位可达、完整时序安全或木马自然触发概率。labels_used_for_selection保留为true，labels_used_for_function_acceptance为false：标签辅助选样，接受条件仍由独立功能证明决定。

## 5. 每源规模与同源重复风险

'''
 text+=mt(summary,['split','source','pairs','components','unique_cones','unique_physical_members','max_shared_cone_membership','positive_pairs'])
 text+='''

所有划分按“源对象等权、源内同上下文连通锥等权、已观测边等权”重新计算权重，划分内和为1，训练/验证制造源互不交叉；验证对象不进入训练。大量新增来自相同电路，不能把样本量增大当统计独立性增大，也不能让数千个PO/D根压倒新补的少数源。

## 6. 已生成的受限曝光索引

为后续50次预训练原型准备了不看标签与分数的索引：每次从10个训练源各选1个已观测配对，共10对/次。源内依次打乱轮换连通锥，再在分量内轮换边；不放大为全传递配对，也不按正例单独增权。

50次总500个配对名额，覆盖381个不同配对；每源恰好50名额，单配对最多17次，任一物理节点的锥池化出现最多50次，全部实算通过。不同源使用各自视图物理坐标，不把同名节点合并。节点上限指进入锥池化的次数，不是完整图消息传播访问次数；完整图前向预算还需在训练实现中单列统计。

该索引是小预算原型采样表，不宣称50步已用遍2965个训练配对，更没有训练。Z/R可共用原端点；P组仍需完成不同函数证书、门型/cut条件和置换后加权端点曝光核验。函数负对及P组新增端点必须与此索引联合核算，当前不能把cap50当三组最终公平性已全部通过。

## 7. 实现流程覆盖

'''
 text+=mt(flows,['split','flow','pairs','sources','positive_pairs'])
 text+='''

验证从abc/aig、id/opt补入abc/nand；正根由2对/2源增至7对/4源。仍缺很多流程组合，训练rt相关覆盖仍为0，验证也未覆盖全部正常配方。新增一条abc/nand边不等于覆盖所有nand变体或所有木马机制。测试独立配对仍未建立，不能输出测试跨实现稳定性结论。

## 8. 加载与证据检查

对最终10429个使用中的锥核对成员唯一性、视图物理范围、39v3特征有限性、root row/bit/pin和两侧独立标签；最终适配器pair_adapter.ExpandedConePairs实际加载train2965/val2273/test0，拒绝all，成员数组只读，不暴露y/trusted，不允许安全标签转移、整段检测embedding或木马概率强制一致。旧图特征、旧证明、成功批次和失败日志均保留。

当前新证据合计独立标量检查4751个配对：4743个联合证明两见证回放和8个完整输入枚举回放。旧487池证书与文件哈希继续核验不变。最终数据比旧版本更适合预训练原型，但功能头、防坍缩、最终公平置换和训练runner仍未实现，本轮没有训练增益结论。

下一步宜完成函数不同负对证书及Z/R/P联合曝光预检，确认非坍缩评价，再进入seed42探索性预训练；暂不需要继续为总配对数大规模扩SAT。后续若要加强论文外推性，应优先新增独立制造源、机制和测试盲选配对，而非继续堆同源PO/D根。

## 9. 复核入口

`_p0pilot/cec_joint_expand_20261105/`：

- joint_pairs/cones.json、whole_expansion.csv、proof_projection.csv、proofs.json、review_recovery.csv、JOINT_COMPLETE.json。
- witness_contexts.json、nonconstant_witnesses.json、scalar_replay.csv；两见证只证明非恒定，功能等价由源绑定联合CEC提供。
- bounded_plan.json、bounded_results.csv、bounded_pairs/cones.json、bounded_certificates.json、BOUNDED_COMPLETE.json；完整输入枚举与精确真值表证书。
- final_pairs/cones.json、weights.csv、source_summary.csv、positive_roots.csv、flow_summary.csv、FINAL_CONTRACT.json、FINAL_COMPLETE.json、pair_adapter.py、adapter_preflight.csv。
- source_balanced_schedule.csv、SCHEDULE_VERIFIED.json；未接入训练。
- 失败证据：small.log、structures/s35932t200__injalpha_d1_s42__ys_abc/prepare.log与prepare.ys。失败在结构导出前，未产生SAT证明结果，不冒充refuted或timeout。
'''
 target.write_text(text,encoding='utf-8')
 brief='''

## PO/D联合证明扩充、review纠正与关键正根补证（2026-11-05）

0训练/0模型前向/0新SAT。复用11个PO/D联合证明7454观察位，取消64点旧上限，新增4743对（train2571/val2172），各有明确输出0/1见证并独立标量回放9486输入；见证不替代CEC。18个review全部恢复，原因是上一轮路径批次解析漏掉reviews_batch2/3，原model SHA+参数定位原查询后绑定通过；均为旧查询复核，新增独立配对0，纠正“18条未绑定暂缓”但不改旧表。限定3个实现对/最多9根补证时WSL准备阶段E_ACCESSDENIED，失败日志保留、未执行SAT；改复用k4成功raw并完整枚举8根132080输入，逐输入独立标量复核通过：s35932 injalpha abc/aig新增3正根，验证injepsilon abc/aig2根、injbeta abc/nand3根。最终5238=train2965/val2273/test0，5227源绑定CEC+11完整枚举，5191已观测连通分量非独立函数数；训练10源/验证5源，正根13来自5源/7来自4源，训练3宿主均有正根，验证仍1宿主。最终10429锥图坐标和5238对加载通过，旧487/476/475及k4成功结果不改。已生成50步每源1对索引：10对/步、500名额381唯一配对、单对最多17次、物理节点锥池化最多50次；不是完整图访问次数，负函数及P组还需联合曝光审计，不宣称训练就绪。详见[本轮报告](等价锥联合证明扩充_review恢复与小范围补证_20261105.md)及`_p0pilot/cec_joint_expand_20261105/`。下一步先做不同函数证书与Z/R/P最终公平预检，暂不为总数扩大SAT。
'''
 for name in ['SAT作用证明.md','SAT工作总结.md']:
  path=R/'10.15/00_说明'/name;assert '## PO/D联合证明扩充、review纠正与关键正根补证' not in path.read_text(encoding='utf-8')
  with path.open('a',encoding='utf-8') as f:f.write(brief)
 with (R/'10.15/99_共用资产/运行登记/运行登记表.csv').open('a',encoding='utf-8',newline='') as f:csv.writer(f).writerow([datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),'联合PO/D扩充和review精确恢复及关键正根补证','cec_joint_expand expand_joint/bounded_enumeration/finalize/publish','ginvenv_gpu Python CPU;0train/forward/SAT;WSL raw prep denied retained','fixed hash;future42/1/2','train2965/val2273;test0','39v3;CEC5227+enum11;old487 retained',str(O.relative_to(R)),'5238pairs;positive13/7;10/5sources;18reviews duplicate;nodepool<=50','完成数据扩充及曝光索引','pretrain runner/functional negatives/permuted weighted exposure pending;one val host'])
 files={str(p.relative_to(R)):sha(p) for p in O.iterdir() if p.is_file() and p.suffix in ['.json','.csv','.py']};files[str(target.relative_to(R))]=sha(target)
 write('PUBLISHED.json',dict(report=str(target.relative_to(R)),files=files,training=0,model_forward=0,new_SAT_queries=0,loaded_pairs=len(load),source_schedule_preflight=True,training_ready=False))
 print(json.dumps(dict(report=str(target.relative_to(R)),pairs=len(load),by_split=report['by_split']),ensure_ascii=False),flush=True)
if __name__=='__main__':main()
