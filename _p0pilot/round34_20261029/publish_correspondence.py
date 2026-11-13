"""Aggregate existing-pair prediction gaps; publish coverage and bounded P2-B decision."""
import sys,json,csv,hashlib,datetime,shutil
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[2];H=Path(__file__).resolve().parent;R32=ROOT/'_p0pilot/round32_20261029';R33=ROOT/'_p0pilot/round33_20261029'
TABLES=ROOT/'10.15/06_统一评测协议/N4_三向泛化/tables'
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
    evidence=json.loads((H/'evidence_audit.json').read_text());prediction=json.loads((H/'prediction_bindings.json').read_text());assert evidence['passed'] and prediction['passed']
    for path,digest in evidence['inputs'].items():assert sha(ROOT/path)==digest
    proof=pd.read_csv(H/'proof_bindings.csv')
    for row in proof.drop_duplicates(['folder','query_id']).itertuples():
        folder=ROOT/row.folder;assert sha(folder/'model.v')==row.model_sha and sha(folder/'run.log')==row.log_sha
        assert hashlib.sha256((folder/'run.ys').read_text(encoding='utf-8').encode()).hexdigest()==row.script_sha
    for binding in prediction['models']:
        assert sha(ROOT/binding['checkpoint'])==binding['checkpoint_sha']
        assert sha(ROOT/binding['validation_scores'])==binding['validation_scores_sha']
        assert sha(ROOT/binding['train_scores'])==binding['train_scores_sha']
        assert binding['state_and_BN_unchanged'] and not binding['optimizer_created'] and binding['backward_calls']==0
    d=pd.read_csv(H/'pair_prediction_differences.csv');assert np.isfinite(d[['source_score','partner_score','absolute_difference']]).all().all()
    pairs=json.loads((H/'frozen_pairs.json').read_text());coverage=pd.read_csv(TABLES/'sat_pair_round15/pair_coverage_40_round15.csv')
    assert len(coverage)==40 and sum(coverage.status=='paired_validated')==11
    coverage[coverage.status!='paired_validated'].to_csv(H/'unmatched_existing_candidates.csv',index=False,encoding='utf-8-sig')
    # Keep physical-Q/QN signal coordinates distinct; never invert a node-risk score.
    def key(row):
        a=(row.source_view,int(row.source_node),int(row.source_bit),row.source_pin)
        b=(row.partner_view,int(row.partner_node),int(row.partner_bit),row.partner_pin)
        return repr((row.context_id,tuple(sorted((a,b)))))
    d['signal_pair_key']=[key(r) for r in d.itertuples()]
    main=d[d.main_eligible].copy();assert len(main)==33 and set(main.source_label)=={0} and set(main.partner_label)=={0}
    assert not main.duplicated(['seed','signal_pair_key']).any()
    summaries=[]
    tiers=[('blind_target_point_proved',main),('blind_target_with_PO_D_proved',main[main.whole_observation_status=='proved']),
           ('boundary_attachment_diagnostic',d[d.cohort=='blind_boundary']),('privileged_mechanism_diagnostic',d[d.cohort=='privileged_mechanism'])]
    for tier,subset in tiers:
        for (seed,split),raw in subset.groupby(['seed','split']):
            x=raw.drop_duplicates('signal_pair_key');positive=(x.source_label==1)&(x.partner_label==1)&x.source_trusted&x.partner_trusted
            bothmiss=(x.source_score<x.threshold)&(x.partner_score<x.threshold)
            summaries.append(dict(tier=tier,seed=int(seed),split=split,raw_rows=len(raw),unique_signal_pairs=len(x),
                mae=float(x.absolute_difference.mean()),median_gap=float(x.absolute_difference.median()),max_gap=float(x.absolute_difference.max()),
                signed_mean=float(x.signed_difference.mean()),flip_rate=float(x.flip.mean()),
                positive_pairs=int(positive.sum()),negative_pairs=int(((x.source_label==0)&(x.partner_label==0)&x.source_trusted&x.partner_trusted).sum()),
                positive_both_missed=int((positive&bothmiss).sum()),test_pairs=0))
    metrics=pd.DataFrame(summaries);metrics.to_csv(H/'cross_impl_per_seed.csv',index=False,encoding='utf-8-sig')
    aggregate=metrics.groupby(['tier','split']).agg(seeds=('seed','size'),pairs_per_seed=('unique_signal_pairs','first'),mae_mean=('mae','mean'),mae_std=('mae','std'),flip_mean=('flip_rate','mean'),flip_std=('flip_rate','std')).reset_index()
    aggregate.to_csv(H/'cross_impl_summary.csv',index=False,encoding='utf-8-sig')
    # Main metric uses each proven target point once. Boundary/case diagnostics cannot inflate it.
    main.to_csv(H/'main_target_prediction_pairs.csv',index=False,encoding='utf-8-sig')
    exclusions=[dict(cohort=p['cohort'],relation_id=p['relation_id'],slot=p['slot'],split=p['split'],reason=p['exclusion_reason'],source_node=p['source']['node'],partner_node=p['partner']['node']) for p in pairs if not p['main_eligible']]
    pd.DataFrame(exclusions).to_csv(H/'excluded_from_main_metric.csv',index=False,encoding='utf-8-sig')
    protocol=dict(version='P2_A_B_frozen_correspondence_eval_round34',primary='mean absolute difference of positive-class node probabilities at proven target-output drivers; not logit or Boolean-signal difference',
        main_pairs_file=str((H/'frozen_pairs.json').relative_to(ROOT)),pairs_sha=sha(H/'frozen_pairs.json'),filter='main_eligible==true; deduplicate context plus two view/node/bit/pin endpoints',
        split_counts=dict(train=9,val=2,test=0),strict_observation_proved_counts=dict(train=9,val=1,test=0),
        role_scope='All blind target endpoints independently trusted negative under existing dataset; no new security-label certification or transfer',
        context='shared named unrestricted physical Q and same PI; no natural/reset reachability claim',
        flip='Apply each model validation-calibrated threshold to both endpoints; no inversion of risk probability for QN',
        training_pair_allowed=False,missing_test_metric=None,prohibited='Do not substitute train/val drift for test drift; do not average unmatched region members as point correspondences',
        input_contract_sha=sha(R32/'input_contract.json'),normalization_sha=sha(R32/'normalization.npz'),coverage_limit='11/40 existing blind relations, validation 2/14, training 9/26; no test candidates in this cohort')
    write(H/'correspondence_eval_contract.json',protocol)
    baseline=pd.read_csv(R33/'fg_htl_ablation_v2_P2A.csv')
    for seed in (42,1,2):
        mask=baseline.seed==seed
        for split in ('train','val'):
            row=metrics[(metrics.tier=='blind_target_point_proved')&(metrics.seed==seed)&(metrics.split==split)].iloc[0]
            baseline.loc[mask,f'cross_impl_{split}_target_mae']=row.mae
            baseline.loc[mask,f'cross_impl_{split}_target_flip']=row.flip_rate
            baseline.loc[mask,f'cross_impl_{split}_target_pairs']=row.unique_signal_pairs
        baseline.loc[mask,'cross_impl_test_target_pairs']=0
        baseline.loc[mask,'cross_impl_test_reason']='No source-bound reliable heldout correspondence in existing frozen cohort'
        baseline.loc[mask,'status']='training/detection complete; bounded train/val correspondence report complete; test correspondence absent'
    baseline.to_csv(H/'fg_htl_ablation_v2_P2A_with_correspondence.csv',index=False,encoding='utf-8-sig')
    now=datetime.datetime.now().astimezone().isoformat()
    decision=dict(time=now,P2_A_training_detection_complete=True,P2_A_existing_evidence_correspondence_report_complete=True,
        P2_A_full_heldout_correspondence_validation_complete=False,ready_for_P2_B=True,P2_B_started=False,
        reason='Architecture-only B comparison does not require new correspondence or SAT; use the same frozen small cohort with honest coverage reporting.',
        B_contract=dict(input='39dim v2 and exactly same graph/split/trust/normalization as A',model='dual branch split29: first29 gate/local and last10 topology including existing SCC; no primitive swap',
            seeds=[42,1,2],updates=100,validation_every=5,loss='same mode2 ASL+1.4 soft miss; consistency/region/SAT/pair=0 for architecture isolation',
            selection='same validation trusted-injection macro AP',metrics='same detection scopes plus frozen correspondence contract; test gap stays NA if evidence remains absent',
            capacity='record parameter counts; do not attribute added capacity to branch separation alone'),
        new_training_runs=0,new_SAT_queries=0,frozen_checkpoint_inferences=3,existing_validation_predictions_reused=3)
    write(H/'P2_A_status_and_P2_B_decision.json',decision)
    val=aggregate[(aggregate.tier=='blind_target_point_proved')&(aggregate.split=='val')].iloc[0]
    train=aggregate[(aggregate.tier=='blind_target_point_proved')&(aggregate.split=='train')].iloc[0]
    strict=aggregate[(aggregate.tier=='blind_target_with_PO_D_proved')&(aggregate.split=='val')].iloc[0]
    metriclines=['|seed|训练9对MAE|验证2对MAE|验证翻转率|','|---|---:|---:|---:|']
    for seed in (42,1,2):
        tr=metrics[(metrics.tier=='blind_target_point_proved')&(metrics.seed==seed)&(metrics.split=='train')].iloc[0]
        va=metrics[(metrics.tier=='blind_target_point_proved')&(metrics.seed==seed)&(metrics.split=='val')].iloc[0]
        metriclines.append(f'|{seed}|{tr.mae:.6f}|{va.mae:.6f}|{va.flip_rate:.1%}|')
    text=f'''# 第三十四轮：P2-A可靠对应预测差异与P2-B准入

完成时间：{now}。训练0、SAT0。复用3份验证预测，仅为缺失训练侧分数执行3个已保存P2-A模型的eval/no_grad前向；无optimizer、无backward，参数和BatchNorm状态指纹前后一致，checkpoint及原预测哈希未变。

## 证据与口径

复用第10/11轮11条完整关系及第15轮110个精确坐标，重核55个槽位配对；另核8条第8/9轮特权机制角色配对。63条引用对应60个不同的既有证明查询；model/script/log SHA、query参数、proved且非timeout的原日志块全部核对，模型从各自原始raw在内存中重新生成并与已有模型对应。复用的证明可能来自另一关系的不同槽号，按实际被证明的两侧物理bit核对，不按相同slot编号盲用。

主指标只取11个target输出驱动节点对：训练9、验证2、测试0；22个唯一物理落点（训练18/验证4），全部为两侧独立可信正常标签。角色标签来自既有监督，不从SAT等价复制。cut、PI、DFF Q/QN和区域内部成员不混入target主指标；Q/QN保持不同bit，不对分类风险做1-p反相。signal/cell embedding等价和训练配对资格仍为false。

差异MAE=mean(|p_source-p_partner|)，p为节点木马类概率，逐唯一信号点对等权；每seed先汇总，再跨seed给样本标准差。翻转率使用每模型原验证阈值判断两侧分类是否不同；不是信号翻转率。

## P2-A结果

{chr(10).join(metriclines)}

训练MAE三种子均值±标准差：{train.mae_mean:.6f} ± {train.mae_std:.6f}。验证：{val.mae_mean:.6f} ± {val.mae_std:.6f}。验证翻转率均为0，但两对全是正常目标、两侧分数均低于阈值；不能据此证明木马检出稳定，甚至不能用0翻转代替概率不变。

其中injzeta验证target等价有直接proved，但既有全PO/D检查为unknown；不把unknown升级为全设计等价。更严格地同时要求PO/D整体proved时，验证仅1对，MAE均值±标准差为{strict.mae_mean:.6f} ± {strict.mae_std:.6f}。两层口径都保留，不能混写分母。

8条privileged机制配对只作训练案例诊断，含6对可信木马角色和2对正常角色，独立输出cohort；它们依照插入案例选取，不混进盲提取主指标，不据此推断测试木马稳定性。具体分数、翻转及木马两侧同时漏检数见cross_impl_per_seed.csv，低漂移可能同时对应错误分类。

## 覆盖与缺失

40条既有盲候选中仅11条完成局部边界对应（27.5%）：训练9/26、验证2/14。本轮没有扩大候选集。29条未对应逐项保留，状态为临时别名未证、映射不完整、局部别名缺失或边界未证；没有用旧P1 proved、同名、相同签名或区域平均补数。

测试划分没有本合同下的可靠配对，cross_implementation_difference(test)=NA，绝不填0，也不把验证0.0908左右的差异填进测试列。当前11条关系和8条机制配对都不是全图覆盖，不能报告为全体等价实现稳定性。所有功能证明只涉及指定共享PI/物理Q组合上下文，不包含自然触发、复位可达性或完整时序证明。

## 完成情况与P2-B

P2-A三种子训练、常规检测主表以及“已有可靠对应范围内”的预测差异报告已完成。全测试划分上的跨实现稳定性验收仍缺证据，不把整个P2-A或P2工作无条件标成全完成。

可以进入P2-B受控架构对照：保持39维v2、同图/划分/可信监督/归一化/损失/100次更新/seed42、1、2/每5次验证不变，仅改双分支（前29维与后10维），本轮不启动。为隔离架构作用，不直接照搬旧mode4的一致性项；区域监督也应单列后续消融。B的跨实现指标继续使用本轮冻结的配对和限制，测试配对不足属于共享评测覆盖缺口，无需为启动B强造对应或追加SAT。不能直接把旧B成绩拼入新版A主表，也不能以此认定C/D/E已就绪。

## 交付

proof_bindings.csv、evidence_audit.json、frozen_pairs.json、prediction_bindings.json；pair_prediction_differences.csv、main_target_prediction_pairs.csv、cross_impl_per_seed.csv、cross_impl_summary.csv；unmatched_existing_candidates.csv、excluded_from_main_metric.csv；correspondence_eval_contract.json；fg_htl_ablation_v2_P2A_with_correspondence.csv；P2_A_status_and_P2_B_decision.json。第三十二/三十三轮产物保留，未改训练/SAT入口，SAT保持暂停。
'''
    report=H/'第三十四轮_P2A可靠对应预测差异与P2B准入.md';report.write_text(text,encoding='utf-8')
    target=TABLES/'p2a_v2_round34';target.mkdir(exist_ok=True)
    for filename in ('cross_impl_per_seed.csv','cross_impl_summary.csv','main_target_prediction_pairs.csv','unmatched_existing_candidates.csv','correspondence_eval_contract.json','fg_htl_ablation_v2_P2A_with_correspondence.csv','P2_A_status_and_P2_B_decision.json',report.name):shutil.copy2(H/filename,target/filename)
    marker='第三十四轮：P2-A可靠对应预测差异与P2-B准入'
    for name in ('SAT作用证明.md','SAT工作总结.md'):
        p=ROOT/'10.15/00_说明'/name
        if marker not in p.read_text(encoding='utf-8'):
            with p.open('a',encoding='utf-8') as f:f.write('\n\n'+text.replace('# 第三十四轮','### 第三十四轮',1))
    registry=ROOT/'10.15/99_共用资产/运行登记/运行登记表.csv'
    if marker not in registry.read_text(encoding='utf-8'):
        with registry.open('a',encoding='utf-8',newline='') as f:csv.writer(f).writerow([now,marker,'audit_correspondence.py; collect_predictions.py; publish_correspondence.py','ginvenv_gpu eval/no_grad only','42/1/2','frozen existing 11 blind +8 mechanism pairs','target-only main; risk probabilities; train/val/test separated',str(H.relative_to(ROOT)),f'val2 target MAE {val.mae_mean:.6f}+-{val.mae_std:.6f}; test0pairs','已有证据评估完成；可进入B；测试对应仍缺','0 training/0 SAT; 3 existing val reused;3 frozen train forwards'])
    write(H/'COMPLETE.json',dict(time=now,completed_existing_evidence_scope=True,new_training=0,new_SAT=0,ready_for_P2_B=True,test_correspondence_complete=False,report_sha=sha(report)))
    print(text)
if __name__=='__main__':main()
