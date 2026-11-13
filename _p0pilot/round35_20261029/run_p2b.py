"""Queued P2-B: only architecture differs from frozen P2-A protocol."""
import sys,json,time,importlib.util,gc,csv,datetime,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
import torch
ROOT=Path(__file__).resolve().parents[2];H=Path(__file__).resolve().parent;A=ROOT/'_p0pilot/round32_20261029';A3=ROOT/'_p0pilot/round33_20261029';CORR=ROOT/'_p0pilot/round34_20261029'
sys.path.insert(0,str(ROOT))
from models.gin_net import GINDual
spec=importlib.util.spec_from_file_location('fixed_A_engine',A/'train_pair.py');M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
original_write=M.write
def write(path,obj):
    if path.name=='config.json':
        obj.update(model='dual_gate GIN: 2 layers per branch hidden64 split29 dropout0.2',architecture='P2-B',input_contract_sha=M.sha(A/'input_contract.json'),
            normalization_sha=M.sha(A/'normalization.npz'),branch_depth=2,branch_split=29,
            architecture_note='A has 4 serial GIN layers; B has 2+2 parallel GIN layers plus gate fusion. Parameter count and receptive depth are architectural differences; no capacity-only causal claim.',
            implementation_note='Same frozen A engine/data/loss/100 updates; only model constructor overridden. Functional auxiliary head exists but no functional consistency loss is enabled.')
    original_write(path,obj)
M.write=write
def model_for(arm):
    assert arm=='base39';M.seed(M.SEED)
    return GINDual(39,64,2,num_layers=2,split=29,fusion='gate').cuda()
M.model_for=model_for
def configure(seed):
    out=H/f'seed{seed}';out.mkdir(exist_ok=True);M.H=out;M.SEED=seed;return out
def main():
    assert 'ginvenv_gpu' in sys.executable and torch.cuda.is_available()
    assert M.sha(A/'train_pair.py')==json.loads((A3/'request.json').read_text())['engine_sha']
    if (H/'COMPLETE.json').exists():print('Verified completed B retained');return
    for path,digest in M.CONTRACT['files'].items():assert M.sha(ROOT/path)==digest
    write(H/'loss_check.json',M.loss_check())
    # No test evaluation until all three validation selections are fixed.
    for seed in (42,1,2):
        configure(seed);torch.cuda.reset_peak_memory_stats();M.train_arm('base39')
    write(H/'ALL_SELECTED.json',{str(s):json.loads((H/f'seed{s}/runs/base39/SELECTED.json').read_text()) for s in (42,1,2)})
    summaries={};drifts=[];pairs=json.loads((CORR/'frozen_pairs.json').read_text())
    for seed in (42,1,2):
        folder=configure(seed);out=folder/'runs/base39';sel=json.loads((out/'SELECTED.json').read_text());model=model_for('base39')
        model.load_state_dict(torch.load(ROOT/sel['path'],map_location='cuda',weights_only=True))
        val=M.predict(model,'trans_val','base39');v=M.arrays('trans_val');threshold=float(np.nextafter(np.quantile(val[v['trusted']&(v['y']==0)],.95),np.inf))
        summaries[str(seed)]=dict(selected=sel,threshold=threshold)
        scores={'val':val}
        for split in ('val','test','train'):
            p=val if split=='val' else M.predict(model,'trans_'+split,'base39');scores[split]=p
            np.save(out/f'trans_{split}_scores.npy',p)
            if split!='train':
                summary,rows=M.metrics(p,'trans_'+split,threshold);summaries[str(seed)]['trans_'+split]=summary;M.save_rows(out/f'trans_{split}_per_view.csv',rows)
        for pair in pairs:
            if not pair['main_eligible']:continue
            a=pair['source'];b=pair['partner'];p=float(scores[pair['split']][a['local_node']]);q=float(scores[pair['split']][b['local_node']])
            drifts.append(dict(seed=seed,split=pair['split'],relation_id=pair['relation_id'],absolute_difference=abs(p-q),flip=int((p>=threshold)!=(q>=threshold)),whole_observation_status=pair['whole_observation_status']))
        ck=torch.load(out/'checkpoint_100.pt',map_location='cpu',weights_only=False)
        assert set(int(x['step']) for x in ck['optimizer']['state'].values())=={100}
        assert len(ck['records'])==100 and all(np.isfinite(x['loss']) and np.isfinite(x['gradient_norm']) for x in ck['records'])
        pd.DataFrame([{k:v for k,v in x.items() if k!='validation'} for x in ck['records']]).to_csv(out/'train_log.csv',index=False,encoding='utf-8-sig')
        del model,ck;gc.collect();torch.cuda.empty_cache()
    write(H/'comparison.json',summaries)
    rows=[]
    for seed,data in summaries.items():
        for split in ('trans_val','trans_test'):
            for scope in ('trusted','legacy'):rows.append(dict(variant='B_v2_dual',seed=int(seed),split=split,scope=scope,**data[split][scope]))
    b=pd.DataFrame(rows);b.to_csv(H/'B_per_seed.csv',index=False,encoding='utf-8-sig')
    a=pd.read_csv(A3/'per_seed_metrics.csv');a=a[a.encoding=='v2_39'].copy();a['variant']='A_v2_single'
    ab=pd.concat([a,b],ignore_index=True);ab.to_csv(H/'AB_per_seed.csv',index=False,encoding='utf-8-sig')
    summary=ab.groupby(['variant','split','scope']).agg(n=('seed','size'),ap_mean=('ap','mean'),ap_std=('ap','std'),auc_mean=('auc','mean'),auc_std=('auc','std'),r1_mean=('r1','mean'),r5_mean=('r5','mean'),normal_fpr_mean=('control_fpr','mean')).reset_index();summary.to_csv(H/'AB_summary.csv',index=False,encoding='utf-8-sig')
    d=pd.DataFrame(drifts);d.to_csv(H/'B_cross_impl_pairs.csv',index=False,encoding='utf-8-sig');d.groupby(['seed','split']).agg(pairs=('relation_id','size'),mae=('absolute_difference','mean'),flip=('flip','mean')).reset_index().to_csv(H/'B_cross_impl_summary.csv',index=False,encoding='utf-8-sig')
    now=datetime.datetime.now().astimezone().isoformat()
    text='\n\n### 第三十五轮：P2-B后台任务完成 '+now+'\n\nP2-B seed42/1/2均完成100次更新；ginvenv_gpu；39维v2、图、可信监督、归一化、损失、选模与P2-A一致，仅改为双分支2+2层、split29、gate融合。未加SAT/区域/一致性/pair损失。对照表见 `_p0pilot/round35_20261029/AB_summary.csv`，逐seed和预测均保留。跨实现沿用冻结的训练9对/验证2对可信正常target，测试对应仍为NA。架构同时改变并行深度和参数量，不声称容量匹配。SAT恢复补跑在本任务之后由队列执行，本段不代表SAT完成。\n'
    for name in ('SAT作用证明.md','SAT工作总结.md'):
        with (ROOT/'10.15/00_说明'/name).open('a',encoding='utf-8') as f:f.write(text)
    target=ROOT/'10.15/06_统一评测协议/N4_三向泛化/tables/p2b_v2_round35';target.mkdir(exist_ok=True)
    for file in ('B_per_seed.csv','AB_per_seed.csv','AB_summary.csv','B_cross_impl_summary.csv'):__import__('shutil').copy2(H/file,target/file)
    with (ROOT/'10.15/99_共用资产/运行登记/运行登记表.csv').open('a',encoding='utf-8',newline='') as f:csv.writer(f).writerow([now,'第三十五轮 P2-B完成','run_p2b.py','ginvenv_gpu;100 updates','42/1/2','hosts_bt31 frozen','same A protocol; dual2+2 split29',str(H.relative_to(ROOT)),'AB_summary.csv','完成','SAT恢复为后续独立队列任务'])
    write(H/'COMPLETE.json',dict(time=now,training_runs=3,updates_each=100,new_SAT=0,result_sha=M.sha(H/'AB_summary.csv')))
    print('P2_B_COMPLETE',flush=True)
if __name__=='__main__':main()
