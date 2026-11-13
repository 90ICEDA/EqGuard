"""Publish a completed round and synchronize both user-requested living notes."""
from __future__ import annotations
import csv
import hashlib
import json
import shutil
from datetime import datetime,timezone,timedelta
from pathlib import Path
import pandas as pd
from build_sparse_sat_round1 import ROOT,PT,OUT


def table(d,cols):
    rows=['| '+' | '.join(cols)+' |','|'+'|'.join('---' for _ in cols)+'|']
    for _,r in d.iterrows():
        vals=[f'{r[c]:.6f}' if isinstance(r[c],float) else str(r[c]) for c in cols]
        rows.append('| '+' | '.join(vals)+' |')
    return '\n'.join(rows)


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):
            h.update(block)
    return h.hexdigest()


def main():
    now=datetime.now(timezone(timedelta(hours=8)))
    runs=json.loads((OUT/'training_runs.json').read_text(encoding='utf-8'))
    assert len(runs)==4 and all(r['exit_code']==0 for r in runs)
    configs={}
    selection=[]
    for r in runs:
        cfg=ROOT/f'results/hosts_bt31_seed42mode4_allb1_fold_fghtl_SparseR1_{r["name"]}_s42/run_config.json'
        c=json.loads(cfg.read_text())
        assert c['device']=='cuda:0' and c['seed']==42 and c['epochs']==100 and c['in_channels']==47
        configs[r['name']]=c
        history=pd.read_csv(cfg.parent/'train_log.csv')
        selection.append(dict(model=r['name'],selected_epoch_1based=int(history.best_epoch.iloc[-1])+1,
                              best_validation_AP=float(history.best_val_AP.iloc[-1]),elapsed_s=r['elapsed_s']))
    pd.DataFrame(selection).to_csv(OUT/'checkpoint_selection.csv',index=False,encoding='utf-8-sig')
    metrics=pd.read_csv(OUT/'model_summary.csv')
    assert set(['real_bounded','perm_bounded','zero_bounded','real_legacy']).issubset(set(metrics.model))
    matched=pd.read_csv(OUT/'matched_comparison_summary.csv')
    norm=pd.read_csv(OUT/'normalization_comparison.csv')
    features=json.loads((OUT/'feature_manifest.json').read_text(encoding='utf-8'))
    qualification=pd.read_csv(OUT/'log_qualification.csv')
    exposure=pd.read_csv(OUT/'directed_receptive_field.csv')
    assert norm.bounded_clipped.sum()==0
    integrity=json.loads((OUT/'metrics_integrity.json').read_text())
    assert all(integrity['test_node_identity_vs_B'].values())
    frozen_check=json.loads((OUT/'frozen_baseline_integrity.json').read_text())
    frozen_repeat=json.loads((OUT/'frozen_repeat_integrity.json').read_text())
    assert frozen_check['deterministic_inference'] and frozen_repeat['max_diff']==0
    assert set(['frozen_real','frozen_perm','frozen_zero']).issubset(set(metrics.model))
    satcontrast=matched[matched.comparison=='semantic_vs_permuted'].set_index('scope')
    da=float(satcontrast.loc['all_labels','mean_delta_AP'])
    dt=float(satcontrast.loc['trusted_only','mean_delta_AP'])
    frozen_contrast=matched[matched.comparison=='frozen_semantic_vs_permuted'].set_index('scope')
    fda=float(frozen_contrast.loc['all_labels','mean_delta_AP'])
    fdt=float(frozen_contrast.loc['trusted_only','mean_delta_AP'])
    if da>0 and dt>0:
        if fda>0 and fdt>0:
            verdict='真实条件 SAT 内容相对同覆盖位置的置换对照，在本 seed 的训练对照和固定权重检查中均有正向 AP 差异；仅构成有限证据，不能宣称三 seed 稳健性或完整 FG-HTL 有效。'
        else:
            verdict='训练对照在本 seed 的两个评价总体有正向 AP 差异，但固定权重检查未在两个总体同时支持真实 SAT 内容优于置换值，因此仍不能将训练差异明确归因于 SAT 语义。'
    elif da<=0 and dt<=0:
        verdict='本 seed 未在两个评价总体观察到真实条件 SAT 内容相对置换对照的 AP 增益；不能由此推断 SAT 方法无效，当前语义和正例邻域覆盖仍受限。'
    else:
        verdict='真实条件 SAT 内容与置换对照的比较在全标签、可信标签总体上方向不一致，当前不能作明确的 SAT 内容增益结论。'
    commands={
        'build':'ginvenv/Scripts/python.exe -X utf8 -u _p0pilot/build_sparse_sat_round1.py',
        'tests':'ginvenv/Scripts/python.exe -X utf8 _p0pilot/test_sparse_sat_round1.py',
        'exposure':'ginvenv/Scripts/python.exe -X utf8 _p0pilot/sparse_sat_receptive_field.py',
        'smoke':'ginvenv/Scripts/python.exe -X utf8 -u _p0pilot/run_sparse_sat_round1.py --smoke',
        'training':'ginvenv/Scripts/python.exe -X utf8 -u _p0pilot/run_sparse_sat_round1.py',
        'evaluate':'ginvenv/Scripts/python.exe -X utf8 -u _p0pilot/evaluate_sparse_sat_round1.py',
        'frozen':'ginvenv_gpu/Scripts/python.exe -X utf8 -u _p0pilot/frozen_sparse_sat_round1.py',
        'publish':'ginvenv/Scripts/python.exe -X utf8 _p0pilot/publish_sparse_sat_round1.py',
    }
    manifest=dict(updated=now.isoformat(),complete=True,configs=configs,training=runs,commands=commands,
                  feature_definition=features,feature_sha256={k:digest(PT/f'satrel_node_feats_sparseR1_{k}.npy') for k in ['real','permuted','zero']},
                  train_script_backup='train_test2.3.py.bak_20261025_bounded',
                  no_new_sat_queries=True,verdict=verdict,frozen_baseline_check=frozen_check)
    (OUT/'round_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    cols=['model','viewmean_AP','viewmean_recall_1pct','viewmean_recall_5pct','inj_percentile_pooled_AP','normal_FPR_at_val_threshold']
    allm=metrics[(metrics.scope=='all_labels') & ~metrics.model.str.startswith('frozen_')]
    trustm=metrics[(metrics.scope=='trusted_only') & ~metrics.model.str.startswith('frozen_')]
    frozenm=metrics[(metrics.scope=='all_labels') & metrics.model.str.startswith('frozen_')]
    report=f'''# 稀疏 SAT 归一化与条件功能证据对照（2026-10-25）

更新时间：{now.strftime('%Y-%m-%d %H:%M:%S')}（Asia/Shanghai）。本轮完成。

## 结论

{verdict}

**已解决的数值问题**：新增 --norm-extra bounded，在确认 extra 全部有限且处于 [0,1] 后保留自然尺度，零值与覆盖标记保持原样，不再以全 covered 集合的标准差放大稀疏列。基础 39 维仍按原协议 z-score，默认 covered 行为不变；旧实验可复现。四个新训练组均为 47 维，GIN 双分支/同 seed42/100 epoch/相同划分及预算，训练均使用 ginvenv_gpu 和 cuda:0 串行完成。未进行新 SAT 搜索。

## 1. 什么证据进入了模型

只使用已有 cone/DFF 的 SAT 查询，排除门类型直接赋值、MUX 库存、P1 对应计数。每个全 1/全 0 条件的目标 0/1 查询必须按顺序核对日志；只有 proved/refuted 配对才给出“该可满足条件下目标被强制为某值”的证据。双方 proved 的空真条件不作有效功能值。没有把两个模式测试冒充完整割集决定性。

{len(qualification)} 份相关源日志中，{int(qualification.accepted.sum())} 份与 CSV 逐项对齐；其余 {int((~qualification.accepted).sum())} 份当前日志长度不匹配，已排除。这只能说明当前证据不可追溯，不能证明 CSV 历史结果当年必错。合格关系 {features['qualified_relations']} 条，匹配 {features['matched_nodes']} 个图节点。源视图以外只允许网表文件字节完全相同的视图接收证据；不按同名直接跨 keep 变体传播。接受的源文件及 raw JSON 时间戳均不晚于对应 SAT 日志。

特征为：结构 reach 两列 + 四列条件 SAT 事实（forced_pattern_fraction、feasible_pattern_fraction、tested_joint_change_ratio、forced_one_fraction）+ evaluated_case + covered。SAT 事实附到真实目标驱动单元，DFF-next 关系另附到接收 DFF。未知不等于功能不存在，evaluated_case 单独保留。每组的 reach/两个覆盖标记逐元素相同。

语义边界仍为 seq1 任意初态及原库映射的复位近似；没有新增复位可达性或联合自然触发传播证明。条件变化中可以有多个割集输入共同变化，因此 tested_joint_change 不称为单一控制信号因果影响。

## 2. 缩放修复的证据

{table(norm,['column','nonzero','legacy_clipped','bounded_clipped','legacy_unique_nonzero','bounded_unique_nonzero'])}

旧版用约 107 万个 covered 节点统计标准差，致使部分少量非零列几乎全部落在 ±10 裁剪上限；例如 forced_one_fraction 的不同幅度被压成同一个值。bounded 模式无此裁剪，原有不同数值保留。此处是 CPU float64 诊断；GPU float32 极边界可能有微小数值差异。修复的是数值表示，不能自动等同于提升模型 AP。

## 3. 对照设计与结果

real_bounded：真实条件 SAT，修复缩放；perm_bounded：在各视图同一 evaluated_case 节点集合内联合置换四列，保持联合值分布、维度及覆盖不变；zero_bounded：四列置零，其余完全相同；real_legacy：相同真实特征使用旧 covered z-score/±10 裁剪。置换实际改变 {features['permutation_changed_rows']} 个节点，其余节点四列相同。

全标签，沿用历史比较总体（未知标签阴性会影响该口径）：

{table(allm,cols)}

仅可信标签，作为独立评价总体（不能与全标签 AP 横比）：

{table(trustm,cols)}

配对逐视图差异：

{table(matched,['comparison','scope','mean_delta_AP','median_delta_AP','AP_wins','AP_losses','AP_ties'])}

验证集选中的 checkpoint（总训练预算均为 100 epoch）：

{table(pd.DataFrame(selection),['model','selected_epoch_1based','best_validation_AP','elapsed_s'])}

逐视图 AP 为主；视图内 tie-aware 百分位 pooled AP 是补充，只含 inj 视图。正常误报阈值由验证集可信负例 99% 分位确定，score > threshold；测试标签不用于阈值选择。所有分数 dump 的测试节点与 B39 完全一致。B39 是不同维度的历史参考，SAT 内容归因主要看相同 47 维的 real_bounded vs perm_bounded；real vs zero 还包含冗余覆盖幅度/训练动力学差异，不能单独证明语义。

固定 real_bounded 的训练权重，仅在推理阶段更换 SAT 四列：

{table(frozenm,cols)}

该检查统一使用 softmax(class=1) 概率，未使用旧 perm_importance.py 的原始 class-1 logit 排序。固定权重三个变体也共享 frozen_real 在验证集确定的阈值，不针对置换/移除后的输入重新校准。最初发现非确定性 GPU scatter 重复执行自身就有约 4e-6 的平均概率差、个别节点超过 0.015，因此最终使用 torch.use_deterministic_algorithms(True) 与 CUBLAS_WORKSPACE_CONFIG=:4096:8；同一输入重复推理最大差为 {frozen_repeat['max_diff']:.8f}，完全一致。该确定性基线与训练期间的非确定性 dump 最大概率差为 {frozen_check['max_absolute_probability_diff_vs_training_dump']:.8f}，平均差为 {frozen_check['mean_absolute_probability_diff']:.8f}；不将这个跨执行模式差异当成 SAT 作用。只在同一确定性固定权重推理的 real/perm/zero 之间比较内容依赖。原训练 seed42 不保证 GPU scatter 位级确定性，这也是微小训练差异不能直接作语义结论的原因。

## 4. 覆盖与可解释范围

{table(exposure,['scenario','hops','test_exposed_nodes','test_positive_exposed','test_positives'])}

测试正例 243 个，条件 SAT 特征直接命中 0 个；沿本图消息传递方向两跳仅可触达 3 个正例。真实/置换特征变化的两跳邻域未触达测试正例。因而 real vs perm 的效果主要能反映正常节点排序变化及训练所得参数变化，不能解释成“已恢复广泛触发/载荷定位”。BatchNorm/共享训练权重也可能影响最终全图输出。提取代码没有使用木马标签或 Trojan 命名筛选候选；测试标签只用于报告覆盖。后续应先在训练/验证集制定并冻结盲提取策略，再报告测试覆盖，不得依据测试正例位置挑选候选。

## 5. 实现、验证与运行时间

- train_test2.3.py 修改前已备份。bounded 仅为 opt-in，旧 covered/none 计算路径未改；配置现在记录 norm-extra、feature 文件、norm-fit 等关键参数。
- 固定查询配对测试覆盖空真、非决定性、确实可满足且被强制两值的情况；同维度/相同掩码/视图内联合置换分布、零对照、数值范围和裁剪均已验证。
- GPU 冒烟 2 epoch 通过，峰值约 6.6 GB。四个正式 run 均为 100 epoch、seed42、cuda:0；总训练墙钟 {sum(r['elapsed_s'] for r in runs)/60:.1f} 分钟。每组命令、日志、时间与配置见 round_manifest.json；训练顺序固定，未根据测试结果挑选配置。
- 构建复用日志用时 {features['elapsed_s']:.1f} 秒，没有调用 SAT 求解器。沿用上一轮的分组向量化评测，避免逐视图扫描全部字符串。

## 6. 下一步

先保留本轮全部正负结果，按“内容对照、数值对照、覆盖限制”分别解释。若要检验更强的 SAT 关系，需要在有限候选内补足非局部条件传播/合法状态语义和测试正例邻域覆盖，再做多 seed；不能靠增加 MUX/gate 配额或放大覆盖标记来替代。本轮不启动这些扩展。

本报告及 model_summary.csv、matched_view_deltas.csv、feature_coverage.csv、normalization_comparison.csv、log_qualification.csv、directed_receptive_field.csv、round_manifest.json 构成本轮证据。后续每完成一轮，必须同步更新 SAT作用证明.md 和 SAT工作总结.md，记录配置、正负结果、证据、局限和下一步。
'''
    path=ROOT/'10.15/00_说明/稀疏SAT归一化对照_20261025.md'
    path.write_text(report,encoding='utf-8')
    summary=f'''## 11. 2026-10-25：稀疏 SAT 归一化修复与条件功能证据对照

更新时间：{now.strftime('%Y-%m-%d %H:%M:%S')}，本轮完成。后续每完成一轮任务，均同步更新本文件与另一份 SAT 说明，包含配置、结果、证据、局限和下一步（用户要求）。

{verdict}

- 数值修复：--norm-extra bounded 保留已处于 [0,1] 的额外列，基础 39 维标准化不变；稀疏 SAT 列裁剪数降为 0。旧 covered 路径保留，训练脚本已备份。
- 真实内容来自日志核验后的 cone/DFF 两模式条件 SAT 事实，不含门类型重标注、MUX 计数及 P1；不冒充完整决定性或复位可达性证明。270 份日志可核验、71 份当前日志不完整而排除；4,809 个节点落点。
- real / perm / zero / legacy 四组同为 47 维、seed42、100 epoch，使用 ginvenv_gpu、cuda:0 串行训练。结构 reach、evaluated_case、covered 相同，置换仅在候选集合内改变 SAT 四列的联合落点。

{table(allm,cols)}

可信标签与正常误报、逐视图配对结果均保留在详细报告。不能只选择 pooled 的正向结果。

- 覆盖限制：SAT 特征直接覆盖测试正例 0/243；两跳仅触达 3/243。真实/置换变化的两跳邻域未触达测试正例，因此不能外推到完整木马功能定位。
- 上一轮结构审计还已确认：结构 reach+covered 相对同维度 covered-only 的逐视图 AP 为 0.16325 vs 0.10991；这是结构特征作用，不是“SAT 真实增益”。
- 本节修正历史强口径：core7 含结构/P1，不能整体归因 SAT；“判定列零信息/纯优化伪影”需由修复后的内容对照判定；逐视图 AP 按任务书保留为主，旧“全部作废”不再适用。
- 下一步：先按本轮内容/数值/覆盖三类证据决定有限补证方案，再多 seed；本轮没有扩大 SAT 搜索。

详细报告：[稀疏SAT归一化对照_20261025.md]({path.as_posix()})；数据目录：{OUT.as_posix()}；完整命令、运行时间和输入 SHA256：round_manifest.json。
'''
    marker='<!-- sparse_sat_round1:start -->'
    end='<!-- sparse_sat_round1:end -->'
    for name in ['SAT作用证明.md','SAT工作总结.md']:
        doc=ROOT/'10.15/00_说明'/name
        backup=doc.with_name(name+'.bak_20261025_sparseR1')
        if not backup.exists():
            shutil.copy2(doc,backup)
        body=doc.read_text(encoding='utf-8')
        if marker in body:
            before,tail=body.split(marker,1)
            _,after=tail.split(end,1)
            body=before+marker+'\n'+summary+'\n'+end+after
        else:
            body=body.rstrip()+'\n\n---\n\n'+marker+'\n'+summary+'\n'+end+'\n'
        banner=f'> 最新完成轮次（2026-10-25）：见文末 §11“稀疏 SAT 归一化修复与条件功能证据对照”；历史强归因及指标口径以该节修正为准。\n'
        if banner not in body:
            first,rest=body.split('\n',1)
            body=first+'\n\n'+banner+rest
        doc.write_text(body,encoding='utf-8')
    index=ROOT/'10.15/99_共用资产/repro/index.csv'
    backup=index.with_name('index.csv.bak_20261025_sparseR1')
    if not backup.exists():
        shutil.copy2(index,backup)
    with index.open(encoding='utf-8-sig',newline='') as f:
        ids={r['id'] for r in csv.DictReader(f)}
    entries=[('table','sparseR1_tables',str(OUT.relative_to(ROOT)),'42','47d','bounded normalization and conditional SAT content controls'),
             ('doc','sparseR1_report',str(path.relative_to(ROOT)),'42','','completed round; synchronized living notes')]
    for r in runs:
        entries.append(('scores','sparseR1_'+r['name'],r['dump'],'42','47d;100epoch;cuda',r['name']))
    for name in ['real','perm','zero']:
        entries.append(('scores','sparseR1_frozen_'+name,f'_devcfg/gnn_sparseR1_frozen_{name}_s42.npz',
                        '42','47d;fixed_weights;cuda','same model with SAT content intervention'))
    with index.open('a',encoding='utf-8',newline='') as f:
        writer=csv.writer(f)
        for row in entries:
            if row[1] not in ids:
                writer.writerow(row)
    print(path,flush=True)
    print(verdict,flush=True)


if __name__=='__main__':
    main()
