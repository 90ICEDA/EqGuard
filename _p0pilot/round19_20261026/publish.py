"""Publish posthoc diagnosis, evidence limits and a staged improvement plan."""
import csv
import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
OLD=ROOT/'10.15/06_统一评测协议/N4_三向泛化/tables/sat_small_round18'
OUT=OLD.parent/'sat_diagnosis_round19';RUN=ROOT/'results_sat_small_r18'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    analysis=json.loads((OUT/'analysis.json').read_text());loss=analysis['summary_loss']
    cf=json.loads((OUT/'fixed_checkpoint.json').read_text());dist=json.loads((OUT/'distribution.json').read_text())
    candidate=json.loads((OUT/'candidate_schema.json').read_text());old_manifest=json.loads((OLD/'manifest.json').read_text())
    assert sha(RUN/'results.json')==old_manifest['result_sha'] and sha(OLD/'plan.json')==old_manifest['source_plan_sha']
    for filename,expected in old_manifest['outputs'].items():assert sha(OLD/filename)==expected
    for filename,expected in analysis['input_hashes'].items():assert sha(ROOT/filename)==expected
    check=subprocess.run([sys.executable,'-B','-X','utf8',str(ROOT/'_p0pilot/round19_20261026/test_diagnosis.py')],cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
    (OUT/'test_diagnosis.log').write_text(check.stdout+check.stderr,encoding='utf-8');assert check.returncode==0,check.stderr
    def mean(split,variant,metric):return float(np.mean([r[metric] for r in cf['records'] if r['split']==split and r['input']==variant]))
    table=[]
    for variant in ('real','permuted','zero','cut_k_only','constant_validity_and_k'):
        table.append(f"| {variant} | {mean('val',variant,'AP'):.6f} | {mean('test',variant,'AP'):.6f} | {mean('val',variant,'mean_probability_change'):.6f} | {mean('test',variant,'FPR'):.2%} |")
    now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
    report=ROOT/'10.15/00_说明/SAT第十九轮_摘要信息损失与跨插入失败诊断_20261026s.md'
    body=f'''# 第十九轮：18维摘要的信息损失与跨插入组失败诊断

更新时间：{now}。本轮**新增SAT=0、优化器更新=0、训练运行=0**。
复用第十八轮全部真值表、掩码、输入/归一化、预测和3个real-arm checkpoint。
仅做描述性统计、完整表离线重编码和30次固定权重eval/no_grad前向。
所有第十八轮manifest登记的输入/结果哈希核对未改，未改变原split或选择新的测试候选。
zeta已经在第十八轮评估，本轮是posthoc开发诊断，不是新的独立确认性测试。

## 1. 结论与证据强度

**已确认**：18维压缩不是单射，会丢失具体激活模式及函数类别；零内容对照同时改变常量/元数据输入，
不能把real-zero差全部归于正确SAT内容；已有real模型对同层置换的正确节点绑定不敏感。

**强支持但不是因果识别**：跨插入组失败与类条件的结构/关系分布变化、局部函数缺少安全语境、训练正例只有两个插入组有关。
不是测试正例没有SAT特征，不是正例归一化裁剪，也不只是阈值设置。

**未证明**：置换更好的具体原因是正则化、随机标签式坐标提示、优化路径还是偶然。
只有一个置换种子和一个验证插入组；3个模型seed不等于3个独立迁移任务，不能据此认定随机SAT优于真实SAT。

## 2. 18维究竟丢了什么

- 2291个覆盖节点有356种原cut顺序的状态表；即使只消除输入排列差异，仍有**231种不同表类**，18维却只有**113种描述**。
- 56个摘要组包含多个不同排列规范表，涉及**1791/2291=78.18%**的节点。
  限定相同目标门类型、相同DFF-D/组合输出角色后，仍有71个更细碰撞组、1635个节点；不是仅由不同门类型混在一起造成。
- 训练覆盖节点上有8列恒定：`{', '.join(loss['train_constant_columns'])}`。
  `forced_fraction=feasible_fraction`，`complete_full_domain+complete_restricted_domain=covered`，还有其他互补关系。
  这并非提取错误：完整cut构造本就使所有可行模式被决定，因此若干“证据有效”字段变成常量，而非额外功能差异。
- 18维保留的是比例/均值/最大值，丢掉“哪个输入模式输出为1/不可行”、变量的具体条件绑定。
  只有1个摘要碰撞组还包含不同的**排序后逐输入统计分布**；仅再增加几个影响性均值/最大值，难以恢复大部分已丢失模式信息。
- 纯数学回归例：XOR2与XNOR2有相同18维摘要，但不在同一个只允许输入重排的表类中。
  真实网表中的同门类型/角色碰撞对及完整SAT表保存在`collision_examples.json`。

这里的“规范表类”只是表示统计，不是跨网表信号等价证明；不把输入/输出取反静默并入同一类，极性必须由物理绑定支持。
`ones_on_forced`也不是实际触发概率：它按cut模式计数，不包含模式的自然出现频率、复位可达状态或真实时序。

## 3. 置换对照实际改变了什么

最终置换保留split、目标角色、门类型、cut大小、覆盖掩码、查询状态的边际分布，结构39维完全不变。
表类真正改变的节点train815/val420/test435，其中**100/53/56个节点的18维仍完全不变**；
因此原18维对照并没有把这些已改变的完整函数暴露给模型。
另一方面，大量常量/有效性字段及k值在real/permuted之间相同，zero组把18列全清零，连这些字段也删了。
所以real优于zero、却不优于permuted，与“利用共同附加统计/尺度、没有充分利用正确函数对应”相容，不能直接称为SAT语义收益。

## 4. 固定checkpoint输入替换（无训练）

对全部3个real-arm best模型，固定权重、eval、冻结BN，分别输入real、已有同层perm、zero、仅k、k+训练覆盖集恒定字段。
每次均用softmax概率；real重算与第十八轮保存概率逐位一致，排除此前logit当概率的评估问题。

| 输入（相同real模型） | val AP均值 | zeta AP均值 | val平均概率绝对变化 | zeta FPR（原冻结阈值） |
|---|---:|---:|---:|---:|
{chr(10).join(table)}

real→perm：val AP 0.901971→0.903298，zeta 0.020977→0.020862，没有出现对正确绑定的明显依赖。
但整列清零会大幅改变概率，并令测试FPR约40%；这属于可能OOD的输入移除，不能当成“重新训练zero就更好”或可部署修复。
不能说模型完全忽略SAT输入；更准确是**有附加输入依赖，但当前证据不支持其利用了正确细粒度功能绑定**。

## 5. zeta为什么失败：局部安全语境与类条件迁移

### 5.1 排除简单解释

- train12/val12/test13个正例全部有SAT覆盖，全部在已有trust映射中为可信正例。
- val/test正例在±10归一化裁剪处都没有被裁剪；zeta正例39个单列值也没有越出训练全体节点范围。
- 失败不仅是阈值：真实SAT模型测试正例的排名中位数为**386/621**（39个seed×正例观测），平均正例概率约0.00107，
  而验证正例排名中位6.5、平均概率约0.811；只调低阈值不能恢复良好的排序。
- 固定权重real概率重算与原文件一致；局部/全局node ID及保存标签也一一对齐，未发现此次评估绑定错误。

### 5.2 可量化的迁移差异

- 在当前训练归一化的39维空间，zeta **13/13** 正例离训练负例比离训练正例更近；val是7/12。
  zeta最近训练正例距离中位2.920，最近负例1.489。该距离是描述性证据，不是对GNN预测的因果证明。
- 5个zeta正例的PI距离/时序边界重置PI距离超出训练**正例**范围，但未超出训练全体范围。
  更像“落入已见正常结构区域”的类条件变化，不是所有输入数值都发生灾难性越界。
- val正例门类型为INV5/XOR5/MUX2，test为INV6/XOR5/MUX2，二者很接近；不能只用门类型频率解释val成功/test失败。
- 18维层面，val12/12与test13/13正例都能找到同split负例的相同摘要。碰撞在val也存在，所以不能单独归因测试失败。
  保留完整规范表后，同类负例碰撞降为val11/12、test9/13；信息恢复有所帮助，但**完整局部函数也不是木马标签**。
- 组合39维结构和完整规范表后，zeta仍有6/13正例与本split某负例单节点属性完全相同。
  图邻域/控制与传播关系仍可能区分，不能把单节点碰撞误说成整个GNN理论上不可区分。
- zeta只有2/13正例的规范表类在训练正例中出现，8/13的规范表类完全没在训练节点中出现；
  18维压缩把其中一些看成“已见描述”，掩盖了真正的函数条件变化。

### 5.3 数据和评估规模限制

- 实际只有2个训练插入组、1个验证插入组、1个zeta测试组；12个正例常属于同一触发/载荷链，并非12个独立任务。
- 每组用同一个epsilon验证样本在25个点选最优，验证AP偏乐观的风险存在；例如real seed42的best-final差0.0607。
  这不是发现了协议泄漏，而是单一小验证集的选择波动，不能靠多跑模型seed补足设计多样性。
- 本实验label-mask=none；训练1193个负例中768个没有现有trust证明，验证597负例中376个、测试608负例中384个亦然。
  这不是这些节点被误标的证明，正例标签均有trust支持；但不能把未验证负例都描述成已证明安全。
  将其作为标签风险分层，当前没有翻转标签或重跑训练。

## 6. 改进方案（本轮只给方案与离线候选，不执行训练）

### 优先级1：复用真值表，换掉过度聚合，而不是继续加覆盖

已生成`candidate_boundary_repr.npz`：每节点最多16行×5状态one-hot，独立pattern mask/k/covered；
另存4输入×(比较覆盖、变化比例、有效性)及7725个原输入绑定。
该表示可逐条恢复2291张已有表（仅规范化输入排列），保留231个类而非113个摘要。
绑定区分PI、逻辑输出、物理Q/QN的pin/极性；DFF目标明确是D数据函数，不冒充Q/完整下一状态。
1508条记录的规范输入排列存在对称歧义，保留所有ties，不强行制造唯一输入对应。
**没有把哈希、类别编号、raw bit或节点ID当数值特征；没有接训练loader，training_allowed=false。**

下一次若获准训练，先比较同宽度的：结构+元数据、结构+元数据+完整表、结构+元数据+同层置换完整表。
元数据只包括k、padding、coverage/查询完成状态，不把真实可行域/强制输出误算成“纯元数据”。
保持容量、支持和元数据相同，才隔离功能内容；旧18维可作匹配宽度参考，不直接拿不同参数量宣称提升。
不要仅给18维增加几个影响性均值，也不要把规范化真值表当成已证明跨实现不变。

### 优先级2：把功能关系接回真实边界，而非只给target一个统计向量

使用候选中的cut输入图节点/PI、Q/QN极性、逐输入统计与target构造关系编码或功能超边；
输入顺序需置换等变/不变，表的模式位与原输入绑定必须同步变换；对称ties保留或池化，不能任意选一个当可靠对应。
完整表只能缓解局部信息损失；9/13测试正例仍与正常局部函数同类，后续还需要控制/载荷/下游可观测角色和更长范围语境。
这些关系不能由木马名或测试正例位置选择，也不能把单条函数复制到整块区域或迁移安全标签。

### 优先级3：修正评估单位，再谈扩大训练

先用多个插入/匹配组做开发验证，报告每组和组级macro AP，而非只报单个epsilon的节点池AP；
同时报告trusted/unverified分层，冻结标签政策、元数据对照和多个置换种子。
模型seed与置换seed是不同方差来源。zeta现已观察，只能作为开发证据；新的确认性实验必须设新的独立留出。
若要补激活稀有性/可达/下游传播，需要另外定义共同环境、物理状态或时序语义与预算；不能把`ones_on_forced`直接叫触发概率。
本轮不扩SAT、不增seed、不调阈值、不追加训练，等待用户选择下一步。

## 7. 可复核产物

- `analysis.json`、`summary_loss.json`、`collision_groups.csv`、`collision_examples.json`、`feature_ranges.csv`。
- `novelty_and_label_collisions.csv`、`positive_structural_distance.csv`、`structural_feature_shift.csv`、`trust_audit.json`。
- `fixed_checkpoint.json/csv`（30个固定权重输入诊断，eval/no_grad，优化器更新0）。
- `positive_prediction_ranks.csv`、`view_score_distribution.csv`、`distribution.json`、`permutation_column_changes.csv`。
- 离线候选：`candidate_boundary_repr.npz`、`candidate_bindings.json`、`candidate_schema.json`；6项回归全部通过。
- 脚本：`_p0pilot/round19_20261026/`；证据：`tables/sat_diagnosis_round19/`。原第十八轮数据/模型/结果不改写。
'''
    report.write_text(body,encoding='utf-8')
    section=f'''
<!-- sat_diagnosis_round19:start -->
## 29. 第十九轮：摘要信息损失与跨插入组失败诊断（未新增训练）

更新时间：{now}。详见[{report.name}]({report.name})。

- 复用第18轮证据；新增SAT0、训练0、优化器更新0，仅30次既有real checkpoint的eval/no_grad输入诊断；原输入/结果哈希未变。
- 2291覆盖节点的231种输入重排规范表被压为113种18维描述；56碰撞组涉及1791节点（78.18%）。同门类型/角色内仍有71碰撞组、1635节点；8列在训练覆盖节点上恒定。
- 原置换train815个节点真值表类改变，其中100个18维未变；validity/k等字段保留而zero全删，real-zero不是纯语义效应。
- 固定real模型换同层perm，val AP0.901971→0.903298、test0.020977→0.020862；清零则大幅改变概率且FPR升高。模型依赖附加输入，但正确函数绑定依赖弱；不定性为已证明正则化收益。
- 测试13正例全部覆盖且trust为真、无正例裁剪；13/13在39维空间更近训练负例，正例排名中位386/621，非仅阈值问题。完整局部表仍有9/13与负例同类，结构+完整表仍有6/13单节点碰撞，需关系语境。
- 已生成保留masked真值表、逐输入统计和PI/Q/QN绑定的离线候选，恢复231类，1508排列歧义保留ties；未接训练、未把hash/bit ID作数值特征；6回归通过。
- 方案优先级：完整表+元数据匹配对照→真实cut-target关系编码→多插入组验证与新独立留出；不继续只堆覆盖。本次zeta已作开发诊断，不再当未见确认集。
<!-- sat_diagnosis_round19:end -->
'''
    for name in ('SAT作用证明.md','SAT工作总结.md'):
        p=ROOT/'10.15/00_说明'/name;text=p.read_text(encoding='utf-8-sig')
        if '<!-- sat_diagnosis_round19:start -->' not in text:p.write_text(text.rstrip()+'\n'+section,encoding='utf-8')
    index=ROOT/'10.15/99_共用资产/repro/index.csv'
    if 'sat_diagnosis_round19_20261026' not in index.read_text(encoding='utf-8-sig'):
        with index.open('a',newline='',encoding='utf-8') as f:csv.writer(f).writerow(['audit','sat_diagnosis_round19_20261026',str(OUT.relative_to(ROOT)),'42,1,2','','posthoc compression/transfer diagnosis; 30 fixed inference passes; no SAT/training'])
    manifest=dict(created=now,report=str(report.relative_to(ROOT)),new_sat_queries=0,new_training_runs=0,optimizer_steps=0,
                  fixed_checkpoint_forward_passes=30,tests_passed=6,original_artifacts_unchanged=True,
                  interpretation='posthoc diagnosis, not a new independent held-out result or identified causal mechanism',
                  code_hashes={str(p.relative_to(ROOT)):sha(p) for p in sorted((ROOT/'_p0pilot/round19_20261026').glob('*.py'))},
                  outputs={p.name:sha(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='manifest.json'})
    (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(report);print('summaries and repro updated; no SAT/training')


if __name__=='__main__':main()
