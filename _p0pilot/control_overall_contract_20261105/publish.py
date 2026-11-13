"""Publish audited review-only contract; append notes, never train or run SAT."""
from pathlib import Path
import csv,json,hashlib,datetime,collections
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;D=R/'10.15/00_说明'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(n):return list(csv.DictReader((O/n).open(encoding='utf-8-sig')))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def table(rr,fields):
 return '\n'.join(['| '+' | '.join(fields)+' |','| '+' | '.join(['---']*len(fields))+' |']+['| '+' | '.join((format(x[k],'.6f') if isinstance(x[k],float) else str(x[k])) for k in fields)+' |' for x in rr])
def main():
 assert (O/'BUDGET_VERIFIED.json').exists();assert not (O/'PUBLISHED.json').exists(),'already published'
 c=read(O/'FIVE_GROUP_CONTRACT.json');part=rows('partition_summary.csv');mat=rows('matching_summary.csv');bud=rows('group_budgets.csv');blocks=rows('block_budgets.csv');vm=rows('view_dictionary.csv');cv=rows('candidate_views.csv');out=[];balance=[];uq=[];ranges=[];hostsummary=[]
 for dm in ['orig','trans']:
  ss=[r for r in rows('budget_per_update.csv') if r['domain']==dm and r['arm']=='G0'];unique=[int(r['unique_negative']) for r in ss];repeat=[int(r['repeated_negative_entries']) for r in ss]
  ranges.append(dict(domain=dm,unique_negative_per_update_min=min(unique),unique_negative_per_update_max=max(unique),repeated_entries_min=min(repeat),repeated_entries_max=max(repeat)))
 groups=collections.defaultdict(list)
 for rr in rows('matching_by_source_view.csv'):groups[(rr['domain'],rr['host'],rr['recipe'],rr['category'])].append(rr)
 for (dm,host,recipe,category),rr in sorted(groups.items()):hostsummary.append(dict(domain=dm,host=host,recipe=recipe,category=category,candidates=sum(int(r['candidates']) for r in rr),geometric_support=sum(int(r['geometric_support']) for r in rr),matched=sum(int(r['matched']) for r in rr),sources=len({r['source'] for r in rr if int(r['matched'])}),views=sum(int(r['matched'])>0 for r in rr)))
 for key in ['orig_train','trans_train','orig_val','trans_val']:
  with np.load(O/('normal_'+key+'.npz')) as z:n={k:z[k] for k in z.files}
  vmap={int(v['view_id']):v for v in vm if v['key']==key}
  for rc in sorted(set(map(int,n['reason'][n['category']==2]))):
   ii=np.flatnonzero((n['category']==2)&(n['reason']==rc));uq.append(dict(key=key,reason=rc,nodes=len(ii),sources=len({vmap[int(n['view_id'][i])]['source'] for i in ii}),views=len(set(map(int,n['view_id'][ii])))))
 for dm in ['orig','trans']:
  key=dm+'_train';p=np.load(O/('matching_'+key+'.npz'));s=np.load(O/('supervision_'+key+'.npz'));vmap={int(v['view_id']):v for v in vm if v['key']==key};v3=read(R/'_p0pilot/control_boundary_v3_20261104/input_contract.json');x=np.load(R/v3['shared_inputs'][key]['folder']/'x39.npy',mmap_mode='r');norm=np.load(R/'_p0pilot/control_boundary_v3_20261104/normalization.npz')
  for k,name in enumerate(['B','M','U']):
   jj=s['category']==k;nn=np.clip((x[s['N'][jj],25:]-norm['mean'][25:])/norm['std'][25:],-10,10);hh=np.clip((x[s['H'][jj],25:]-norm['mean'][25:])/norm['std'][25:],-10,10);dd=np.sqrt(np.mean((nn-hh)**2,axis=1));mean_diff=np.abs(nn.mean(0)-hh.mean(0))
   balance.append(dict(domain=dm,category=name,unique_pairs=int(jj.sum()),rms_median=float(np.median(dd)),rms_p95=float(np.quantile(dd,.95)),rms_max=float(dd.max()),largest_abs_mean_gap_train_z=float(mean_diff.max()),largest_gap_column=int(25+mean_diff.argmax()),normal_sources=len({vmap[int(vi)]['source'] for vi in s['Nview'][jj]}),H_sources=len({vmap[int(vi)]['source'] for vi in s['Hview'][jj]})))
 for name,rr in [('U_reason_breakdown.csv',uq),('match_balance.csv',balance),('budget_unique_ranges.csv',ranges),('matching_by_host_recipe.csv',hostsummary)]:
  with (O/name).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
 title='正常对照整体作用：B/M/U审计与五组公平实验合同（2026-11-05）';target=D/'正常对照整体作用_五组公平实验合同_20261105.md'
 out=['# '+title,'','本轮只完成候选血缘审计、训练侧匹配、200步预算预检及合同准备；0训练、0模型前向、0 SAT。未更改标签、图、39维v2/v3、旧训练结果或SAT成功批次。合同状态为待审视，不能视为训练已授权。','',
 '## 1. 本轮要回答什么','',
 '在图输入、正负监督预算及训练配置一致时，来自正常对照网表的负标签是否有用；普通正常宿主背景与制造的木马相似正常区域分别贡献多少。G0从公共监督移除全部正常对照标签，旧H组已有大量正常标签，不能作为本实验G0。五组均输入相同的完整训练图，正常对照节点仍参与消息传递和批归一化，因此检验的是相同图暴露下的正常对照标签监督作用，不能宣称“加入正常图数据的全部作用”。','',
 '## 2. 候选定义及覆盖','',
 '- B：正常对照中的纯宿主来源节点。变换侧还要求新增区域追踪完整，或已有干净参考结构完全相等的消除证据；否则即使现有父节点像宿主，也进入U。\n- M：制造类型matched/deep_xor的新增正常区域，且当前节点具有纯新增来源。无需存在木马配对伙伴，也不再局限于旧116/233功能边界池。它表示制造的木马相似区域，不表示已证明实现某个木马功能或必定PO可达。\n- U：仍有原可信负标签，但属于dup等其他新增、宿主/新增混合、追踪不完整或分类未明的部分。U不是未打标签节点，不能将其全部称为木马相似正常逻辑。\n- H：严格从木马训练视图选取的可信负标、纯宿主来源、且该视图木马新增追踪完整的背景节点；不是从正常对照中取“普通负例”。','',
 table(part,['key','views','sources','physical','trusted_negative','B','M','U','excluded_untrusted']),'',
 'B/M/U逐节点互斥、并集严格等于当前正常对照物理可信负标。所有辅助节点和旧不可信节点不参与监督；没有扩张掩码或把“covered”当可信标签。验证集仅审计分类与评价可用性，不参与匹配或采样。测试节点、预测分数、测试正例位置均未用于候选选择。','',
 '## 3. 与木马视图宿主背景的匹配','',
 '训练侧限定同宿主、同实现流程（原始侧orig；变换侧op）、相同25类门型；使用v3训练归一化的14维结构/拓扑特征，截断范围±10，匹配RMS≤2。每个H至多匹配一个正常节点，三类之间不复用。至少保留各匹配层一半严格H作公共监督；优先M，余下B/U分配并回收空配额。正常源对象轮转排序，不按风险分数挑选。','',
 table(mat,['domain','category','candidates','unrestricted_same_stratum_caliper_support','unique_matched','matched_source_objects','matched_views','no_H_stratum','outside_caliper','common_reservation_or_bounded_matching']),'',
 '“几何支持”是在不限制H占用时至少存在一个合格H，不能与一对一匹配覆盖混用。无同层H和超距离是当前合同下不可匹配；预留容量、配额和有界贪心未分配只是暂未纳入，不证明不存在更优匹配。本轮不是最大匹配覆盖求解。查询只复用完全相同的浮点特征，不做舍入，不放宽距离阈值；原始侧已完成结果复用并重新校验。','',
 table(balance,['domain','category','unique_pairs','rms_median','rms_p95','rms_max','largest_abs_mean_gap_train_z','largest_gap_column']),'',
 '上述均值差以训练标准差为单位，不是配对后样本方差标准化的SMD；同层匹配和RMS门槛不等于14列分布完全一致，残差须随结果报告。每个独立源对象/视图的覆盖见matching_by_source_view.csv，逐对坐标和宿主、流程、门型见matched_pairs.csv。','',
 '## 4. 五组替换合同','',
 '| 组别 | B块 | M块 | U块 | 主要比较 |\n|---|---|---|---|---|\n| G0 | H_B | H_M | H_U | 无正常对照标签基线 |\n| GB | B | H_M | H_U | GB−G0：普通正常背景 |\n| GM | H_B | M | H_U | GM−G0：木马相似正常区域 |\n| GBM | B | M | H_U | M在B上的增量及交互 |\n| GAll | B | M | U | GAll−G0：可匹配三类整体；GAll−GBM：U增量 |','',
 '公共正例保留全部原可信物理木马正标，不改标签、不按可达性剔除、不引入正例保护或角色调权。公共负例只来自木马视图，排除所有已配对H端点；配对H只在相应替换块使用。木马视图中不满足严格H资格的原可信负标仍可作为已有公共分类监督，不能将其称为纯宿主H。三类正常端点和全部H端点唯一，且与公共负例互斥。','',
 table(bud,['domain','arm','positive_entries','common_negative_unique','B_entries','M_entries','U_entries','total_negative_entries','normal_control_entries','negative_unique_over_200']),'',
 '保留上一轮每域每步负条目预算：orig110230、trans420365；正例136/829不变。由于G0可用独立木马负节点少于历史包含正常对照的基座，所有五组均需重复采样。本合同不把条目数当独立节点数，也不把旧结果充当同协议基线。五组每一步的正负条目、独立负节点数、每节点重复次数分布均相同，200步总独立负节点预算亦相同；实际节点内容按上表成对替换。','',
 table(blocks,['domain','block','unique_pairs','sources','views','entries_per_update','entries_200','min_visits_200','max_visits_200']),'',
 '预算提案：每侧M块320条/步沿用此前额外监督规模；剩余负条目按B/U配对池规模分配。各块按正常独立源等额、视图循环、节点固定打乱后循环；同一配对序列供五组及三个模型种子使用，200步覆盖全部配对端点。监督条目重复是明确的权重设计，不增加独立证据。B/M/U块预算不相等，GB与GM不能直接解释为每单位预算下哪类更有效；本五组首先回答给定预算下的贡献及交互。若要研究等量B/M效率，需另设剂量实验。','',
 '每步独立负节点数及重复条目范围（五组严格相同；独立节点数不要求跨步骤恒定）：','',table(ranges,['domain','unique_negative_per_update_min','unique_negative_per_update_max','repeated_entries_min','repeated_entries_max']),'',
 '## 5. 暂不纳入和结论边界','',
 '- 训练变换正常对照537839个、验证407617个物理节点不在旧可信掩码内，全部排除，不借源网表全负事实自动扩标签。\n- 变换训练146341个木马视图可信负标中，严格H140197个；19个非纯宿主/混合来源、6125个新增追踪不完整节点不用于H替换。它们的原监督身份保持，继续留在公共分类监督。\n- B/M/U的未匹配节点按逐源表及reason20/21/22/23列出，不借用跨宿主、不同实现流程、不同门型或超距离H填补。\n- 被变换消除的新增正常对象没有可评节点，不能记为零误报；混合/未知来源在U中单独报告。M没有相应木马制造伙伴也不因此被排除，但配对联合成功指标仅在实际存在可靠伙伴的子集报告。\n- 原始侧/变换侧独立报告，不假定同一个源对象的两个实现是两个独立证据。种子不替代独立宿主，重复视图不放大源对象样本量。\n- GAll仅代表本轮可匹配共同支持集的三类整体监督，不代表所有正常网表、全部不可信节点或全部制造区域均已覆盖。既有测试已多次查看，后续结果仍属探索性。','',
 'U细分原因（5其他新增、6混合、7新增追踪不完整、8分类未明、9跨源/未知/正父类）：','',table(uq,['key','reason','nodes','sources','views']),'',
 '## 6. 固定训练与评价规则（尚未执行）','',
 '若后续授权，使用ginvenv_gpu、39维v3、不加SAT；dual_mix_post_cat，split29、hidden64、2+2分支及1层融合后GIN，46620参数；seed42/1/2对应旧冻结初始化，五组各200次，Adam lr0.0002、weight_decay0.001、BF16、clip1。ASL+1.4 soft-miss平方保持原实现，两域分别反向后同一次更新，不加等价一致性、不引入保护项。全部图、边、标签、掩码和训练归一化相同；逐文件哈希写入JSON合同，核对父合同36份数组未变化。未来加载必须显式使用本轮监督索引，不能套用旧base_mask。','',
 '每5次按旧可信__inj木马验证视图平均AP选模。主操作点继续使用变换验证可信正例分数的0.2分位数（method=lower），另报0.1分位数及旧负例95%分位操作点；各组应用同一算法，不为某组特别调整。此规则是节点池召回校准，不等于源对象宏召回精确80%/90%；两者必须同时报告，禁止再把量化后的源宏召回目标暗中加作保护阈值。','',
 '主结果同时给出：源对象宏平均新增正常区域FPR/报警率、区域风险排名、木马源/角色召回及配对联合成功；辅以全体可信节点AP和普通背景FPR。B/M/U分别报告完整可评集及共同支持子集，不因训练未匹配就从评价全表删掉难例。源/角色结果与节点量分开，报告三种子的配对差；不能仅凭正常降分声称有用，木马召回变化必须同表呈现。交互按GBM−GB−GM+G0逐指标计算，注意FPR下降为好而召回上升为好。','',
 '## 7. 可复核文件','',
 '`_p0pilot/control_overall_contract_20261105/`：PARTITION_COMPLETE.json、MATCHING_COMPLETE.json、FIVE_GROUP_CONTRACT.json、BUDGET_VERIFIED.json；partition_summary.csv、matching_summary.csv、matching_by_source_view.csv、matched_pairs.csv、match_balance.csv；group_budgets.csv、block_budgets.csv、budget_per_update.csv、source_exposures.csv；逐域supervision和三块schedule/units。匹配端点重新独立核查标签、物理坐标、同宿主/流程/门型、真实RMS，200步预算逐步验证，并在第1/100/200步实际构造五组索引核对重复次数分布。','',
 '下一步应先审视覆盖限制、B/M/U块剂量及重复监督比例；确认合同后才准备与核验训练加载器。本轮没有创建自动训练队列或启动SAT。','']
 target.write_text('\n'.join(out),encoding='utf-8')
 brief='\n\n## 正常对照整体作用五组合同准备（2026-11-05）\n\n已完成B/M/U来源审计、仅训练侧与木马视图纯宿主H匹配及五组200步监督预算预检，0训练/0前向/0SAT。G0移除全部正常对照标签；GB、GM、GBM、GAll按配对块替换，所有组同图、正负条目/独立节点/重复次数预算，原标签和结果不改，不引入正例保护。'
 for dm in ['orig','trans']:
  q=c['domains'][dm];brief+=f"{dm}匹配B/M/U={q['paired_unique']['B']}/{q['paired_unique']['M']}/{q['paired_unique']['U']}；每步正/负={q['positive']}/{q['negative_entries']}。"
 brief+='覆盖限于可匹配共同支持集，未匹配区分无同层H/超距离与容量或贪心暂未分配；变换训练537839旧不可信正常节点不提升标签。B/M/U块预算不相同，不能将GB/GM直接称为等量类型效率比较；旧H不能作为G0。此前正例保护/角色调权建议不作为本实验路线。详见[五组合同]('+target.name+')及`_p0pilot/control_overall_contract_20261105/`。合同待审视，未启动训练队列。\n'
 for name in ['SAT作用证明.md','SAT工作总结.md','正常对照贡献量化与公平实验方案_20261104.md']:
  with (D/name).open('a',encoding='utf-8') as f:f.write(brief)
 reg=R/'10.15/99_共用资产/运行登记/运行登记表.csv'
 with reg.open('a',encoding='utf-8-sig',newline='') as f:csv.writer(f).writerow([datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),'正常对照整体作用B/M/U五组合同','control_overall_contract_20261105 partition/match/budget/publish.py','CPU only;0 training/model/SAT','none;future42/1/2','train matching;val audit;no test selection','39v3;fixed old labels;five paired budgets',str(O.relative_to(R)),'G0 no control labels;five arms identical per-step P/N/unique/repeats','完成合同待审视','not training authorization;unmatched/exclusions documented'])
 files={str(p.relative_to(R)):sha(p) for p in O.iterdir() if p.is_file() and p.name not in ['PUBLISHED.json','COMPLETE.json']}
 files[str(target.relative_to(R))]=sha(target)
 (O/'COMPLETE.json').write_text(json.dumps(dict(training=0,model_forward=0,SAT=0,labels_modified=False,files=files),ensure_ascii=False,indent=2),encoding='utf-8');(O/'PUBLISHED.json').write_text(json.dumps(dict(report=str(target.relative_to(R)),sha=sha(target),complete_sha=sha(O/'COMPLETE.json')),ensure_ascii=False,indent=2),encoding='utf-8');print(target,flush=True)
if __name__=='__main__':main()
