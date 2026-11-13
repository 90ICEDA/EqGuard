from pathlib import Path
import csv,hashlib,json
import numpy as np
O=Path(__file__).resolve().parent;R=O.parents[1];D=R/'10.15/00_说明'
def read(n):return json.loads((O/n).read_text(encoding='utf-8-sig'))
def rows(n):
 with (O/n).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert read('VERIFIED.json')['passed'];dc=rows('threshold_score_macro.csv');aps=rows('AP_decomposition_per_source.csv');apm=rows('AP_decomposition_macro.csv');ar=rows('AP_role_contribution_per_source.csv')
name='正常对照五组_阈值降分与角色召回机制审计_20261107.md'
text='''# 五组预测复用：误报、角色召回与原始侧AP的变化来源

2026-11-07。本轮只读取五组已有预测、固定角色/区域和39维v3图特征，0模型前向、0反向、0训练、0新增SAT，不引入正例保护或改标签。

结论：GM/GBM降低新增正常区域误报主要来自模型实际降分，不只是阈值上移；触发/载荷召回损失则有三种不同情况。**原始alpha触发召回下降属于阈值变化，分数没有下降；原始侧AP下降是真实排序退化，不能用阈值解释。**建议原合同五组补seed1、2验证稳定性，本轮不启动。

## 1. 怎样区分阈值和分数

对同一批节点计算四格：G0分数/G0阈值、GM或GBM分数/G0阈值、G0分数/新阈值、新分数/新阈值。统计每视图比例，再源内等视图、最后等源平均；不按结果删源。

采用两种替换顺序的平均贡献，令a/b/c/d依次为上述四格：

`分数部分=[(b-a)+(d-c)]/2；阈值部分=[(c-a)+(d-b)]/2`

两部分严格相加等于总差d−a；这是固定预测的描述性分解，不是训练梯度因果归因。阈值始终来自原验证校准规则，没有重新用测试集找阈值。下表为val_recall80；“80”指验证节点池校准，不保证测试或源宏召回恰为80%。

|组/划分/指标|总变化（百分点）|分数部分|阈值部分|
|---|---:|---:|---:|
'''
for arm,key,scope,label in [('GM','trans_val','normal_primary_added','变换验证正常区域FPR'),('GM','trans_test','normal_primary_added','变换测试正常区域FPR'),('GBM','trans_test','normal_primary_added','变换测试正常区域FPR'),('GM','orig_test','role/trigger','原始测试触发召回'),('GBM','orig_test','role/trigger','原始测试触发召回'),('GM','trans_test','role/trigger','变换测试触发召回'),('GM','trans_test','role/payload','变换测试载荷召回'),('GBM','trans_test','role/trigger','变换测试触发召回'),('GBM','trans_test','role/payload','变换测试载荷召回')]:
 r=next(r for r in dc if r['arm']==arm and r['key']==key and r['operation']=='val_recall80' and r['scope']==scope);text+=f'|{arm} {label}|{100*float(r["delta"]):+.2f}|{100*float(r["score_effect"]):+.2f}|{100*float(r["threshold_effect"]):+.2f}|\n'
text+='''
GM变换测试正常区域FPR总降13.65个百分点，分数部分约−13.15、阈值部分约−0.51，支持正常区域实际降分。验证6/6、测试6/6个已有可评价正常区域源均改善的结论保留；这不是6个独立宿主。

## 2. 三个关键漏检案例，不应混称“都被模型压低”

|GM相对G0|G0分数|GM分数|G0阈值|GM阈值|判断|
|---|---:|---:|---:|---:|---|
|原始测试alpha触发，row58320|0.576369|0.578999|0.576005|0.600540|分数上升；仅阈值上移造成漏检|
|变换测试delta载荷，nand，row771358|0.645343|0.590425|0.576005|0.600540|单独改分数或阈值仍检出；两者一起才漏检|
|变换测试epsilon触发，nand，row839395|0.641422|0.565059|0.576005|0.600540|在旧阈值下也漏检，属于实际降分损失|

GBM同样三种类型：对应新分数约0.588534、0.596609、0.546980，新阈值0.608012。不能把alpha召回损失当成“正常监督把该正例分数压低”的证据；此前建议中“核查alpha触发降分”应精确更正为“核查其召回丢失”。

独立源层面，GM/GBM变换测试epsilon触发下降、delta触发有增益但载荷下降；原始测试alpha触发源召回1→0，其他已追溯触发源不变。源宏触发下降20个百分点主要由这一个小角色集合引起，不等于20%的全部木马节点都漏检。

## 3. AP为什么下降——阈值无关，载荷排序确有退化

AP只取决于标签和分数排序，不使用上述报警阈值。下表为源宏平均：

|组/划分|G0 AP|新AP|差值|
|---|---:|---:|---:|
'''
for key,label in [('orig_val','原始验证'),('orig_test','原始测试'),('trans_val','变换验证'),('trans_test','变换测试')]:
 for arm in ['GM','GBM']:
  r=next(r for r in apm if r['key']==key and r['arm']==arm);text+=f'|{arm} {label}|{float(r["AP0"]):.4f}|{float(r["AP1"]):.4f}|{float(r["AP_delta"]):+.4f}|\n'
text+='''
### 原始测试按独立木马源拆分

|源|GM AP差|GBM AP差|
|---|---:|---:|
'''
aa={r['source']:r for r in aps if r['key']=='orig_test' and r['arm']=='GM'};bb={r['source']:r for r in aps if r['key']=='orig_test' and r['arm']=='GBM'}
for source,a in sorted(aa.items()):text+=f'|{source}|{float(a["AP_delta"]):+.4f}|{float(bb[source]["AP_delta"]):+.4f}|\n'
text+='''
原始测试不是所有源都变差：alpha、epsilon、gamma下降，delta、zeta略升；原始验证GM在beta、epsilon、gamma、zeta下降，alpha略升。因此不是单个阈值敏感触发点能解释全部AP下降。

按正例在其分数处的precision贡献精确分解AP，保留并列分数处理、全部负例和未分类正例。原始测试GM的AP总差约−0.02879，其中载荷角色贡献−0.02455、触发+0.00181、载荷选择−0.00022、未分类−0.00583，合计等于总差（舍入会有小误差）。这里是实际AP贡献，不是角色子集重新算AP，也不是训练因果贡献。

以原始alpha为例：

|正例|角色|G0→GM分数|排在其前/同分的可信负例数|AP贡献变化|
|---|---|---|---|---:|
|58320|触发|0.5764→0.5790|41→45|−0.0017|
|58321|载荷|0.9404→0.9252|0→0|0|
|58322|载荷|0.8050→0.7691|5→11|−0.0460|
|58323|载荷|0.8176→0.7603|5→11|−0.0217|
|58324|未分类|0.8601→0.8164|4→5|−0.0095|

这些载荷仍高于阈值、召回仍为1，AP却会因更多负例排在前面下降。因此“载荷召回不变”不能证明载荷区分能力没损失；触发分数上升也不保证相对排序提升。

另做正例分数替换/负例分数替换的四格AP辅助诊断：原始测试GM的正例分数部分约−0.04635、负例部分+0.01756；变换测试约−0.08225、+0.10586。它描述负背景降分在变换侧足以抵消正例降分，而原始侧不足。**跨模型拼接分数受校准/标度影响，不能把这些数当作正例学习损害百分比；主要判断仍依赖各自模型的真实排序和上表精确AP贡献。**

## 4. 正常区域与木马角色是否发生直接冲突

复用既有制造角色后代集合，分别报告正常/木马分数变化、FPR/召回四格分解以及当前39v3特征距离，没有新建SAT功能对应。

- 变换测试GM的80个既有“制造角色×视图”集合中58个正常与木马平均分数同时下降；验证70个中52个，原始测试40个中28个。它们不是独立电路数，仍按源/角色汇总。
- delta载荷丢失对应正常CtlMDP2：正常分数约0.7786→0.6855，仍持续误报；木马后代集合召回1→0.5。这是共同降分，但该角色的正常FPR没有改善。
- epsilon触发丢失对应正常CtlMETM1：正常后代本来已低于阈值，FPR保持0，木马后代召回0.5→0。同样不能说这次漏检换来了该对应角色的正常报警消除。
- 在当前合格对应集合及val_recall80下，未观察到同一“正常角色×视图”同时出现正常FPR下降和木马召回下降的记录。该结论只限已有对应集合，不能扩成全部节点不存在冲突；均值降分、集合FPR与集合召回是不同指标。

当前v3上下文检查：epsilon的一个正常/木马后代39维特征完全相同，但1/2/3层入邻域并非全部相同；另一个后代仅到1层相同，至2层已不同。delta丢失载荷也没有完全相同的三层输入多重集。故这些漏检不能直接归结为“当前三跳模型在完全同输入上必然无法区分”。相似基础特征和共同降分与泛化抑制相容，但没有证明是哪一列、哪条梯度导致；本轮未做模型/梯度干预。

## 5. 该如何解释正常对照的作用

目前支持“在同预算下，制造相似正常区域M可改善当前变换侧排序和新增正常区域误报”，同时存在域与角色代价。尚不支持“正常监督全面提高两侧木马检测”或“所有漏检都由共同结构不可分造成”。

GB普通背景变化较小、GBM相对GM增量较小、GAll未显示明确额外优势的单种子结果保留，完整四格表包含GB/GAll，不按它们表现不佳就删除。整图正常报警仍100%的旧结论不变；局部FPR改善没有等价于电路级误报解决。

角色分解仍只使用已追溯制造角色：变换验证86/215、测试106/243个正例可分类，未分类正例保留在全部召回及AP分解中。新增正常区域验证集可达PO档缺支持，不能把本轮解释为功能活跃正常逻辑或独立SAT功能作用的验证。测试已多轮审视，仍为探索性。

## 6. 是否补seed1、2

**建议补，但保持原五组合同，不先改权重、标签、模型、采样或阈值规则。**理由是正常误报收益不只是阈值变化，变换AP有真实改善，值得验证；同时原始AP有多源排序损失，部分角色召回由单个近阈值节点驱动，不能只凭seed42判定稳定收益或稳定伤害。

优先把五组都补成seed42/1/2，避免看完seed42后只保留GM/GBM产生组别选择偏差。每个seed内五组用对应同一份旧初始化；seed1/2各用原有init_s1/init_s2。冻结采样表跨seed不变、200步、39v3、改进双分支、ASL+软漏检、BF16、无SAT/等价约束/正例保护均不变。原seed42复用，不重跑。

在新训练前固定主要对比GM−G0、GBM−G0，并保留GB及GAll增量；汇总三种子均值与样本SD，同时报告每个源、每个seed的方向。区域FPR、变换AP、原始AP、实际全部正例/追溯角色召回及整图报警一起判断，不按最好seed/操作点选结论。如果原始侧排序损失反复出现，应把它作为可复现代价，再独立设计改进，不能先引入正例保护掩盖本实验问题。

本轮仅给建议，未准备或启动新训练队列。

## 证据

`_p0pilot/control_five_cause_20261107/`：threshold_score_per_source.csv/macro.csv（四格及加和分解）、AP_decomposition_per_source.csv、AP_role_contribution_per_source.csv、positive_rank_contributions.csv、role_hit_flips.csv、manufacturing_coupling_source_role.csv、recall_loss_context_cases.csv、VERIFIED.json。完整原五组预测保持，0前向/0训练/0SAT。

独立复核11,256个阈值四格视图、740个不依赖sklearn的并列正确AP四格、224个源级AP角色加和、492个宏指标与上一轮已核验结果一致；受保护旧文件哈希不变。分数/阈值分解与AP分解均为固定预测的审计，不是训练过程的因果证明。
'''
(D/name).write_text(text,encoding='utf-8')
recommendation=dict(recommend_add_seeds=[1,2],arms=['G0','GB','GM','GBM','GAll'],reuse_seed42=True,reason='realnormalROI/transranking benefit plus originalAP/rolecosts;need replicateddirection,not posthocprotection',keep='original frozen39v3 dual200budget/sampler/loss/selection/thresholds,noSAT/EQ/protection',status='recommendation_only_no_new_training',training=0,SAT=0)
(O/'SEED_RECOMMENDATION.json').write_text(json.dumps(recommendation,ensure_ascii=False,indent=2),encoding='utf-8')
entry='''

### 2026-11-07 五组预测阈值/降分/角色与原始AP审计（只读，无新训练）

复用全部五组预测，按视图→源分解“分数变化×阈值变化”四格，用两顺序平均确保分数/阈值部分相加为总差；0模型前向/0训练/0SAT/0正例保护。GM变换测试新增区域FPR降13.65个百分点，其中分数部分−13.15、阈值部分−0.51，正常降分真实存在。触发/载荷损失类型不同：原始alpha触发0.576369→0.578999，分数上升但阈值0.576005→0.600540造成漏检，纠正“alpha触发降分”的不精确表述；delta-nand载荷0.6453→0.5904为分数/阈值共同触发，epsilon-nand触发0.6414→0.5651在旧阈值下也漏检。GBM同类型。

AP不依赖阈值。原始测试GM/GBM AP0.3458→0.3171/0.3182，alpha/epsilon/gamma下降、delta/zeta略升；GM实际AP角色贡献主要为载荷−0.02455、未分类−0.00583，触发+0.00181等抵消，总差−0.02879。alpha两个载荷正例虽仍检出，前方负例5→11，是真实排序退化。变换AP上升反映负背景相对降分更强，不能据总体AP掩盖局部正例损失。

已有制造对应集合中多处正常/木马共同降分，但val_recall80未见同一角色×视图同时正常FPR下降与木马召回下降；delta正常角色仍误报、epsilon正常角色原已正确。当前epsilon有39维相同输入，但至邻域1—3层不同，未发现这些丢失点三层输入完全相同，不能断言必然不可分。角色覆盖仍受限，未分类正例完整计入AP/全部召回；整图报警100%及PO缺支持限制保留。

建议补seed1、2完整五组，复用seed42；保持预算/初始化对应/采样/损失/选模/阈值不变，不先保护或调权。正常ROI收益及多源原始排序损失都值得验证稳定性，按源/seed报告方向及三种子样本SD。本轮未启动队列。独立复核11256四格视图、740AP四格、224源角色加和、492宏指标通过，旧资产保持。

详见[阈值与角色机制审计](正常对照五组_阈值降分与角色召回机制审计_20261107.md)，证据`_p0pilot/control_five_cause_20261107/`。
'''
for n in ['SAT作用证明.md','SAT工作总结.md']:
 p=D/n;b=p.read_bytes();assert '五组预测阈值/降分/角色与原始AP审计（只读' not in b.decode('utf-8-sig');(O/(n+'.before')).write_bytes(b);p.write_bytes(b+entry.replace('\n','\r\n').encode('utf-8'))
manifest={p.name:sha(p) for p in O.iterdir() if p.is_file() and p.suffix in ['.py','.json','.csv'] and p.name not in ['OUTPUT_MANIFEST.json','PUBLISHED.json']}
(O/'OUTPUT_MANIFEST.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8');(O/'PUBLISHED.json').write_text(json.dumps(dict(report=str(D/name),report_sha=sha(D/name),summaries_updated=True,training=0,SAT=0),ensure_ascii=False,indent=2),encoding='utf-8');print('Cause audit report and both summaries updated.')
