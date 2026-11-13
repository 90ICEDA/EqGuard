"""Assemble evidence, commands, and an optional additive repro registration."""
import argparse
import csv
import hashlib
import json
import shutil
from datetime import datetime,timezone,timedelta
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'10.15/06_统一评测协议/N4_三向泛化/tables/audit_20261025'
DOC=ROOT/'10.15/00_说明/SAT审计与reach对照_20261025.md'


def mdtable(d,cols):
    lines=['| '+' | '.join(cols)+' |','|'+'|'.join(['---']*len(cols))+'|']
    for _,r in d.iterrows():
        vals=[]
        for c in cols:
            v=r[c]
            vals.append(f'{v:.6f}' if isinstance(v,float) else str(v))
        lines.append('| '+' | '.join(vals)+' |')
    return '\n'.join(lines)


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):
            h.update(block)
    return h.hexdigest()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--register',action='store_true')
    a=parser.parse_args()
    now=datetime.now(timezone(timedelta(hours=8)))
    relations=pd.read_csv(OUT/'two_case_relations.csv')
    observ=pd.read_csv(OUT/'two_case_observability.csv')
    replay=pd.read_csv(OUT/'witness_replay.csv')
    funnel=pd.read_csv(OUT/'node_funnel.csv')
    norm=pd.read_csv(OUT/'normalization_audit.csv')
    bench=json.loads((OUT/'feature_group_benchmark.json').read_text())
    reachbench=pd.read_csv(OUT/'reach_benchmark.csv')
    metrics=pd.read_csv(OUT/'model_summary.csv')
    legacy=pd.read_csv(OUT/'legacy_query_alignment.csv')
    fold=json.loads((ROOT/'generate_trans/folds/hosts_bt31/views.json').read_text())
    cec=pd.read_csv(ROOT/'generate_trans/folds/hosts_bt31/view_manifest_cec.csv')
    cecrows=[]
    for split in ['train','val','test']:
        d=pd.DataFrame(dict(view_name=fold[split+'_views'])).merge(cec[['view_name','cec_status']],on='view_name',how='left')
        d['split']=split
        d.cec_status=d.cec_status.fillna('MISSING_RECORD')
        cecrows.append(d)
    cecjoined=pd.concat(cecrows,ignore_index=True)
    cecjoined.to_csv(OUT/'view_cec_audit.csv',index=False,encoding='utf-8-sig')
    allm=metrics[metrics.scope=='all_labels']
    trustm=metrics[metrics.scope=='trusted_only']
    configs={}
    for tag in ['fghtl_AuditReachD42_20261025','fghtl_AuditCovered3D42_20261025']:
        p=ROOT/f'results/hosts_bt31_seed42mode4_allb1_fold_{tag}/run_config.json'
        if p.exists():
            configs[tag]=json.loads(p.read_text())
    complete='covered_matched42' in set(metrics.model)
    if a.register:
        assert complete and len(configs)==2
        assert all(c['device']=='cuda:0' and c['in_channels']==42 and c['epochs']==100 for c in configs.values())
        assert len(replay)==int((observ.status=='sensitizable_sat').sum()) and replay.passed.all()
    manifest=dict(updated=now.isoformat(),complete=complete,training_python=str(ROOT/'ginvenv_gpu/Scripts/python.exe'),
                  cpu_python=str(ROOT/'ginvenv/Scripts/python.exe'),configs=configs,
                  feature_sha256={name:sha(ROOT/'generate_trans/folds/hosts_bt31/data/processed'/name) for name in [
                      'satrel_node_feats_sat_p0clean4_core_reach.npy','satrel_node_feats_audit_covered_matched3_20261025.npy']},
                  config_sha256=sha(ROOT/'_devcfg/dual.yaml'))
    commands={
        'coverage':'ginvenv/Scripts/python.exe -X utf8 -u _p0pilot/audit_sat_20261025.py coverage',
        'relations':'ginvenv/Scripts/python.exe -X utf8 -u _p0pilot/audit_sat_20261025.py cases',
        'observability':'ginvenv/Scripts/python.exe -X utf8 -u _p0pilot/audit_observability_20261025.py',
        'witness_replay':'ginvenv/Scripts/python.exe -X utf8 _p0pilot/replay_observability_20261025.py',
        'regression':'ginvenv/Scripts/python.exe -X utf8 _p0pilot/test_audit_20261025.py',
        'metrics':'ginvenv/Scripts/python.exe -X utf8 -u _p0pilot/audit_metrics_20261025.py',
        'reach_benchmark':'ginvenv/Scripts/python.exe -X utf8 _p0pilot/audit_reach_bench_20261025.py',
        'feature_benchmark':'ginvenv/Scripts/python.exe -X utf8 _p0pilot/benchmark_feature_groups_20261025.py',
        'legacy_alignment':'ginvenv/Scripts/python.exe -X utf8 _p0pilot/audit_legacy_queries_20261025.py',
        'covered_train':'powershell -NoProfile -ExecutionPolicy Bypass -File _run_audit_covered_20261025.ps1',
    }
    common=('ginvenv_gpu/Scripts/python.exe -X utf8 -u train_test2.3.py '
            '--work-dir generate_trans/folds/hosts_bt31 --fold-json generate_trans/folds/hosts_bt31/views.json '
            '--pt-dir generate_trans/folds/hosts_bt31/data/processed --config _devcfg/dual.yaml '
            '--fold-mode fold --steps-per-epoch 1 --val-every 5 --view-policy all --amp --resume '
            '--epochs 100 --train-mode 4 --label-mask trust --save-ckpt --extra-feats satrel_node --seed 42 ')
    commands['reach_train']=common+'--extra-node-file satrel_node_feats_sat_p0clean4_core_reach.npy --tag fghtl_AuditReachD42_20261025 --dump-scores _devcfg/gnn_audit_reach_s42_20261025.npz'
    commands['report']='ginvenv/Scripts/python.exe -X utf8 _p0pilot/write_audit_report_20261025.py --register'
    manifest['commands']=commands
    reach_log=ROOT/'logs/audit_reach_20261025.log'
    covered_log=ROOT/'logs/audit_covered3_20261025.log'
    manifest['training_timing']={
        'reach_log_creation_to_last_write_s':reach_log.stat().st_mtime-reach_log.stat().st_birthtime,
        'covered_start_end_lines':[line for line in covered_log.read_text(encoding='utf-8-sig',errors='replace').splitlines() if line.startswith(('START ','END '))],
    }
    manifest['cec_manifest_status_counts']=cecjoined.groupby(['split','cec_status']).size().astype(int).to_dict()
    manifest['cec_manifest_status_counts']={f'{k[0]}/{k[1]}':v for k,v in manifest['cec_manifest_status_counts'].items()}
    (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    controls_note='covered 对照尚未完成；不能把 reach 与 B 的差异单独归给 reach。'
    if complete:
        v=allm.set_index('model')
        delta=v.loc['reach_plus_covered','inj_percentile_pooled_AP']-v.loc['covered_matched42','inj_percentile_pooled_AP']
        delta_view=v.loc['reach_plus_covered','viewmean_AP']-v.loc['covered_matched42','viewmean_AP']
        controls_note=f'相同 42 维的 reach+covered 相对 covered-only：pooled AP 差 {delta:+.6f}，逐视图平均 AP 差 {delta_view:+.6f}。这仍是单 seed 结果。'
    norm['clipped_fraction_of_nonzero']=norm.clipped_covered/norm.covered_nonzero.clip(lower=1)
    rawcols=['model','viewmean_AP','viewmean_recall_1pct','viewmean_recall_5pct','inj_percentile_pooled_AP','normal_FPR_at_val_threshold']
    text=f'''# SAT 功能关系审计、覆盖漏斗与结构 reach 对照

更新时间：{now.strftime('%Y-%m-%d %H:%M:%S')}（Asia/Shanghai）。状态：{'本轮完成' if complete else 'covered 配对对照训练中'}。

本轮围绕“两例功能关系审计、逐列覆盖漏斗、结构 reach 对照”。全部模型训练使用 ginvenv_gpu，100 epoch、seed42、GPU 串行；ginvenv 只运行 CPU 数据审计和 WSL/Yosys 调用。未改 train_test2.3.py，未覆盖历史特征或结果。新证据在 tables/audit_20261025/；本轮新关系尚未加入模型训练，不能据此声称新 SAT 特征已提升 AP。

## 1. 判断

- core7 是 P0 旧查询统计、结构 reach 和 P1 对应统计的混合；其增益不能整体称为“SAT 真实增益”。
- 训练所读 functional_relations_v3.csv 来自 sat_label_v3.py 对旧 agnostic CSV 的重新标注，两个文件均为 32,936 行。它不是 sat_functional_relations_v3.py 全模式验证的产物；本地默认 _p0pilot/functional_relations_v3.csv 不存在。core7 又从 p0clean3/p0clean2 继承，未因这次重标注而更新。
- {controls_note}
- 稀疏列的裁剪非常严重，因此“判定列完全没有信息”“全部是优化伪影”仍不能作最终结论。
- 保留原任务书的逐视图 AP 为主；视图内百分位 pooled AP 作补充。不能因为某种口径结果更好就更换主指标。

## 2. 两例 SAT 审计

样本为 rs232t1000 的 injalpha、injepsilon，在 ys_id/ys_abc/ys_aig 六个实际文件上选取 {len(relations)} 条 mux/cone/DFF 关系。为审计机制，优先选带木马命名的候选；这个选择仅用于审计，不能当作盲提取方案推广到训练集。

- 完整枚举 {int(relations.patterns.sum())} 个割集模式；{int(relations.feasible_patterns.sum())} 个可满足，{int(relations.vacuous_patterns.sum())} 个不可满足；每模式检查可满足性及目标 0/1，合计 {int(3*relations.patterns.sum())} 次查询。
- unknown 模式 {int(relations.unknown_patterns.sum())}，每查询超时预算 3 秒。不可满足模式单列，不当成有效真值证明。
- 每个查询都有独立编号；中间超时不会让后续查询错位。影响性通过实际模式元组查找仅翻转一个输入的邻居，不再依赖查询序号异或。
- 下游双副本检查：{int((observ.status=='sensitizable_sat').sum())} 条 sensitizable_sat，{int((observ.status=='blocked_unsat').sum())} 条 blocked_unsat。所有 {len(replay)} 个正向见证均通过独立三值逻辑回放，至少一个双方都已定义的观察端确实不同；其他端点的 X 不作为传播证据。
- 负例 injepsilon/ys_abc 的 TrojanETM1.Y：局部功能关系存在，但到所选 PO/DFF.D 观察端被阻断。局部功能成立不等于下游可观测。

语义边界：局部查询为 seq1 任意初态，沿用旧库单元映射及其异步复位近似；下游验证共享 PI 与任意寄存器状态，仅干预目标信号。**没有证明复位可达性、合法协议约束或自然控制变化与输出变化的同一条联合见证**。这些仍为待办。

见 two_case_relations.csv、two_case_queries.csv、two_case_observability.csv、witness_replay.csv 及对应 .ys/.sat.log/.witness.json。

## 3. 覆盖率：分开统计各层

以下是不同来源的节点集合，不是逐层必然递减的一条漏斗。positive 指图标签 1，可信正例另有字段；训练仍使用 trust mask。非零支撑不是“已证明功能覆盖率”，例如 proved_sat=0 也可能是证据未映射。

{mdtable(funnel,['stage','nodes','fraction','positives','test_positives'])}

covered=33.34% 主要由 P1 对应层贡献；新增 case 列实际落点只有 43,402 节点（1.35%）。proved_sat 在测试正例上为 0，无法直接提供这些阳性节点的正向判定标记。

已验证 core7 七列及 covered 与旧版本逐列一致。build_p0clean4 --netmap 只重新聚合新增计数/判定块，不会自动重建继承的 core7/covered；提高其中一个块的映射率不能宣称整组功能覆盖已提高。

逐列、逐视图、逐宿主和逐综合流程统计见 column_coverage*.csv；完整性见 integrity_checks.csv。

## 4. 归一化问题

按训练当前规则，在 covered 的 1,073,732 个节点上拟合各列标准差，再裁剪至 ±10。以下为 CPU float64 复算的诊断值，极接近边界时可能与 GPU float32 有微小数值差异。

{mdtable(norm[norm.column.isin(['reach_po_log','reach_dff_log','n_mux_log','n_cone_log','n_dff_log','frac_proved_sat','frac_partial_sat'])],['column','covered_nonzero','clipped_covered','clipped_fraction_of_nonzero'])}

多列的非零值几乎全被裁剪，计数/比例的幅度信息可能退化成近似支撑掩码。后续应先固定语义和归一化协议，再评价判定列，而非立即扩大 SAT 搜索量。

## 5. 模型对照

同一测试节点、同一划分。原 CEC manifest 中训练 259、验证 65、测试 64 个已声明视图均为 PASS；这是读取既有证据，没有重新跑 CEC。全图 metadata 的 389 视图比划分多一个未纳入折的 s15850t100__a4ctlequiv_s0_d1_s42__keepcur__ys_abc，因此全图覆盖分母与实验视图分母不同。全标签沿用旧口径，未确认标签的阴性可能影响评估；trusted-only 是另一评价总体，不能与全标签 AP 横向比较。inj pooled 仅含木马视图，正常对照另报。

全标签：

{mdtable(allm,rawcols)}

仅可信标签：

{mdtable(trustm,rawcols)}

normal_FPR_at_val_threshold 的阈值只由验证集可信负例的 99% 分位确定，判定规则 score > threshold；没有用测试标签选阈值。它是本轮预先声明的诊断口径，不是沿用某个历史最佳阈值。节点预算 Recall 在并列分数处使用期望命中数，避免节点索引破坏并列。

B39 为 39 维；core7 为 47 维；safe_nomux 为 52 维；本轮 reach+covered 与 covered-only 均为 42 维，后者两列置零、同一 covered。两组新增模型维度、seed、预算和特征归一化规则相同。只跑 seed42，不报告统计显著性或跨宿主泛化结论。详见 model_summary.csv、model_view_metrics.csv、paired_view_deltas.csv、metrics_integrity.json。

注意：trusted-only 的 reach AP 低于 B39；在验证集可信负例 1% FPR 阈值处，reach 的正常对照误报率也高于 B39。不能只展示正向 pooled AP。训练脚本尾部的“65 个评测视图、64 个 CEC PASS”还包含一个 ORIG 参考行，并不代表这 64 个 TRANS 测试视图中有一个 CEC 失败。

## 6. 提速与回归验证

- build_p0clean4.py 已备份为 build_p0clean4.py.bak_20261025_audit。视图分组只建一次，供全部列与随机化变体复用；保持节点顺序和随机数调用顺序。
- 19 个变体在固定回归夹具上与旧版文件字节一致；真实全量 core_reach/covered_only 快速导出与历史数组逐元素一致。
- 真实 {bench['nodes']:,} 节点、{bench['views']} 视图，四列归一化从 {bench['legacy_normalization_s']:.4f}s 降至 {bench['fast_normalization_s']:.4f}s，约 {bench['normalization_speedup']:.1f} 倍；不应外推为整个训练也快这么多。
- --only core_reach,covered_only --suffix <新后缀> 可直接从继承的 core 导出，绕过 SAT 表、网名解析及其余 17 个变体；拒绝覆盖已有输出。
- 新 structural_reach_index.py 保留所有网别名，一次建立邻接索引，只把物理 DFF.D 当作 D 端点，并显式标记截断。六个小网表抽样包含构图开销的提速为 {reachbench.speedup.min():.1f}–{reachbench.speedup.max():.1f} 倍。
- 新旧 reach 结果有差异：旧实现会丢 PO 别名，也会把时钟/复位等触发器输入计作 D；新实现修正这两个语义问题。因此不能将新 reach 数字直接覆盖历史数字。
- 旧解析器的中间 unknown 错位风险已用故障样例复现。两例对应的 {len(legacy)} 份历史日志共 {int(legacy.logged_queries.sum())} 个查询，未解析查询 {int(legacy.unresolved_queries.sum())}，与 CSV 不匹配的保存结果 {int(legacy.saved_result_mismatches.sum())}；这批结果没有实际错位证据。见 legacy_query_alignment.csv。
- test_audit_20261025.py 已检查查询编号、真实模式邻居、别名、D 端点、BFS 截断、19 变体一致性及快速导出。独立见证回放另见 replay_observability_20261025.py。

## 7. 下一轮应做什么

1. 为决定性、割集影响、干预传播、复位可达性分别定义状态，禁止把 structural/partial/unknown 合并成 SAT proved。
2. 沿“原始关系→可靠信号对应→驱动节点→特征列→独立掩码”重建一套新版本，分别记录未查询、反驳、超时、映射歧义；保持这次的盲采样/机制审计边界。
3. 在不含 n_mux 的配置上固定缩放方法及掩码对照，先小规模验证三 seed；随后才扩展 cone/DFF 功能证据及 ys_aig/ys_nand 缺口。
4. 把新 SAT 证据真正加入模型后，再做 C/D/E、LOCO/LRO；当前审计不是这些实验的替代。

复现命令、输入摘要哈希和 GPU 配置见 manifest.json。训练日志 logs/audit_reach_20261025.log、logs/audit_covered3_20261025.log；结果目录为 results/*_fold_fghtl_AuditReachD42_20261025 和 results/*_fold_fghtl_AuditCovered3D42_20261025。历史结论文件保留；本报告作为追加审计证据。

耗时：reach 日志创建至最后输出约 {manifest['training_timing']['reach_log_creation_to_last_write_s']/60:.1f} 分钟；covered 训练脚本的 START/END 时间另见 manifest.training_timing（约 13.9 分钟）。两组均以 run_config.json 确认 cuda:0、42 维、100 epoch，峰值显存约 6.5 GB。CPU 覆盖扫描约 8–16 秒；优化后的四模型评测约 20 秒。以上是本机本轮记录，不是其他规模的运行时间保证。
'''
    DOC.write_text(text,encoding='utf-8')
    if a.register:
        index=ROOT/'10.15/99_共用资产/repro/index.csv'
        backup=index.with_name('index.csv.bak_20261025_sat_audit')
        if not backup.exists():
            shutil.copy2(index,backup)
        with index.open(encoding='utf-8-sig',newline='') as f:
            existing=list(csv.DictReader(f))
        ids={r['id'] for r in existing}
        entries=[('table','SAT_audit_20261025',str(OUT.relative_to(ROOT)), '', '', 'two-case query/observation audit; column coverage; matched reach controls'),
                 ('doc','SAT_audit_report_20261025',str(DOC.relative_to(ROOT)), '', '', 'versioned evidence and limitations'),
                 ('scores','SAT_audit_reach_s42_20261025','_devcfg/gnn_audit_reach_s42_20261025.npz','42','42d;100epoch;cuda','reach plus identical covered; one seed'),
                 ('scores','SAT_audit_covered3_s42_20261025','_devcfg/gnn_audit_covered3_s42_20261025.npz','42','42d;100epoch;cuda','matched two zero columns plus covered'),
                 ('config','SAT_audit_manifest_20261025',str((OUT/'manifest.json').relative_to(ROOT)),'42','','commands and input sha256')]
        with index.open('a',encoding='utf-8',newline='') as f:
            writer=csv.writer(f)
            for entry in entries:
                if entry[1] not in ids:
                    writer.writerow(entry)
    print(DOC)


if __name__=='__main__':
    main()
