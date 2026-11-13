"""Freeze PO evaluation support and publish loader/native-reach audit. No predictions."""
from pathlib import Path
import numpy as np
import json,csv,collections,datetime
from supervision_loader import sha,read
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;D=R/'10.15/00_说明'
def rows(name):return list(csv.DictReader((O/name).open(encoding='utf-8-sig')))
def dump(name,rr):
 with (O/name).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def table(rr,fields):return '\n'.join(['| '+' | '.join(fields)+' |','| '+' | '.join(['---']*len(fields))+' |']+['| '+' | '.join(str(r[k]) for k in fields)+' |' for r in rr])
def main():
 assert not (O/'COMPLETE.json').exists();load=read(O/'LOADING_VERIFIED.json');reach=read(O/'REACH_AUDIT.json');assert reach['all_distances_match'] and reach['all_directed_edges_match'];policy=read(O/'PO_POLICY.json');weights=rows('train_reference_weights.csv');perview=rows('PO_population_per_view.csv');population=rows('PO_population.csv');names=['unreachable','PO0','PO1_2','PO3_5','PO6plus']
 # Background reference is additional to the fixed added-region/positive references.
 for dm in ['orig','trans']:
  byview=collections.defaultdict(lambda:np.zeros(5));viewsource={}
  for r in perview:
   if r['key']==dm+'_train' and r['scope']=='normal_all':byview[r['view']][names.index(r['PO_bin'])]=int(r['nodes']);viewsource[r['view']]=r['source']
  bysource=collections.defaultdict(list)
  for v,q in byview.items():
   if q.sum():bysource[viewsource[v]].append(q/q.sum())
  w=np.mean([np.mean(q,axis=0) for q in bysource.values()],axis=0)
  weights.extend(dict(domain=dm,scope='normal_all',metric='FPR',PO_bin=n,weight=float(w[j]),source_objects=len(bysource),fitting_split='train_only') for j,n in enumerate(names))
 dump('evaluation_reference_weights.csv',weights);support=[]
 for key in [dm+'_'+sp for dm in ['orig','trans'] for sp in ['val','test']]:
  for scope in ['normal_primary_added','normal_all','trojan_positive']:
   ww={r['PO_bin']:float(r['weight']) for r in weights if r['domain']==key.split('_')[0] and r['scope']==scope};pp={r['PO_bin']:int(r['nodes']) for r in population if r['key']==key and r['scope']==scope};missing=[n for n in names if ww[n]>0 and pp[n]==0];support.append(dict(key=key,scope=scope,standardized_metric_available=not missing,missing_positive_weight_bins='|'.join(missing),rule='NA if any frozen positive-weight stratum absent; never renormalize'))
 dump('standardization_support.csv',support)
 policy['status']='FINAL_FROZEN_WITH_NATIVE_REACH_AND_SUPPORT_CHECKS';policy['reference_weights_file']='evaluation_reference_weights.csv';policy['support_file']='standardization_support.csv';policy['native_reach_audit_sha']=sha(O/'REACH_AUDIT.json');policy['loader_preflight_sha']=sha(O/'LOADING_VERIFIED.json');policy['normal_background_reference']='additional train-only source-equal normal_all FPR, reported separately from manufactured added-region FPR';policy['critical_support_limit']='normal M in validation is entirely PO-unreachable; historical primary added validation130/130 and test139/142 unreachable; no validation support for active added normal controls; empty reachable strata remainNA';policy['source_native_cause']='val/test original controls are dead-output matched/deep_xor/dup; train contains4a4ctlequiv sources22reachable added nodes; no code/label fixes made';policy['inputs_frozen']={str(p.relative_to(R)):sha(p) for p in O.iterdir() if p.is_file() and (p.name.startswith('PO_membership_') or p.name in ['ROLE_PO_PAIRS.json','view_dictionary.csv','scope_availability.csv','evaluation_reference_weights.csv','standardization_support.csv'])};(O/'PO_EVALUATION_CONTRACT.json').write_text(json.dumps(policy,ensure_ascii=False,indent=2),encoding='utf-8')
 # Compact physical population summary, not an experiment-performance result.
 compact=[]
 for key in ['orig_val','trans_val','orig_test','trans_test']:
  for scope in ['normal_M','normal_primary_added','normal_all','trojan_positive']:
   rr=[r for r in population if r['key']==key and r['scope']==scope]
   if not rr:continue
   compact.append(dict(key=key,scope=scope,unreachable=sum(int(r['nodes']) for r in rr if r['PO_bin']=='unreachable'),reachable=sum(int(r['nodes']) for r in rr if r['PO_bin']!='unreachable'),total=sum(int(r['nodes']) for r in rr)))
 dump('population_reach_summary.csv',compact);boundaries=rows('manufactured_normal_boundaries.csv');sourceval=[r for r in boundaries if r['key']=='orig_val'];witness=[r for r in rows('reachable_normal_witnesses.csv') if r['key']=='trans_test'];heldstandard=[r for r in support if r['standardized_metric_available']==False];target=D/'新版五组加载预检_PO分层评价及正常区域不可达核查_20261105.md'
 text=['# 新版五组加载预检、PO分层评价及正常区域不可达核查（2026-11-05）','',
 '本轮完成实际加载器预检、PO评价合同冻结，并响应“为什么都不可达”追加独立网表检查。0训练、0模型前向、0损失调用、0反向、0SAT；未读预测、未移动或删除文件，图/标签/特征/旧结果未改。','',
 '## 1. 为什么验证M都不可达','',
 '**不是整张正常网表都不可达，也不是本轮发现PO距离算错；当前验证集新增正常逻辑的制造方式本来就是死支路。**原始验证宿主s38417t100的8个正常源视图是ctlmatcha—f、ctlxor和ctldup，没有a4ctlequiv。匹配对照的触发/载荷链输出停在CtlMA_payload等不驱动原电路的线，deep_xor停在CtrlX_dead，复制逻辑驱动CtrlD_dup*。它们读取宿主信号，但不回接宿主或PO，故没有有向输出路径。','',
 '依据不仅是制造脚本注释：对46视图从实际Verilog位别名、库输入/输出引脚重建全部有向边，并以真实输出驱动门为PO种子重新反向BFS，全部保存边和所有节点PO距离均一致。未把x39列30的既定0值作为独立种子，也未仅重复遍历同一保存图。原始验证/测试各8源的63个新增节点全部无PO路径、无新增到宿主的边；验证其中M为58个，dup为5个。','',
 table(sourceval,['source','ctl_type','new_nodes','native_reachable_new','new_to_host_edges','new_PO_drivers','terminal_output_pins']),'',
 '实际网表例子：`s38417t100__ctlmatcha_d1_s42.v`的CtlMAPD反相输出CtlMA_payload，该网既不是PO也没有消费者；上游5个新增门因此都不可达。生成器`phase2/inject_trojan.py`第81—95行构造deep_xor死线，第196—203行的默认载荷出口接dead线；匹配对照默认没有hijack_out目标。此处本轮只核对来源，不重新声称SAT等价证明。','',
 '## 2. 训练有可达正常对照，为什么验证没有','',
 '训练含4个A4可达等价对照源：rs232t1000和s15850t100各s0/s1；独立检查22个新增节点全部PO可达，含4个新增PO驱动门。其余死线对照不能替代这类对象。现有验证宿主s38417t100、测试宿主s38584t100没有相应A4可达等价源；这是数据集制造类型与留出覆盖不一致，不应靠修改PO距离或将死节点改成可达来处理。','',
 table(compact,['key','scope','unreachable','reachable','total']),'',
 '因此原始验证M58/58、变换验证M143/143不可达；历史主新增区域原始验证47/47、变换验证130/130不可达。完整正常视图仍有大量可达的宿主背景（变换验证168699个可信正常节点可达），必须与“新增木马相似正常区域”分开解释。这里的可达是数字图上的结构路径，不等同于路径已可激活或具有某安全作用。','',
 '## 3. 测试3个可达新增后代是什么','',
 '变换测试主区域共142节点，139不可达；另外3个来自同一个ctlmatchd源的abc/nand实现。原始CtlMDS2是死支路反相门，映射分别指向g_CtlMD_s2_658及g_CtlMD_s2_1088/1089。目标网表中这些门已通过g_g34464和多个寄存器连接到PO，独立路径长度分别7/9/8。','',
 table(witness,['view','name','distance','PO_driver','path']),'',
 '网表直接可见目标CtlMD_s2驱动g_g34464后进入宿主寄存器网络，证实目标结构可达。它表示变换后存在内部信号复用或来源角色变化，不能因仍带CtlMD名字、且映射只有CtlMDS2父项，就断言保持了原始死支路的同一功能角色。本轮没有SAT验证其内部功能对应，也没有将3节点扩成“已有充分可达正常对照”；独立源仍只有1个，且没有验证侧同类支持。','',
 '## 4. 实际加载器与五组合同','',
 '`_p0pilot/control_loader_po_20261105/supervision_loader.py`提供显式FiveGroupLoader，严格绑定新版预算与39维v3文件哈希。训练索引顺序为全部固定正例、公共8192、B、M、U；以0起step0—199取冻结配对表，各位置按组别仅替换N/H端点。未知域/组/种子/版本和越界步数直接拒绝，不回退旧base_mask、旧可信全掩码或旧320槽采样。加载出的图字典不暴露默认训练mask，调用者必须显式取step索引。','',
 '使用ginvenv_gpu实际检查2版本×2域×5组×200步=4000条加载记录，seed42/1/2索引逐一一致；索引int64、边界、物理/可信、正负数、G0零正常监督、固定正例、公共与块端点、200步负节点/源上限及重复分布均与独立预算台账相符。绑定89份输入文件；CPU归一化与旧加载算式逐元素一致，原门型/边/标签不变。完整两域训练图完成CPU/CUDA张量加载核对，并对每组第1/100/200步共60次GPU索引取标签核对。未构造模型或调用损失。','',
 '| 域 | 每步正例 | 每步负例 | 索引总长 |\n|---|---:|---:|---:|\n| orig | 136 | 8296 | 8432 |\n| trans | 829 | 8336 | 9165 |','',
 '这验证的是新入口的实际消费结果，现有历史训练runner未修改、也未自动接入本加载器；未来启动新五组实验必须显式使用该入口。不能继续运行旧runner就认为已采用新预算。','',
 '## 5. 冻结的PO分层评价','',
 '最终合同为PO_EVALUATION_CONTRACT.json。使用未经归一化的v3原始列30、仅物理节点；固定五档：不可达d=−1、PO0、距离1—2、3—5、≥6。辅助节点不进入档位；无效/非整数距离直接报错。分档不按验证/测试分布重选，不影响模型选模、训练特征、监督或损失。','',
 '- 每组沿用同一全局变换验证阈值算法（正例分数0.2/0.1分位及旧负例95%分位），阈值跨PO档和原始/变换侧复用，禁止每档重新调阈值。\n- 原始/变换分开报，正常全视图背景、历史可信新增区域、木马正例、木马视图背景分别报；训练/验证既有B/M/U可另列，测试未完成该分区审计，标NA，不能自动归U。\n- 先算每视图每档比例，再在源内等视图平均，最后等源平均；每格给节点、视图、独立源数，空格为NA而非零误报/零召回。\n- 主要指标为新增正常区域源宏FPR/任意报警和木马源宏召回；AP/AUC仅在同格有正负两类时报告，单类格不报虚假的AP=1。风险排名仍相对完整视图物理节点，使用并列最差名次，不因分箱缩小排名分母。\n- 410条既有制造角色后代集合已固定坐标及双方PO档签名；联合成功使用完整集合的normal_max<threshold≤Trojan_max。混合PO档集合不裁剪为“同档配对”，不作笛卡尔展开、也不称SAT等价对象。','',
 '参考标准化权重只来自训练集，按源等权、源内视图等权，分别冻结普通normal_all背景FPR、主新增区域FPR及木马正例召回；不给正负类强行用同一PO分布。任一正权重档在评价集缺支持，标准化总量必须NA，不能删档重归一化。每组使用相同权重与完整评价节点，不能按模型结果剔除难例。','',
 table(support,['key','scope','standardized_metric_available','missing_positive_weight_bins']),'',
 '当前新增正常区域的验证/测试均缺训练参考中的可达近PO档，因此完整参考标准化FPR不可报告；不可达档自身FPR仍可报告，完整正常背景的分层与标准化另列。不能用完整背景的可达样本弥补新增相似区域缺失，再宣称已验证可达相似正常逻辑。','',
 '## 6. 对下一步的判断','',
 '新版监督加载已准备好，PO评价也已冻结；但“都不可达”的根因是数据覆盖，应先明确实验结论范围。现有五组最多检验相同图暴露下、当前覆盖的可信正常标签，尤其死支路相似区域，对误报的作用。若研究目标要覆盖“真实功能路径上的木马相似正常逻辑”，建议下一轮先提出为留出宿主独立制造/验证可达等价正常对照的覆盖方案，不能从训练挪A4对象到验证/测试、不能按已见测试正例位置选对象；生成与重建合同应另行授权。','',
 '本轮不因此偷偷修改数据或启动训练。若后续选择先做现有数据的探索性五组，必须标注可达新增正常区域结论缺失，并把正常背景可达、相似新增不可达及木马可达/不可达结果分表，而不是用总FPR/AP替代这些边界。','',
 '证据目录：`_p0pilot/control_loader_po_20261105/`。LOADING_VERIFIED.json、loaded_indices_ledger.csv保存实际加载证据；PO_EVALUATION_CONTRACT.json、PO_membership_*.npz、PO_population*.csv、evaluation_reference_weights.csv、standardization_support.csv冻结评价；REACH_AUDIT.json、native_reach_per_view.csv、native_reach_targets.csv、manufactured_normal_boundaries.csv、reachable_normal_witnesses.csv保存独立网表复核。旧合同与旧结果未改。','']
 target.write_text('\n'.join(text),encoding='utf-8')
 brief='\n\n## 新五组实际加载、PO分层及不可达根因（2026-11-05）\n\nginvenv_gpu纯加载预检4000记录通过，89输入绑定，CPU归一化/完整图CUDA复制及60次GPU索引标签检查通过；0模型/损失/反向/训练/SAT。显式新加载器不暴露旧默认监督mask，旧runner未自动接入。PO固定−1/0/1—2/3—5/≥6，统一全局验证阈值、空档NA、训练参考权重不因评价缺档重归一化。用户追问“为何都不可达”后独立重建46视图端口/位别名/全部有向边及PO距离，全部一致：验证宿主8源新增63门均为死线制造（M58），变换验证M143/143不可达；训练4个a4ctlequiv源22新增门可达，但验证/测试无该源类型。历史主新增验证130/130、测试139/142不可达；测试3个可达后代有真实7/9/8步路径，但为同一ctlmatchd源的变换后角色复用，非充分的可达相似正常覆盖或新SAT证明。完整正常背景大量可达，不能混为新增区域。可达近PO档缺支持，新增区域标准化FPR须NA。详见['+target.stem+']('+target.name+')与`_p0pilot/control_loader_po_20261105/`。建议先审视留出宿主可达等价正常对照覆盖方案；本轮未生成新数据、未动标签/图/特征、未移动删除文件。\n'
 for name in ['SAT作用证明.md','SAT工作总结.md','正常对照贡献量化与公平实验方案_20261104.md']:
  with (D/name).open('a',encoding='utf-8') as f:f.write(brief)
 with (R/'10.15/99_共用资产/运行登记/运行登记表.csv').open('a',encoding='utf-8-sig',newline='') as f:csv.writer(f).writerow([datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),'五组实际加载预检_PO分层及不可达根因','control_loader_po preflight/freeze_po/audit_unreachable/finalize.py','ginvenv_gpu;CPU+CUDA tensors;no model/loss/train/SAT','42/1/2 index equality','train loader;all six eval inventory;val/test native audit','39v3;bounded budgets;old labels',str(O.relative_to(R)),'4000 loaded;60 CUDA;46 native match;valM143 dead;trainA4 22 reachable','完成离线预检','active added-control holdout gap;new runner not connected;no training authorization'])
 # Hash mutable research notes indirectly through final report only; keep later append possible.
 files={str(p.relative_to(R)):sha(p) for p in O.iterdir() if p.is_file() and p.name not in ['COMPLETE.json','PUBLISHED.json']};files[str(target.relative_to(R))]=sha(target);(O/'COMPLETE.json').write_text(json.dumps(dict(training=0,model_forward=0,loss_calls=0,SAT=0,predictions_read=0,files_moved_deleted=0,files=files),ensure_ascii=False,indent=2),encoding='utf-8');(O/'PUBLISHED.json').write_text(json.dumps(dict(report=str(target.relative_to(R)),sha=sha(target),complete_sha=sha(O/'COMPLETE.json')),ensure_ascii=False,indent=2),encoding='utf-8');print('Published loader/PO/native audit and appended both research notes',flush=True)
if __name__=='__main__':main()
