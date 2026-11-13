"""Publish frozen small-netlist experiment, including negative held-out results."""
import csv
import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[2]
T=ROOT/'10.15/06_统一评测协议/N4_三向泛化/tables/sat_small_round18'
RUNS=ROOT/'results_sat_small_r18'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    plan=json.loads((T/'plan.json').read_text());coverage=json.loads((T/'coverage.json').read_text())
    audit=json.loads((T/'post_audit.json').read_text());gate=json.loads((T/'pretrain_gate.json').read_text())
    result=json.loads((RUNS/'results.json').read_text());rows=json.loads((T/'records.json').read_text())
    for file in ['_p0pilot/round18_20261026/test_native_extract.py','_p0pilot/round17_20261026/test_sat_semantics.py']:
        run=subprocess.run([sys.executable,'-B','-X','utf8',str(ROOT/file)],cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
        (T/(Path(file).stem+'.log')).write_text(run.stdout+run.stderr,encoding='utf-8');assert run.returncode==0
    now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
    stats_rows=[]
    for s in ('train','val','test'):
        a=gate['stats'][s];stats_rows.append(dict(split=s,**a,unique_covered_profiles=audit['corrected_covered_profile_counts'][s]['unique_covered_profiles']))
    with (T/'coverage_summary.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(stats_rows[0]));w.writeheader();w.writerows(stats_rows)
    output=[]
    for r in result['results']:
        output.append(dict(arm=r['arm'],seed=r['seed'],best_epoch=r['best_epoch'],updates=r['updates'],
                           val_AP=r['val_best']['AP'],val_AUC=r['val_best']['ROC_AUC'],
                           test_AP=r['test']['AP'],test_AUC=r['test']['ROC_AUC'],
                           test_recall=r['test']['recall'],test_FPR=r['test']['FPR'],
                           init_sha=r['init_sha'],checkpoint_sha=r['checkpoint_sha']))
    with (T/'training_results.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(output[0]));w.writeheader();w.writerows(output)
    agg=result['aggregate'];summary_table=[]
    for arm in ('zero','real','permuted'):
        val=agg[arm]['val_best']['AP'];test=agg[arm]['test']['AP'];auc=agg[arm]['test']['ROC_AUC']
        summary_table.append(f"| {arm} | {val['mean']:.6f} ± {val['std']:.6f} | {test['mean']:.6f} ± {test['std']:.6f} | {auc['mean']:.6f} ± {auc['std']:.6f} |")
    split_table=[]
    for r in stats_rows:
        split_table.append(f"| {r['split']} | {r['nodes']} | {r['covered']} | {r['coverage']:.2%} | {r['unique_covered_profiles']} | {r['nonlocal_nodes']} | {r['permutation_changed']} |")
    report=ROOT/'10.15/00_说明/SAT第十八轮_小网表逐节点提取与三组GPU对照_20261026r.md'
    text=f'''# 第十八轮：小网表逐节点native SAT提取与三组GPU对照

更新时间：{now}。**提取、信息量验收、3个seed×3组训练及冻结测试评估均已完成**。
结果为受控小样本实验；不宣称SAT已带来检测增益，不因测试结果追加训练或修改候选。

## 1. 网表与预先冻结的划分

仅使用rs232t1000、ys_abc，8个约48–51KB网表；选择依据是小规模、确切来源和匹配设计组，不查看正例节点位置。

- train：injalpha/ctlmatcha、injbeta/ctlmatchb，4网表/1205节点。
- val：injepsilon/ctlmatche，2网表/609节点。
- test：injzeta/ctlmatchf，2网表/621节点。

同插入/匹配对照组不跨split；没有混入同设计的其他综合实现。**所有组仍共享rs232主体逻辑**，
因此这是同宿主不同插入组的受控实验，不能作为跨宿主或大规模独立设计泛化结果。
`plan.json`在候选标签读取前冻结；训练超参数/类权重规则在训练前固定，所有模型完成验证选模后才读取测试标签。

## 2. native上下文与逐节点定义

复用第10–16轮的`native_unrestricted_combinational_physical_Q_v1`语义：同名物理Q为任意状态，QN为补；
PI无模式限制，无复位、可达性、协议或扫描模式约束。8个新模型的全部组合赋值与历史native生成器逐行一致。

全部2435个图单元均访问一次：组合单元取实际输出pin；DFF单元单列`DFF_data_D`，描述其**D数据输入组合函数**。
后者不是该DFF的当前Q函数，也不是包含SE/SI/异步置位复位的完整下一状态函数；不把两者混写。
cut从完整扇入边界逐步展开，最多4个输入、展开深度规则4，不丢掉某个门的其他输入，不按Trojan名字选择候选。
输入排序按当前raw中的bit，完整枚举2^k模式；以单一predicate表达cut条件，保留同bit与Q/QN关联导致的不可行模式。

- 2291个单元得到完整表，1971个不同(target bit, cut bits)查询任务；320个DFF数据端与组合输出复用同源证明。
- 144个单元没有非平凡可展开cut，显式未覆盖，不伪造特征或增加covered。
- 18维摘要+covered，共19列；只附着对应单元，缺失为零。
- 1418条完整全域表、873条完整受限域表；强制及可比较影响证据均有2291条，但influence仍是条件模式对变化，不是共享环境因果干预。

## 3. 覆盖和信息量先验收，再训练

| split | 全部节点 | 有效覆盖 | 有效覆盖率 | 覆盖节点唯一描述 | 非局部边界节点 | 同层置换实际改变节点 |
|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(split_table)}

训练/验证覆盖超过80%、描述多样性超过10种、同层置换改变超过30%，通过工程验收；这些门槛不是检测增益证明。
相同目标门类型内也存在多种描述，说明不只是目标门one-hot；但深度≤4的Boolean结构仍可能由结构模型学习，未证明相对全部39维结构信息的不可替代性。
原coverage/gate的unique_profiles包含1个未覆盖全零占位，本报告和post_audit改为只统计覆盖描述85/73/66；
冻结gate文件保留原样，其哈希与训练记录一致，修正计数仍满足同一门槛。

初版置换仅按split/角色分层；**开训前**发现会改变cut大小，新增独立修订：最终置换按split、target_role、driver_type、k共同分层，
保留cut大小、门类型、支持位置、covered和39维结构。初版数组保留但没有参与训练。
训练用`permuted_stratified.npy`，完整映射已逐条核对，没有跨split池。

## 4. SAT执行与独立审计

- 实际SAT **46,480** 次：proved 26,502 / refuted 19,978 / unknown 0 / error 0。
- 64个批次；源/raw/model/script/log绑定；64个模型重生成一致，逐查询标记/命令/状态重核一致。
- 2291条完整边界图证书通过：从target沿扇入遍历，所有自由叶子均被cut截断，没有漏输入。
- 预先按序号选取每网表3个代表任务，24个SAT反例由独立三值native解释器回放通过。
- 新提取器5项回归+共享语义13项回归通过，后者内部含272个布尔函数穷举。
- SAT子进程累计墙钟约 **{audit['sat_process_wall_s']:.1f}s**，不含读图/结构导出/审计；批量建模、同源任务复用，无需逐查询启动WSL。

## 5. GPU训练协议

- 解释器：`ginvenv_gpu`；设备：{result['protocol']['device']}；PyTorch {result['protocol']['torch_version']}。
- GIN：4层、hidden64；三组均58维，39结构+18内容+covered。
- 组：zero、real、permuted；seed42/1/2，共9次训练，每次250次更新，无额外辅助损失。
- Adam lr0.001/weight_decay0.001；CE类权重由训练标签计算[1,99.4167]，训练12正例/1205节点。
- 仅用训练节点fit39维归一化；bounded内容不z-score、不裁掉有效变化。
- **训练forward和BatchNorm仅见训练图**；验证/测试在独立图、eval模式下前向，无跨split边。
- FP32、严格GPU确定性设置通过；同seed三组init哈希一致，保存checkpoint同输入重算差≤1e-6。
- 每10步验证，按最大val AP选模，精确同分保留更早；保存best和final。
- 所有9个模型选模完成后写`validation_selection_complete.json`，之后才访问13个测试正例并预测。
- 概率统一为`softmax(logits.float(), dim=1)[:,1]`；保存预测的AP/AUC由独立脚本重算一致。
- 测试阈值由各自验证负例的95%分位数固定，严格`p>thr`，不在测试集调阈值。
- 正式训练+最后测试墙钟约 **{result['wall_s']:.1f}s**；3组同seed预算一致，无看测试后追加。

## 6. 结果（均值±样本标准差，3 seeds）

| 组 | 验证AP | 留出zeta测试AP | 测试ROC-AUC |
|---|---:|---:|---:|
{chr(10).join(summary_table)}

验证12正例/609节点（比例1.97%），模型已能学习，优于第16轮仅10步、近随机的全图smoke。
但真实SAT在验证上低于置换SAT，不能把相对零内容的提升解释为正确功能内容收益。
测试13正例/621节点，正例比例 **{13/621:.6f}**；真实SAT的平均AP接近该比例。
三组全部seed的测试recall均为0（阈值由验证集冻结）；测试FPR均值zero 3.40%、real 2.80%、permuted 3.56%。

配对AP差：real-zero验证均值+0.03609，测试均值+0.00502（其中1/3 seed为负）；
real-permuted验证均值−0.01155（3/3 seed为负），测试均值+0.00327（其中1/3 seed为负）。
**结论：高覆盖提取已实现，但尚无稳定的正确SAT语义增益，且未解决跨插入组迁移。**
不挑选最好seed，不因结果不好改变测试组，不把本次共享host实验外推成跨host性能。

## 7. 产物、保留与下一步

- 生产模块：`phase2/ys/native_boundary_extract.py`；编排/审计：`_p0pilot/round18_20261026/`。
- 证据、表、输入：`tables/sat_small_round18/`；模型/日志/概率：`results_sat_small_r18/`。
- 汇总表：`coverage_summary.csv`、`training_results.csv`；源选择`plan.json`、信息门槛`pretrain_gate.json`、后审计`post_audit.json`。
- 没有修改旧训练入口、旧模型或旧特征数组；原11条跨实现配对状态不因本次单实现逐节点提取增加。
- 本次zeta测试已使用；后续若针对其失败进行表示/协议改动，应把它视为已观察开发证据，并设新的独立留出后再声称确认性结果。
- 后续应优先分析18维聚合是否丢失关键条件、物理Q自由初态与真实触发语义的差距，以及共享host/插入组迁移；
  不建议继续只堆covered或重复相同三组训练。本轮到此停止。
'''
    report.write_text(text,encoding='utf-8')
    section=f'''
<!-- sat_small_round18:start -->
## 28. 第十八轮：小网表高覆盖native提取与三组GPU对照

更新时间：{now}。详见[{report.name}]({report.name})。

- 冻结8个rs232/ys_abc小网表：alpha/beta及对照train、epsilon及对照val、zeta及对照test；不按正例位置选候选。共享host主体，非跨host泛化。
- 逐节点访问2435单元，完整有效表2291（1971个同源任务，DFF D数据函数复用320）；144无非平凡cut不伪造覆盖。DFF特征明确是D数据端函数，不是Q或完整下一状态。
- 有效覆盖train1133/1205=94.02%、val573/609=94.09%、test585/621=94.20%；覆盖描述85/73/66种；非局部边界1883条。
- 46,480次SAT无unknown/error；64批模型重生成、2291完整边界证书、24独立反例回放通过；SAT子进程累计约99.5秒。
- 最终置换按split/角色/门类型/k分层，改变715/367/379节点；保留cut大小、结构、支持及mask。初版置换保留但未训练。
- ginvenv_gpu FP32确定性GIN，三组同58维、同seed初始化，seed42/1/2各250更新；train-only归一化及BatchNorm，9组全部选模后才读测试标签；训练约29.3秒。
- 验证AP均值zero0.8659、real0.9020、perm0.9135；测试AP均值0.0160/0.0210/0.0177，测试正例比例0.02093、冻结阈值召回全0。高覆盖已实现，但没有稳定正确SAT语义增益，未解决跨插入组迁移；不挑seed、不追加测试调参。
<!-- sat_small_round18:end -->
'''
    for name in ('SAT作用证明.md','SAT工作总结.md'):
        p=ROOT/'10.15/00_说明'/name;old=p.read_text(encoding='utf-8-sig')
        if '<!-- sat_small_round18:start -->' not in old:p.write_text(old.rstrip()+'\n'+section,encoding='utf-8')
    index=ROOT/'10.15/99_共用资产/repro/index.csv'
    if 'sat_small_round18_20261026' not in index.read_text(encoding='utf-8-sig'):
        with index.open('a',newline='',encoding='utf-8') as f:csv.writer(f).writerow(['experiment','sat_small_round18_20261026',str(T.relative_to(ROOT)),'42,1,2',str((RUNS/'protocol.json').relative_to(ROOT)),'8 netlists, 94% native SAT support, 46480 queries, 3 arms x 3 seeds; no stable semantic gain'])
    manifest=dict(created=now,report=str(report.relative_to(ROOT)),actual_sat_queries=46480,training_runs=9,updates_per_run=250,seeds=[42,1,2],test_access='after all validation model selections',result_sha=sha(RUNS/'results.json'),source_plan_sha=sha(T/'plan.json'),code_hashes={str(p.relative_to(ROOT)):sha(p) for p in [ROOT/'phase2/ys/native_boundary_extract.py',*sorted((ROOT/'_p0pilot/round18_20261026').glob('*.py'))]},outputs={p.name:sha(p) for p in [T/'real.npy',T/'zero.npy',T/'permuted_stratified.npy',T/'post_audit.json',T/'pretrain_gate.json']})
    (T/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(report);print('summaries and repro updated')


if __name__=='__main__':main()
