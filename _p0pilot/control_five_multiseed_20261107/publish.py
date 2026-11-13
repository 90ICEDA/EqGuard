from pathlib import Path
import csv,hashlib,json
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;D=R/'10.15/00_说明';ARMS=['G0','GB','GM','GBM','GAll']
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(n):
 with (O/n).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
assert read(O/'VERIFIED.json')['passed'];stats=rows('KEY_RESULTS_meanSD.csv');delta=rows('PAIRED_KEY_DELTAS_meanSD.csv');raw=rows('KEY_RESULTS_all_seeds.csv');sdirection=rows('SOURCE_DIRECTION_COUNTS.csv');ps=rows('paired_source_meanSD.csv');rd=rows('PAIRED_ROLE_SOURCE_meanSD.csv')
def key(arm,split,op='val_recall80'):return next(r for r in stats if r['arm']==arm and r['key']==split and r['operation']==op)
def diff(comp,split,op='val_recall80'):return next(r for r in delta if r['comparison']==comp and r['key']==split and r['operation']==op)
def fmt(r,col,percent=False,signed=False):
 if r[col+'_mean']=='':return 'NA'
 factor=100 if percent else 1;mean=float(r[col+'_mean'])*factor;sd=float(r[col+'_sampleSD'])*factor;precision=2 if percent else 4;return (f'{mean:+.{precision}f}' if signed else f'{mean:.{precision}f}')+f' ± {sd:.{precision}f}'
name='正常对照五组_三种子公平实验汇总_20261107.md'
text='''# 正常对照五组：seed42/1/2公平实验汇总

2026-11-07。seed1、2十组各200次训练与独立核验已完成，新增2000次更新；seed42五组1000次全部复用，共15组/3000次，未重跑旧结果。

**主要结论：正常区域误报下降的方向较稳定；原始侧AP下降也重复出现。变换测试AP仅2/3种子提升，角色召回有源和种子依赖，不能把结果写成无代价的全面提升。**

## 1. 保持了哪些条件

ginvenv_gpu、39维v3、改进双分支split29/hidden64/2+2+post1（46,620参数）、200次更新、Adam lr0.0002/weight_decay0.001/clip1、BF16、原ASL+1.4软漏检平方保持。每个seed内五组使用对应的同一旧初始化；三个seed的实际初始张量摘要不同，既不是重复seed42，也不只检查了文件名。

显式使用FiveGroupLoader/main_fanout05：原始每步正136、负8296；变换每步正829、负8336；每域公共负8192，B/M块各48，U原始8/变换48。采样表跨seed完全相同，实际索引及曝光预算逐项核验；不提升可信标签，不加SAT、等价约束、正例保护或角色权重。

五组均看相同完整图，G0只将正常对照监督槽位换为配对H，检验的是正常负标签来源的贡献。每5次沿用变换验证可信__inj视图AP选模，每组仍完成全部200次更新；验证分位阈值规则与此前一致，不用测试选模或调阈值。小型CUDA归约预热不含模型/优化器更新，新增十组训练均成功，没有重复已提交更新。

## 2. 统计口径

- 每视图先算，再源内等视图平均，最后等源平均；在每个seed得到源宏指标后，才对三个seed计算均值和**样本SD（ddof=1）**。
- 所有“±”均为跨三个随机种子的样本SD；不是标准误、置信区间或跨宿主SD。百分比表中±后的单位为百分点，AP按0—1原值。
- 配对差值先在同一seed计算GM−G0等差，再对三个差求均值/SD；不拿两组SD相减，也不把变换视图当独立重复。
- 主展示沿用val_recall80操作点；“80”是变换验证节点池校准，实际源宏/测试召回另报。AP与阈值无关。
- 方向计数仅用1e-12数值容差，不是显著性或有效提升门槛；3个种子未增加独立宿主数，测试仍为探索性。

## 3. 五组主要结果

AP是可信木马视图节点AP的源宏平均；新增正常区域验证/测试各6源、130/142节点。整图报警指正常视图任意物理节点过阈值，包含对未训练可信节点的分数检查，但不将它们升级为训练标签。触发/载荷仅是既有可追溯制造角色子集。

'''
for split,label in [('trans_val','变换验证'),('trans_test','变换测试')]:
 text+=f'### {label}：均值 ± 样本SD\n\n|组|节点AP|新增区域FPR（%）|全部正例召回（%）|触发召回（%）|载荷召回（%）|整图报警（%）|\n|---|---:|---:|---:|---:|---:|---:|\n'
 for arm in ARMS:
  r=key(arm,split);text+=f'|{arm}|{fmt(r,"node_AP")}|{fmt(r,"normal_added_FPR",True)}|{fmt(r,"all_positive_recall",True)}|{fmt(r,"trigger_recall",True)}|{fmt(r,"payload_recall",True)}|{fmt(r,"whole_normal_view_alarm",True)}|\n'
 text+='\n'
text+='''
GM测试新增区域FPR平均降低约13.21个百分点，GBM约12.38个百分点，两者3/3种子都降低。变换验证AP两者3/3提升；变换测试只有2/3提升，seed1均反向。测试GM的AP配对增量约+0.0100±0.0191、GBM约+0.0097±0.0202，不应仅凭均值为正就写成稳定AP提升。

### 各seed的变换测试结果

|seed|G0 AP|GM AP|GBM AP|G0区域FPR（%）|GM区域FPR（%）|GBM区域FPR（%）|
|---|---:|---:|---:|---:|---:|---:|
'''
for seed in [42,1,2]:
 rr={a:next(r for r in raw if int(r['seed'])==seed and r['arm']==a and r['key']=='trans_test' and r['operation']=='val_recall80') for a in ['G0','GM','GBM']};text+=f'|{seed}|'+ '|'.join(f'{float(rr[a]["node_AP"]):.4f}' for a in ['G0','GM','GBM'])+'|'+ '|'.join(f'{100*float(rr[a]["normal_added_FPR"]):.2f}' for a in ['G0','GM','GBM'])+'|\n'
text+='''
### 高召回操作点（变换测试，val_recall90）

|组|区域FPR（%）|实际全部正例召回（%）|触发召回（%）|载荷召回（%）|
|---|---:|---:|---:|---:|
'''
for arm in ARMS:
 r=key(arm,'trans_test','val_recall90');text+=f'|{arm}|'+ '|'.join(fmt(r,col,True) for col in ['normal_added_FPR','all_positive_recall','trigger_recall','payload_recall'])+'|\n'
text+='''
提高召回操作点后，误报仍很高，M仍有下降，但载荷召回均值低于G0；不能只选80%点讲收益。所有五组整图报警在三个seed均100%±0%，局部误报改善尚未解决电路级报警。

## 4. 原始侧的代价

原始侧复用同一全局变换验证阈值，不另挑原始阈值。

|划分|组|节点AP|新增区域FPR（%）|全部正例召回（%）|触发召回（%）|载荷召回（%）|
|---|---|---:|---:|---:|---:|---:|
'''
for split,label in [('orig_val','验证'),('orig_test','测试')]:
 for arm in ARMS:
  r=key(arm,split);text+=f'|{label}|{arm}|{fmt(r,"node_AP")}|'+ '|'.join(fmt(r,col,True) for col in ['normal_added_FPR','all_positive_recall','trigger_recall','payload_recall'])+'|\n'
text+='''
GM/GBM在原始验证和原始测试的AP均为3/3种子下降。原始测试配对差分别为−0.0154±0.0128、−0.0122±0.0140；原始验证分别约−0.0361±0.0222、−0.0247±0.0050。原始侧绝对AP种子波动尤其大，应使用配对差和源分层，不能把seed42的高绝对AP视为通用水平。

## 5. 收益/代价是否稳定：配对差

下表为“新组−G0”，百分比指标的差值单位为百分点。“改善种子/恶化种子”根据指标有利方向计算，其余为不变。

|划分|比较|指标|差值均值 ± SD|改善/恶化种子|
|---|---|---|---:|---|
'''
for split,label in [('trans_val','变换验证'),('trans_test','变换测试'),('orig_test','原始测试')]:
 for comp in ['GM-G0','GBM-G0']:
  r=diff(comp,split)
  for col,metric,pct in [('node_AP','AP',False),('normal_added_FPR','区域FPR',True),('all_positive_recall','全部正例召回',True),('trigger_recall','触发召回',True),('payload_recall','载荷召回',True)]:text+=f'|{label}|{comp}|{metric}|{fmt(r,col,pct,True)}|{r[col+"_improving_seeds"]}/3，{r[col+"_worsening_seeds"]}/3|\n'
text+='''
三种子修正了“召回普遍下降”的概括：GM/GBM变换测试全部召回与触发召回均值略升，但各有1个seed下降；载荷均值下降约0.96个百分点，2/3下降。原始测试触发下降主要受seed42的alpha影响，另两个seed为不变/略升；原始载荷召回均值反而上升。AP排序代价比固定操作点召回代价更一致。

## 6. 独立源分层

### 变换测试新增正常区域：配对FPR差（百分点）

|正常源|GM−G0均值±SD|下降/上升种子|GBM−G0均值±SD|下降/上升种子|
|---|---:|---|---:|---|
'''
ss=sorted({r['source'] for r in sdirection if r['key']=='trans_test' and r['scope']=='normal_primary_added' and r['operation']=='val_recall80'})
for source in ss:
 vals=[]
 for comp in ['GM-G0','GBM-G0']:
  r=next(r for r in ps if r['comparison']==comp and r['key']=='trans_test' and r['scope']=='normal_primary_added' and r['PO_bin']=='all' and r['source']==source and r['operation']=='val_recall80');s=next(r for r in sdirection if r['comparison']==comp and r['key']=='trans_test' and r['scope']=='normal_primary_added' and r['source']==source and r['operation']=='val_recall80');vals.extend([fmt(r,'FPR_difference',True,True),f'{s["FPR_difference_negative_seeds"]}/3，{s["FPR_difference_positive_seeds"]}/3'])
 text+=f'|{source}|'+ '|'.join(vals)+'|\n'
text+='''
GM六个正常源中4个在3/3种子下降，另2个2/3下降且1次不变；GBM为5个3/3下降，另1个2/3下降且1次不变。当前没有这些正常源FPR反向上升的seed，不是仅一个源拉低宏平均；但仍是同一测试宿主中的6个制造源，不能当6个新宿主。

### 木马制造角色：变换测试GM−G0召回差（百分点）

|木马源|角色|均值 ± SD|下降/上升种子|
|---|---|---:|---|
'''
for r in rd:
 if r['comparison']=='GM-G0' and r['key']=='trans_test' and r['operation']=='val_recall80' and r['role_class'] in ['trigger','payload']:text+=f'|{r["source"]}|{r["role_class"]}|{fmt(r,"recall_delta",True,True)}|{r["recall_worsening_seeds"]}/3，{r["recall_improving_seeds"]}/3|\n'
text+='''
epsilon触发、delta载荷的下降各重复2/3，delta/gamma触发则有提升；不能将触发均值略升解释成所有触发源都改善。GBM、原始侧和其余角色的全部均值/SD及方向存于PAIRED_ROLE_SOURCE_meanSD.csv，未按结果删源。角色标签描述制造来源，不等同于新SAT证明其当前功能必要性。

## 7. 普通背景B及剩余U的增量

变换测试、val_recall80，AP差按0—1原值，FPR差为百分点：

|比较|AP差均值±SD|区域FPR差均值±SD|正常全背景FPR差均值±SD|
|---|---:|---:|---:|
'''
for comp in ['GB-G0','GBM-GM','GAll-GBM']:
 r=diff(comp,'trans_test');text+=f'|{comp}|{fmt(r,"node_AP",False,True)}|{fmt(r,"normal_added_FPR",True,True)}|{fmt(r,"normal_all_FPR",True,True)}|\n'
text+='''
B单独的效果较小；GBM相对GM在变换测试没有稳定增量。U的结论需比seed42更精确：GAll相对GBM可进一步降低部分区域误报，但测试AP在3/3下降，表现为额外权衡，不能简单称U完全无用。U仍是追踪不完整等剩余可信正常标签，不能归功于某类明确功能。

## 8. 限制和下一步

正常新增验证区域PO可达档缺支持，冻结PO标准化FPR保持NA，未删档重归一化；普通背景不能与新增区域混报。采样B/M虽然同条目剂量，独立节点数和残余PO分布不相同，结果不是独立功能因素或SAT收益证明。

角色覆盖与seed42完全一致：变换验证86/215、测试106/243正例可分类，原始验证35/40、测试40/45；未分类仍进入全部召回和AP。3个随机种子不是3个独立宿主；仅单一验证宿主和单一测试宿主，不能把样本SD当跨宿主泛化不确定性。

建议暂不追加训练、保护正例或修改区域权重。先复用三种子预测重点审查：为何seed1变换测试AP反向、为何原始AP损失3/3出现，以及epsilon/delta的角色损失是否仍分别来自分数变化/阈值变化。研究结论可表述为“等预算M监督对新增正常区域降误报方向可重复，但排序收益具有域和种子依赖，需同时报告角色与原始侧代价”。不把GAll或GBM直接宣布为全面最优。

## 9. 核验和文件

每个新增seed均已独立核验2000条实际监督记录、200步五组、选模/阈值、BN和实际Adam步数、源级误报/角色及整图指标。三seed初始化实际张量不同，五组内部初始化相同；采样索引跨seed完全相同。原seed42和全部绑定输入哈希保持。

跨seed另用statistics.mean/stdev独立复核268,968个统计单元、2,142个配对指标差，最大数值误差约1.36e-16；样本SD正确使用ddof=1，缺支持仍NA。新增十组无失败或重复成功更新。汇总程序改用按键索引避免重复全表扫描，保留过程日志，未因此重跑训练。

新训练目录：`_p0pilot/control_five_seed1_20261107/`、`_p0pilot/control_five_seed2_20261107/`；seed42原目录完整保留。每组含best/resume.pt、200步历史、六划分预测与核验结果。

汇总目录`_p0pilot/control_five_multiseed_20261107/`：KEY_RESULTS_meanSD.csv、PAIRED_KEY_DELTAS_meanSD.csv、source_meanSD.csv、paired_source_meanSD.csv、whole_source_meanSD.csv、role_source_meanSD.csv、PAIRED_ROLE_SOURCE_meanSD.csv、SOURCE_DIRECTION_COUNTS.csv、standardized_meanSD.csv、selected_checkpoints.csv、VERIFIED.json。全部逐seed原数值也保留为对应all_seeds.csv。无新增SAT、等价约束或正例保护。
'''
(D/name).write_text(text,encoding='utf-8')
entry='''

### 2026-11-07 正常对照五组三种子补齐（seed42复用，新增seed1/2）

ginvenv_gpu补齐seed1、2各5组×200步，新增2000更新；复用seed42原1000更新，共15组/3000次。39v3、改进双分支46620参数、旧对应初始化、main_fanout05采样和正负预算、BF16/Adam/损失/选模/阈值均保持，0SAT/0等价约束/0正例保护。新十组成功，无重复已提交更新，旧结果及输入哈希保持。

先每seed按视图→独立源统计，再跨seed求均值和样本SD(ddof1)；差值先同seed配对。变换测试AP G0/GB/GM/GBM/GAll=0.2588±0.0217/0.2599±0.0216/0.2688±0.0185/0.2685±0.0183/0.2673±0.0183；新增区域FPR=72.88±4.58/73.11±3.83/59.67±3.81/60.50±4.37/58.45±2.44%。GM/GBM误报3/3种子下降，AP验证3/3提升但测试仅2/3（seed1反向）；测试配对AP增量+0.0100±0.0191/+0.0097±0.0202，不能称稳定测试AP提升。

原始测试AP G0=0.2100±0.1277、GM=0.1947±0.1195、GBM=0.1978±0.1173；原始验证/测试AP均3/3下降，是真实需保留的代价。召回不宜概括为普降：变换测试触发G0/GM/GBM=63.61±1.94/65.37±4.78/65.37±4.78%，2种子升1降；载荷89.21±0.51→88.25±2.31%，2降1升。epsilon触发、delta载荷各重复2/3下降；原始alpha触发损失仅seed42出现，原始载荷均值反而提高。整图正常报警全部100%±0%，未解决电路级报警。

独立正常源：GM测试6源中4源3/3误报下降、2源2/3下降1不变；GBM为5源3/3、1源2/3，无这些源反向上升。B增量小，U可进一步降部分误报但GAll相对GBM测试AP3/3降低，属权衡而非简单无用。角色覆盖与PO缺档NA不变，3随机种子不是3新宿主。独立复核268968统计单元和2142配对差通过。建议先复用三seed预测审计seed1测试反向、原始AP一致下降和epsilon/delta角色损失，暂不继续训练/调权/保护。

详见[三种子公平实验汇总](正常对照五组_三种子公平实验汇总_20261107.md)。新结果`_p0pilot/control_five_seed1_20261107/`、`control_five_seed2_20261107/`；汇总`_p0pilot/control_five_multiseed_20261107/`。
'''
for n in ['SAT作用证明.md','SAT工作总结.md']:
 p=D/n;b=p.read_bytes();assert '正常对照五组三种子补齐（seed42复用' not in b.decode('utf-8-sig');(O/(n+'.before')).write_bytes(b);p.write_bytes(b+entry.replace('\n','\r\n').encode('utf-8'))
for seed in [1,2]:
 folder=R/f'_p0pilot/control_five_seed{seed}_20261107';manifest={str(p.relative_to(folder)):sha(p) for p in folder.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix in ['.py','.json','.csv','.npy','.pt','.log'] and p.name!='OUTPUT_MANIFEST.json'};(folder/'OUTPUT_MANIFEST.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
manifest={p.name:sha(p) for p in O.iterdir() if p.is_file() and p.suffix in ['.py','.json','.csv','.log'] and p.name not in ['OUTPUT_MANIFEST.json','PUBLISHED.json']};(O/'OUTPUT_MANIFEST.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8');(O/'PUBLISHED.json').write_text(json.dumps(dict(report=str(D/name),report_sha=sha(D/name),summaries_updated=True,new_updates=2000,reused_updates=1000,total_updates=3000,SAT=0,EQ=0),ensure_ascii=False,indent=2),encoding='utf-8');print('Three-seed report and both summaries updated.')
