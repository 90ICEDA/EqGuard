"""Publish fixed-budget results without changing criteria or historical artifacts."""
from pathlib import Path
import csv,hashlib,json
O=Path(__file__).resolve().parent;R=O.parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(n):
 with (O/n).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def main():
 v=read(O/'VERIFIED.json');pr=read(O/'PRIMARY_RESULT.json');rep=read(O/'REPEAT_REFERENCE.json');assert v['passed'] and rep['model_BN_unchanged']
 for p,h in read(O/'EXECUTION_CONTRACT.json')['frozen_files'].items():assert sha(R/p)==h,p
 for p,h in v['output_SHA'].items():assert sha(O/p)==h,p
 arms=['Z','A_R','A_P','S_R','S_P'];summ=rows('evaluation_summary.csv');by=rows('evaluation_by_source.csv');ck=rows('checkpoint_audit.csv');sens=rows('semantic_sensitivity.csv');train=read(O/'TRAINING_COMPLETE.json')
 primary='\n'.join(f"|{a}|{100*pr['root64'][a]['source_macro_win']:.2f}%|{pr['root64'][a]['source_macro_auc']:.4f}|{pr['root64'][a]['cross_auc']:.4f}|" for a in arms)
 sources=pr['primary_sources'];source_table=[]
 for source in sources:
  vals=[next(r for r in by if r['arm']==a and r['condition']=='correct' and r['space']=='root64' and r['source']==source) for a in ['Z','S_R','S_P']]
  source_table.append('|'+source+'|'+str(vals[0]['triples'])+'|'+'|'.join(f"{100*float(r['anchor_win']):.2f}%" for r in vals)+f"|{100*(float(vals[1]['anchor_win'])-float(vals[2]['anchor_win'])):+.2f}个百分点|")
 secondary=[]
 for space in ['root64','mean64','concat128','projection32']:
  gg=[next(r for r in summ if r['arm']==a and r['condition']=='correct' and r['space']==space and r['scope']=='primary_two_sources') for a in ['Z','S_R','S_P']]
  secondary.append('|'+space+'|'+'|'.join(f"{100*float(r['source_macro_win']):.2f}%" for r in gg)+'|')
 strata=[]
 for scope in ['shallow_primary','deep_primary','has_mux_primary']:
  gg=[next(r for r in summ if r['arm']==a and r['condition']=='correct' and r['space']=='root64' and r['scope']==scope) for a in ['Z','S_R','S_P']]
  strata.append('|'+scope+'|'+str(gg[0]['triples'])+'|'+'|'.join(f"{100*float(r['source_macro_win']):.2f}% / {float(r['source_macro_auc']):.4f}" for r in gg)+'|')
 report='''# 同根三候选相对排序：seed42五组固定50步探索性预训练

日期：2026-11-06。状态：**五组各50步全部完成，未做检测微调，未追加SAT，旧结果全部保留。**

## 1. 结论

新三候选目标在初始预检中确实让真实/置换关联梯度产生差别，但**本轮没有把这个差别转化成满足冻结门槛的留出函数排序收益**。S_R主指标胜率76.59%，S_P为76.77%，Z为76.06%；S_R的源等权函数区分AUC略升至0.7465，但两源方向不一致，不能只挑AUC宣布有效。

因此暂不进入检测微调，不补种子或扩SAT。小幅AUC与次要读出的变化保留为探索线索，不作为木马检测AP提升或跨宿主功能泛化成果。

## 2. 实际配置与预算

用ginvenv_gpu执行，五组Z/A_R/A_P/S_R/S_P全部从相同原init_s42、零语义适配器、投影seed819开始；逐步使用同一采样和随机种子。39v3、有向图、正确共享边界/MUX角色、dual2+2+post1 hidden64、root64+mean64→128→64→32、dropout0.2、BN训练模式、BF16保持；Adam lr0.0002/wd0.001/clip1，关联系数1、CE温度1、方差系数0.1。检测分类头冻结且未变，节点标签和监督文件未修改。

形式化证据仅用于已有等价配对和不同函数反例；本轮没有追加SATk4节点特征，也没有SAT求解。

每组8源各25三元组名额，合计200块/143唯一三元组、400关联正对名额/286唯一候选正对、143第三函数对、800锥根查询、2400候选距离、1200共有负项及1200端点读出名额。单函数实际最大重复2次、单节点锥读出曝光27。所有组同一索引、同一负边、逐步正目标曝光相同。

实际共250次优化器更新，250次训练前向；主脚本7次验证前向，另1次正确输入重复前向校准数值噪声，没有额外训练。所有组固定最终第50步，不按验证挑检查点。BN自身的新模型运行计数均恰增50，旧模型及初始文件保持。

为减少开销，五个独立模型/优化器按同一update交错运行，复用当步边界特征准备和池化索引，不共享权重或优化器状态。每次成功更新原子保存新实验自己的恢复点，旧实验目录不写入。

## 3. 冻结主评价

验证60个互不重叠三元组；主要统计ctlmatchb的27块与injalpha的32块，各源等权。injzeta仅1块单列描述，不进入主要结论。全部来自s38417同一宿主。每块四个有方向的同根查询包含对称方向，不能算四个独立样本。

主读出root64，距离RMS。同根胜率表示真实跨实现对应比置换对应更近，等距离计0.5；源等权胜率先在每源内求均值，再对两源平均。AUC区分真实/错误跨实现距离，**不是木马检测AP**。Z包含相同不同函数分离与方差项，是训练后的公共约束控制，非随机未训练模型。

|组|源等权同根胜率|源等权函数AUC|主要两源合并AUC|
|---|---:|---:|---:|
'''+primary+'''

S_R−S_P胜率为-0.17个百分点，S_R−Z为+0.54个百分点，均不满足预定“对二者至少提高2个百分点”。源等权AUC差分别+0.00846/+0.00905，方向为正但不能替代预定主胜率与源一致性门槛。

差分再差分`(S_R-S_P)-(A_R-A_P)`：胜率+1.53个百分点，源等权AUC+0.00727。这说明相对排序相较绝对MSE缩小了真实/置换的不利差异，但S_R本身仍未胜过S_P的主胜率，不构成通过证据。CE与MSE损失尺度并未预先匹配，也不能将差分全归因于相对性本身。

## 4. 两个独立源的方向相反

|源对象|三元组|Z胜率|S_R胜率|S_P胜率|S_R−S_P|
|---|---:|---:|---:|---:|---:|
'''+ '\n'.join(source_table)+'''

ctlmatchb相对S_P提高2.78个百分点，injalpha下降3.13个百分点；相对Z分别+1.85/-0.78个百分点。源方向门槛未通过。这里源对象名称中的正常对照/木马插入来源不等于这些函数根的检测标签，不能将它解释成正常误报或木马召回的变化。

## 5. 分层与次要读出

下表每格为“源等权胜率 / 源等权AUC”：

|层|三元组|Z|S_R|S_P|
|---|---:|---:|---:|---:|
'''+ '\n'.join(strata)+'''

浅层27块没有MUX；含MUX的16块全部来自ctlmatchb的较深层，不是16个独立源。MUX局部S_R胜率有改善，但AUC仍约0.515，且没有多源验证，不能作为总体成功结论。浅层与深层S_R的AUC均未超过S_P；总体小幅AUC变化并非各层一致改善，也可能包含跨层距离尺度变化，仍需后续缓存诊断。

|读出空间|Z源等权胜率|S_R源等权胜率|S_P源等权胜率|
|---|---:|---:|---:|
'''+ '\n'.join(secondary)+'''

拼接读出S_R对S_P/Z有小幅正差，但不能事后替换冻结的root64主指标；同索引绝对MSE的拼接读出A_R/A_P胜率均约79.25%，也不支持“只有真实功能监督才有收益”。投影头没有藏着显著而稳定的真实对应优势。

## 6. 语义通道敏感度与表示信息量

固定S_R第50步，仅前向干预，保留共同边界20维通道：

|干预|root变化/原root整体标准差|主要源胜率|主要源AUC|
|---|---:|---:|---:|
|正确输入|参考|76.59%|0.7465|
|重复正确输入|0.0172%|仅作重复性参考|仅作重复性参考|
|错位MUX引脚角色|0.4136%|76.59%|0.7463|
|关闭新增引脚通道、保留共同边界|3.0535%|77.52%|0.7512|

角色错位的表示扰动高于同正确输入重复噪声约24倍，说明通道确实进入模型计算；但主要胜率不变，关闭引脚通道后指标也未降低。当前仍未证明模型把正确引脚语义转化为功能排序增益，不能说接口完全断开，也不能说语义已经学好。上述都是固定权重的局部干预，不是新增训练对照。

全部60验证单元共360个端点的root64有效秩：Z/A_R/A_P/S_R/S_P约2.31/2.96/3.49/2.06/2.59；S_R投影32维有效秩仅约1.19。各通道标准差非零、训练全过程std均值最低仍约0.047，没有完全常数坍缩，但表示明显集中于很少方向。方差项保证每维有变化不等于保留多个独立功能因素。低秩是后续诊断线索，尚未证明它是唯一无收益原因。

初始预检“关联梯度更可区分”与本轮“留出排序未稳定提升”并不矛盾：前者是初始化局部信号，后者涉及50步后的表示和跨实现迁移。本轮没有测量训练终点的分项梯度，不能直接声称终点仍保持初始的梯度差异。

## 7. 正确性、速度与保留情况

独立CPU核查了：原初始权重及零语义参数、投影seed819、五组Adam实际step50、BN计数增50、分类头/未使用功能头未变、每步三元组ID/随机种子/边界tag、实际源与候选预算、参数有限性。训练记录无缺步或重复更新，首步检查均通过，未发生失败补跑。

直接从落盘表示独立复算各源和所有四种读出的主要胜率/AUC，与公布值逐项一致；冻结门槛按原规则重新计算仍未通过。旧合同、输入、图、说明证据和历史检查点SHA检查通过。

主执行流程约122.7秒，训练步内时间中位数约0.317秒，训练峰值分配约4.93GiB。主执行时间含加载、训练、恢复点保存和7次验证，不含本次代码准备、独立核查及追加的重复性参考。不是“整个任务只用了两分钟”。

## 8. 下一步判断

不进入检测微调，暂不追加种子、增加训练步数或扩大SAT。优先复用本轮终点表示和初始状态，检查：(1)低秩主方向是否主要对应锥大小、门型、深度或源对象；(2)训练内能否真正区分真实/错误对应而留出失败，还是两者均未学到；(3)根节点与整锥平均如何分担信息，以及终点关联梯度是否重新同向。先离线和固定检查点诊断，再决定单因素改表示、读出或目标权重，不能把多个改动一起堆上去。

本轮可确认的成果是：原有公平合同被正确执行，新目标有可实现的真假竞争梯度，但其真实配对优势仍未通过留出验证。不能把“无增益”改写成已证明功能预训练有效，也不能由单种子、同宿主小面板否定整个方向。

证据目录：`_p0pilot/cec_relative_seed42_20261106/`。含冻结执行合同、共同INITIAL_STATE、五组resume/history/COMPLETE、TRAINING_COMPLETE、落盘val表示、evaluation_blocks/summary/by_source、PRIMARY_RESULT、checkpoint_audit、independent_primary_metrics、VERIFIED、语义干预与重复性参考。SAT作用证明和SAT工作总结仅追加本轮结果。
'''
 target=R/'10.15/00_说明/等价锥同根相对排序_五组seed42固定50步结果_20261106.md';target.write_text(report,encoding='utf-8')
 marker='### 2026-11-06 同根相对排序五组seed42各50步（已完成，未通过留出门槛）'
 appendix='\n\n'+marker+'''

用ginvenv_gpu按冻结合同完成Z/A_R/A_P/S_R/S_P各50步，共250次更新；相同原始初始化、采样、模型、正确边界/MUX接口、损失系数、dropout/BN与预算。未检测微调、未追加SAT或读取测试集，旧文件SHA保持。五组实际Adamstep和BN更新均50，无失败、缺步或重复更新。

- 主指标为root64、主要两个验证源等权的同根真实/置换胜率及函数AUC，不是检测AP。Z/A_R/A_P/S_R/S_P胜率分别76.06/76.69/78.40/76.59/76.77%；源等权AUC分别0.7375/0.7567/0.7555/0.7465/0.7381。
- S_R对S_P胜率-0.17个百分点，对Z+0.54，未达到分别+2个百分点的预定门槛；ctlmatchb对S_P+2.78个百分点，injalpha-3.13，源方向门槛也失败。AUC小幅提高不能替代主门槛。差分再差分胜率+1.53个百分点仅作探索线索，不能宣称成功。
- 浅/深层S_R AUC均未优于S_P；MUX子集16块仅同一个源，虽局部胜率提高但AUC约0.515。拼接/投影次要读出不替换冻结root64主指标。
- 固定S_R角色错位使root变化0.4136%std但主胜率不变；正确输入重复噪声0.0172%，关闭新增引脚通道而保留共同边界后胜率77.52%、AUC0.7512，未证明正确引脚语义带来收益。全部验证端点S_R root有效秩约2.06/64、投影1.19/32，未完全坍缩但信息方向集中；不把低秩当已证明唯一原因。
- 每组200三元组名额/143唯一单元、400关联正对、800查询/2400候选距离/1200共有负项，最大函数重复2、节点锥读出27。主要验证59块/2源/同宿主，另1块单列；浅MUX缺口保留。
- 主执行流程约122.7秒，步内中位0.317秒，峰值显存4.93GiB。250训练前向+7主验证前向，另1次不更新重复前向校准。CPU独立复核检查点、实际预算、各源/各空间指标与门槛通过（实验正确性通过，性能门槛未通过）。
- 下一步优先复用终点表示检查低秩主方向、结构捷径、训练内/留出差异及终点梯度；暂不检测微调、补种子或扩SAT。初始化梯度区分的改善不等于训练后的功能泛化增益。

详见《等价锥同根相对排序_五组seed42固定50步结果_20261106.md》。证据：`_p0pilot/cec_relative_seed42_20261106/VERIFIED.json`、PRIMARY_RESULT.json、checkpoint_audit.csv、evaluation_*.csv及五组检查点。
'''
 for name in ['SAT作用证明.md','SAT工作总结.md']:
  p=R/'10.15/00_说明'/name
  if marker not in p.read_text(encoding='utf-8-sig'):
   with p.open('a',encoding='utf-8') as f:f.write(appendix)
 (O/'PUBLISHED.json').write_text(json.dumps(dict(report=str(target.relative_to(R)),report_sha=sha(target),verified_sha=sha(O/'VERIFIED.json'),primary_result_sha=sha(O/'PRIMARY_RESULT.json'),updates=250,performance_gate_passed=pr['functional_performance_gate'],finetune=0,SAT=0,docs_updated=True),ensure_ascii=False,indent=2),encoding='utf-8');print('PUBLISHED',str(target),flush=True)
if __name__=='__main__':main()
