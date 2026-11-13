from pathlib import Path
import json,csv,hashlib,collections,datetime
O=Path(__file__).resolve().parent;R=O.parents[1];N=R/'10.15/00_说明';B=R/'_p0pilot/control_fair200_20261104'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert not (O/'COMPLETE.json').exists();a=read(O/'audit.json');v=read(O/'verification.json');p=read(O/'proposal.json');assert v['all_label_chains_match']
 for key,h in a['inputs'].items():assert sha(R/key)==h,key
 for key,h in read(B/'manifest.json')['files'].items():assert sha(B/key)==h,key
 for seed in [42,1,2]:
  for arm in ['H','C']:
   q=B/f'seed{seed}'/arm;assert sha(q/'best.pt')==read(q/'EVALUATED.json')['checkpoint_sha']
 dead=rows(O/'unreachable34.csv');coll=rows(O/'collision_node_pairs.csv');graph=rows(O/'graph_checks.csv');role=rows(O/'collision_role_sets.csv')
 lines=['# 输出不可达正标节点与三跳上下文冲突核查（2026-11-04）','',
 '## 核查结论','',
 '**34个测试正标节点的不可达是真实网表中的死支路，不是行号错位或漏边造成；3条相同上下文记录展开为4对物理节点，两侧也都处于死支路。主要问题是制造来源标签与当前节点的输出功能作用不同。**',
 '所有34个目标均有唯一源门、有效inst_prov锚点、正确源/划分坐标和一致的标签继承链。映射可作为制造溯源使用，但不能据此证明变换后节点继续承担源门的输出作用；同一源角色的映射后代中，本次34个节点所在集合均没有输出可达成员。','',
 '另发现PO距离的起点口径缺陷：现有特征以“任意引脚触碰PO”的门为起点，包含消费PO信号的门；真正的到输出可达性应以驱动输出的门为边界。核查13个视图中有3个训练视图共41节点因此被额外算作可达。该差异未改变34个测试不可达节点及4对冲突节点的判断。本轮只登记，未修改特征生成器或已有输入。','',
 '本轮0训练、0模型前向、0 SAT；没有改动任何标签、图、掩码、采样表、模型或旧预测。34个案例属测试描述性核查，后续候选规则须由训练/验证决定，不按这些测试节点的位置删样本或选训练对象。','',
 '## 证据链及核查方法','',
 '1. 将split坐标映射回全局node_names，再按同源/同划分核查原始门坐标；同时核对class_map_orig、全局alignment、transported标签和当前y/trusted。34个测试节点加8个冲突物理节点，共42条完整标签链均一致，无正负混合父节点。',
 '2. 从实际Verilog实例和库引脚方向独立构建门间连线，按位处理别名和向量拼接，以真正驱动PO的门为种子逆向遍历；同时使用原v2解析器重建比较保存的edge_index。13视图全部门集合、边集合一致。这里的独立网络与v2使用不同实现，不仅重复读取已保存图。',
 '3. 对比fold中的变换网表与b1bind/keepbnd转换产物哈希，再将转换器inst_prov锚点核对到原网表源门输出。对每个不可达节点保存完整下游门集合及无消费端终点。',
 '4. 在独立核实的入边上重建39维归一化输入的三跳计算树，复核相同指纹、真实引脚连线及六组既有预测。没有调用训练入口、模型forward或求解器。','',
 '## 34个节点逐源汇总','',
 '|木马源对象|不可达节点|涉及变换视图|不同源门|源门原本到PO可达|映射/标签链一致|',
 '|---|---:|---:|---:|---|---|']
 for src in sorted({x['source'] for x in dead}):
  rr=[x for x in dead if x['source']==src];lines.append(f"|{src}|{len(rr)}|{len({x['view'] for x in rr})}|{len({x['source_gate'] for x in rr})}|全部是|全部是|")
 lines += ['',
 '|变换视图|不可达节点数|', '|---|---:|']
 for view in sorted({x['view'] for x in dead}):lines.append(f"|{view}|{sum(x['view']==view for x in dead)}|")
 lines += ['',
 '34个目标的源门原先均有结构路径通向输出，变换后这些保留节点的下游锥仅含1—4个门：23个单门锥、8个双门锥、2个三门锥、1个四门锥，全部终止在无后继门，不触及任何输出驱动门。相同源门的映射后代也全部不可达（有可达映射兄弟的节点为0/34）。这说明现有映射覆盖到的是保留原信号的锚点/表达式后代，而非保证覆盖其实际输出实现。','',
 '### 一个直接的连线例子','',
 's38584t100/injzeta/ys_abc中，g_TrojanF_p5_665的XOR输出TrojanF_p5__g664只进入g_TrojanF_p5_666；后者的反相输出TrojanF_p5没有消费者。两门均因TrojanFP5的制造血缘而继承正标。真正驱动原输出附近的MUX使用另一条重写信号_02039_，不消费该保留支路。原网表TrojanFP5则处在载荷到劫持输出的结构路径上。','',
 '这可以证明该变换后支路没有当前数字连接图中的输出作用，不能在无SAT情况下进一步断言源门功能已消失、其它匿名重写逻辑与源门等价，或整体木马已经消除。保持整体等价并不要求保留的每一条命名中间线仍参与输出。','',
 '## 3条上下文相同记录：4对真实节点','',
 '|源宿主/角色|正常节点|木马节点|变换后N/T到PO|原源门N/T到PO|六模型分差|',
 '|---|---|---|---|---|---:|']
 for x in coll:lines.append(f"|{x['source'].split('__')[0]}/{x['role']}|{x['normal_node']}|{x['trojan_node']}|否/否|否/是|{x['max_score_difference_six_models']}|")
 lines += ['',
 '三条均为ctlmatche/injepsilon的TM1角色、ys_nand实现；s35932一条记录内有OR和INV两对，故总计4对物理节点、8个节点，而非3对。每对正负节点均在死支路中；正常/木马原始源门则分别不可达/可达。每个目标映射回自己的正确源门，无行号错位或跨宿主误配。完整角色后代集合在N/T两侧均无可达成员。','',
 '四对的39维输入和三跳入边计算树相同，六模型预测差均为0。正负差别来自不同制造对象的标签继承，不能在当前局部输入和当前功能用途均相同的节点上要求模型同时满足相反判定。单纯增大负例权重只会改变冲突的折中方向；增加下游传播也不能自动让一条真实死支路变成有输出作用的木马功能节点。','',
 '## 映射、图与标签分别出了什么问题','',
 '|层面|本次证据|应如何解释|',
 '|---|---|---|',
 '|坐标及血缘映射|34+8节点标签链、源/划分坐标一致|未发现错位或正负混合父节点；仅证明制造溯源|',
 '|门间边构建|13视图独立引脚连线与保存图一致|34节点不是因漏边而被判不可达|',
 '|PO距离边界|3视图41节点存在额外可达标记|有边界定义问题，需独立特征版本修复，不能笼统声称39维v2全部边界语义正确|',
 '|标签传播语义|parser2对1:N后代全部继承源标签|正确实现了历史制造来源合同，但超出了逐节点功能作用合同|',
 '|功能对应可靠性|本次34节点所在源角色映射集合均只覆盖死锚点|不得把此类映射命中率称为功能有效覆盖率|','',
 '历史机制：assign_to_gates给一个assign表达式产生的多个门统一记录原左值锚点；make_inst_alignment将该锚点归到源驱动门；parser2.build_label_transport让1:N所有后代继承同一源标签；trusted只表示已有这条可追溯标签。整个链条没有逐节点输出作用的检验。不能将“实现与历史代码一致”表述为“每个功能标签已经证实正确”。','',
 '### 对上一轮PO核验结论的更正','',
 '上一轮用保存的touches_PO起点独立遍历，验证了距离列与起点的一致性，没有独立验证起点是否为真正的输出驱动门。本轮补上库输出引脚核验后发现如下差异：','',
 '|训练视图|保存为可达、实际无输出驱动路径的节点数|', '|---|---:|']
 for x in graph:
  if int(x['stored_reachable_but_no_output_drive_path']):lines.append(f"|{x['view']}|{x['stored_reachable_but_no_output_drive_path']}|")
 lines += ['',
 '这41个是本次13视图范围内的附加发现，不能外推为全数据集总数；不与34个测试不可达节点混为一组。触碰PO仍可作为单独的邻接描述，但“到PO的距离”应按真正的输出驱动边界计算。后续如修复需生成独立版本，并重新做同协议基线，不能直接覆盖39维v2或把变更后的结果与旧训练混比。','',
 '## 分角色监督方案修订：先修合同，再试权重','',
 '本节优先于上一轮直接考虑2倍/4倍区域权重的建议。当前不启动任何新训练，也不实际修改候选掩码。','',
 '1. **保留制造来源主任务。** 现有标签、旧训练监督和完整测试主指标保留；本轮不将死支路正标改0，也不从测试正例中删除34节点。后续另加“制造来源/对象归属”和“当前输出作用”分层说明，不能用筛掉困难正例后的新AP替代旧主表。',
 '2. **按证据资格划分额外区域监督。** anchor_only：仅有源锚点血缘、后代都无输出路径；connected_unproved：有输出路径但功能作用未经证实；functional_verified：已有同合同、同查询上下文的功能证据。结构可达只作为必要筛查之一，不能自动升级为功能证明。分类状态用于辅助损失与分层评价，不写回原y/trusted。',
 '3. **暂缓已知冲突角色的额外加权资格。** 本轮294个trans候选中，三条TM1/NAND角色涉及6个C节点及其6个匹配H节点；其中4个C节点存在已证实局部输入冲突。原训练中，6个C节点额外曝光676次，其中4个冲突节点448次。下一轮辅助区域损失应同时暂停C/H这6对的额外加权，公共监督和源标签先保持；这样避免放大已知冲突，但不宣称已经消除公共监督中的全部语义冲突。',
 '4. **288只是剩余池上限，尚非训练许可清单。** 去掉已知6对后，剩288对、20源对象、44视图；还须对训练及验证候选用相同静态规则核查死锚点、实际边界、谱系混合和一对多集合。规则来源于训练冲突，不能拿34个测试位置反向挑候选。orig资格按其自身有效边界单独核查，不因某个trans变体的死锚点而自动改orig标签。',
 '5. **对一致性约束使用功能边界/集合。** 原始侧有效源门与变换侧死锚点不能被强制赋予同一安全预测；制造对应仅用于定位候选边界，功能/安全角色一致性须在经过验证的活动边界或对象集合上成立。本次源角色在变换侧找不到活动映射后代的，登记为功能定位未解决，不能用旧mapping覆盖数补足。',
 '6. **修复PO边界需单独版本与公平基线。** 先确定驱动PO的引脚及输出别名合同，生成独立特征版本并验证；保留原39维v2图和SAT成功结果。当前仍只是方案，不执行特征修复。若后续授权训练，边界修复对照与角色权重对照分开，避免同时改两项后无法归因。',
 '7. **通过资格审计后才讨论调权。** 在两组候选、域权重、正例权重和总负例权重相同的条件下，从公共负例等额转移权重到合格角色；先保护触发/选择正例召回，再检验载荷正常误报和集合联合成功。2倍/4倍不是当前已确定的下一轮任务；局部同输入冲突和anchor_only关系不能靠权重搜索修复。测试继续只作探索性汇报。','',
 '因此下一步优先级为：审计剩余训练/验证区域的功能边界资格 → 独立修订PO距离合同 → 明确制造来源与功能作用的监督及评测边界 → 再决定是否启动受约束权重试验。优先复用现有网表、映射、图和已验证SAT证据；本轮没有扩大SAT搜索。','',
 '## 证据入口','',
 '- unreachable34.csv：34节点逐项源门、锚点、下游锥与标签结论。',
 '- downstream_witnesses.json：完整死支路门和原始引脚证据。',
 '- collision_node_pairs.csv、collision_tree_witnesses.json、collision_role_sets.csv：4对节点、完整三跳计算树与角色后代集合。',
 '- graph_checks.csv：13视图全部连线对照及PO边界差异。',
 '- label_chain_checks.csv：42节点完整来源、全局/划分坐标、原标/传播标/当前标对照。',
 '- proposed_extra_role_eligibility.csv、proposal.json：294候选的方案状态，未改任何训练文件。',
 '- audit.json、verification.json、COMPLETE.json：输入哈希、只读核查及版本记录。',
 '- audit*.log：保留审计过程日志；前几次为本轮只读脚本的常量解析/边界断言/指纹序列化调试，不是训练或SAT失败。','']
 report='\n'.join(lines);target=N/'输出不可达正标与上下文冲突核查_20261104.md';target.write_text(report,encoding='utf-8');(O/'核查报告与监督方案修订.md').write_text(report,encoding='utf-8')
 brief=f'''\n\n## 输出不可达正标与上下文冲突核查及监督方案修订（2026-11-04）\n\n完成34个测试不可达正标、3条训练上下文冲突（4对物理节点）的原网表/实例锚点/源标签/alignment/transported/当前标签链审计，0训练/0前向/0SAT，标签与图未改。34节点来自4源7视图，源门原本均到PO可达；变换后均为真实死支路，映射集合无活动后代，血缘链一致但不构成功能作用对应。4对上下文相同节点N/T也均在死支路，制造归属相反、六模型同分。13视图保存边与独立引脚建图一致；另发现PO距离以touches_PO起点引入3个训练视图共41个额外可达标记，不影响本次34结论。更正上一轮“独立PO核验”的边界含义：当时只验证距既定touches_PO种子一致。暂缓整体加权；未来将anchor_only、connected_unproved、functional_verified分开；三条训练TM1/NAND角色的6个C/H配对仅建议暂停额外加权资格，未实际改掩码，剩288只是待审计上限。先审资格、修独立PO边界版本、明确来源与功能监督合同，再决定权重实验。详见[核查与方案]({target.name})和`_p0pilot/control_labelaudit_20261104/`。\n'''
 for name in ['SAT作用证明.md','SAT工作总结.md','正常对照贡献量化与公平实验方案_20261104.md']:
  with (N/name).open('a',encoding='utf-8') as file:file.write(brief)
 with (R/'10.15/99_共用资产/运行登记/运行登记表.csv').open('a',encoding='utf-8',newline='') as file:csv.writer(file).writerow([datetime.datetime.now().astimezone().isoformat(),'34不可达正标与3条上下文冲突的原网表核查','control_labelaudit audit/verify_chains/proposal/publish.py','CPU read-only;0 forward/train/SAT','42/1/2 existing','4 test sources7 views +3 train role records','42 label chains;13 rebuilt view graphs','_p0pilot/control_labelaudit_20261104','34 retained dead lineage nodes;4 identical-input dead pairs;PO boundary41 extras','完成','no label/graph changes;weight proposal revised;offline audit debug logs retained'])
 artifacts=[p for p in O.iterdir() if p.suffix in ['.csv','.json','.py','.md']]+[target]
 (O/'COMPLETE.json').write_text(json.dumps(dict(time=datetime.datetime.now().astimezone().isoformat(),training=0,SAT=0,model_forward=0,labels_modified=False,graphs_modified=False,masks_and_schedules_modified=False,old_predictions_unchanged=True,report=str(target),artifacts={str(p.relative_to(R)):sha(p) for p in artifacts}),ensure_ascii=False,indent=2),encoding='utf-8');print(target)
if __name__=='__main__':main()
