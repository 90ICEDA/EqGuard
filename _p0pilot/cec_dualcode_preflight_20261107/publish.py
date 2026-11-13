from pathlib import Path
import csv,hashlib,json
import numpy as np
O=Path(__file__).resolve().parent;R=O.parents[1];D=R/'10.15/00_说明';C=R/'_p0pilot/cec_repaired_contract_20261107';PRE=R/'_p0pilot/cec_freeq_preflight_20261106'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(n):
 with (O/n).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
assert read(O/'VERIFIED.json')['passed'];coefficient=read(O/'FROZEN_COEFFICIENT.json')['coefficient'];cal=rows('calibration_gradients.csv');diagnostics=[]
def cos(a,b):return float(a@b/(np.linalg.norm(a)*np.linalg.norm(b)))
with np.load(O/'gradient_vectors.npz') as z:
 for step in [1,2,16,32]:diagnostics.append(dict(step=step,total_R0_P0_cosine=cos(z[f'step{step}_total_R0'].astype(float),z[f'step{step}_total_P0'].astype(float)),total_R1_P1_cosine=cos(z[f'step{step}_total_R1'].astype(float),z[f'step{step}_total_P1'].astype(float))))
(O/'GRADIENT_DIRECTION_DIAGNOSTICS.json').write_text(json.dumps(diagnostics,indent=2),encoding='utf-8')
contract=dict(status='prepared_after_no_update_preflight;training_not_executed_or_authorized_this_round',arms=['Z0','Z1','R0','R1','P0','P1'],seed=42,planned_updates_each=32,initial_file=str((PRE/'INITIAL_STATE.pt').relative_to(R)),initial_sha=sha(PRE/'INITIAL_STATE.pt'),model_parameters=47360,model_sha=sha(PRE/'model_interface.py'),interface_sha=sha(O/'dual_interface.py'),schedule_sha=sha(C/'SCHEDULE_SEED42.json'),training_pool_sha=sha(C/'TRAIN_TRIPLES.json'),coefficient=coefficient,coefficient_file_sha=sha(O/'FROZEN_COEFFICIENT.json'),loss='average original base over codes t and10000+t;add lambdaJS only for suffix1;all arms compute sameJS with no labels,temperature1',budget_each=read(O/'PREFLIGHT_CONTRACT.json')['budget_each'],optimizer='Adam lr0.0002 wd0.001 clip_norm1 FP32 noAMP/noTF32;one optimizer step per two-code batch',selection='common oldinit,fixedlast32,no validation checkpoint or coefficient choice',evaluation=dict(primary='73H3 validation root64 familymacro pairwisewin tag9000',retained_tags=list(range(9000,9006)),new_code_tags=list(range(9006,9012)),strata='source,flow,MUX,2/3candidates;PO separate;no pooled top1 across candidatecounts',diagnose='R1 vsR0,P1,Z1;codefliprate;entropy/distance spread andnoncollapse;trainMUX vsvalMUX'),scope='same current proof pool;no detector finetune/SAT/test;new two-code baseline protocol not oldsingle-code directcomparison',training_authorized=False,training=0,SAT=0)
(O/'FROZEN_TRAINING_CONTRACT.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2),encoding='utf-8')
name='双编码候选排序一致性加载与梯度预检_20261107.md'
text=f'''# 双编码候选排序一致性：加载与无更新梯度预检

2026-11-07。结论：必要加载、数值、目标独立性和梯度检查通过，可以准备seed42六组各32步探索训练；本轮没有训练或新增SAT，也不能据此认定能够改善MUX或留出宿主泛化。

## 冻结实现

仍使用原7个三函数单元/21函数类/4制造源/2家族、原47,360参数模型及共同INITIAL_STATE，不用上轮训练末步作新初始化。每个原采样批消费两套共享边界编码：步t和10000+t。图、节点类型、引脚角色、相位、目标及候选顺序完全一致，只有16维边界身份编码改变；两实现共享同一上下文映射。

Z/R/P基础目标分别取两套编码损失均值；一致性项是同一查询3候选概率softmax(−RMS距离)的加权Jensen–Shannon散度，温度1，查询权重沿用旧合同，双侧均传梯度。它不读取真实/置换标签，不要求不同函数的根向量相等。

|组|基础损失|JS系数|输入/前向预算|
|---|---|---:|---|
|Z0/Z1|公共不同函数负项+方差项，两编码均值|0 / {coefficient:.6f}|完全相同两编码|
|R0/R1|Z基础+真实跨实现候选分类，两编码均值|0 / {coefficient:.6f}|同上|
|P0/P1|Z基础+原冻结置换候选分类，两编码均值|0 / {coefficient:.6f}|同上|

关闭组也计算JS，仅系数为0；开启与关闭组均在同一次目标计算中消费两编码，后续每批只有一次优化器更新。不能拿旧单编码R直接替代R0。

## 实际加载及未来每组预算

本轮实际共享冻结前向加载32个双编码批，每批2逻辑单元、12查询、每查询3候选；另外4批完整梯度检查、6个独立初始化组的首批实际前向。因为没有参数更新，公共前向可共享；这不是已经运行六组训练。

|各组未来32步的计数|数量|
|---|---:|
|逻辑单元名额/查询身份|64 / 384|
|含两编码的单元输入/查询计算|128 / 768|
|候选距离/公共负项计算|2304 / 768|
|跨编码JS查询|384|

同一函数的抽样曝光上限16不变，含两编码的输入次数上限32，不能把编码复制计为新增功能样本。目标双射、逆置换、P目标区别于真目标、完整锥消费、32批同拓扑、六组192条预算记录检查通过。基础监督取两编码均值，不把监督权重翻倍。

## 系数与梯度

只用训练批1、2、16、32的共同初始化梯度，冻结

`lambda = 0.25 / median(||grad JS|| / ||grad base_R||)`

得到λ={coefficient:.10f}。JS本身约0.00074—0.00258，系数大于1不代表梯度占比大于基础项。没有使用验证成绩、额外训练或调参搜索。

|批|JS梯度范数|R基础梯度范数|加权JS/R范数比|JS与真实关联项梯度余弦|
|---|---:|---:|---:|---:|
'''
for r in cal:text+=f"|{r['step']}|{float(r['JS_gradient_norm']):.5f}|{float(r['base_R_gradient_norm']):.5f}|{float(r['weighted_ratio']):.2%}|{float(r['JS_vs_real_CE_cos']):+.3f}|\n"
text+='''
范数比中位数25%，范围14.01%—32.32%；相对Z/P基础项范围约14.65%—49.47%，三组同一系数，不偷偷分别调节。真实/置换关联梯度余弦−0.738至−0.472，仍有不同目标方向；JS与真实关联项余弦−0.060至+0.200，未发现四个局部检查点上一致强反向冲突，但也不能声称它必定帮助真实目标。24条六组总梯度与“基础梯度+系数×JS梯度”一致，最大相对误差7.27e-7以内。

## 反例与独立核验

- JS不读标签：实际32批交换真实与置换标签，JS值不变；改变监督目标仍会改变R/P基础目标，公共项保持相同。
- 共享候选顺序变换不改变JS，同一编码对自身的JS为0。它保留函数/边界身份的相对关系，而非强制单锥向量对任何输入身份重排不变。
- 已明确保留反例：两侧均匀候选概率也能使JS=0。因此损失下降或编码翻转减少并不自动证明学到了功能；下一轮必须同时报告候选熵、距离离散度、真实排序及表示是否坍缩。
- CPU独立重构32批双编码、224个基础损失、192个六组总目标、32个JS；最大基础损失误差2.07e-7、JS误差2.19e-8。独立重算系数相对误差7.72e-9以内，24条总梯度可加性通过。
- 本轮共92次模型前向、56次autograd求梯度，0优化器/0更新/0新增SAT/0检测微调/0测试读取；未消费验证评分作标定。原初始化权重、缓冲区及.grad字段不变，受保护旧文件哈希不变。

## 是否可以训练

可以进入小规模探索，不能跳过真实/置换/公共项三类对照。已生成FROZEN_TRAINING_CONTRACT.json，仍标记“本轮未授权/未执行训练”；未来获得训练指令后以新执行记录继承，保留该历史预检状态。六组各32步、seed42、共同旧初始化，Adam lr0.0002、weight_decay0.001、clip1、FP32及原模型不改。固定末步32；73个H3的9000为原主诊断，9001—9005保留，另冻结9006—9011检查未用于本轮原因诊断的编码，不挑最优编码/检查点。

重点比较R1−R0以及R1是否优于P1/Z1，并分源、流程、MUX、双/三候选报告；严格PO仍单列。若只提高编码一致性、候选分布变平而真实排序无改善，不算成功。当前验证面板已多轮用于诊断，不宜包装为新的确认性结论；编码复制也不补齐独立源对象。暂不检测微调、追加种子或扩大SAT。

证据目录：`_p0pilot/cec_dualcode_preflight_20261107/`。PREFLIGHT_CONTRACT.json、FROZEN_COEFFICIENT.json、FROZEN_TRAINING_CONTRACT.json、COMPLETE.json、VERIFIED.json、six_arm_budget_ledger.csv、calibration_gradients.csv、six_arm_gradient_checks.csv、six_actual_clone_checks.csv、gradient_vectors.npz及32份双编码preview；dual_interface.py供后续复用，避免训练另写目标造成偏差。
'''
(D/name).write_text(text,encoding='utf-8')
entry=f'''

### 2026-11-07 双编码候选排序一致性加载及无更新梯度预检（通过，未训练）

原7单元训练池/模型/共同INITIAL_STATE不变，实际加载32个双编码批（t、10000+t），六组Z0/Z1/R0/R1/P0/P1同输入同基础目标均值，仅JS系数开关。各组未来32步为64逻辑单元/384查询身份、128编码单元/768编码查询、2304候选距离/768公共负项、384个JS查询；基础监督不翻倍，不能与旧单编码R直接比较。

训练初始化批1/2/16/32标定λ={coefficient:.10f}，加权JS/R基础梯度范数比14.01%—32.32%、中位25%，六组共用同一系数，未用验证调节。真实/置换关联梯度仍负向，JS与真实项梯度余弦−0.060至+0.200；24条总梯度可加性通过。P内JS不读真实标签，未额外添加真实关联；共享候选重排与标签交换检查通过。均匀候选分布同样JS=0的反例保留，未来必须同时核查熵/离散度/真实排序，不能以一致性下降当功能收益。

独立复核32双编码批、224基础损失、192六组目标、32JS及系数通过，旧资产保持。92次冻结前向、56次autograd，0优化器/0训练/0新增SAT/0检测微调/0测试读取；可准备六组各32步探索，尚未执行。固定73H3及原9000主诊断，保留9001—9005，追加预定9006—9011编码诊断；不挑编码/检查点、不把编码数当独立宿主。

详见[双编码加载与梯度预检](双编码候选排序一致性加载与梯度预检_20261107.md)，证据`_p0pilot/cec_dualcode_preflight_20261107/`。
'''
for n in ['SAT作用证明.md','SAT工作总结.md']:
 p=D/n;b=p.read_bytes();old=b.decode('utf-8-sig');assert '双编码候选排序一致性加载及无更新梯度预检（通过' not in old
 (O/(n+'.before')).write_bytes(b);p.write_text(old+entry,encoding='utf-8')
manifest={p.name:sha(p) for p in O.iterdir() if p.is_file() and p.suffix in ['.py','.json','.csv','.npz'] and p.name not in ['OUTPUT_MANIFEST.json','PUBLISHED.json']}
(O/'OUTPUT_MANIFEST.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
(O/'PUBLISHED.json').write_text(json.dumps(dict(report=str(D/name),report_sha=sha(D/name),summaries_updated=True,training=0,SAT=0),ensure_ascii=False,indent=2),encoding='utf-8')
print('Published preflight and frozen exploratory contract; no training/SAT.')
