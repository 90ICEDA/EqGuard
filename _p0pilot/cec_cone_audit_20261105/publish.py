"""Publish read-only cone-proof audit; append required notes, no training/SAT."""
from pathlib import Path
import json,csv,collections,datetime
from audit import read,rows,sha,ident
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;D=R/'10.15/00_说明'
def table(rr,fields):return '\n'.join(['| '+' | '.join(fields)+' |','| '+' | '.join(['---']*len(fields))+' |']+['| '+' | '.join(str(r[k]) for k in fields)+' |' for r in rr])
def main():
 assert not (O/'COMPLETE.json').exists();a=read(O/'AUDIT_COMPLETE.json');v=read(O/'CONES_VERIFIED.json');ad=read(O/'ADAPTER_VERIFIED.json');tiers=read(O/'LABEL_INDEPENDENCE_TIERS.json');pairs=read(O/'FUNCTIONAL_PAIR_CONTRACT.json')['pairs'];cones={c['cone_id']:c for c in read(O/'cones.json')};enumeration={r['pair_id']:r for r in rows(O/'cone_enumeration.csv')};strict=set(tiers['pools']['strict_label_blind']['pair_ids']);pairtable=[];pooltable=[]
 for name,by in tiers['by_pool'].items():
  for sp,z in by.items():pooltable.append(dict(pool=name,split=sp,pairs=z['pairs'],source_objects=z['sources'],physical_members=ad['by_split'][name+':'+sp]['unique_physical_members']))
 for p in pairs:
  x,y=cones[p['left_cone']],cones[p['right_cone']];pairtable.append(dict(split=p['split'],source_object=p['source_object'],source_output=x['output_cell']+'.'+x['output_pin'],partner_output=y['output_cell']+'.'+y['output_pin'],left_cells=len(x['members']),right_cells=len(y['members']),shared_inputs=enumeration[p['pair_id']]['shared_inputs'],strict_blind=p['pair_id'] in strict,pair_id=p['pair_id']))
 with (O/'reliable_pair_inventory.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(pairtable[0]));w.writeheader();w.writerows(pairtable)
 # Dependency bindings checked again before publishing, including unchanged old evidence.
 for name,hh in a['inputs'].items():assert sha(R/name)==hh,name
 for name,hh in tiers['producer_sha'].items():assert sha(R/name)==hh,name
 target=D/'已有区域对应_无标签逐锥CEC资格与可靠配对审计_20261105.md';text=['# 已有区域对应：无标签逐锥CEC资格与可靠配对审计（2026-11-05）','',
 '本轮检查旧区域对应、旧SAT sweeping表和冻结盲候选，复用已有证明；不启动训练、不调用模型、不执行任何新增SAT/CEC求解进程。为检查局部锥是否真正闭合，对14对小锥做完整二值布尔枚举（最多11个共享输入、合计2834组输入赋值），不是扩展SAT搜索。未改任何原标签、旧证明、旧图或旧训练结果；未删除或移动文件。','',
 '## 1. 结论与两层“无标签”口径','',
 '**有可靠的局部功能锥配对，但数量很小，不能直接套到当前检测概率一致性。**复核55条盲候选信号引用，按源对象、raw快照/输出bit/上下文去重，得到14对非平凡组合锥（训练9、验证5），属于8个制造源对象（训练6、验证2）与4个宿主（训练3、验证1）。14个逻辑锥等价连通分量，未扩成笛卡尔配对；同宿主、同语义输入变量顺序的函数签名也为14个。','',
 '需要区分：A层接受条件不看节点y/trusted，但第5/6轮视图曾按已知control/noncontrol分层预选；B层进一步只收第7轮在限定未用视图池中按哈希选视图/锥根的配对。严格池默认采用B层，不能将14对笼统写成全流程完全盲发现。第7轮也排除了已选视图及keep实现，是限定候选池内盲选，不宣称对整个工程无偏抽样。','',
 table(pooltable,['pool','split','pairs','source_objects','physical_members']),'',
 '默认strict_label_blind只有训练2对、验证3对，来自3源对象/3宿主；补充node_label_independent_stratified_views含训练9对、验证5对。验证绝不进入训练，测试0对。制造source对象与独立物理宿主不是同一分母，不能把8个制造对象称为8个独立宿主。','',
 '## 2. 清点哪些旧证据、为什么不直接用大行数','',
 '| 证据 | 现有规模 | 本轮处理 |\n|---|---:|---|\n| node_pairs_sat_node.csv | 974004行；630207 proved | 统计全部旧行，保留历史口径；不直接当当前逐锥证明 |\n| 其中同实例proved | 624212行 | 可供后续来源重绑定，但本轮未逐条重审其所有旧批次 |\n| 其中跨实例proved | 5995行 | 不自动视为同源实现或同安全对象 |\n| region_pairs_v3.csv | 483行 | 全部依赖Trojan前缀划区，严格标签无关区域池纳入0 |\n| 已冻结盲候选关系 | 40条；11条完整/29条未对应 | 不扩大，不提升29条阻塞状态 |\n| 11条完整关系的信号引用 | 55条，复用52个不同查询 | 14对两端有组合逻辑；41条至少一端只是PI/Q锚 |\n| 第8/9轮机制角色配对 | 8条 | 按插入角色挑选，单列排除 |','',
 '`region_pairs_v3`的生成器明确先过滤两边Trojan*网名，再按旧proved边分组；483行n_boundary_sigs全部0，region_role直接赋trusted_trojan。这不是逐锥输入输出合同，也不是不依赖木马身份的区域发现。`region_partition.py`的名字语义分区及`region_methods.py`的结构DFF/PO区域可作为后续候选构造方式，但区域划分或alignment平移本身不能代替跨实现逐锥证明。','',
 '630207是旧证明模型/假设下的信号行数，不等于630207个独立锥或当前可加载样本。旧CSV没有逐行原始source/model/context哈希绑定，证明脚本含equiv_simple/induct不同模式，工程还曾修复canonical/keep视图混用。不能不重绑定就套到当前named-PI/physical-Q合同；这不是宣布全部旧证明无效，而是本轮未将它们自动升级。14是本轮已确认的可靠下限，不是证明整个工程最多只能有14对。','',
 '## 3. 已有证明怎样复用','',
 '55条引用逐条检查原source与raw快照SHA、model.v/run.ys/run.log哈希、精确query_id与SAT参数、对应日志块SUCCESS且非TIMEOUT。原生模型从各自raw重新生成；输出探针按被证明的实际bit核对，不按关系slot号碰巧相同复用。52个不同原查询全部重新检查，共享环境wrapper确实把同一env送到两边，无额外节点标签、复位或强制输入假设。','',
 '证明边界是同名PI及不受限物理Q的二值组合上下文；QN明确为同一物理Q的反相。它不证明初态可达、复位可达、自然时序触发或全设计PO/D整体等价。局部根输出等价也不要求全设计比较一定已proved；两种口径不能混用。','',
 '本轮从每个被证明输出bit反向提取最大组合锥，遇PI/物理Q停止，保留Q/QN极性及输出pin；独立检查单驱动、闭合边界、支持门语义、无组合环与完整当前图落点。14对两边实际PI/Q语义锚集合都可对齐，没有未映射内部成员。其他41条引用因至少一边是PI/Q锚或单侧只有状态，不计为两端非平凡区域。','',
 '随后对14对逐一构造局部CEC miter文件，未执行求解器。共享输入最多11个，完整枚举2834组输入，两边全部相同且均非恒定函数；因此获得的是最大PI/Q边界局部锥等价核验，不是旧四内部cut探针可以随意独立赋值的证明。14对中13对两侧至少2门，1对是1门/1门简单逻辑；不以单状态锚增加区域数。','',
 '## 4. 逐对清单','',
 table(pairtable,['split','source_object','source_output','partner_output','left_cells','right_cells','shared_inputs','strict_blind']),'',
 '原11条关系仍是训练9/验证2；额外的3个验证锥来自其中已有cut观察点的完整PI/Q组合锥，并非新增3条源关系。因此不能把完整关系覆盖率11/40改写成14/40，也不能将验证cut锥转作训练。所有14对按raw SHA+输出bit、上下文和同源对象消除了同bit别名及重复引用，并按已观测等价边合并逻辑锥分量，没有借传递闭包制造更多配对。','',
 '## 5. 什么可以训练、什么仍不能训练','',
 '| 用法 | 本轮结论 |\n|---|---|\n| 严格池的功能输出/锥功能表示辅助一致性数据 | 训练2对、验证3对；证据及数据适配器就绪 |\n| 放宽到节点标签不参与接受、但视图分层已知的补充池 | 训练9对、验证5对；必须明确来源分层 |\n| 当前节点木马概率直接一致 | 允许0：CEC不证明相同安全角色 |\n| 整个锥所有内部节点一一对齐或标签传播 | 允许0：实现拆合及内部角色未被证明一致 |\n| 当前39维检测模型整段隐藏向量必须相同 | 允许0：需要另行定义功能分量，不能声称等价证明覆盖安全/位置表征 |\n| 完整时序或测试泛化保证 | 无：不在证明范围、测试无配对 |','',
 '新pair_adapter.py只提供当前v3图上的组合成员、精确输出bit/pin与PI/Q语义边界，不读取y/trusted。默认严格池，必须显式选择train/val/test，拒绝all；当前图坐标、物理成员、边界信息已预检，严格训练31个/验证26个唯一物理成员，补充训练209个/验证37个。节点多次出现在不同锥中并不构成独立源证据。原合同training_pair_allowed=false等历史字段保持，新的FUNCTIONAL_PAIR_CONTRACT只授予功能数据资格，不把旧检测一致性禁用项翻成true。','',
 '尚未实现功能分支、辅助目标及防坍缩协议，也未接入训练runner。因此“数据与功能证据就绪”不等于已有可以直接启动的完整训练方案。尤其不能用risk概率拉近损失代替功能一致性；同布尔功能的信号可能具有不同安全来源，功能证据不能签发正常标签。','',
 '## 6. 下一步建议','',
 '当前严格训练仅2个锥、2个源对象，不足以直接开展有说服力的GNN一致性增益实验。优先继续离线恢复旧sweep中训练侧同源批次的精确输入与证明上下文，或在已有同源视图内按DFF-D/PO锥根和固定哈希提出小批无标签候选，先核对PI/Q接口；能复用旧证明就复用，缺证据再另行明确小规模CEC预算。不应反过来按木马角色、标签或已见测试正例位置补配对。','',
 '如需做方法原型，先明确只对功能输出/独立功能表示施加一致性、保留原检测监督，并设计等预算零一致性/真实配对/置换配对对照；本轮未授权或启动该训练。默认不为了扩大数字而把补充视图分层池混称严格盲池，也不继续依靠旧483条木马前缀区域增加分母。','',
 '## 7. 可复核产物','',
 '`_p0pilot/cec_cone_audit_20261105/`：AUDIT_COMPLETE.json、CONES_VERIFIED.json、LABEL_INDEPENDENCE_TIERS.json；legacy_sweep_inventory.csv、legacy_region_exclusions.csv、candidate_reference_audit.csv、relation40_status.csv；functional_cone_pairs.json、cones.json、reused_queries.json、cone_components.csv、reliable_pair_inventory.csv；cone_enumeration.csv、cone_proof_certificates.json、cone_truth_tables.npz、local_miters/*.v/*.ys（未执行）；FUNCTIONAL_PAIR_CONTRACT.json、pair_adapter.py、adapter_preflight.csv、ADAPTER_VERIFIED.json。所有证明输入重新核对哈希，原始证据未改。','']
 target.write_text('\n'.join(text),encoding='utf-8')
 brief='\n\n## 已有对应的无标签逐锥CEC资格审计（2026-11-05）\n\n0训练/0模型/0新增SAT，旧图标签证明不改。旧sweep974004行/630207proved（同实例624212、跨实例5995）不直接升级当前逐锥证据；region_pairs_v3的483行均依赖Trojan前缀、无真实边界合同，严格标签无关池0。复核11条盲关系55信号引用、52个不同旧查询，原raw/模型/参数/日志重新绑定，提取14对完整PI/Q组合锥（训练9/验证5，8制造源、4宿主），41条PI/Q锚不计区域、8机制配对排除。14对最多11自由输入，完整布尔枚举2834组全部相同且非恒定，局部miter仅生成未执行；未把最大PI/Q锥等价写成任意内部cut独立等价。14对节点接受条件不看y/trusted，但r5/r6视图有人工control/noncontrol分层；更严格r7哈希盲池仅训练2对2源、验证3对1源、测试0，适配器默认此池，补充池明确另列。11/40关系覆盖不变，新增3个验证锥是既有cut观察点，不是新源关系。当前图功能数据接口已预检；检测概率/全节点embedding一致性及标签传播允许0，功能头与防坍缩方案未实现，未启训练。详见['+target.stem+']('+target.name+')及`_p0pilot/cec_cone_audit_20261105/`。建议先小范围离线恢复同源旧证明上下文与PI/Q边界，不按标签或测试位置扩样。\n'
 for name in ['SAT作用证明.md','SAT工作总结.md']:
  with (D/name).open('a',encoding='utf-8') as f:f.write(brief)
 with (R/'10.15/99_共用资产/运行登记/运行登记表.csv').open('a',encoding='utf-8-sig',newline='') as f:csv.writer(f).writerow([datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),'已有区域对应无标签逐锥CEC资格','cec_cone_audit audit/verify_cones/preflight/publish.py','CPU read-only;0 SAT/model/train;14 bounded Boolean enumerations','none','train/val only;test0','39v3 graph;old52 proofs;PI/freeQ;no label acceptance',str(O.relative_to(R)),'14 cones9/5;strict2/3;8sources;legacy483 excluded','完成离线审计','strict training2 too small;functional data only;no detector-risk equivalence'])
 files={str(p.relative_to(R)):sha(p) for p in O.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name not in ['COMPLETE.json','PUBLISHED.json']};files[str(target.relative_to(R))]=sha(target);(O/'COMPLETE.json').write_text(json.dumps(dict(training=0,model_forward=0,new_SAT_queries=0,files=files),ensure_ascii=False,indent=2),encoding='utf-8');(O/'PUBLISHED.json').write_text(json.dumps(dict(report=str(target.relative_to(R)),sha=sha(target),complete_sha=sha(O/'COMPLETE.json')),ensure_ascii=False,indent=2),encoding='utf-8');print('Published audit and updated both notes',flush=True)
if __name__=='__main__':main()
