"""Publish conditional model-dependence results with identifiability limits."""
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
OUT=OLD.parent/'sat_importance_round20'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    result=json.loads((OUT/'results.json').read_text());protocol=result['protocol']
    assert protocol['new_training_runs']==protocol['optimizer_steps']==protocol['new_sat_queries']==0
    for path,expected in result['input_hashes'].items():assert sha(ROOT/path)==expected
    tests=subprocess.run([sys.executable,'-B','-X','utf8',str(ROOT/'_p0pilot/round20_20261026/test_importance.py')],cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
    (OUT/'test_importance.log').write_text(tests.stdout+tests.stderr,encoding='utf-8');assert tests.returncode==0,tests.stderr
    # Raw runs stay intact; suppress AP roundoff below 1e-12 for interpretation.
    runs=list(csv.DictReader((OUT/'runs.csv').open(encoding='utf-8')));summary=[]
    for row in result['summary']:
        rr=[r for r in runs if r['split']==row['split'] and r['group']==row['group']]
        drops=np.array([float(r['AP_drop']) for r in rr]);drops[np.abs(drops)<1e-12]=0
        r=dict(row,mean_AP_drop=float(drops.mean()),sd_AP_drop=float(drops.std(ddof=1)),positive_drop_runs=int((drops>0).sum()))
        summary.append(r)
    (OUT/'summary_tolerance.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    def get(s,g):return next(r for r in summary if r['split']==s and r['group']==g)
    aliases={'output_one_fraction':'输出取1占比','influence_strength_joint':'平均变化比例＋最大输入影响',
             'mean_change_fraction':'平均变化比例（单项）','domain_and_comparability':'可行域＋比较覆盖联合',
             'comparable_pair_fraction':'比较覆盖率（单项）','max_input_influence':'最大输入影响（单项）',
             'feasible_fraction_alone':'可行比例（单项）','forced_fraction_alone':'强制比例（单项）','all_function_content':'完整功能内容块（保留k/掩码）'}
    table=[]
    for group in protocol['groups']:
        a,b=get('val',group),get('test',group)
        def fmt(r):return f"{r['mean_AP_drop']:+.6f} ± {r['sd_AP_drop']:.6f}" if r['identifiable'] else '不可辨识'
        table.append(f"| {aliases[group]} | {a['mean_changed_nodes']:.1f} | {fmt(a)} | {b['mean_changed_nodes']:.1f} | {fmt(b)} |")
    now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
    report=ROOT/'10.15/00_说明/SAT第二十轮_功能特征条件重要性诊断_20261026t.md'
    body=f'''# 第二十轮：哪些SAT功能特征被当前模型利用

更新时间：{now}。**新增SAT=0、训练=0、优化器更新=0**；只用第十八轮3个real-arm checkpoint。
5个固定干预种子×9种特征组×2split×3模型seed，共270个诊断记录；无合法变化时不执行额外前向，实际141次eval/no_grad前向。
测试zeta已观察，本轮仅posthoc开发诊断，不选新测试、不证明跨任务泛化。

## 1. 为什么真值表不直接等于木马检测

当前表只描述局部cut怎样决定target，正常逻辑和木马中的门可以具有相同函数；它不是“是否为木马”的oracle。
第十九轮已发现zeta13个正例中9个与负例具有相同规范局部表，说明局部行为不包含完整安全语境。
若有可信无木马参考设计或明确安全性质，确实可以直接用SAT/CEC验证相应功能差异/性质，无需为同一验证问题强行训练GNN。
当前实验面向缺少此类完整参考、需要学习结构和功能语境的检测任务；模型的必要性应由与规则/验证基线的对照证明，而非预设。

## 2. 重要性方法及边界

- 使用3个既有real模型，固定权重、eval/no_grad、冻结BN，不构造优化器。
- 5个干预种子11/23/37/53/71；按split、角色、门类型、k分层，再要求**所有未扰动字段逐值完全相同**。
- 只从现有SAT表的真实特征向量替换所测字段；全向量必须等于某个合法peer向量，避免forced≠feasible或掩码/函数状态自相矛盾。
- 基线重算与保存概率差≤1e-6（本次为0）；AP使用softmax正类概率。
- AP下降=原AP−条件扰动AP，正值表示当前模型在这批支持点上依赖正确值。低于1e-12的AP差按舍入误差归零；原始结果保留。
- 这测的是**当前已训练模型的条件依赖**，不等于删除该特征后重新训练的贡献，也不是已识别的独立因果效应。
- 各组可扰动支持不同、部分组重叠，不能直接相加或当作无偏的重要性排行榜。
  没有合法变化的“不可辨识”，不能读成“无用”；15条重复诊断不是15个独立设计。

## 3. 结果（AP差均值±描述性标准差）

| 特征组 | val平均改变节点 | val AP下降 | zeta平均改变节点 | zeta AP下降 |
|---|---:|---:|---:|---:|
{chr(10).join(table)}

可辨识的单项/小组中：

- **影响强度联合**（change_on_comparable＋max_input_influence）在val平均下降0.00134，但标准差0.00231，只有4/15次为正；
  在zeta平均下降为−0.000322，15次均未显示正向重要性。它是可继续研究的候选，**不是已经证明有迁移收益的特征**。
- **输出取1占比**在val平均下降0.000336、zeta约0.000015，均远小于重复诊断波动。
  val中该严格条件下可改变的直接正例节点为0，不能把间接/负例排名变化解释成它直接识别了触发节点。
  该比例仍不是实际触发概率。
- **平均变化比例单项**：val AP差在舍入容差内为0；当前没有观察到可迁移正向作用，但不能据此证明所有任务上无效。
- **可行/强制比例等**高度耦合。当前所有可行模式均被决定，forced_fraction=feasible_fraction；
  若只动一列会制造不合法向量，严格条件下找不到peer，因此单项贡献不可辨识。
  最大输入影响单项、比较覆盖率单项也没有可独立变化的支持，不能凭此删除。
- **完整功能块**换多个置换种子后，val平均AP下降0.00788±0.01725，zeta0.000716±0.000940；
  有轻微整体依赖迹象，但规模和一致性不足以构成检测增益结论。
  第十九轮只用一个置换时未下降，本轮说明单一置换不能概括全部随机对照；也不能因此改称真实SAT已优于置换。

## 4. 目前能定位到什么，不能定位到什么

能定位：哪些字段在当前模型中存在可测依赖、哪些是恒定记账字段、哪些因相关性和缺乏支持无法单独识别。
目前**没有任何一项被证实具有稳定的跨插入组检测收益**。更不能由第一层权重大小或一次全列清零直接宣布“某列最有用”。
不能定位：在新插入组上必然有用的功能性质。对此至少需要匹配容量/元数据的重新训练消融，以及多个独立插入组。

## 5. 建议的保留/改进优先级

1. 保留“可行域”和“条件影响”作为**联合证据组**，暂不按单列排名删除；把有效性字段作为mask/元数据，避免当成功能创新量。
2. 输出1占比可留作廉价辅助统计，不应作为主要功能表示，更不能称为稀有触发概率。
3. 若要恢复功能信息，不必直接给模型一个巨大“全电路真值表”；优先使用已有小cut表的紧凑条件表示：
   哪些条件强制0/1、输入如何影响target、cut与PI/Q/QN/目标的可靠绑定。第十九轮候选已离线准备，但未训练。
4. 安全上更有意义的候选是“某条件下控制能否改变载荷、是否能传播到PO/DFF、是否具有可达或稀有联合条件”。
   这些需要单独的语义/证据，不能把当前均值/最大影响当作已完成的因果/时序证明；本轮不扩搜。
5. 下一次若获准训练，用结构+元数据、结构+单个功能组、结构+组合功能组、同层置换做同宽度对照；
   多插入组开发验证、再用新独立留出确认。也可设置无需GNN的SAT规则/检索基线，检验模型是否提供额外价值。

## 6. 产物与保留

`protocol.json`、`runs.csv`、`summary.csv`/`summary_tolerance.json`、`conditional_mappings.npz`、`results.json`。
方法回归5项通过：相关列不伪独立、联合替换为真实peer、常量不可辨识、角色/门类型/k/split保持、可复现且不修改输入。
所有原第十八轮输入/结果哈希已核对；未改模型、特征数组或SAT脚本。两份SAT总结和repro更新。
'''
    report.write_text(body,encoding='utf-8')
    section=f'''
<!-- sat_importance_round20:start -->
## 30. 第二十轮：功能特征条件重要性（无训练）

更新时间：{now}。详见[{report.name}]({report.name})。

- 局部真值表不是木马标签；有可信参考/安全性质时SAT可直接验证，否则仍需关系和安全语境，不能预设必须用GNN。
- 3个既有real模型×5干预种子，按split/角色/门类型/k且未扰动字段全等进行真实peer替换；270条诊断记录、141次eval/no_grad前向，新增SAT/训练/优化器更新均0。
- 影响强度联合val AP下降0.00134±0.00231，zeta为−0.000322；输出1占比val约0.000336，zeta约0.000015，均无稳定迁移结论。
- 可行/强制比例、最大影响等单项因耦合/无合法peer不可独立辨识，不能称无用；8个恒定字段属于有效性/记账而非独立功能信号。
- 完整功能块多置换的平均AP下降val0.00788±0.01725、test0.000716±0.000940；有轻微依赖迹象但未证明检测增益，单一置换不能代替多随机对照。
- 当前没有已确认跨插入组有用的单项；后续保留联合证据、恢复条件与输入绑定，并做匹配元数据/容量的训练消融和新留出。5项方法回归通过，原模型/数据未改。
<!-- sat_importance_round20:end -->
'''
    for name in ('SAT作用证明.md','SAT工作总结.md'):
        p=ROOT/'10.15/00_说明'/name;text=p.read_text(encoding='utf-8-sig')
        if '<!-- sat_importance_round20:start -->' not in text:p.write_text(text.rstrip()+'\n'+section,encoding='utf-8')
    index=ROOT/'10.15/99_共用资产/repro/index.csv'
    if 'sat_importance_round20_20261026' not in index.read_text(encoding='utf-8-sig'):
        with index.open('a',newline='',encoding='utf-8') as f:csv.writer(f).writerow(['audit','sat_importance_round20_20261026',str(OUT.relative_to(ROOT)),'42,1,2','','conditional feature dependence; 5 perturbation seeds; no SAT/training'])
    manifest=dict(created=now,report=str(report.relative_to(ROOT)),new_sat_queries=0,new_training_runs=0,optimizer_steps=0,
                  actual_forward_passes=141,diagnostic_records=270,tests=5,
                  code_hashes={str(p.relative_to(ROOT)):sha(p) for p in sorted((ROOT/'_p0pilot/round20_20261026').glob('*.py'))},
                  output_hashes={p.name:sha(p) for p in OUT.iterdir() if p.is_file() and p.name!='manifest.json'})
    (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(report)


if __name__=='__main__':main()
