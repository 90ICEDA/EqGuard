"""Publish verified effective pin-role results and transparent superseded budget."""
from pathlib import Path
import json,csv,datetime,hashlib
import numpy as np
O=Path(__file__).resolve().parent;R=O.parents[1];D=R/'10.15/00_说明'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def rows(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def main():
 verified=read(O/'VERIFIED.json');assert verified['passed'] and read(O/'FINAL_ANALYSIS_COMPLETE.json')['verified']
 summary=rows(O/'evaluation_summary.csv');contrast=rows(O/'alignment_contrasts.csv');mux=rows(O/'mux_strata_summary.csv');strata=rows(O/'evaluation_strata.csv');sens=read(O/'CHANNEL_SENSITIVITY.json');co=read(O/'COMPLETE.json');load=read(O/'PIN_LOADING_VERIFIED.json');cov=read(O/'MUX_COVERAGE.json');pre=read(O/'PREFLIGHT.json')
 get=lambda cond,arm,tag='9000',space='root64':next(r for r in summary if r['alignment']==cond and r['arm']==arm and r['remap']==tag and r['space']==space)
 mainrows=[];muxrows=[];sourcerows=[];contrastrows=[]
 for arm in ['Z','R','P']:
  a,b=get('shared',arm),get('viewshuffle',arm)
  mainrows.append(f"|{arm}|{float(a['cross_auc']):.4f}|{float(b['cross_auc']):.4f}|{float(a['source_macro_auc']):.4f}|{float(b['source_macro_auc']):.4f}|{float(a['source_macro_anchor_win']):.2%}|{float(b['source_macro_anchor_win']):.2%}|")
  a,b=[next(r for r in mux if r['alignment']==c and r['arm']==arm and r['remap']=='9000' and r['space']=='root64' and r['subset']=='has_MUX') for c in ['shared','viewshuffle']]
  muxrows.append(f"|{arm}|{float(a['auc']):.4f}|{float(b['auc']):.4f}|{float(a['source_macro_anchor_win']):.2%}|{float(b['source_macro_anchor_win']):.2%}|")
 for tag in ['9000','9001']:
  for metric in ['cross_auc','source_macro_auc','source_macro_anchor_win']:
   r=next(r for r in contrast if r['remap']==tag and r['space']=='root64' and r['metric']==metric)
   contrastrows.append(f"|{tag}|{metric}|{float(r['D_R']):+.5f}|{float(r['D_P']):+.5f}|{float(r['D_Z']):+.5f}|{float(r['R_minus_P']):+.5f}|{float(r['R_minus_Z']):+.5f}|")
 for source in sorted({r['value'] for r in strata if r['stratum']=='source'}):
  aa=[next(r for r in strata if r['alignment']=='shared' and r['arm']==arm and r['remap']=='9000' and r['space']=='root64' and r['stratum']=='source' and r['value']==source) for arm in ['Z','R','P']]
  sourcerows.append('|'+source+'|'+aa[0]['blocks']+'|'+'|'.join(f"{float(r['cross_auc']):.4f}" for r in aa)+'|')
 sensrows=[f"|{r['mode']}|{r['root_rms_change']:.6f}|{r['relative_to_root_std']:.3%}|{r['cross_auc']:.4f}|{r['source_macro_auc']:.4f}|" for r in sens['results']]
 histories=[read(O/(c+'_'+arm)/'history.json') for c in ['shared','viewshuffle'] for arm in ['Z','R','P']];times=[r['seconds'] for h in histories for r in h];peaks=[read(O/(c+'_'+arm)/'COMPLETE.json')['peak_bytes']/2**30 for c in ['shared','viewshuffle'] for arm in ['Z','R','P']]
 name='等价锥MUX引脚角色单因素预训练_seed42_20261106.md'
 report=f'''# 等价锥MUX引脚角色：加载、反例与等预算预训练（seed42）

日期：2026-11-06。状态：六组有效对照完成；仅预训练与离线评价，未检测微调、未扩SAT。

## 结论

**引脚语义已经进入实际模型接口，加载与反例检查通过，但当前实验仍未确立真实等价配对优于置换。** 正确角色下root64合并函数区分AUC：Z/R/P=0.5936/0.6038/0.6041；R/P基本持平。R的源等权AUC0.6623低于P0.6642，同anchor排序则略高，指标没有一致优势；不能用某一个小差异宣布成功。

含MUX的28块子集R比P略高（0.5271/0.5166），但角色错位后的R为0.5277，且28块全部来自同一个源对象，无法归因于正确引脚语义。固定真实R权重，仅错位角色，合并AUC仍0.6038；关闭引脚通道而保留原共享边界通道，AUC约0.6052。当前模型未把新增语义转化为明确的函数判别收益，暂不进入检测微调。

以上均为**真实/错误跨实现函数配对的距离AUC，不是木马检测AP**；本轮不改变此前检测模型及约0.30的检测AP结论。不否定完整等价锥方向，也不宣称全时序等价学习已经成立。

## 1. 实际加了什么

保留39维v3、原有向边、归一化、标签与初始化。引脚接口区分COMM（AND/OR/XOR的对称输入）、NOT单输入、MUX DATA0、DATA1、SELECT；原生MX2X1_RS为A/B/S0，Yosys $mux为A/B/S。Q/QN共用物理Q槽位并保留相位；INV输出名叫QN时不额外翻转。常量0/1及重复输入脚保留。

相同模型底座中新增两部分：

|通道|如何进入计算|新增参数|
|---|---|---:|
|上一轮共同边界通道|20→39残差适配器；两组都正确共享边界身份|780（保留）|
|按角色分组的直接边界输入|五角色各20维，共100→39无偏置残差，作用于实际接收门|3900|
|内部组合连线角色|五层GIN聚合中按接收脚角色加逐通道残差消息；宽度29/64/10/64/64|1155|

原46620参数，加共同边界780、引脚5055，主模型总52455（不含各组相同的10336参数投影头）。所有新增参数在六组中均零初始化。内部消息为原聚合+Σ(scale[role]⊙h_src)，一输入脚一关联；没有删除或重写存盘边，也没有把普通输入脚错误当成时钟/复位。DFF不展开状态方程；物理Q作为自由边界，已有DFF图结构仍保留。

角色信息既进入内部连线消息，也进入PI/Q/常量到门的输入通道；并非只写入edge_roles元数据。信号名、源对象ID、证书结论、木马标签、真值表或反例输出都没有作为新增输入。

## 2. 单因素、公平性与有效覆盖

两种接口都保持正确共享的边界身份，模型参数、维度、算子与训练预算相同：

- **正确角色（文件名shared）**：使用真实COMM/NOT/DATA0/DATA1/SELECT。
- **有效角色错位（文件名viewshuffle）**：COMM/NOT不变；每个视图将MUX三角色循环错位，轮换量为1+视图序号mod2。没有保留身份锚视图，相邻视图角色约定不同，避免单一全局改名被学回来。
- 只错位模型侧角色信息，不修改网表、边界对应或已有证明；不会给错误角色重新发CEC证书。
- 各接口均做Z/R/P：Z关闭等价正项而保留公共不同函数与方差项，R拉近真实等价，P拉近置换端点。其余原MSE+不同函数间隔+0.1方差、Adam lr0.0002/wd0.001、clip1、dropout0.2、BN、BF16保持。
- seed42；每组固定50次功能预训练，不按验证AP选模。382唯一训练配对、500名额，10源各50名额；root64+mean64→128/64/32读出。评价复用68块既有验证证书和预定边界重排9000/9001；不读取测试特征、标签或预测。

|有效控制覆盖|数量|
|---|---:|
|已有训练唯一配对|382|
|包含MUX且会被错位的训练唯一配对|102|
|500名额中含MUX且会被错位的名额|111|
|已有验证证书块|68|
|含MUX且会被错位的验证块|28|

32视图中训练22、验证10；全视图MUX分别320、2475。这些全图数量不是参与配对的独立函数数；只在实际锥成员中计算上表，不能用2795个MUX冒充2795个独立训练例。

### 先前控制的修正及预算账本

最初实现保留锚视图不动，实际只扰动4条训练配对、0个验证锥块，控制覆盖不足。覆盖核查后停止该控制，记录于`cec_pinrole_seed42_20261106/CONTROL_SUPERSEDED.json`；保存其Z50/R50/P47共147次更新及日志，排除出最终因果比较。

正确角色的Z/R/P各50步不受控制修订影响，原样复制复用并核对二进制SHA，不重跑、不重写检查点binding。新跑全视图错位Z/R/P各50步。最终有效六组共300步=复用正确组150+新有效控制150；**本次用户任务实际保存优化器更新447=有效300+弃用控制147**。两个成功的无优化器梯度预检另记，不算训练步。开发中的混合精度类型错误和辅助路径错误均在训练更新前停止，日志保留。

修订依据是角色关联覆盖，而非评价分数；没有根据测试正例、验证结果增删候选或更换种子。不能把弃用控制的零扰动结果当作引脚角色无效的证据。

## 3. 加载与反例正确性

新全图行地址加载器与原导出的10429个锥、1,158,804条局部引脚关联逐条一致，715103次成员出现均核对操作类型与行坐标。内部输入脚关联训练72801、验证160398，全部有原有向边支持；重复输入单独保留。名字只用于映射，处理旧members名称顺序与graph_rows数值顺序不同的问题；63个连续赋值辅助门仍按操作、输出bit、输入bit映射。

实际新加载器重放68个既有不同函数证书、272根输出，全部与原记录一致。合成反例通过实际typed_conv与角色边界适配器验证：

|检查|结果及含义|
|---|---|
|MUX选择/数据交换，三条来源结构对称|原无类型聚合不能区分；非零诊断角色权重下实际typed_conv可以区分|
|直接边界MUX选择/数据交换|实际100→39角色适配器可保留差别|
|AND等交换对称输入|同角色交换不制造语义差别|
|重复输入|保留一脚一关联及重数|
|PI/Q身份、Q/QN相位、常量|同旧共享边界20维数值完全一致；新角色表与原证据逐项一致，272根重放通过|

“可以区分”是接口表达能力检查，使用预定非零诊断权重，**不是训练模型已学会布尔等价**。零初始化时新模型与原编码器权重逐项相同，输出最大浮点差{pre['zero_adapter_output_max_delta']:.3g}；共同边界与上一轮差值0。两种控制的基础边界、连线、初始参数一致，只改角色分配。引脚边界与五层角色消息均有有限非零梯度，三个MUX角色的梯度单独检查通过。

六组检查点均50步，优化器实际step=50，分类头未更新，所有参数有限；{verified['old_files_verified']}项旧输入/检查点/统计文件SHA保持。未改标签、旧脚本、原图或SAT成功证据。

## 4. 主结果：root64函数区分（映射9000）

|组|正确角色 合并AUC|错位角色 合并AUC|正确 源等权AUC|错位 源等权AUC|正确 源等权同anchor排序|错位 源等权同anchor排序|
|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(mainrows)}

真/错两类距离均跨相同实现方向；负距离作为同函数分数。每个证书块共享同一组四端点，函数不同有已有反例支持。源等权与合并口径并报，不把大量同源块当作独立源。R−P合并AUC约−0.00032，接近持平；单seed不能作显著性或全宿主泛化结论。

D_R=正确角色R−错位角色R，P/Z同理；差分再减P/Z用于排除共同接口或一般正则化作用：

|预定映射|root64指标|D_R|D_P|D_Z|D_R−D_P|D_R−D_Z|
|---|---|---:|---:|---:|---:|---:|
{chr(10).join(contrastrows)}

R相对P的部分差分为正，但R本身仍未优于正确角色P，且R相对Z的差分不一致。不能只挑正的差分宣布真实等价监督成立。

## 5. 含MUX子集及逐源结果

|含MUX28块|正确角色AUC|错位角色AUC|正确同anchor排序|错位同anchor排序|
|---|---:|---:|---:|---:|
{chr(10).join(muxrows)}

这28块全部来自s38417t100__ctlmatchb_d1_s42一个源，并非28个独立源。R虽略高于P，但错位R不降，AUC总体仍接近0.5；不足以确认MUX功能学习。无MUX40块及两个映射的完整指标保存在mux_strata_summary.csv，不把含MUX子集替代总体。

|正确角色逐源root64 AUC|证书块数|Z|R|P|
|---|---:|---:|---:|---:|
{chr(10).join(sourcerows)}

总验证仅5源、同一宿主，小源为2/1/1块。三种子未做，测试配对未评价；不从源级差异得出宿主因果结论。

## 6. 通道敏感度与传播范围

固定正确角色R第50步检查点、相同验证锥和BN，仅做3次纯前向；不更新参数：

|输入干预|相对原root RMS变化|相对原root整体标准差|合并AUC|源等权AUC|
|---|---:|---:|---:|---:|
{chr(10).join(sensrows)}

重复正确角色提供BF16/散射重复性参考。仅错位角色时表示扰动约0.43%、AUC不变；关闭全部新增引脚通道但保留共同边界时扰动约2.28%，AUC略升。引脚参数已更新，不是接口未接通；更合理的有限判断是当前模型对MUX角色约定依赖弱，仍可能主要利用一般结构。不能从此断定语义信息不重要。

复用既有内部三跳清单，68块中仅1块的四个端点锥全部落在各自根的内部三跳内，另67块至少有一端更深。当前两个分支2层+融合后1层，根局部传播与较深功能锥可能不匹配。但mean pooling仍包含所有成员，训练BN也会耦合全图，**不能把三跳统计写成整个模型只看到三跳或大锥必然不可学**。仅1个浅块不足以比较浅/深功能学习。见ROOT3HOP_COVERAGE.json与root3hop_strata.csv。

最终有效六组步内时间中位数{np.median(times):.3f}秒，峰值显存最大{max(peaks):.2f}GiB；时间不含启动、核查、落盘和评价。未扩大搜索、未追加种子、未检测微调、未删除或移动文件。

## 7. 下一步建议

暂不做检测微调，也不以扩大SAT池或机械补种子代替机制核查。优先**从已有同源CEC配对与已有不同函数反例中，建立浅、小、明确边界的功能验证面板**：覆盖多个源与实现方向，区分含MUX/不含MUX，保证根传播可覆盖或明确分层，不按木马测试标签挑选。先复用现有表示判断通道和读出是否真的区分函数；若小锥仍不分，再单因素检查语义通道强度/读出与目标，若小锥有效而深锥失效，再考虑锥内拓扑递推编码或深度匹配。

这需要先列覆盖和证据合同，不预设必须新增SAT；在浅面板上确认真实配对相对置换的作用后，再另立检测迁移合同，并明确语义通道如何覆盖原始侧与留出实现。当前实验只证明接口保留信息且实现正确，尚未证明功能预训练提高木马检测。

证据：`_p0pilot/cec_pinrole_effective_20261106/`的EXECUTION_CONTRACT、REUSED_TRUE_ROLE_RUNS、PIN_LOADING_VERIFIED、FIXTURES_VERIFIED、PREFLIGHT、MUX_COVERAGE、六组检查点、evaluation_*.csv、alignment_contrasts.csv、mux_strata_summary.csv、CHANNEL_SENSITIVITY、ROOT3HOP_COVERAGE、VERIFIED及FINAL_ANALYSIS_COMPLETE。弃用控制与失败日志保留在`_p0pilot/cec_pinrole_seed42_20261106/`，不得混入有效结论。
'''
 (D/name).write_text(report,encoding='utf-8')
 marker='### 2026-11-06 MUX引脚角色单因素预训练与有效控制（已完成）'
 entry=f'''\n\n{marker}

ginvenv_gpu完成正确/错位引脚各Z/R/P六组有效50步对照，边界身份始终正确共享；保留39v3/原图/损失/初始化/382唯一配对500名额。共同新增100→39角色边界3900参数及五层逐通道角色残差1155，连同上一轮780边界参数总52455，新增参数均零初始化。32视图、10429锥、1158804引脚关联及715103成员出现逐项核对；新全局行加载器重放68证书272根输出通过，实际typed_conv/角色适配器能保留MUX选择/数据交换反例，重复脚与对称输入检查通过。原锚视图不动的控制只扰动训练4对/验证0块，已标SUPERSEDED并保留Z50/R50/P47；修订为所有视图MUX循环错位，COMM/NOT不变，实际扰动102训练对/111名额/28验证块。正确三组150步原样复用，新有效控制150步；最终有效300步，本次实际保存447步，弃用147不混入结论。主root64正确Z/R/P AUC=.5936/.6038/.6041，错位=.5924/.6038/.6053；R与P基本持平，未确立真配对独立优势。含MUX28块R/P=.5271/.5166，但错位R=.5277且全来自一个源；固定正确R仅错位角色AUC不变，关闭引脚而保留边界AUC=.6052，语义作用仍弱。两个预定重排、源/配方/大小、MUX与三跳分层完整保存；仅1/68块四端内部锥全在根三跳内，不足以评价浅锥泛化，mean pooling仍含全锥不能误写只看三跳。172项旧资产哈希核验通过，0检测微调/新SAT/测试读取；旧模型、图、标签和成功证据保留。建议先复用已有证明与反例建立多源浅小锥面板，再决定编码/读出单因素，不直接检测微调。详见[{name[:-3]}]({name})，有效证据`_p0pilot/cec_pinrole_effective_20261106/`，弃用控制`_p0pilot/cec_pinrole_seed42_20261106/CONTROL_SUPERSEDED.json`。
'''
 for n in ['SAT作用证明.md','SAT工作总结.md']:
  p=D/n
  if marker not in p.read_text(encoding='utf-8-sig'):
   with p.open('a',encoding='utf-8') as f:f.write(entry)
 z=dict(report=str((D/name).relative_to(R)),time=datetime.datetime.now().isoformat(),report_sha=hashlib.sha256((D/name).read_bytes()).hexdigest(),documents=['SAT作用证明.md','SAT工作总结.md'],effective_updates=300,actual_saved_updates=co['total_unique_saved_optimizer_updates_this_task'])
 (O/'PUBLISHED.json').write_text(json.dumps(z,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(z,ensure_ascii=False))
if __name__=='__main__':main()
