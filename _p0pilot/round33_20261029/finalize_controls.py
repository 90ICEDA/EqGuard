"""Audit saved artifacts, aggregate seeds, and append Chinese research notes."""
import sys,json,csv,hashlib,datetime,shutil
from pathlib import Path
import numpy as np
import pandas as pd
import torch
from sklearn.metrics import average_precision_score,roc_auc_score
ROOT=Path(__file__).resolve().parents[2];H=Path(__file__).resolve().parent;PRE=ROOT/'_p0pilot/round32_20261029'
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
    assert json.loads((H/'TRAINING_COMPLETE.json').read_text())['new_training_runs']==6
    request=json.loads((H/'request.json').read_text());allres=json.loads((H/'comparisons.json').read_text())
    assert sha(PRE/'comparison.json')==request['previous_seed42_comparison_sha']
    v2=json.loads((PRE/'input_contract.json').read_text());fixed=json.loads((H/'fixed_contract.json').read_text());old=json.loads((H/'old_graph_contract.json').read_text())
    for contract in (v2,fixed,old):
        for path,digest in contract['files'].items():assert sha(ROOT/path)==digest
    physical_checks={}
    for key,conf in v2['shared_inputs'].items():
        v={n:np.load(ROOT/conf['folder']/(n+'.npy'),mmap_mode='r') for n in ('x39','edge_index','y','trusted','physical')}
        f={n:np.load(ROOT/fixed['shared_inputs'][key]['folder']/(n+'.npy'),mmap_mode='r') for n in ('x39','edge_index','y','trusted','physical')}
        o={n:np.load(ROOT/old['shared_inputs'][key]['folder']/(n+'.npy'),mmap_mode='r') for n in ('x39','edge_index','y','trusted','physical')}
        for n in ('edge_index','y','trusted','physical'):assert np.array_equal(v[n],f[n])
        assert np.array_equal(v['y'][v['physical']],o['y']) and np.array_equal(v['trusted'][v['physical']],o['trusted'])
        assert np.array_equal(f['x39'][f['physical']],o['x39'])
        assert not v['trusted'][~v['physical']].any()
        physical_checks[key]=dict(labels_and_trust_identical=True,fixed_topology_identical=True,old_features_identical_between_controls=True,changed_physical_features=int(np.any(v['x39'][v['physical']]!=o['x39'],axis=1).sum()))
    runrecords=[];summaries=[];maxdiff=0;training_audits=[];runtime=0
    entries=[]
    for case,data in allres.items():
        seed=42 if '42' in case else int(case[-1]);contract=fixed if case.startswith('old_features') else old if case.startswith('old_graph') else v2
        folder=PRE if case=='v2_seed42_reused' else H/case
        for arm,result in data.items():entries.append((case,seed,contract,folder,arm,result))
    for case,seed,contract,folder,arm,result in entries:
        out=folder/'runs'/arm
        ck=torch.load(out/'checkpoint_100.pt',map_location='cpu',weights_only=False)
        steps=sorted(set(int(s['step']) for s in ck['optimizer']['state'].values()));assert steps==[100]
        records=ck['records'];assert len(records)==100 and [r['updates'] for r in records]==list(range(1,101))
        assert all(np.isfinite(r['loss']) and np.isfinite(r['gradient_norm']) and r['finite'] for r in records)
        if folder!=PRE:
            pd.DataFrame([{k:v for k,v in r.items() if k!='validation'}|{'validation_ap':r.get('validation',{}).get('trusted',{}).get('ap')} for r in records]).to_csv(out/'train_log.csv',index=False,encoding='utf-8-sig')
        init=torch.load(out/'initial.pt',map_location='cpu',weights_only=True)
        common=torch.load(folder/'common_init.pt',map_location='cpu',weights_only=True)
        assert all(torch.equal(t,common[k]) for k,t in init.items() if t.shape==common[k].shape)
        selected=json.loads((out/'SELECTED.json').read_text());assert sha(out/'config.json')==selected['config_sha']
        audit=dict(case=case,arm=arm,seed=seed,optimizer_steps=steps,epochs=100,parameters=sum(t.numel() for k,t in init.items() if 'running_' not in k and 'num_batches' not in k),nonfinite=0,selected_epoch=selected['epoch'],init_sha=sha(out/'initial.pt'),train_log_sha=sha(out/'train_log.json'),model_sha=sha(ROOT/selected['path']),input_version=contract['version'])
        training_audits.append(audit)
        label=('old39_fixed_v2_graph' if case.startswith('old_features') else 'old39_old_graph' if case.startswith('old_graph') else 'v2_39' if arm=='base39' else 'primitive21')
        for key in ('trans_val','trans_test'):
            base=ROOT/contract['shared_inputs'][key]['folder'];scores=np.load(out/(key+'_scores.npy'));y=np.load(base/'y.npy',mmap_mode='r');trust=np.load(base/'trusted.npy',mmap_mode='r');physical=np.load(base/'physical.npy',mmap_mode='r')
            saved=pd.read_csv(out/(key+'_per_view.csv'))
            for scope,mask in [('trusted',trust),('legacy',physical)]:
                expected_aps=[]
                for view in contract['shared_inputs'][key]['views']:
                    lo,hi=view['start'],view['stop'];m=mask[lo:hi];yy=y[lo:hi][m];ss=scores[lo:hi][m];record=saved[(saved.view==view['view'])&(saved.scope==scope)].iloc[0]
                    if yy.sum():
                        ap=average_precision_score(yy,ss);diff=abs(ap-record.ap);maxdiff=max(maxdiff,diff);assert diff<1e-12
                        if '__inj' in view['view']:expected_aps.append(ap)
                    assert len(yy)==record.n and int(yy.sum())==record.positive
                assert abs(np.mean(expected_aps)-result[key][scope]['ap'])<1e-12
                summaries.append(dict(case=case,encoding=label,seed=seed,split=key,scope=scope,best_epoch=selected['epoch'],**result[key][scope],cross_implementation_difference=np.nan,functional_relation_coverage=np.nan))
        runrecords.append(dict(case=case,encoding=label,seed=seed,run=str(out.relative_to(ROOT)),reused=folder==PRE,updates=100,model_sha=audit['model_sha']))
        del ck,init,common
    # Seed42 full39 initial parameters must be identical in the two added controls and the reused v2 fit.
    reference=torch.load(PRE/'runs/base39/initial.pt',map_location='cpu',weights_only=True)
    for case in ('old_features_fixed_v2_seed42','old_graph_old_features_seed42'):
        init=torch.load(H/case/'runs/base39/initial.pt',map_location='cpu',weights_only=True)
        assert all(torch.equal(t,reference[k]) for k,t in init.items())
    table=pd.DataFrame(summaries);table.to_csv(H/'per_seed_metrics.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(runrecords).to_csv(H/'run_manifest.csv',index=False,encoding='utf-8-sig')
    group=table[table.encoding.isin(['v2_39','primitive21'])]
    agg=group.groupby(['encoding','split','scope']).agg(n=('seed','size'),ap_mean=('ap','mean'),ap_std=('ap','std'),auc_mean=('auc','mean'),auc_std=('auc','std'),r1_mean=('r1','mean'),r1_std=('r1','std'),r5_mean=('r5','mean'),r5_std=('r5','std'),control_fpr_mean=('control_fpr','mean'),control_fpr_std=('control_fpr','std')).reset_index()
    assert set(agg.n)=={3};agg.to_csv(H/'three_seed_summary.csv',index=False,encoding='utf-8-sig')
    pairs=group.pivot(index=['seed','split','scope'],columns='encoding',values='ap').reset_index();pairs['delta_primitive_minus_v2']=pairs.primitive21-pairs.v2_39;pairs.to_csv(H/'paired_seed_deltas.csv',index=False,encoding='utf-8-sig')
    package=table[table.seed==42].copy();package.to_csv(H/'seed42_old_v2_controls.csv',index=False,encoding='utf-8-sig')
    # Unified P2-A artifact keeps unavailable correspondence metrics explicit.
    formal=table[(table.encoding=='v2_39')&(table.split=='trans_test')].copy();formal['variant']='A_v2_single';formal['status']='training_and_detection_metrics_complete; correspondence_metric_pending';formal.to_csv(H/'fg_htl_ablation_v2_P2A.csv',index=False,encoding='utf-8-sig')
    now=datetime.datetime.now().astimezone().isoformat()
    controls={scope:{label:float(package[(package.encoding==label)&(package.split=='trans_test')&(package.scope==scope)].ap.iloc[0]) for label in ('old39_old_graph','old39_fixed_v2_graph','v2_39')} for scope in ('trusted','legacy')}
    write(H/'final_audit.json',dict(time=now,passed=True,new_fits=6,reused_fits=2,optimizer_updates_each=100,physical_controls=physical_checks,training_audits=training_audits,max_metric_recalculation_difference=maxdiff,previous_results_unchanged=True,old_v2_test_controls=controls,SAT_queries=0,baseline_status='three-seed training/detection complete; reliable cross-implementation metric pending',formal_P2_complete=False))
    lines=['|seed42测试AP|旧图＋旧39维|v2图＋旧物理39维|v2图＋v2特征|','|---|---:|---:|---:|']
    for scope,title in [('trusted','可信节点'),('legacy','旧标签全物理节点')]:
        c=controls[scope];lines.append(f"|{title}|{c['old39_old_graph']:.6f}|{c['old39_fixed_v2_graph']:.6f}|{c['v2_39']:.6f}|")
    stable=['|编码|seed42|seed1|seed2|均值±样本标准差|','|---|---:|---:|---:|---:|']
    for label,title in [('v2_39','39维v2'),('primitive21','原语21维')]:
        subset=group[(group.encoding==label)&(group.split=='trans_test')&(group.scope=='trusted')].set_index('seed');row=agg[(agg.encoding==label)&(agg.split=='trans_test')&(agg.scope=='trusted')].iloc[0]
        stable.append(f"|{title}|{subset.loc[42,'ap']:.6f}|{subset.loc[1,'ap']:.6f}|{subset.loc[2,'ap']:.6f}|{row.ap_mean:.6f} ± {row.ap_std:.6f}|")
    feature_delta=controls['trusted']['v2_39']-controls['trusted']['old39_fixed_v2_graph'];package_delta=controls['trusted']['v2_39']-controls['trusted']['old39_old_graph']
    conclusion=f"相同v2图上，v2物理特征相对旧物理特征的seed42可信测试AP差为{feature_delta:+.6f}；整套v2图与特征相对旧图旧特征差为{package_delta:+.6f}。这两个问题必须分开解释，不能仅凭v2正确性推断AP一定提高。"
    text=f'''# 第三十三轮：旧39维对照与P2-A三种子补齐

完成时间：{now}。

## 同协议旧39维与v2 seed42

{chr(10).join(lines)}

{conclusion}

主控制为固定v2有向全引脚图，只替换物理节点39维数值；辅助节点无历史特征，保留相同v2上下文并始终不监督。补充控制为旧图＋旧特征，采用历史双向消息边且没有新增辅助节点。因此整套对照包含方向策略、连接修复及辅助上下文变化，不能单独归因于PI/PO或向量修复。

三个39维seed42组初始参数逐项相同。两侧都使用冻结388视图划分、相同物理标签/可信掩码、单分支4层hidden64 GIN、ASL+1.4检出率损失、Adam lr0.0002/wd0.001、BF16、100次更新、每5次验证、验证可信注入视图macro AP选模。归一化均按同一train-only方法拟合各自特征；门型有界原值，14维z-score裁剪±10。旧控制不沿用历史全图归一化或旧阈值。不含SAT、区域、一致性或pair损失。

## 39维v2与原语21维三种子

{chr(10).join(stable)}

以上为测试可信节点、24个含正例注入视图等权AP；不是pooled AP。旧标签全节点口径另见three_seed_summary.csv，验证结果、AUC、Recall@1%/5%、正常对照FPR均分别保留。三种子差异见paired_seed_deltas.csv，不把折/视图当作独立随机种子。原语不是完整函数编码；历史开发效果不保证当前泛化，不能用测试结果为某组单独增加训练预算。

本轮新增6次训练：旧物理39维固定v2图seed42、旧图旧特征seed42、v2/原语seed1和2共4次；复用第三十二轮seed42两组，未重算。全部最终Adam step=100，无非有限损失/梯度。相同形状的初始化参数在各seed内一致。先固定本轮6个模型的验证选择，再评估测试；历史测试已被多轮分析，不称为全新盲测。

## P2-A完成范围

P2-A固定划分下的结构基线三种子训练及AP/AUC/预算召回/正常对照FPR主表已完成，编码替代与预处理控制也有独立证据。仍不能把整个P2的A–E消融标为完成：B–E尚需采用共同协议，不能直接拼接旧双分支/区域/SAT结果。

严格按10.22交付项，可靠对应上的跨实现预测差异仍待统一评测，因此完整P2-A验收暂记“主训练和检测指标完成，跨实现差异待补”。本轮不使用未审定的旧mapping填数；cross_implementation_difference留空并说明原因。结构基线不输入SAT，功能关系覆盖率记N/A而非伪造0/100%。

## 保留与产物

ginvenv_gpu执行；新代码仅在本轮目录，第三十二轮输入及结果哈希不变，旧图/旧训练结果保留，SAT保持暂停，新SAT查询0。prepare_controls.py、run_controls.py复用被冻结的第三十二轮训练引擎，request.json绑定其hash、输入和归一化版本；每组case_contract.json补充输入特征说明，不能只看arm=base39名称辨识。

证据：PREPARED.json、request.json、ALL_SELECTED.json、TRAINING_COMPLETE.json、final_audit.json；per_seed_metrics.csv、three_seed_summary.csv、paired_seed_deltas.csv、seed42_old_v2_controls.csv、fg_htl_ablation_v2_P2A.csv、run_manifest.csv；每组config、initial、100步checkpoint、train_log、SELECTED、预测npy及每视图CSV。
'''
    report=H/'第三十三轮_旧特征对照与P2A三种子.md';report.write_text(text,encoding='utf-8')
    target=ROOT/'10.15/06_统一评测协议/N4_三向泛化/tables/p2a_v2_round33';target.mkdir(exist_ok=True)
    for filename in ('per_seed_metrics.csv','three_seed_summary.csv','paired_seed_deltas.csv','seed42_old_v2_controls.csv','fg_htl_ablation_v2_P2A.csv','run_manifest.csv'):shutil.copy2(H/filename,target/filename)
    shutil.copy2(report,target/report.name)
    marker='第三十三轮：旧39维对照与P2-A三种子补齐'
    for name in ('SAT作用证明.md','SAT工作总结.md'):
        p=ROOT/'10.15/00_说明'/name
        if marker not in p.read_text(encoding='utf-8'):
            with p.open('a',encoding='utf-8') as f:f.write('\n\n'+text.replace('# 第三十三轮','### 第三十三轮',1))
    registry=ROOT/'10.15/99_共用资产/运行登记/运行登记表.csv'
    if marker not in registry.read_text(encoding='utf-8'):
        with registry.open('a',encoding='utf-8',newline='') as f:csv.writer(f).writerow([now,marker,'prepare_controls.py; run_controls.py; finalize_controls.py','ginvenv_gpu;100updates;BF16','42/1/2','frozen hosts_bt31','same supervision/loss/budget; physical feature vs topology controls',str(H.relative_to(ROOT)),conclusion,'主训练完成；跨实现指标待补','6new fits+2 reused; no SAT; old artifacts retained'])
    print(text)
if __name__=='__main__':main()
