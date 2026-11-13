from pathlib import Path
import csv,json,hashlib,datetime,collections
O=Path(__file__).resolve().parent;R=O.parents[1];N=R/'10.15/00_说明';B=R/'_p0pilot/control_fair200_20261104'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert not (O/'COMPLETE.json').exists();q=read(O/'qualification.json');feat=read(O/'FEATURES_COMPLETE.json');pre=read(O/'PREFLIGHT_COMPLETE.json');assert read(O/'lineage.json')['passed']
 for p,h in q['inputs'].items():assert sha(R/p)==h,p
 for p,h in feat['inputs'].items():assert sha(R/p)==h,p
 old=read(R/'_p0pilot/round32_20261029/input_contract.json')
 for p,h in old['files'].items():assert sha(R/p)==h,p
 summary=rows(O/'qualification_summary.csv');changes=rows(O/'feature_change_summary.csv');positive=rows(O/'positive_boundary_counts.csv');pool=rows(O/'provisional_pool_summary.csv');role=rows(O/'role_boundary_qualification.csv');review=rows(O/'C_H_pairs_v3_review.csv')
 graphviews=len({(x['domain'],x['view']) for x in rows(O/'view_graph_checks.csv')})
 lines=['# 训练/验证功能边界资格审计与独立39维v3（2026-11-04）','',
 '## 本轮完成及判断','',
 '**资格审计和独立新版特征已完成；具备准备受约束分角色对照的输入条件，但下一轮应先隔离验证v2→v3的影响，不能同时改特征、候选池和权重。**','',
 '本轮0训练、0模型前向、0SAT；标签、掩码、采样表、图边及旧39维v2和模型预测均保持原哈希。独立v3覆盖全部六个orig/trans训练、验证、测试输入，共464个视图。只修正第30列（0起算，即第31维）的到PO距离；其余38维原值与归一化后值均逐元素一致。新输入不会被现有训练入口自动采用，需后续显式使用新合同与加载器。','',
 '## 剩余训练/验证候选的资格','',
 '|范围|审计正常节点池|结构边界支持|应暂缓额外加权|说明|',
 '|---|---:|---:|---:|---|',
 '|orig/train 当前匹配池|116|116|0|20源对象、20视图|',
 '|trans/train 当前匹配池|294|233|61|仍保留20源对象、44视图的结构支持|',
 '|orig/val 制造配对区域|35|35|0|5源对象，仅作资格/评价，不送入训练|',
 '|trans/val 制造配对区域|94|76|18|5源对象，仅作资格/评价，不送入训练|','',
 '“结构边界支持”仅表示对应木马后代集合确有到真实输出驱动门的路径，来源、坐标及局部输入检查通过；不等于功能等价、恶意作用或安全角色已被SAT验证。本轮未将任何对象升级为functional_verified，亦未否定本工程其它合同中的既有SAT证据。','',
 '原始侧训练先审计完整121个制造配对节点，再与已有匹配池取交集116个；变换训练先审计329个节点，再与294匹配池相交。完整329池中266有结构支持、63需暂缓；不要与实际可匹配池的233/61混用。','',
 '|范围|制造角色×实现记录|木马后代全不可达|木马后代全可达|部分可达|',
 '|---|---:|---:|---:|---:|']
 for x in summary:lines.append(f"|{x['domain']}/{x['split']}|{x['role_records']}|{x['T_anchor_only_roles']}|{x['T_all_live_roles']}|{x['T_mixed_roles']}|")
 lines += ['',
 f'独立引脚/表达式图核对覆盖{graphviews}个不同候选网表；原始/变换、训练/验证共1132条角色目标记录的来源/划分/标签链一致，变换侧涉及802个唯一物理节点。未发现混合源父节点或当前图漏边；连续表达式拆成显式辅助节点后也与保存边一致。所有辅助节点继续不接受标签监督。','',
 '61个训练暂缓节点包含上一轮已知3条TM1/NAND角色的6个节点（其中4个局部同输入），另有55个来自其它死锚点关系。因此此前“288个剩余候选”只是上限，本轮已收紧到233。暂缓的是未来额外区域加权资格，未实际改任何y、trusted、监督掩码或采样文件。','',
 '## PO距离起点如何修复','',
 '旧版列28仍表达“任意引脚触碰PO”，适合作为接触边界描述；旧列30却直接以这类门作为距离0起点，可能把消费输出信号的门也当成输出驱动门，给上游制造不应有的距离捷径。','',
 '新版独立生产器feature_encoding_v3_po.py新增PO_driver标志：只有库定义的输出引脚连接到归一化后的主输出位，才是距离0起点。主输出向量、位选、拼接和别名均按位处理；连续表达式的真实输出辅助节点也可成为起点。沿原有有向图的入边反向求最短距离，无路径仍为−1。列28及其他38列不变。','',
 '|输入|视图|列30原值改变节点|旧可达→真实不可达|',
 '|---|---:|---:|---:|']
 for x in changes:lines.append(f"|{x['key']}|{x['views']}|{int(x['changed_column30']):,}|{x['old_reachable_new_unreachable']}|")
 lines += ['',
 '全量合计1,331,707个节点的原始PO距离改变，571个从旧可达变为不可达。大部分改变是最短距离增加，表明旧起点形成的捷径影响范围较大；不能只按571个可达翻转节点估计修复影响。','',
 f"归一化仅在与旧版完全相同的{feat['train_fit_count']:,}个orig+trans物理训练节点上重拟合列30：均值{feat['old_mean30']:.6f}→{feat['new_mean30']:.6f}，标准差{feat['old_std30']:.6f}→{feat['new_std30']:.6f}。其他38维归一化参数逐元素保持；验证/测试不参与拟合。由于均值/标准差改变，列30归一化值的变化范围比原始距离变化更大，必须随新版特征一起使用新版normalization.npz。",'',
 '## 验证与尚未解决的边界','',
 '- 五个专门样例通过：PO消费门、输出向量拼接别名、无驱动输出、连续表达式输出、条件表达式输出；同时使用独立引脚/表达式图验证。',
 '- 全部464视图的新解析边与保存边一致；独立图边、输出驱动种子和可达集合核验通过。所有节点通过最短距离Bellman不等式及逐级下降见证检查。',
 '- 六个输入的独立加载器通过形状、有限性、辅助节点无监督检查；其他38列在原值及标准化后均完全一致，图边/边角色/y/trusted/physical文件字节哈希一致。',
 '- v2/v3所有训练和验证配对重新计算三跳输入指纹：原来的3条角色×视图、4对局部相同输入仍存在，无新增此类冲突；它们已包含在61个暂缓节点中。未调用模型，因此没有v3 AP、误报或召回结果。',
 '- 新归一化下重新核对已有H/C同视图、同门型和拓扑匹配，233对结构支持候选均在原RMS≤2范围内，无需因本次距离变化另行重配。此结论仅针对现有配对规则，不等于H/C功能等价。','',
 '|范围|可信正标节点|v2不可达正标|v3不可达正标|', '|---|---:|---:|---:|']
 for x in positive:lines.append(f"|{x['key']}|{x['trusted_positive']}|{x['v2_unreachable_positive']}|{x['v3_unreachable_positive']}|")
 lines += ['',
 '测试原有34个不可达正标结论保持；训练由71变为74，新增3个来自旧PO边界的额外可达标记。不可达是当前数字连接图中的结构结论，不自动将来源正标改为负，也不证明源门功能在整个重写电路中被消除。','',
 '## 分角色监督与下一轮安排修订','',
 '1. **先做特征版本单因素基线。** 后续得到训练授权后，保持当前强双分支200次、图、原监督、损失、初始化、选模及旧H采样表完全相同，只换v2/v3特征和配套列30归一化。可以复用本轮v2/H已有seed42、1、2的模型与预测，不必重跑不变的v2；先验证seed42的新特征加载和同协议行为，再决定补齐种子。当前不启动。',
 '2. **功能与制造来源的监督解释分开。** 主任务仍保留原制造来源标签与完整节点AP/召回；额外正常区域损失只在通过边界和局部冲突审计的池上讨论。anchor_only单独记录；connected_unproved不自动当作SAT已证明。不得将活动祖先或死锚点强行视作每个中间门的同一安全角色。',
 '3. **分角色试验在同一v3上比较。** 固定orig116、trans233对结构支持候选，C/H两组使用同一来源资格、同一名额、唯一节点预算、重复次数和域权重。先有这个新池的等权H/C对照，再考虑小倍率权重；不能把旧294池H组直接与新233池加权C组当作公平因果比较。保留全部前向图和BN范围。',
 '4. **暂缓关系对称处理。** 61个C及其61个匹配H应在未来额外加权资格中同时暂缓；公共源标签保留，具体公共监督基座须在两组间一致。若某源/实现缺少合格节点，应事先统一预算，不因某组样本数变化而隐式改变正负梯度比例。233对仍覆盖原20源和44视图，但这是候选数量，尚未生成新的训练曝光表。',
 '5. **保护正例与总负例权重。** 若随后试权重，从公共负例等额转移到合格区域，两组相同倍率；正例和soft-miss权重不变。分层检查触发/载荷/选择召回及同源对象联合成功，参数仅依据训练/验证确定。选择角色缺少本次定向覆盖的问题仍未解决，不用给其它角色加权来冒充补齐。',
 '6. **测试范围固定。** 新版测试特征仅按统一修复规则生成；不据测试正例位置选择候选，也不删除34个正标或用筛后的AP替代历史主表。本轮“结构支持”并不产生新的功能证明覆盖率。','',
 '判断：可以进入v3单因素基线和分角色等预算对照的准备阶段；尚不能直接宣称权重对照已具备性能基线，更不能把v3修复、池清理和加权三个改变同时合并后解释收益。','',
 '## 文件与复用入口','',
 '- input_contract.json：独立v3完整输入合同；inputs/{orig,trans}_{train,val,test}/x39.npy为新版特征，其余图/标签文件是与v2逐字节相同的独立副本。',
 '- normalization.npz：只重拟合列30；load_v3.py：显式离线加载入口，未接入生产训练脚本。',
 '- feature_encoding_v3_po.py、build_v3.py、view_cache/：独立生产器、逐视图检查点和完整生成记录，可校验复用，不覆盖旧版。',
 '- qualification_summary.csv、role_boundary_qualification.csv、normal_candidate_qualification.csv：训练/验证角色与节点资格。',
 '- lineage_checks.csv：1132条目标来源及标签链核查；target_activity.csv为真实输出边界活动情况。',
 '- C_H_pairs_v3_review.csv、provisional_pool_summary.csv：116/233对结构支持和61对暂缓清单，未修改旧采样。',
 '- context_v2_v3.csv、feature_change_summary.csv、positive_boundary_counts.csv：版本变化和局部冲突复核。',
 '- boundary_tests.json、PREFLIGHT_COMPLETE.json、FEATURES_COMPLETE.json、COMPLETE.json：输入与边界验证、归一化合同、哈希及无训练/SAT记录。','']
 report='\n'.join(lines);target=N/'训练验证功能边界资格与39维v3_PO修复_20261104.md';target.write_text(report,encoding='utf-8');(O/'资格审计与v3特征报告.md').write_text(report,encoding='utf-8')
 brief=f'''\n\n## 训练验证功能边界资格与独立39维v3（2026-11-04）\n\n已完成训练/验证候选独立引脚/表达式边界审计及1132条来源标签链检查，0训练/0前向/0SAT，原标签/图/掩码/预测不改。orig训练匹配池116均有结构边界支持；trans训练294中233有支持、61为死锚点暂缓（含原6个，另55）；trans验证94中76支持、18暂缓。仅结构支持，未新增SAT功能证明。独立39维v3覆盖六划分464视图，仅列30改为库输出引脚真正驱动PO的起点，其余38列原值/归一化值及边/标签字节一致；1,331,707个原始距离变化，571个旧可达翻转不可达，训练同范围1360793物理节点仅重拟合该列归一化。5边界样例、全视图独立连线/种子/最短路径、加载预检通过；原4对局部同输入冲突仍在，测试34不可达正标保持，训练71→74。v3匹配预检保留orig116/trans233对、20源/44变换视图，旧池和采样表未动。下一轮先单因素v2/v3强配置基线（可复用v2/H现有预测），再在同一v3新池内做等权H/C和受约束分角色权重对照；不同时合并版本/池/权重变化。详见[报告]({target.name})与`_p0pilot/control_boundary_v3_20261104/`。\n'''
 for name in ['SAT作用证明.md','SAT工作总结.md','正常对照贡献量化与公平实验方案_20261104.md']:
  with (N/name).open('a',encoding='utf-8') as f:f.write(brief)
 with (R/'10.15/99_共用资产/运行登记/运行登记表.csv').open('a',encoding='utf-8',newline='') as f:csv.writer(f).writerow([datetime.datetime.now().astimezone().isoformat(),'训练验证边界资格与39v3 PO距离独立修复','control_boundary_v3 qualify/lineage/build_v3/preflight/publish.py','CPU only;0 train/forward/SAT','NA','orig/trans train,val audit;all six inputs v3','frozen v2 parent;new v3 PO_driver column30','_p0pilot/control_boundary_v3_20261104','orig116/trans233 supported;61 hold;1331707 distance changes','完成','old labels/graphs/predictions preserved;weight training pending version baseline'])
 artifacts=[p for p in O.iterdir() if p.suffix in ['.json','.csv','.py','.md','.npz']]+[target]
 (O/'COMPLETE.json').write_text(json.dumps(dict(time=datetime.datetime.now().astimezone().isoformat(),training=0,SAT=0,model_forward=0,labels_modified=False,old_v2_preserved=True,new_version='base39_v3_PO_output_driver_only_column30',input_contract=str((O/'input_contract.json').relative_to(R)),artifacts={str(p.relative_to(R)):sha(p) for p in artifacts}),ensure_ascii=False,indent=2),encoding='utf-8');print(target)
if __name__=='__main__':main()
