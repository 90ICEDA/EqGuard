"""Publish the final bounded offline contract and append research notes."""
from pathlib import Path
import csv,json,hashlib,datetime
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;D=R/'10.15/00_说明'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(name):return list(csv.DictReader((O/name).open(encoding='utf-8-sig')))
def table(rr,keys):
 def fmt(v):return format(v,'.6f') if isinstance(v,float) else str(v)
 return '\n'.join(['| '+' | '.join(keys)+' |','| '+' | '.join(['---']*len(keys))+' |']+['| '+' | '.join(fmt(r[k]) for k in keys)+' |' for r in rr])
def main():
 assert (O/'VERIFIED.json').exists() and (O/'STRATA_VERIFIED.json').exists();assert not (O/'PUBLISHED.json').exists();c=read(O/'CONTRACT.json');verified=read(O/'VERIFIED.json');c['status']='OFFLINE_FAIRNESS_VERIFIED_NOT_AUTHORIZED_TO_TRAIN';c['verification_sha']=sha(O/'VERIFIED.json');c['strata_verification_sha']=sha(O/'STRATA_VERIFIED.json');c['supersedes']=['control_overall_contract_20261105 historical draft budget','control_budget_v2_20261105 preliminary schedule without all-source exposure condition'];(O/'EXPERIMENT_CONTRACT.json').write_text(json.dumps(c,ensure_ascii=False,indent=2),encoding='utf-8')
 mainbudget=[r for r in rows('group_budgets.csv') if r['variant']=='main_fanout05'];coverage=[r for r in rows('coverage.csv') if r['variant']=='main_fanout05'];balance=[r for r in rows('balance.csv') if r['block']=='M'];held=[r for r in rows('M_source_coverage.csv') if r['variant']=='main_fanout05' and r['source_status']=='fully_held_fanout'];u=[r for r in rows('U_actual_exposure.csv') if r['variant']=='main_fanout05'];allsource=[r for r in rows('source_exposure_two_domains.csv') if r['variant']=='main_fanout05'];maxsource=max(int(r['negative_entries_two_domains_200']) for r in allsource);maxstep=max(int(r['max_entries_two_domains_per_update']) for r in allsource);maxextra=max(int(r['extra_entries_200']) for r in rows('source_exposure_actual.csv') if r['variant']=='main_fanout05')
 concise=[]
 for dm in ['orig','trans']:
  for variant in ['sensitivity_wideM','main_fanout05']:
   z=next(r for r in balance if r['domain']==dm and r['variant']==variant and r['scope']=='actual_200_exposure');concise.append(dict(domain=dm,variant=variant,M_pairs=int(z['pairs']),signed_fanout_mean_z=float(z['fanout_signed_train_z']),mean_abs_fanout_z=float(z['fanout_abs_train_z']),normal_twoedge_count_mean=float(z['twohop_count_normal_mean']),H_twoedge_count_mean=float(z['twohop_count_H_mean']),largest_14d_mean_gap=float(z['largest_14d_mean_gap']),largest_gap_column=z['largest_gap_column']))
 target=D/'正常对照五组预算修订与二跳扇出复核_20261105.md'
 text=['# 正常对照五组预算修订与二跳扇出复核（2026-11-05）','',
 '本轮仅复用训练侧候选、映射、39维v3与已有匹配结果，完成新采样表、独立二跳复算及离线公平性检查。0训练、0模型前向、0 SAT；无文件删除或移动，原标签、掩码、图、特征、旧预算和旧结果均保留。最终推荐以`_p0pilot/control_budget_bounded_20261105/EXPERIMENT_CONTRACT.json`为准，早期`control_budget_v2_20261105`保留为过程快照，不是最终采样输入。','',
 '## 1. 修订原则与五组问题','',
 '五组依然是G0（全部H）、GB（B替换）、GM（M替换）、GBM（B+M替换）、GAll（B+M+U替换）。G0的监督没有正常对照标签，公共负例仅来自木马训练视图；所有组输入相同完整图，故回答相同图暴露下正常对照标签监督的作用，不是正常图是否进入消息传递的作用。','',
 '本次同时下调五组的负例条目预算，并限制公共负例与替换端点的曝光。原全部正例每步一次、200步不变，图、39v3、损失、优化器、初始化、验证选模规则不变；不加入角色调权、额外正例保护或SAT。预算变化对全部五组一致，但构成新的训练协议，不能将旧H/C结果直接充当其中任何基线，也不能把未来与旧实验的差异全归于正常对照。','',
 '## 2. 每一步的预算','',
 '| 域 | 原草案负条目/步 | 新公共负例/步 | B块 | M块 | U块 | 新负条目/步 | 固定正例/步 |\n|---|---:|---:|---:|---:|---:|---:|---:|\n| 原始侧 | 110230 | 8192 | 48 | 48 | 8 | 8296 | 136 |\n| 变换侧 | 420365 | 8192 | 48 | 48 | 48 | 8336 | 829 |','',
 '块在未启用正常标签时使用各自配对H端点，绝不删除名额。B/M同条目剂量，每域200步各9600条；原始U只有15个可配对节点，预算限定8条/步，避免超过单节点上限。不同块的独立节点多样性仍不同：B实际用9600个、M93/173个，故B/M同条目不等于同数量独立正常样本，不宜据效应大小断言哪种语义天然更有效。','',
 table(mainbudget,['domain','arm','positive_per_update','common_negative_per_update','negative_per_update','normal_control_per_update','negative_unique_200','max_negative_node_exposure']),'',
 '五组每一步负例全部互异，即负条目数=独立负节点数、同一步重复为0；跨200步各组独立负节点总数与每节点重复次数直方图也严格相同。原始侧各组共28896个独立负节点，变换侧96031个。五组每步宿主/实现流程/25类门型的条目分布也由配对端点逐一保持；实际源对象身份会因正常/H替换而改变，不能称每个源对象的曝光完全相同。','',
 '## 3. 单节点和单源曝光上限','',
 '| 约束 | 新合同上限 |\n|---|---:|\n| 同一步任一负节点 | 1次 |\n| 200步任一负节点（公共、B/M/U及H均适用） | 128次 |\n| 单源公共负监督，每域每步/200步 | 1024 / 160000条 |\n| 单源三块替换负监督合计，每域每步/200步 | 32 / 3200条 |\n| 单源全部负监督，两域合计每步/200步 | 2112 / 326400条 |','',
 f'全部五组实际核验通过：推荐版本三块替换中单源最大累计{maxextra}条；两域全部负监督单源最大累计{maxsource}条、单步最大{maxstep}条，均低于上限。源以原始制造对象source识别，变换视图不能各自重置单源预算；原始和变换两域也做合并核查。以上上限明确适用于负监督，原正例仍200步各一次，不按角色特殊加权。','',
 '公共负例按“源容量=min(物理节点数×128,160000)”做整数水位分配，再固定乱序循环；小源不会为追求等源条目而无限重复。替换块优先未曝光源，之后优先较少使用的物理配对，联合检查正常端与H端的源上限。各组共享同一配对序列，在相同位置仅改变N/H端点；不同模型种子也共享采样表，减少采样噪声。既非按预测挑难例，也非按测试正例位置筛选。','',
 '相较旧草案变换U单节点最高442550次，本轮U在变换侧实际9600个节点各1次；原始U15节点各106—107次。M原始93节点各102—104次，变换173节点各33—67次；公共负例最大128次。这里的累计条目并不是独立样本数，图节点相关性仍在；node_exposure.csv中的权重集中等效数只描述权重分布，不是统计有效样本量。','',
 '## 4. M/H二跳扇出是否编码错误','',
 '对原宽匹配M的全部738对、1476个正常/H端点，直接用保存图中的有向物理边独立重算：沿两条边可达的终点去重并排除自身，再取log1p；全部与39维v3列32（0起，第33维）在2e-6以内一致。其语义是长度2路径的去重终点数量，不是最短距离恰为2；若直接邻居同时可经两边到达，仍计数。此定义与当前编码实现一致，本轮未改特征。','',
 '宽匹配的正常M端点平均二跳扇出确实小于H，不是读取错列或单纯归一化问题。新主版本在旧同宿主/同实现/同门型、14维RMS≤2的配对内，再要求原始log1p扇出差除以原训练标准差的绝对值≤0.5。只过滤已有训练配对，不扩搜索、不补SAT、不改制造标签、不将被过滤M改归B/U。','',
 table(concise,['domain','variant','M_pairs','signed_fanout_mean_z','mean_abs_fanout_z','normal_twoedge_count_mean','H_twoedge_count_mean','largest_14d_mean_gap','largest_gap_column']),'',
 '上表按实际200步曝光加权。宽匹配与严格版本的二跳扇出均值差：原始约−0.8775→−0.0117、变换−0.7181→−0.0017个训练标准差。原始M正常/H的二跳终点均值约1.216/1.260，变换约0.821/0.834。完整配对、源、宿主×实现×门型分层见M_fanout_pair_audit.csv、M_source_coverage.csv、M_host_recipe_gate.csv。','',
 '**二跳扇出平衡不等于所有结构平衡。**严格版本剩余最大14维均值差转到列30（真正输出驱动PO距离），原始约0.805、变换约0.488个训练标准差；原始U的扇出差仍约1.675个训练标准差。故后续只能检验该共同支持集上负标签监督的效果，不能宣称已隔离独立功能因素或SAT增益。PO距离/可达性应在后续结果中分层报告；若要提出独立于位置的作用结论，需要另做预先冻结的匹配敏感性合同，不能靠现有表直接声称。','',
 '## 5. 严格配对的覆盖代价与敏感性版本','',
 table(coverage,['domain','block','old_matched','eligible','used_unique','eligible_not_used','fanout_held','sources','views','entries_per_update','min_node_exposure','max_node_exposure']),'',
 '严格M原始93对/26源，变换173对/29源；相对原可信M候选218/595，节点覆盖为42.66%/29.08%，不能沿用旧94.0%/89.6%的宽匹配覆盖。原始112对、变换360对因扇出差暂不进入主M块，原标签保留。原始3个源在主M中完全暂缓如下，变换没有完全丢失的M源。','',
 table(held,['domain','source','old_M_pairs','fanout_held']),'',
 '预算不足而未抽到的B/U与扇出过滤分开记录：原始B9202个、变换B31032个、变换U18918个合格端点未在200步被抽中，不能称不可匹配。所有合格源均至少出现，B两侧32源、M26/29源、U3/32源。','',
 '另保存仅离线的sensitivity_wideM采样表：使用旧205/533对M，负条目预算、所有上限、公共负例和B/U逐步索引与主版本相同，只改变M池。它用于审视覆盖—平衡取舍，并非已排入额外训练。宽/严M池大小不同，不能要求200步独立节点数跨版本也相同；要求的是各版本内部五组一致。','',
 '## 6. U的解释边界','',
 'U表示“当前已有可信正常负标签，但无法归为纯宿主B或纯制造相似M的剩余部分”，不是未标注节点。原始U15个均为dup等其他新增；变换候选U79447个中：其他新增9、宿主/新增混合38、新增区域追踪不完整79400。不能把U统称为dup、功能不明正例或尚未可信的标签。','',
 table(u,['domain','reason','unique_nodes','entries_200','share_of_U_entries']),'',
 '推荐采样中变换U：9574/9600（99.73%）条来自追踪不完整，4条其他新增、22条混合。因此GAll−GBM只解释为这批“剩余可信正常标签”的增量监督效果，不能分摊给某类正常功能，更不能用效果反证映射正确。原始U只3源，结论单独报告。旧不可信正常节点仍排除（变换训练537839个），没有提升掩码或重贴标签。U若误报应按来源状态独立展示，不能合并为制造相似M的成绩。','',
 '## 7. 公平性核验和固定设置','',
 '已实际构造2种匹配版本×2域×5组×200步=4000条逐步监督索引，检查物理/旧可信/负标签、公共与替换互斥、G0零正常标签、正例不丢失、负条目/独立数/重复分布、源上限及两域合并上限；所有检查通过。独立复核旧配对宿主/流程/门型和RMS，同步核查全部合格源实际曝光。v3父合同36份数组及旧五组证据文件哈希均保持。','',
 '若未来获准训练，沿用ginvenv_gpu、dual_mix_post_cat、39v3、split29/hidden64/2+2+post1、46620参数，原seed42/1/2对应初始化，Adam lr0.0002、weight_decay0.001、BF16、clip1，ASL+1.4 soft-miss平方、200次更新、两域反向后同一步更新。不加SAT、不加等价一致性、不做正例角色保护。每5步延续旧可信__inj木马视图平均验证AP选模；A4等其他制造类型仍须在评价中独立列出，不能把旧__inj选模范围说成所有木马类型。','',
 '操作点保持统一算法：变换验证可信正例分数0.2/0.1分位（lower）及旧可信负例95%分位，不对某组单独调阈值；同时报实际源宏召回，不能把节点池分位校准称精确宏召回80%。正常源FPR/报警/排名、木马角色召回及可靠伙伴联合成功同表报告，完整可评正常集与训练共同支持集分开；已查看测试仅探索性，不用于本轮池、剂量、阈值的选择。','',
 '## 8. 结论与下一步','',
 '负例过量重复的问题已通过共同下调预算及节点/源上限处理；离线公平性通过。推荐主版本是严格M配对，宽M仅保留为敏感性备选。U语义与覆盖缺口已明确，但不会因监督效果预期而被重新标成M。剩余PO位置差异仍限制因果解释。下一步可先核验训练加载器精确使用本轮common、pairs和pools重建索引，禁止套用旧base_mask或旧320槽表；该预检应先不调用模型。只有后续明确授权才启动探索性seed42五组，不能自动将敏感性版本或其他种子加入队列。','',
 '证据目录：`_p0pilot/control_budget_bounded_20261105/`。核心为EXPERIMENT_CONTRACT.json、VERIFIED.json、STRATA_VERIFIED.json、step_fairness.csv、group_budgets.csv、node_exposure.csv、source_exposure_actual.csv、source_exposure_two_domains.csv、coverage.csv、balance.csv、U_actual_exposure.csv及两版本逐步pairs.npy。历史预算和初稿均保留，本轮无训练、无SAT、无移动删除。','']
 target.write_text('\n'.join(text),encoding='utf-8')
 brief='\n\n## 正常对照五组限额预算与二跳扇出复核（2026-11-05）\n\n完成纯离线修订，0训练/0前向/0SAT，无移动删除、标签/图/特征不改。最终合同为`_p0pilot/control_budget_bounded_20261105/EXPERIMENT_CONTRACT.json`，替代旧高重复预算；每侧公共负8192，B/M各48、U原始8/变换48，五组每步正/负原始136/8296、变换829/8336，负节点同一步不重复、200步≤128次，单源公共/替换分别封顶并核验两域合计。4000个版本×域×组×步监督索引检查通过，各组正负条目/独立数/重复分布、宿主/实现/门型条目一致。独立二跳复算1476个端点与v3列32相符；严格M要求扇出差≤0.5训练标准差，保留原始93对26源/变换173对29源，实际曝光均值差约−.0117/−.0017，原112/变360对暂缓不改标签；宽M只存离线敏感性备选。原始M完全暂缓3源、B/U预算未使用节点另列。U变换采样99.73%为追踪不完整的已有可信负标，GAll−GBM不能称某功能类型贡献。严格M剩余PO距离均值差约.805/.488，不能宣称独立功能作用；旧H/C不能充当新预算G0。全部原正例仍200步，不引入保护或角色权重。详见['+target.stem+']('+target.name+')。下一步先做索引加载预检，尚未授权任何训练队列。\n'
 for name in ['SAT作用证明.md','SAT工作总结.md','正常对照贡献量化与公平实验方案_20261104.md']:
  with (D/name).open('a',encoding='utf-8') as f:f.write(brief)
 with (R/'10.15/99_共用资产/运行登记/运行登记表.csv').open('a',encoding='utf-8-sig',newline='') as f:csv.writer(f).writerow([datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),'正常对照五组限额预算与二跳扇出离线复核','control_budget_bounded prepare/verify/verify_strata/publish.py','CPU only;0 training/model/SAT;node/source caps','none;future42/1/2','train pools only;no test selection','39v3 fixed labels;fanout05;paired five-arm',str(O.relative_to(R)),'P/N136/8296,829/8336;node<=128;M93/173;4000 checks','完成离线合同','no training authorization;PO residual;U residual trusted labels'])
 files={str(p.relative_to(R)):sha(p) for p in O.iterdir() if p.is_file() and p.name not in ['COMPLETE.json','PUBLISHED.json']};files[str(target.relative_to(R))]=sha(target);(O/'COMPLETE.json').write_text(json.dumps(dict(training=0,model_forward=0,SAT=0,labels_changed=False,files_moved_or_deleted=0,files=files),ensure_ascii=False,indent=2),encoding='utf-8');(O/'PUBLISHED.json').write_text(json.dumps(dict(report=str(target.relative_to(R)),sha=sha(target),complete_sha=sha(O/'COMPLETE.json'),state='offline verified;no training'),ensure_ascii=False,indent=2),encoding='utf-8');print('Published report and appended research notes',flush=True)
if __name__=='__main__':main()
