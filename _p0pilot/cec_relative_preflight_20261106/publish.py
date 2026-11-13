"""Publish the checked no-update preflight without changing the frozen contract."""
from pathlib import Path
import csv,hashlib,json
import numpy as np
O=Path(__file__).resolve().parent;R=O.parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(n):
 with (O/n).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def main():
 v=read(O/'VERIFIED.json');assert v['passed'];ex=read(O/'EXECUTION_CONTRACT.json')
 for p,h in ex['frozen_files'].items():assert sha(R/p)==h,p
 for n,h in v['outputs_sha'].items():assert sha(O/n)==h,n
 s=rows('gradient_summary.csv');g=rows('gradient_norms.csv');a=rows('gradient_angles.csv');loss=rows('loss_values.csv');replay=rows('first_batch_arm_replays.csv');linearity=rows('BF16_gradient_linearity.csv')
 def cs(mode,group,l,r):return float(next(x['cosine_mean'] for x in s if x['mode']==mode and x['group']==group and x['left']==l and x['right']==r))
 def gn(group,t):return float(np.mean([float(x['grad_norm']) for x in g if x['mode']=='contract_train' and x['group']==group and x['term']==t]))
 comparison=[]
 for mode in ['contract_train','frozen_eval']:
  for group in ['backbone','pin_boundary','pin_internal','projection']:
   comparison.append('|'+('合同训练模式' if mode=='contract_train' else '冻结评价模式')+'|'+group+'|'+'|'.join(f'{cs(mode,group,l,r):.4f}' for l,r in [('A_R','A_P'),('S_R','S_P'),('A_R_total','A_P_total'),('S_R_total','S_P_total')])+'|')
 perbatch=[]
 for u in [1,2,25,50]:
  rr=[x for x in a if x['mode']=='contract_train' and x['group']=='backbone' and int(x['batch'])==u]
  get=lambda l,r:float(next(x['cosine'] for x in rr if x['left']==l and x['right']==r))
  perbatch.append('|'+str(u)+'|'+'|'.join(f'{get(l,r):.4f}' for l,r in [('A_R','A_P'),('S_R','S_P'),('A_R_total','A_P_total'),('S_R_total','S_P_total')])+'|')
 report='''# 五组相对排序合同：加载与无更新梯度预检

日期：2026-11-06。结论：**加载、预算、正负项及三候选竞争预检通过；新的关联目标明显区分真实与置换梯度，但加入共有项后总梯度仍较同向。可以准备seed42五组探索性预训练，尚未训练，不能声称已出现功能或检测收益。**

## 1. 本轮实际执行范围

使用ginvenv_gpu。全部50步监督索引经过实际加载接口核查；GPU只预检固定的update1、2、25、50四批，每批在合同训练模式和冻结评价模式各运行一次、同一前向图计算五组目标。两种模式的第1批再实际重放五组前向，核查同初始化与随机数状态。

总计18次模型前向、88次参数向量-Jacobian积、16次仅logit叶节点的梯度计算，优化器更新0、SAT0、测试读取0。没有创建优化器，也没有按50步推进训练。参数.grad未累积；旧文件SHA、原始模型/投影头参数及BN缓冲区逐项保持。

主模式完整保留合同的BF16、dropout0.2与BN训练行为。BN统计更新只发生在临时克隆缓冲区，计算结束丢弃克隆并恢复原对象，原缓冲区不改变。冻结模式同时关闭dropout、冻结BN，用于辅助诊断；它不是单独的dropout或BN单因素实验。

## 2. 同初始化、同图、同监督加载

五组使用原init_s42、零初始化边界/引脚适配器和projection seed819。未接着旧R/P第50步检查点运行。主模型52455参数，投影10336；排除冻结分类头后实际梯度向量62661维。全部组使用相同39v3、归一化、有向边、正确共享PI/物理Q边界身份与MUX角色。

实际PinBoundary加载器对10429个既有锥的引脚关联进行了原有一致性核查；本轮又核对训练池的根和成员全局行地址。独立验证对本轮选中858个物理锥检查了视图所属范围、physical标记、根行与成员行。旧图、节点标签、监督及SAT证据不变。

实际加载50步的总预算：

|项目|加载结果|冻结合同|
|---|---:|---:|
|训练源 / 每源三元组名额|8 / 25|8 / 25|
|三元组名额 / 唯一三元组|200 / 143|200 / 143|
|关联正对名额|400|400|
|锥根查询 / 三候选距离|800 / 2400|800 / 2400|
|共有负项 / 端点读出名额|1200 / 1200|1200 / 1200|
|单函数最大重复 / 单节点锥读出曝光|2 / 27|2 / 27|

各组逐步候选集合和锥根完全相同，真实/置换选定目标的加权端点曝光也完全相同。未默默纳入合同排除的2个源。800个查询包含对称方向，不是800个独立源；50步是索引合同，不能写成已训练50步。

## 3. 三候选竞争和正负项确实进入计算

实际加载的六端点顺序为A_L/A_R/B_L/B_R/C_L/C_R，四个查询依次为A_L、B_L、A_R、B_R。每个查询都输入相反实现中的A/B/C三个候选，真实与置换组只切换被选目标。三候选一起进入交叉熵分母；没有先过滤成选定边或只与C比较。

通过实际GPU产出的投影表示进行独立NumPy复算，六个损失分项及五组总损失的最大绝对误差为2.48e-7以内。真实/置换CE对logit的梯度差与预定one-hot目标差逐项吻合，C候选在两组都有非零导数，证明没有从分母断开。

共有负项恰为AB同实现两条、AC/BC跨实现四条，未混入置换组正对应AB跨实现边。对实际全局根行地址，全部50步的正边/共有负边重合、关联正边/非目标竞争边重合均为0；加载接口再次检查共有负边没有落入任一组正边连通分量。C角色固定，没有跨批轮换。

Z、A_R、A_P、S_R、S_P都计算四种关联中间量，未启用项乘0。Z关闭关联梯度是有意干预；不同函数分离与0.1方差项一致。S_P把真实候选当关联非目标仍是故意的错误监督控制，不能将它说成已被证明不同函数的共有负例。

## 4. 梯度主结果：关联项已不再高度同向

以下是在相同初始化、相同批次、同一前向图上的真实/置换梯度余弦均值。越接近1越同向，0表示近正交，负数表示部分相反。A为原式MSE，S为三候选CE；总梯度为对应关联项加共有分离和方差项，实际通过完整目标反向计算，未用分项相加近似替代。

|模式|参数组|A真实/置换关联项|S真实/置换关联项|A真实/置换总梯度|S真实/置换总梯度|
|---|---|---:|---:|---:|---:|
'''+ '\n'.join(comparison)+'''

主模式逐批主干结果：

|固定批次|A关联项|S关联项|A总梯度|S总梯度|
|---|---:|---:|---:|---:|
'''+ '\n'.join(perbatch)+'''

四批S关联项余弦均为负，不是只有一批拉低均值。主干、引脚边界、内部角色消息和投影头均有有限非零梯度。三候选目标已向编码器与引脚通道提供区别真假关联的局部信号，不是仅在投影头或日志里计算了一个不同数值。

这是同一初始化的新合同A/S比较。不能把它与此前旧R第50步的0.9875总梯度直接当作唯一改动的因果对比，那个实验的权重、批次和共同负项均不同。

## 5. 为什么总梯度仍偏同向

合同训练模式下四批平均主干梯度范数：

|分项|范数均值|
|---|---:|
|A_R关联|0.24736|
|S_R关联|0.24760|
|共有不同函数分离|0.88746|
|加权方差项|0.05740|
|两项共有总梯度Z|0.93611|

关联项的方向差异已改变，但共有分离项范数仍约为S_R关联项3.58倍，因此真实/置换总梯度仍有很大的共同部分。A_R与共有分离项的主干余弦均值约-0.7679，S_R与其约-0.1231：相对排序在这些批次上减少了原式一般收缩与分离之间的正面冲突。

A_R与S_R平均范数很接近，说明这里观察到的方向改变并非单纯因CE把关联范数放大很多；这只是本轮描述，合同没有预先匹配每批梯度尺度，不能据此宣布所有训练阶段都排除了尺度影响。

现阶段不建议再改共有负项或关联权重，否则会把目标形式和权重两个因素混在一起。先保持合同系数做探索，若后续总梯度/函数排序仍无收益，再研究权重平衡。

## 6. 数值与非坍缩检查

主训练模式投影维度标准差均值为0.06010—0.06481，超过原首步0.01检查线，全部损失与梯度有限。冻结评价模式仅0.00363—0.00422，使用的是未经训练/校准的初始化BN运行统计，不能据此断言训练后表示坍缩；也不能将冻结模式当作本次主预检失败。后续训练仍须检查持续非坍缩和留出函数区分。

相同初始化与RNG的五组第1批重放，投影相对RMS差异最大约0.2692%，符合BF16和散射归约的重复性误差；原权重与BN仍完全一致。梯度主比较共享同一次前向，避免这类重复性差异混入真实/置换对比。

单项VJP之和与完整目标VJP存在最多约0.84%的BF16数值差异，因此主表使用完整目标实际梯度。全部梯度向量已落盘，独立CPU重算范数、余弦与损失一致，不只保存了汇总均值。

## 7. 结论与后续门槛

通过加载与无更新梯度预检：三候选竞争生效、预算与合同一致、正负项无冲突、初始关联梯度对真假目标具有明显区分。因此该目标值得进入原合同seed42五组50步探索性预训练；本轮没有执行。

探索仍保留Z与同索引A_R/A_P控制，不用历史检查点替代。暂不补种子、不检测微调、不扩大SAT。最终看root64同一锥根真实对置换的留出排序与AUC，不能只看训练损失下降或函数C被分开。仍需满足原先约定的实用门槛、两个主要验证源一致性及非坍缩条件。浅MUX和多验证宿主缺口保持原样，不扩大结论。

## 8. 证据位置

目录：`_p0pilot/cec_relative_preflight_20261106/`。

- 实际接口：interface.py；GPU无更新预检：preflight.py；独立缓存复核：verify.py。
- 批次/加载：loaded_batches.json、loaded_budget_per_step.csv、LOADING_BUDGET_VERIFIED.json、ATTACHMENT_VERIFIED.json。
- 数值/梯度：forward_*.npz、vectors_*.npz、PARAMETER_LAYOUT.json、gradient_norms.csv、gradient_angles.csv、gradient_summary.csv、numeric_checks.csv、first_batch_arm_replays.csv、BF16_gradient_linearity.csv。
- 执行与核查：EXECUTION_CONTRACT.json、COMPLETE.json、VERIFIED.json、run_attempt1.log、verify.log。

旧五组合同及其SHA保持，SAT作用证明和SAT工作总结只追加本轮说明。本轮未出现中途失败或重跑训练。
'''
 target=R/'10.15/00_说明/等价锥五组合同加载与无更新梯度预检_20261106.md';target.write_text(report,encoding='utf-8')
 marker='### 2026-11-06 五组合同加载与无更新梯度预检（通过，未训练）'
 appendix='\n\n'+marker+'''

按冻结合同完成加载和梯度预检。全部50步索引逐项审计；GPU只用固定1/2/25/50四批，两种模式及五组首批重放合计18次前向、88次参数VJP、16次logit叶节点VJP。优化器/训练/SAT/测试读取均为0。主模式BF16/dropout.2/BN训练仅使用临时BN克隆缓冲区，原参数及BN状态均保持。

- 实际加载8源各25名额、200块/143唯一三元组、400正对、800根查询/2400候选距离、1200共有负项与端点读出，最大函数重复2、节点锥读出曝光27。858个选中物理锥的根与成员地址通过独立核查。正边/共有负边及关联非目标冲突为0，逐步真实/置换目标曝光相同。
- 三候选一起进入CE分母；NumPy独立复算损失最大误差2.48e-7以内，实际logit梯度差与one-hot目标差吻合，C导数非零。五组共享所有候选和共有项，未将置换正边误加入共有负项。
- 同初始化同批次主模式主干：MSE真实/置换关联梯度余弦0.8848，三候选CE为-0.1485；总梯度分别0.9945/0.9115。内部引脚消息的关联项分别0.7428/-0.4951，总项0.9942/0.8476。说明新关联目标已提供真假区分信号，但共有项仍让总梯度偏同向。
- 主干S_R关联范数0.24760，共有分离0.88746；A_R关联0.24736。关联目标改变的方向信号不只是平均范数大幅放大，但这不是预先梯度尺度匹配，也不证明后续训练收益。新合同比较在同初始化下进行，不能直接拿旧R第50步余弦作单因素因果比较。
- 主训练模式初始投影std均值0.0601—0.0648，损失梯度有限；冻结评价模式初始化BN未校准，低std不作训练后坍缩结论。单项与总项BF16 VJP加和误差最大0.84%，主结论使用实际总梯度；完整梯度向量落盘，独立CPU范数/余弦复算通过。
- 预检通过，可以准备原合同seed42五组探索性预训练，尚未执行；先不改权重、不补种子、不检测微调。以真实对置换的留出root64排序和AUC判定，不能只看第三函数分离。验证浅MUX和多宿主缺口保持原说明。

详见《等价锥五组合同加载与无更新梯度预检_20261106.md》。证据：`_p0pilot/cec_relative_preflight_20261106/VERIFIED.json`、COMPLETE.json、gradient_summary.csv及完整forward/vectors文件。
'''
 for name in ['SAT作用证明.md','SAT工作总结.md']:
  p=R/'10.15/00_说明'/name
  if marker not in p.read_text(encoding='utf-8-sig'):
   with p.open('a',encoding='utf-8') as f:f.write(appendix)
 (O/'PUBLISHED.json').write_text(json.dumps(dict(report=str(target.relative_to(R)),report_sha=sha(target),verified_sha=sha(O/'VERIFIED.json'),gradient_summary_sha=sha(O/'gradient_summary.csv'),model_forwards=18,optimizer_steps=0,SAT=0,docs_updated=True),ensure_ascii=False,indent=2),encoding='utf-8');print('PUBLISHED',str(target),flush=True)
if __name__=='__main__':main()
