"""Exact-stratum descriptive discrimination audit. No fitting or new SAT."""
import os
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'):os.environ[k]='1'
import json,datetime,gc
from pathlib import Path
import numpy as np
import pandas as pd
import torch
from scipy.stats import rankdata
import k4_runtime as R

SOURCE=Path(__file__).parent/'label_distribution_reviews/review_00000'
SCORES=['change','max_change','fixed_mean','fixed_product','max_minus_mean','pooled_rank_mean']
LEVELS={'all':[], 'host':['host'], 'view':['view'], 'view_gate':['view','gate','role'], 'view_gate_k':['view','gate','k','role']}

def auc(a,b):
    z=np.r_[a,b];r=rankdata(z)
    return float((r[:len(a)].sum()-len(a)*(len(a)+1)/2)/(len(a)*len(b)))

def evaluate(df,keys,level):
    groups=df.groupby(keys,sort=True,observed=True) if keys else [((),df)]
    records=[];joint=[];supports=[]
    for key,z in groups:
        key=key if isinstance(key,tuple) else (key,)
        p=z.y.to_numpy()==1;n=~p;np_=int(p.sum());nn=int(n.sum())
        ident=dict(zip(keys,key));supported=bool(np_ and nn)
        supports.append(dict(level=level,**ident,positive=np_,negative=nn,supported=supported))
        if not supported:continue
        c=z.change.to_numpy();m=z.max_change.to_numpy()
        vals=[c,m,(c+m)/2,c*m,m-c,(rankdata(c)+rankdata(m))/(2*len(z))]
        for name,score in zip(SCORES,vals):
            records.append(dict(level=level,**ident,score=name,positive=np_,negative=nn,pairs=np_*nn,auc_high=auc(score[p],score[n]),pos_mean=float(score[p].mean()),neg_mean=float(score[n].mean())))
        if level=='view_gate_k':
            # Exact pairs at the saved float32 descriptor precision, not a
            # learned lookup classifier. Shared profiles are not unique labels.
            pc={tuple(v) for v in np.c_[c[n],m[n]]}
            shared=sum(tuple(v) in pc for v in np.c_[c[p],m[p]])
            sharedc=int(np.isin(c[p],c[n]).sum());sharedm=int(np.isin(m[p],m[n]).sum())
            joint.append(dict(**ident,positive=np_,negative=nn,positive_shared_pair=shared,positive_shared_change=sharedc,positive_shared_max=sharedm))
    return records,supports,joint

def aggregate(records,scopes):
    d=pd.DataFrame(records);out=[]
    for label,subset in scopes:
        for score in SCORES:
            z=d[(d.score==score)&subset(d)]
            if z.empty:continue
            vauc=[]
            if 'view' in z and z.view.notna().any():
                for _,vv in z.groupby('view'):vauc.append(float(np.average(vv.auc_high,weights=vv.positive)))
            out.append(dict(scope=label,score=score,strata=len(z),positive=int(z.positive.sum()),negative=int(z.negative.sum()),
                pos_weighted_auc=float(np.average(z.auc_high,weights=z.positive)),pair_weighted_auc=float(np.average(z.auc_high,weights=z.pairs)),
                stratum_macro_auc=float(z.auc_high.mean()),view_macro_auc=float(np.mean(vauc)) if vauc else None,
                eligible_views=len(vauc),views_auc_above_half=sum(a>.50000001 for a in vauc),views_auc_below_half=sum(a<.49999999 for a in vauc)))
    return out

def main():
    old=json.loads((SOURCE/'comparison.json').read_text());source_snapshot=R.ROOT/old['snapshot_source']
    snap=json.loads((source_snapshot/'snapshot.json').read_text())
    prev=json.loads((source_snapshot/'distribution.json').read_text())
    out=R.fresh_dir(Path(__file__).parent/'matched_feature_reviews','review')
    R.write_new(out/'analysis_plan.json',dict(created=datetime.datetime.now().astimezone().isoformat(),snapshot=str(source_snapshot),levels=LEVELS,scores=SCORES,
        rules=dict(fixed_mean='(change+max)/2',fixed_product='change*max',max_minus_mean='max-change',pooled_rank_mean='average pooled empirical ranks within stratum; labels unused'),
        cohort='covered=1 AND influence_valid=1; exact native gate AND target role; no fitting, no SAT, no test labels',
        weighting='primary: each positive equally weighted against negatives in its own stratum; also report pair, stratum, view weights'))
    torch.set_num_threads(1);gp=R.ROOT/'generate_trans/folds/hosts_bt31/data/processed/trans_graph.pt'
    graph=torch.load(gp,map_location='cpu',weights_only=False,mmap=True)
    expected=set(json.loads((R.ROOT/'generate_trans/folds/hosts_bt31/views.json').read_text())['train_views'])
    frames=[];bindings=[];total=0;pos=0;invalidpos=0;invalidneg=0
    for i,(folder,inp,oldbind) in enumerate(zip(snap['completed_folders'],prev['inputs'],old['bindings'])):
        folder=R.ROOT/folder;v=inp['view'];assert v==oldbind['view'] and v in expected
        assert R.sha(folder/'real.npy')==inp['feature_sha256']
        info=json.loads((folder/'coverage.json').read_text());x=np.load(folder/'real.npy')
        with np.load(folder/info.get('base_file','base_inputs.npz')) as z:ids=z['global_ids'].astype(np.int64)
        assert all(graph.file_ids[int(j)]==v for j in ids)
        yy=graph.y[torch.from_numpy(ids)].numpy().reshape(-1);assert np.isin(yy,[0,1]).all();y=yy.astype(np.int8)
        import hashlib
        assert hashlib.sha256(y.tobytes()).hexdigest()==oldbind['labels_sha256']
        records=json.loads((folder/'records.json').read_text());assert len(records)==len(ids)
        byid={a['global_node']:a for a in records};assert len(byid)==len(ids) and set(byid)==set(ids.tolist())
        snapshots=json.loads((folder/'snapshots.json').read_text());assert len(snapshots)==1
        ss=snapshots[0];assert ss['view']==v and ss['source_sha']==inp['source_sha256']
        rawpath=R.ROOT/ss['folder']/'raw.json';assert R.sha(rawpath)==ss['raw_sha']
        raw=json.loads(rawpath.read_text());cells=next(iter(raw['modules'].values()))['cells']
        keep=(x[:,18]==1)&(x[:,12]==1)
        total+=len(y);pos+=int(y.sum());invalidpos+=int(((y==1)&~keep).sum());invalidneg+=int(((y==0)&~keep).sum())
        rows=[]
        for j in np.flatnonzero(keep):
            a=byid[int(ids[j])];assert a['view']==v
            assert cells[a['cell']]['type']==a['driver_type']
            assert len(a['cut_bits'])==a['k']==round(float(x[j,0])*4)
            for col,ix in [('change_on_comparable',11),('max_input_influence',13)]:assert np.isclose(a['features'][col],x[j,ix],rtol=0,atol=1e-7)
            assert x[j,13]+1e-7>=x[j,11]
            rows.append((int(ids[j]),v,v.split('__')[0],a['driver_type'],a['target_role'],a['k'],int(y[j]),float(x[j,11]),float(x[j,13])))
        frames.append(pd.DataFrame(rows,columns=['global_id','view','host','gate','role','k','y','change','max_change']))
        bindings.append(dict(view=v,records_sha=R.sha(folder/'records.json'),raw_sha=ss['raw_sha'],features_sha=inp['feature_sha256'],labels_sha=oldbind['labels_sha256']))
        del records,byid,raw,cells,rows;gc.collect()
        if i%25==0:print(f'Validated {i+1}/{len(snap["completed_folders"])} views',flush=True)
    del graph;gc.collect()
    df=pd.concat(frames,ignore_index=True);del frames;assert not df.global_id.duplicated().any()
    for col in ['view','host','gate','role']:df[col]=df[col].astype('category')
    allrecords=[];supports=[];joint=[]
    for level,keys in LEVELS.items():
        a,b,c=evaluate(df,keys,level);allrecords+=a;supports+=b;joint+=c
    strict=pd.DataFrame([r for r in allrecords if r['level']=='view_gate_k'])
    scopes=[(level,lambda d,l=level:d.level==l) for level in LEVELS]
    aggregate_rows=aggregate(allrecords,scopes)
    host_rows=[]
    if not strict.empty:
        strict['host']=strict.view.str.split('__').str[0]
        for h in sorted(df.host.unique()):
            host_rows+=aggregate(strict.to_dict('records'),[(str(h),lambda d,h=h:d.host==h)])
    supported=pd.DataFrame([a for a in supports if a['level']=='view_gate_k'])
    missing=supported[(supported.positive>0)&~supported.supported]
    support_summary=dict(total_nodes=total,total_positive=pos,valid_nodes=len(df),valid_positive=int(df.y.sum()),valid_negative=int((df.y==0).sum()),excluded_positive=invalidpos,excluded_negative=invalidneg,
        strict_supported_positive=int(supported.loc[supported.supported,'positive'].sum()),strict_supported_negative=int(supported.loc[supported.supported,'negative'].sum()),strict_supported_strata=int(supported.supported.sum()),
        unsupported_positive=int(missing.positive.sum()),unsupported_positive_strata=len(missing),views_with_valid_positives=int(df.loc[df.y==1,'view'].nunique()))
    r=dict(created=datetime.datetime.now().astimezone().isoformat(),source_snapshot=old['frozen_at'],support=support_summary,aggregate=aggregate_rows,host=host_rows,
        joint_profile_overlap=dict(positive_shared_pair=sum(a['positive_shared_pair'] for a in joint),positive_shared_change=sum(a['positive_shared_change'] for a in joint),positive_shared_max=sum(a['positive_shared_max'] for a in joint)),
        bindings=bindings,no_new_sat=True,no_training=True,no_test_labels=True,
        limitations=['Repeated equivalent views are dependent; no significance or population-generalization claim.',
            'Exact matching controls listed variables only, not topology, physical context or insertion family.',
            'Unmatched positives excluded from conditional AUC and separately reported.',
            'Fixed combination rules are descriptive, not an optimized joint classifier; no conclusion about all nonlinear combinations.',
            'Scores tie at saved float32 precision; AUC gives ties half credit.'])
    R.write_new(out/'report.json',r)
    for name,rows in [('stratum_scores',allrecords),('support',supports),('aggregate',aggregate_rows),('host',host_rows),('joint_overlap',joint)]:
        pd.DataFrame(rows).to_csv(out/(name+'.csv'),index=False,encoding='utf-8-sig')
    df.to_csv(out/'analysis_nodes.csv.gz',index=False,compression='gzip')
    write_report(out,r);plot(out,r)
    print(json.dumps(dict(out=str(out),support=support_summary,strict=[a for a in aggregate_rows if a['scope']=='view_gate_k'],joint=r['joint_profile_overlap']),ensure_ascii=False),flush=True)

def write_report(out,r):
    s=r['support'];lines=['# 同视图、同原生门型、同cut大小的SAT区分审阅','',f"复用{r['source_snapshot']}冻结的221个已完成GLOBAL训练视图。沿用真实节点标签；无新增SAT、训练或当前测试标签读取。",'',
        '## 样本与匹配','',f"原正例{s['total_positive']}；有效比较正例{s['valid_positive']}、负例{s['valid_negative']}。排除正例{s['excluded_positive']}（无有效比较输入对）。精确匹配键=view+原生driver_type+k+target_role；同视图自然固定宿主与实现配方。",'',
        f"严格共同支持：{s['strict_supported_strata']}组，正例{s['strict_supported_positive']}、负例{s['strict_supported_negative']}；另有{s['unsupported_positive']}个有效正例在{s['unsupported_positive_strata']}组中没有同组负例，不能计算条件AUC，单独保留于support.csv。",'',
        '## 逐层控制后的AUC','', '| 控制层级 | 分数 | 正例数 | 正例等权条件AUC | 视图宏平均AUC |','|---|---|---:|---:|---:|']
    for a in r['aggregate']:
        if a['score'] in SCORES:
            v=f"{a['view_macro_auc']:.4f}" if a['view_macro_auc'] is not None else '—'
            lines.append(f"| {a['scope']} | {a['score']} | {a['positive']} | {a['pos_weighted_auc']:.4f} | {v} |")
    lines+=['','正例等权条件AUC：先让每个正例只与同组负例比较，再给每个正例等权；不同组正负例不互相比。视图宏平均：先在各视图内按正例数汇总，再给视图等权。pair_weighted与stratum_macro结果另见CSV。层级变更可能同时改变共同支持样本，不能把逐层差值全当作混杂贡献。','',
        '固定组合：fixed_mean=(change+max)/2；fixed_product=change*max；max_minus_mean=max-change；pooled_rank_mean是两列在组内无标签混合样本上的秩均值。全部规则写入analysis_plan.json后才分析，不拟合权重或阈值。', '',
        '## 严格匹配后按宿主','', '| 宿主 | 分数 | 正例数 | 正例等权条件AUC | 视图宏平均AUC |','|---|---|---:|---:|---:|']
    for a in r['host']:
        if a['score'] in SCORES:lines.append(f"| {a['scope']} | {a['score']} | {a['positive']} | {a['pos_weighted_auc']:.4f} | {a['view_macro_auc']:.4f} |")
    j=r['joint_profile_overlap'];lines+=['','## 同组内的值碰撞','',f"严格匹配正例中，change单值也见于同组负例：{j['positive_shared_change']}；max单值也见于同组负例：{j['positive_shared_max']}；二维(change,max)精确组合也见于同组负例：{j['positive_shared_pair']}。分母均为{s['strict_supported_positive']}。二维不重合不等于可泛化的检测规则，稀有值可能只出现一次。",'',
        '## 证据与限制','', '记录与real.npy两列重放对齐；每个有效节点的driver_type与已绑定raw.json原生cell类型一致，k与cut_bits长度和特征一致；逐节点global_ids/file_ids及上轮标签摘要一致。记录、原始快照、特征哈希保存于report.json。']
    lines+=['']+['- '+a for a in r['limitations']]
    (out/'匹配对比报告.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')

def plot(out,r):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False})
    names=SCORES;lab=['条件变化率','最大单输入变化率','固定均值组合','固定乘积组合','差值(max−change)','组内秩均值组合']
    fig,axes=plt.subplots(1,2,figsize=(12,5))
    for ax,key,title in zip(axes,['pos_weighted_auc','view_macro_auc'],['正例等权条件AUC','视图宏平均条件AUC']):
        hosts=sorted({a['scope'] for a in r['host']});xx=np.arange(len(names))
        for i,h in enumerate(hosts):
            vals=[next(a[key] for a in r['host'] if a['scope']==h and a['score']==n) for n in names]
            ax.bar(xx+(i-1)*.24,vals,width=.23,label=h)
        ax.axhline(.5,color='black',linestyle='--',linewidth=1);ax.set_ylim(0,1);ax.set_xticks(xx,lab,rotation=25,ha='right');ax.set_title(title);ax.legend(fontsize=8);ax.grid(axis='y',alpha=.2)
    fig.suptitle('同视图 + 同原生门型 + 同cut大小 + 同目标角色；仅共同支持样本')
    fig.tight_layout(rect=(0,0,1,.94));fig.savefig(out/'严格匹配区分能力.png',dpi=150);plt.close(fig)

if __name__=='__main__':main()
