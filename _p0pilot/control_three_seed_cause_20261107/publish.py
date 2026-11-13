from pathlib import Path
import csv,hashlib,json
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;D=R/'10.15/00_说明'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(n):
 with (O/n).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert read(O/'VERIFIED.json')['passed'];ap=rows('AP_macro_all_seeds.csv');sources=rows('AP_source_all_seeds.csv');roles=rows('AP_role_all_seeds.csv');rm=rows('AP_ROLE_MACRO_all_seeds.csv');td=rows('threshold_macro_all_seeds.csv')
name='正常对照三种子_seed1反向与原始AP退化审计_20261107.md'
text='''# 三种子预测复用：seed1测试反向与原始侧AP退化

2026-11-07。只读既有五组预测、角色/区域坐标与图特征；seed42机制审计复用，seed1/2使用相同算法补齐。0模型前向、0反向、0训练、0SAT，不引入正例保护、不改标签或合同。

结论分三层：

1. **seed1变换测试反向由少数源/实现的高分正例排序损失主导，不是阈值造成AP下降。**alpha是三个种子共有弱点，seed1幅度更大，且gamma也转负，其他源收益不足抵消。
2. **原始侧排序代价不只出现在留出集，原始训练AP也3/3下降。**不能只解释为“训练内很好、到了陌生宿主才失败”，也不能将其全部归于阈值。
3. 阈值确实影响固定操作点的触发/载荷召回，但三个种子的阈值并非都提高。正常误报下降主要来自真实降分，而具体角色损失随源与seed变化。

## 1. 训练内与留出的AP方向

下表为源宏AP的新组−G0，按同一seed配对；各组均完成200次训练，使用冻结规则选中的检查点。

|组/seed|原始训练|原始验证|原始测试|变换训练|变换验证|变换测试|
|---|---:|---:|---:|---:|---:|---:|
'''
for arm in ['GM','GBM']:
 for seed in [42,1,2]:
  rr={r['key']:r for r in ap if r['arm']==arm and int(r['seed'])==seed};text+=f'|{arm}/{seed}|'+ '|'.join(f'{float(rr[k]["AP_delta"]):+.4f}' for k in ['orig_train','orig_val','orig_test','trans_train','trans_val','trans_test'])+'|\n'
text+='''
seed1变换训练和验证均改善，测试却下降，确有迁移/实现依赖问题；原始侧则连训练AP都下降，存在更直接的拟合/目标取舍线索。这不能单凭预测证明是orig/trans梯度冲突、某一特征错误或架构必然缺陷；当前只能确认代价已经体现在原始训练排序中。

## 2. seed1为什么反向：源与实现分解

### 变换测试各源AP差

|源|GM seed42|GM seed1|GM seed2|GBM seed1|
|---|---:|---:|---:|---:|
'''
src=sorted({r['source'] for r in sources if r['key']=='trans_test'})
for s in src:
 def val(seed,arm):return float(next(r['AP_delta'] for r in sources if int(r['seed'])==seed and r['arm']==arm and r['key']=='trans_test' and r['source']==s))
 text+=f'|{s}|'+ '|'.join(f'{val(seed,arm):+.4f}' for seed,arm in [(42,'GM'),(1,'GM'),(2,'GM'),(1,'GBM')])+'|\n'
text+='''
seed1 GM的alpha源下降0.09075，gamma下降0.02205；delta、epsilon、zeta仍提升。由于五个木马源等权，alpha/gamma分别贡献全体AP变化−0.01815/−0.00441，其他三源合计约+0.01077，净差−0.01179。GBM同样由alpha/gamma主导，净差−0.01325。

alpha本身在三个seed都变差，不能仅称seed1偶然噪声；seed1是这一源弱点放大，加上其他源补偿不足。gamma的反向仅出现在seed1，另两个seed为正。

### seed1 alpha按实现拆分（GM−G0）

|实现|AP差|
|---|---:|
|ys_id|−0.2442|
|ys_opt|−0.1855|
|ys_abc|−0.0584|
|ys_aig|+0.0094|
|ys_nand|+0.0250|

同一源的id/opt损失最大，aig/nand反而改善，说明不是整个alpha在所有实现上同步失效。既不能只看源平均，也不能把这些视图当独立电路样本。

### 高分正例仍检出，AP却下降

|seed1 alpha正例（现有节点名）|角色覆盖状态|G0→GM分数|前方/并列负例数|所在视图AP贡献变化|
|---|---|---|---|---:|
|opt:g__TrojanAHJ.IN2_8|未分类|0.9932→0.9722|0→5|−0.13889|
|id:g_g8918_2|未分类|0.9935→0.9774|0→2|−0.08333|
|id:g__TrojanAHJ.IN2_8|未分类|0.9956→0.9822|0→1|−0.08333|
|id:g__TrojanAP1.Q_6|未分类|0.9707→0.9176|4→16|−0.03810|
|opt:g__TrojanAP1.Q_6|未分类|0.9709→0.9164|8→34|−0.03194|

这些分数仍远高于seed1 GM的80%校准阈值0.5011，固定阈值召回未必丢失，但正例不再排在最前，AP必然受影响。表中贡献是其视图AP贡献；合成源宏时还要按视图/源权重，不能直接将这些条目相加当全体AP。

名称只用于追溯，不凭TrojanAP/AHJ前缀重新贴角色或安全标签。g_g8918_2一类宿主名正例、端口展开点尤其需要现有血缘/原网表复核，不能从名字推断是误标。

## 3. 制造角色覆盖为什么影响解释

seed1 alpha源AP差−0.09075中，已追溯payload贡献约−0.0145、trigger约+0.0031，**未分类正例约−0.0794**；gamma源未分类贡献约−0.0342，已追溯payload/trigger贡献却为正。不能把全体AP下降简单概括成“触发、载荷都学坏了”。

未分类不代表无标签：这些节点仍是原有可信正标，全部进入AP和总体召回；只是制造角色映射尚不完整。变换验证86/215、测试106/243正例可分类的边界保持，当前角色统计不能覆盖全部木马机制。

## 4. 原始侧为什么三个seed都下降

### 原始测试：独立源AP差（GM−G0）

|源|seed42|seed1|seed2|
|---|---:|---:|---:|
'''
for s in sorted({r['source'] for r in sources if r['key']=='orig_test'}):
 text+=f'|{s}|'+ '|'.join(f'{float(next(r["AP_delta"] for r in sources if r["source"]==s and r["key"]=="orig_test" and r["arm"]=="GM" and int(r["seed"])==seed)):+.4f}' for seed in [42,1,2])+'|\n'
text+='''
alpha、epsilon、gamma三个原始测试源在三个seed都下降，delta/zeta方向不一。因此原始侧宏AP下降具有重复性，但受损源和幅度仍有差异。

### 原始测试：精确的角色AP贡献

AP可写成每个正例在其分数处precision的平均，按角色汇总后仍保留全部负例、并列处理及原视图/源权重。以下为GM−G0，不是角色子集重算AP：

|seed|payload|trigger|payload_select|未分类|合计AP差|
|---|---:|---:|---:|---:|---:|
'''
for seed in [42,1,2]:
 rr={r['role_class']:float(r['AP_contribution_delta']) for r in rm if int(r['seed'])==seed and r['arm']=='GM' and r['key']=='orig_test'};total=float(next(r['AP_delta'] for r in ap if int(r['seed'])==seed and r['arm']=='GM' and r['key']=='orig_test'));text+=f'|{seed}|'+ '|'.join(f'{rr[k]:+.5f}' for k in ['payload','trigger','payload_select','unclassified'])+f'|{total:+.5f}|\n'
text+='''
seed42/1主要由载荷与未分类正例的排序损失体现；seed2载荷贡献为正，载荷选择损失更突出。稳定的是原始总体AP代价，不是“同一种角色在每个seed都下降”。GBM及全部划分的同口径分解保留于CSV。

已知例子：seed42原始alpha两个载荷节点仍越过报警阈值，但前方负例5→11；召回保持1，AP下降。seed1的高分展开节点也有类似现象。原始AP退化不可能由阈值直接造成。

## 5. 阈值、分数下降与排序退化必须分开

复用原四格：旧分数/旧阈值a、新分数/旧阈值b、旧分数/新阈值c、新分数/新阈值d；分数部分=((b−a)+(d−c))/2，阈值部分=((c−a)+(d−b))/2，严格相加等于总差。

这只是固定预测的描述性分解，不是训练梯度因果比例。阈值仍只来自原验证校准，未用测试重调。

### 变换测试GM正常区域FPR（val_recall80）

|seed|G0阈值→GM阈值|FPR总差（百分点）|分数部分|阈值部分|
|---|---|---:|---:|---:|
'''
for seed in [42,1,2]:
 r=next(r for r in td if int(r['seed'])==seed and r['arm']=='GM' and r['key']=='trans_test' and r['operation']=='val_recall80' and r['scope']=='normal_primary_added');text+=f'|{seed}|{float(r["threshold0"]):.6f}→{float(r["threshold1"]):.6f}|{100*float(r["delta"]):+.2f}|{100*float(r["score_effect"]):+.2f}|{100*float(r["threshold_effect"]):+.2f}|\n'
text+='''
seed1/2阈值降低，反而抵消了一部分正常误报收益；FPR仍下降，说明真实正常区域降分在三种子中都存在。不能套用seed42“阈值上移”解释所有seed。

### 变换测试GM触发/载荷召回

|seed|角色|召回总差（百分点）|分数部分|阈值部分|平均分数变化|
|---|---|---:|---:|---:|---:|
'''
for seed in [42,1,2]:
 for scope in ['role/trigger','role/payload']:
  r=next(r for r in td if int(r['seed'])==seed and r['arm']=='GM' and r['key']=='trans_test' and r['operation']=='val_recall80' and r['scope']==scope);text+=f'|{seed}|{scope[5:]}|{100*float(r["delta"]):+.2f}|{100*float(r["score_effect"]):+.2f}|{100*float(r["threshold_effect"]):+.2f}|{float(r["score_delta"]):+.5f}|\n'
text+='''
seed1的触发/载荷召回可以上升而AP下降，二者并不矛盾：召回只检查阈值处几个点，AP考察整条排序。分数均值下降也不必导致召回下降；必须看具体节点与阈值相对位置，不能以均值替代漏检分析。

前轮seed42三个例子的判断保留：原始alpha触发分数略升，丢失由阈值上移引起；delta载荷需要分数下降与阈值上移共同发生才丢失；epsilon触发在旧阈值下也丢失。它们不能作为所有种子、所有角色的通用原因。

正例分数/负例分数替换的AP四格也保留，但跨模型拼接受校准标度影响，不能把分量称为训练因果损害；主要依据仍是各模型自身的正例名次、前方负例数和精确AP贡献。

## 6. 可以判断什么，还不能判断什么

证据支持：M监督降低当前正常区域分数，同时在部分源/实现使高分正例相对排序受损；变换侧其他源的背景降分收益有时能抵消该损失，seed1未抵消。原始域训练排序也下降，提示共享模型/目标下已经存在拟合取舍，而不只是留出宿主问题。

尚未证明：具体哪个监督节点、特征列或参数梯度导致损失；不能据预测直接宣布orig/trans梯度冲突、节点误标、三跳必然不可分或某种门型编码错误。

选模也未被完全单独分离：seed42 GM与G0均选195，seed1均选185，因此这两个seed的代价不是由“选了不同更新次数”单独造成；seed2 G0选170、GM选195，存在时期差异。本轮不做新模型前向，尚不能排除seed2的选模贡献。

整图报警仍全部100%，正常新增验证PO可达档缺支持，角色覆盖有限及单一验证/测试宿主的限制保持。三种子不等于三个独立宿主，不能由这些分析扩张成普遍功能因果结论。

## 7. 下一步建议

1. **先核查关键正例的制造血缘/角色。**优先seed1 alpha的AHJ.IN2、AP0/AP1端口展开节点和g_g8918_2；复用现有映射、原网表与证明，区分植入门后代、被改写宿主节点、不同功能中间节点。保留现标签，只补审计角色与证据，不能凭名称或预测重贴标签。
2. **用已有末步200检查点做统一轮次离线推理对照。**与现有验证选中预测并列，按源检查原始AP损失是否仍在、seed1反向是否依赖选模；不重训、不按测试选新检查点。当前只是建议，本轮未做新前向。
3. 若共同轮次下代价仍稳定，再在固定训练批次做无更新的原始/变换/M负例分项梯度诊断，决定是否值得设计一个模型/采样单因素；此时仍不引入正例保护，不同时调权、换池或改阈值。

不建议继续补更多seed、扩大SAT或直接加大正常监督。正常对照“等预算降局部误报”的成果可以保留，但原始域排序和特定实现的代价必须同时写出。

## 8. 证据和核验

seed42旧审计`_p0pilot/control_five_cause_20261107/`完整复用；新增`control_five_cause_seed1_20261107/`、`control_five_cause_seed2_20261107/`各独立复核11,256个阈值四格视图、740个AP四格、224个源级角色加和、492个宏指标。新审计首次仅因seed1/2没有各自PUBLISHED元数据失败，改为绑定已存在的三种子总发布记录后通过；日志保留，训练及原结果未改。

汇总`_p0pilot/control_three_seed_cause_20261107/`：AP_source_all_seeds.csv、AP_macro_all_seeds.csv、AP_ROLE_MACRO_all_seeds.csv、threshold_source_all_seeds.csv、threshold_macro_all_seeds.csv、SEED1_TEST_SOURCE_CONTRIBUTIONS.csv、SEED1_LARGEST_POSITIVE_RANK_LOSSES.csv、VERIFIED.json。36组角色AP加和与各源/宏总差一致，旧文件哈希保持。全部分析只复用预测，0前向/0训练/0SAT。
'''
(D/name).write_text(text,encoding='utf-8')
entry='''

### 2026-11-07 三种子预测机制复核：seed1反向与原始AP一致代价（无训练）

复用五组三seed预测及seed42既有审计，补seed1/2相同四格和AP贡献分解；0模型前向/0反向/0训练/0SAT/0正例保护。seed1 GM变换测试AP−0.01179主要由alpha源−0.09075、gamma−0.02205主导，其他3源仍提升；alpha在三seed都下降，seed1幅度更大，id/opt实现损失最强（−0.2442/−0.1855）。最大损失来自未分类高分正例，含AHJ.IN2/AP端口展开名及宿主名节点；其分数仍远过阈值但前方负例增多，不凭名称新贴角色。

原始训练/验证/测试AP的GM/GBM均3/3下降，不能只解释成陌生宿主泛化失败。原始测试alpha/epsilon/gamma三个源AP均3/3下降，其他源方向混合。角色代价不同：seed42/1载荷及未分类排序损失突出，seed2载荷贡献为正而载荷选择损失更强，不能说所有seed同角色普降。

阈值不是AP原因，且不都上移：GM变换测试阈值seed42 0.5760→0.6005、seed1 0.5220→0.5011、seed2 0.6039→0.5971。FPR差中分数部分分别−13.15/−8.97/−19.65个百分点，阈值部分−0.51/+1.83/+0.81；正常实际降分跨seed存在。seed1触发/载荷召回升但AP降，说明阈值检出与全排序不同。选模时期因素尚未完全隔离：seed42/1 GM与G0同选195/185，seed2不同170/195；不能凭预测断言梯度冲突或标签错误。

建议下一轮先只读核查关键展开正例的血缘/制造角色，并用已保存末步200检查点补统一轮次离线推理，与现有选中结果并列，再决定是否需要无更新的域/M负例梯度诊断。不重训、不按测试选检查点、不改标签/权重/阈值、不加入正例保护。本轮未做这些新前向。每新增seed独立复核11256四格视图、740AP四格、224源角色加和、492宏指标通过，三seed36组角色AP加和一致，旧资产保持。

详见[三种子AP与角色机制复核](正常对照三种子_seed1反向与原始AP退化审计_20261107.md)，汇总`_p0pilot/control_three_seed_cause_20261107/`，新增审计`control_five_cause_seed1_20261107/`、`control_five_cause_seed2_20261107/`。
'''
for n in ['SAT作用证明.md','SAT工作总结.md']:
 p=D/n;b=p.read_bytes();assert '三种子预测机制复核：seed1反向与原始AP一致代价（无训练）' not in b.decode('utf-8-sig');(O/(n+'.before')).write_bytes(b);p.write_bytes(b+entry.replace('\n','\r\n').encode('utf-8'))
for seed in [1,2]:
 folder=R/f'_p0pilot/control_five_cause_seed{seed}_20261107';manifest={p.name:sha(p) for p in folder.iterdir() if p.is_file() and p.suffix in ['.py','.json','.csv','.log'] and p.name!='OUTPUT_MANIFEST.json'};(folder/'OUTPUT_MANIFEST.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
manifest={p.name:sha(p) for p in O.iterdir() if p.is_file() and p.suffix in ['.py','.json','.csv','.log'] and p.name not in ['OUTPUT_MANIFEST.json','PUBLISHED.json']};(O/'OUTPUT_MANIFEST.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8');(O/'PUBLISHED.json').write_text(json.dumps(dict(report=str(D/name),report_sha=sha(D/name),summaries_updated=True,model_forwards=0,training=0,SAT=0),ensure_ascii=False,indent=2),encoding='utf-8');print('Three-seed cause report and both summaries updated.')
