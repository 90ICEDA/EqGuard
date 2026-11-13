"""Read-only, label-free statistics over frozen completed k4 training views.

Does not import training/solver entry points. Failed/partial views are excluded.
Only new review artifacts are written; extraction evidence remains unchanged.
"""
import os
for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'):
    os.environ[key]='1'
import collections
import csv
import datetime
import gc
import hashlib
import json
from pathlib import Path
import numpy as np
import k4_runtime as R

COLS=['k_over_4','feasibility_known_fraction','feasible_fraction','forced_fraction',
      'undecided_fraction','infeasible_fraction','determinism_on_feasible',
      'determinism_valid','ones_on_forced','ones_valid','comparable_pair_fraction',
      'change_on_comparable','influence_valid','max_input_influence',
      'complete_full_domain','complete_restricted_domain','partial_forcing','has_unknown','covered']
LABELS={'k_over_4':'cut输入数 / 4','feasible_fraction':'可行模式比例',
        'ones_on_forced':'决定行中输出1的比例','comparable_pair_fraction':'可比较输入对比例',
        'change_on_comparable':'可比较对中的变化比例','max_input_influence':'最大单输入条件变化比例'}


def dump(p,obj):R.write_new(p,obj)
def entropy(counts):
    p=np.asarray(counts,dtype=np.float64);p=p/p.sum()
    return float(-(p*np.log2(p)).sum())
def csvout(p,rows):
    if not rows:return
    with p.open('x',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def main():
    out=R.fresh_dir(Path(__file__).parent/'feature_distribution_reviews','review')
    frozen_at=datetime.datetime.now().astimezone().isoformat()
    expected=set(json.loads((R.ROOT/'generate_trans/folds/hosts_bt31/views.json').read_text(encoding='utf-8'))['train_views'])
    panels=[R.TABLES/'sat_k4_rs232_round23',R.TABLES/'sat_s15850_round22',R.PANEL,R.PANEL/'train_controls_complement']
    folders=[];seen=set();plan_rows={};pending=[]
    # Freeze membership once; views finishing after this point are next-round data.
    for panel in panels:
        for item in R.read_plan(panel/'plan.json')['views']:
            v=item['view'];assert v in expected
            plan_rows[v]=item
            folder=panel/'views'/v
            if not (folder/'coverage.json').exists():continue
            if v in seen:raise ValueError('Duplicate completed view: '+v)
            seen.add(v);folders.append((folder,item))
    pending=sorted(expected-seen)
    dump(out/'snapshot.json',dict(frozen_at=frozen_at,completed_views=len(seen),planned_views=len(expected),
        pending_views=pending,completed_folders=[str(f.relative_to(R.ROOT)) for f,_ in folders],
        scope='GLOBAL train only; no labels or test features read; no partial views included'))
    arrays=[];ids=[];per_view=[];inputs=[]
    for ordinal,(folder,item) in enumerate(folders):
        info=json.loads((folder/'coverage.json').read_text(encoding='utf-8'))
        assert info['columns']==COLS
        feature_path=folder/'real.npy';digest=R.sha(feature_path)
        assert digest==info['feature_sha']['real']
        assert R.sha(R.ROOT/item['source'])==item['source_sha']
        x=np.load(feature_path)
        assert x.ndim==2 and x.shape[1]==19 and np.isfinite(x).all()
        assert np.all((x>=0)&(x<=1)) and np.all((x[:,-1]==0)|(x[:,-1]==1))
        mask=x[:,-1]==1
        assert not np.any(x[~mask,:18])
        # Historical fold names are not the current GLOBAL split. Membership was
        # checked against the frozen current train list before opening features.
        stats={key:sum(s.get(key,0) for s in info['splits'].values()) for key in ('nodes','covered','permutation_changed_nodes')}
        stats['excluded']=dict(collections.Counter({k:sum(s.get('excluded',{}).get(k,0) for s in info['splits'].values()) for s in info['splits'].values() for k in s.get('excluded',{})}))
        assert len(x)==stats['nodes'] and int(mask.sum())==stats['covered']
        base=folder/info.get('base_file','base_inputs.npz')
        with np.load(base) as z:g=z['global_ids'].copy()
        assert len(g)==len(x)
        ids.append(g);arrays.append(x)
        v=item['view'];host=v.split('__')[0];recipe=v.split('__')[-1]
        family=v.split('__')[1]
        kind=('a4ctldead' if family.startswith('a4ctldead') else 'a4ctlequiv' if family.startswith('a4ctlequiv') else 'a4trojan' if family.startswith('a4trojan') else 'control' if family.startswith('ctl') else 'insertion_named' if family.startswith('inj') else 'other')
        covered=x[mask,:18]
        unique=np.unique(covered,axis=0)
        row=dict(view=v,host=host,recipe=recipe,source_kind=kind,nodes=len(x),covered=int(mask.sum()),coverage=float(mask.mean()),
            unique_profiles=len(unique),full_domain=float(covered[:,14].mean()),restricted_domain=float(covered[:,15].mean()),
            partial_forcing=float(covered[:,16].mean()),mean_k=float(covered[:,0].mean()*4),
            mean_feasible=float(covered[:,2].mean()),mean_ones=float(covered[:,8].mean()),
            mean_comparable=float(covered[:,10].mean()),mean_change=float(covered[:,11].mean()),mean_max_change=float(covered[:,13].mean()),
            permutation_changed=int(stats.get('permutation_changed_nodes',0)),nonlocal_covered=None,
            excluded=json.dumps(stats.get('excluded',{}),ensure_ascii=False),feature_sha256=digest)
        per_view.append(row)
        inputs.append(dict(view=v,path=str(feature_path.relative_to(R.ROOT)),feature_sha256=digest,source_sha256=item['source_sha'],
            coverage_sha256=R.sha(folder/'coverage.json'),base_ids_only=True,
            historical_split_nodes={k:s['nodes'] for k,s in info['splits'].items()},current_split='train'))
        if ordinal%30==0:print(f'Loaded {ordinal+1}/{len(folders)} completed views',flush=True)
    x=np.concatenate(arrays);g=np.concatenate(ids);del arrays,ids;gc.collect()
    assert len(np.unique(g))==len(g)
    mask=x[:,18]==1;xc=x[mask,:18]
    column_rows=[];histograms={};nonconstant=[]
    quantiles=[0,.01,.1,.25,.5,.75,.9,.99,1]
    for i,name in enumerate(COLS[:18]):
        values=xc[:,i];unique,counts=np.unique(values,return_counts=True);qs=np.quantile(values,quantiles)
        row=dict(column=name,n=len(values),unique_values=len(unique),mean=float(values.mean(dtype=np.float64)),std=float(values.std(dtype=np.float64)),
            min=float(qs[0]),p01=float(qs[1]),p10=float(qs[2]),p25=float(qs[3]),median=float(qs[4]),p75=float(qs[5]),p90=float(qs[6]),p99=float(qs[7]),max=float(qs[8]),
            zero_fraction=float(np.mean(values==0)),one_fraction=float(np.mean(values==1)),
            mode=float(unique[np.argmax(counts)]),mode_fraction=float(counts.max()/len(values)),entropy_bits=entropy(counts),constant=len(unique)==1)
        column_rows.append(row)
        if len(unique)>1:nonconstant.append(i)
        if name in LABELS:
            counts_hist,edges=np.histogram(values,bins=np.linspace(-.000001,1.000001,21))
            histograms[name]=dict(counts=counts_hist.tolist(),edges=edges.tolist())
    unique_profiles,profile_counts=np.unique(xc,axis=0,return_counts=True)
    ordering=np.argsort(profile_counts)[::-1]
    top=[]
    for j in ordering[:20]:
        top.append(dict(count=int(profile_counts[j]),fraction=float(profile_counts[j]/len(xc)),values={n:float(v) for n,v in zip(COLS[:18],unique_profiles[j])}))
    if nonconstant:
        corr=np.corrcoef(xc[:,nonconstant].astype(np.float64),rowvar=False)
        # Descriptor algebra, not a claim about predictive information dimension.
        standardized=xc[:,nonconstant].astype(np.float64)
        standardized-=standardized.mean(axis=0);standardized/=standardized.std(axis=0)
        eig=np.linalg.eigvalsh(standardized.T@standardized/len(standardized));del standardized
        algebra_rank=int((eig>1e-6).sum())
    else:corr=np.empty((0,0));algebra_rank=0;eig=np.array([])
    correlations=[]
    for a in range(len(nonconstant)):
        for b in range(a+1,len(nonconstant)):
            if abs(corr[a,b])>.99999:correlations.append(dict(left=COLS[nonconstant[a]],right=COLS[nonconstant[b]],correlation=float(corr[a,b])))
    group_rows=[];group_plot={}
    offsets=np.cumsum([0]+[r['nodes'] for r in per_view]);view_index=np.repeat(np.arange(len(per_view)),[r['nodes'] for r in per_view])
    for key in ('host','recipe','source_kind'):
        for value in sorted({r[key] for r in per_view}):
            ix=np.array([j for j,r in enumerate(per_view) if r[key]==value]);rows=[per_view[j] for j in ix]
            which=np.isin(view_index,ix);cm=which&mask;xx=x[cm,:18]
            row=dict(grouping=key,group=value,completed_views=len(rows),nodes=int(which.sum()),covered=int(cm.sum()),coverage=float(cm.sum()/which.sum()),
                unique_profiles=len(np.unique(xx,axis=0)),mean_k=float(xx[:,0].mean()*4),
                full_domain=float(xx[:,14].mean()),restricted_domain=float(xx[:,15].mean()),
                mean_feasible=float(xx[:,2].mean()),mean_ones=float(xx[:,8].mean()),mean_change=float(xx[:,11].mean()),
                mean_max_change=float(xx[:,13].mean()),view_weighted_mean_change=float(np.mean([r['mean_change'] for r in rows])))
            if key=='host':
                row['planned_views']=sum(v.startswith(value+'__') for v in expected)
            else:row['planned_views']=None
            group_rows.append(row)
        gc.collect()
    relations=dict(forced_equals_feasible=bool(np.array_equal(xc[:,3],xc[:,2])),
        feasibility_plus_infeasibility_one=bool(np.allclose(xc[:,2]+xc[:,5],1,rtol=0,atol=1e-7)),
        full_plus_restricted_one=bool(np.all(xc[:,14]+xc[:,15]==1)),
        all_covered_has_unknown_zero=bool(np.all(xc[:,17]==0)))
    kvalues,kcounts=np.unique(np.rint(xc[:,0]*4).astype(int),return_counts=True)
    report=dict(frozen_at=frozen_at,completed_at=datetime.datetime.now().astimezone().isoformat(),completed_views=len(per_view),planned_views=259,
        completed_nodes=len(x),planned_nodes=1250510,covered_nodes=int(mask.sum()),effective_coverage=float(mask.mean()),
        covered_values_only=True,uncovered_rows_excluded_from_content_statistics=True,
        constant_columns=[r['column'] for r in column_rows if r['constant']],nonconstant_columns=[COLS[i] for i in nonconstant],
        near_exact_correlations=correlations,standardized_covariance_rank=algebra_rank,rank_tolerance=1e-6,eigenvalues=eig.tolist(),descriptor_relations=relations,
        k_distribution={int(k):dict(count=int(n),fraction=float(n/len(xc))) for k,n in zip(kvalues,kcounts)},
        profiles=dict(unique=len(unique_profiles),entropy_bits=entropy(profile_counts),top1_fraction=float(profile_counts[ordering[0]]/len(xc)),
            top10_fraction=float(profile_counts[ordering[:10]].sum()/len(xc)),top20=top),
        columns=column_rows,groups=group_rows,inputs=inputs,labels_read=False,test_features_read=False,new_sat_queries=0,new_training_runs=0,
        limitations=['Snapshot includes only completed GLOBAL-train views; remaining large netlists can change distributions.',
            'High effective coverage is not evidence of detection gain.',
            'Change/influence columns describe feasible conditional-table comparisons, not causal intervention.',
            'ones_on_forced is not natural trigger frequency or input-distribution probability.',
            'Profile entropy and covariance rank are descriptive; they do not measure security information.',
            'Source-kind group names are construction metadata, not node-level security labels.',
            'Legacy base adjacency defects do not affect these feature-only statistics; this review reads global_ids only.'],errors=[])
    dump(out/'distribution.json',report);dump(out/'histogram_counts.json',histograms)
    csvout(out/'column_statistics.csv',column_rows);csvout(out/'group_statistics.csv',group_rows);csvout(out/'view_statistics.csv',per_view)
    csvout(out/'profile_top20.csv',[dict(rank=i+1,count=r['count'],fraction=r['fraction'],**r['values']) for i,r in enumerate(top)])
    # No feature matrix is exported or attached for model training.
    del x,xc,g,unique_profiles,profile_counts,view_index,mask;gc.collect()
    print(json.dumps(dict(report_folder=str(out),completed_views=report['completed_views'],nodes=report['completed_nodes'],covered=report['covered_nodes'],constant=report['constant_columns'],unique_profiles=report['profiles']['unique']),ensure_ascii=False),flush=True)
    plots(out,report,histograms,corr,[COLS[i] for i in nonconstant])
    markdown(out,report)


def plots(out,report,histograms,corr,names):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False,'font.size':10})
    fig,axes=plt.subplots(2,3,figsize=(13,7))
    for ax,(name,title) in zip(axes.flat,LABELS.items()):
        d=histograms[name];edges=np.array(d['edges']);counts=np.array(d['counts'])/report['covered_nodes']*100
        ax.bar((edges[:-1]+edges[1:])/2,counts,width=np.diff(edges)*.9,color='#48799b')
        ax.set_title(title);ax.set_xlim(-.03,1.03);ax.set_ylabel('有效覆盖节点占比（%）');ax.grid(axis='y',alpha=.2)
        row=next(r for r in report['columns'] if r['column']==name)
        ax.text(.97,.95,f"中位数 {row['median']:.3f}\n均值 {row['mean']:.3f}",transform=ax.transAxes,ha='right',va='top',fontsize=9)
    fig.suptitle(f"已完成SAT特征分布：{report['completed_views']}个训练视图，{report['covered_nodes']:,}个有效节点",fontsize=14)
    fig.tight_layout(rect=(0,0,1,.95));fig.savefig(out/'特征分布.png',dpi=150);plt.close(fig)
    fig,ax=plt.subplots(figsize=(max(8,len(names)*.65),max(6,len(names)*.55)))
    im=ax.imshow(corr,vmin=-1,vmax=1,cmap='RdBu_r');ax.set_xticks(range(len(names)),names,rotation=55,ha='right');ax.set_yticks(range(len(names)),names)
    fig.colorbar(im,ax=ax,shrink=.8,label='Pearson相关系数');ax.set_title('仅非常量列的相关性；不代表检测价值')
    fig.tight_layout();fig.savefig(out/'特征相关性.png',dpi=140);plt.close(fig)
    rr=[r for r in report['groups'] if r['grouping']=='recipe']
    fig,axes=plt.subplots(1,3,figsize=(13,4.5))
    for ax,key,title in zip(axes,['coverage','mean_change','restricted_domain'],['有效覆盖率','条件变化比例均值','受限完整域比例']):
        ax.bar([r['group'] for r in rr],[r[key]*100 for r in rr],color='#56866c');ax.set_title(title);ax.set_ylabel('%');ax.tick_params(axis='x',rotation=45);ax.grid(axis='y',alpha=.2)
    fig.suptitle('已完成实现配方的分布差异（混合宿主与门型，不作因果归因）',fontsize=13)
    fig.tight_layout(rect=(0,0,1,.93));fig.savefig(out/'配方分布.png',dpi=150);plt.close(fig)


def markdown(out,r):
    rows=['# 已完成SAT特征分布分析','',f"冻结时间：{r['frozen_at']}。仅分析全局训练集已完成视图，不包含进行中的部分批次，不读取节点标签或测试特征。",
          '',f"完成视图 {r['completed_views']}/259；节点 {r['completed_nodes']:,}/1,250,510；有效覆盖 {r['covered_nodes']:,}（{r['effective_coverage']:.2%}）。未覆盖全零行不参与内容统计。",
          '', '## 逐列分布','', '| 列 | 均值 | P10 | 中位数 | P90 | 最常见值及占比 | 唯一值数 |', '|---|---:|---:|---:|---:|---|---:|']
    for x in r['columns']:
        rows.append(f"| {x['column']} | {x['mean']:.4f} | {x['p10']:.4f} | {x['median']:.4f} | {x['p90']:.4f} | {x['mode']:.4f}，{x['mode_fraction']:.2%} | {x['unique_values']} |")
    rows+=['','## 摘要冗余与功能类型','',f"常量列共{len(r['constant_columns'])}列："+'、'.join(r['constant_columns'])+'。',
        '',f"18维摘要共{r['profiles']['unique']:,}种取值；最常见摘要占{r['profiles']['top1_fraction']:.2%}，前10种占{r['profiles']['top10_fraction']:.2%}；经验熵{r['profiles']['entropy_bits']:.3f} bit。重复摘要可以来自重复门和等价视图，不能仅凭唯一值数量判定无信息。",
        '',f"非常量列标准化协方差在1e-6阈值下的秩为{r['standardized_covariance_rank']}。这是数值冗余描述，不是可训练安全信息维度。",
        '', '确定关系：'+json.dumps(r['descriptor_relations'],ensure_ascii=False)+'。','', '## 宿主覆盖与分布','',
        '| 宿主 | 完成/计划视图 | 已完成节点 | 有效覆盖 | 平均cut大小 | 条件变化均值 | 完整受限域占比 |','|---|---:|---:|---:|---:|---:|---:|']
    for x in r['groups']:
        if x['grouping']=='host':rows.append(f"| {x['group']} | {x['completed_views']}/{x['planned_views']} | {x['nodes']:,} | {x['coverage']:.2%} | {x['mean_k']:.3f} | {x['mean_change']:.4f} | {x['restricted_domain']:.2%} |")
    rows+=['','## 解释边界','']+['- '+x for x in r['limitations']]
    rows+=['','## 产物','', '特征分布.png、特征相关性.png、配方分布.png；column_statistics.csv、group_statistics.csv、view_statistics.csv、profile_top20.csv；distribution.json与snapshot.json记录输入绑定和冻结成员。','',
        '本轮未修改提取或训练脚本，未合并成训练输入，未执行SAT或训练。后续应在全量完成后按同样口径重算，再检验功能内容与结构元数据的独立增量。']
    (out/'分析报告.md').write_text('\n'.join(rows)+'\n',encoding='utf-8')


if __name__=='__main__':main()
