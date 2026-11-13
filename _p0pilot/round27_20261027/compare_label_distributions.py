"""Label-aware descriptive audit of the SAME completed GLOBAL-train snapshot.
No fitting, candidate selection, SAT solving or test-label analysis.
"""
import os
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'):os.environ[k]='1'
import csv,json,gc,datetime
from pathlib import Path
import numpy as np
import torch
from scipy.stats import rankdata,ks_2samp
from sklearn.metrics import average_precision_score
import k4_runtime as R
from analyze_completed_distribution import COLS

def savecsv(p,rows):
    with p.open('x',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def auc(p,n):
    if not len(p) or not len(n):return None
    ranks=rankdata(np.r_[p,n]);return float((ranks[:len(p)].sum()-len(p)*(len(p)+1)/2)/(len(p)*len(n)))

def summary(a):
    if not len(a):return dict(n=0,mean=None,p10=None,median=None,p90=None,zero_fraction=None,one_fraction=None)
    q=np.quantile(a,[.1,.5,.9]);return dict(n=len(a),mean=float(a.mean(dtype=np.float64)),p10=float(q[0]),median=float(q[1]),p90=float(q[2]),zero_fraction=float(np.mean(a==0)),one_fraction=float(np.mean(a==1)))

def main():
    source=Path(__file__).parent/'feature_distribution_reviews/review_00002'
    old=json.loads((source/'distribution.json').read_text());snap=json.loads((source/'snapshot.json').read_text())
    out=R.fresh_dir(Path(__file__).parent/'label_distribution_reviews','review')
    torch.set_num_threads(1)
    graph_path=R.ROOT/'generate_trans/folds/hosts_bt31/data/processed/trans_graph.pt'
    g=torch.load(graph_path,map_location='cpu',weights_only=False,mmap=True)
    expected=set(json.loads((R.ROOT/'generate_trans/folds/hosts_bt31/views.json').read_text())['train_views'])
    xs=[];ys=[];vis=[];vr=[];bindings=[];allids=[]
    for i,(f,inp) in enumerate(zip(snap['completed_folders'],old['inputs'])):
        folder=R.ROOT/f;v=inp['view'];assert v in expected
        assert R.sha(folder/'real.npy')==inp['feature_sha256']
        c=json.loads((folder/'coverage.json').read_text());assert c['columns']==COLS
        with np.load(folder/c.get('base_file','base_inputs.npz')) as z:ids=z['global_ids'].astype(np.int64)
        assert all(g.file_ids[int(j)]==v for j in ids)
        y=g.y[torch.from_numpy(ids)].numpy().reshape(-1).astype(np.int8)
        assert set(np.unique(y))<={0,1}
        x=np.load(folder/'real.npy');assert len(x)==len(y)
        xs.append(x);ys.append(y);vis.append(np.full(len(y),i,dtype=np.int16));allids.append(ids)
        vr.append(dict(view=v,host=v.split('__')[0],recipe=v.split('__')[-1]))
        bindings.append(dict(view=v,feature_sha256=inp['feature_sha256'],node_ids_sha256=__import__('hashlib').sha256(ids.tobytes()).hexdigest(),labels_sha256=__import__('hashlib').sha256(y.tobytes()).hexdigest()))
    ids=np.concatenate(allids);assert len(np.unique(ids))==len(ids)
    x=np.concatenate(xs);y=np.concatenate(ys);vi=np.concatenate(vis);del xs,ys,vis,g,allids,ids;gc.collect()
    covered=x[:,18]==1;positive=y==1;negative=y==0
    counts=[]
    scopes=[('all','all',np.ones(len(y),dtype=bool))]
    for field in ('host','recipe'):
        for value in sorted({r[field] for r in vr}):
            scopes.append((field,value,np.isin(vi,[i for i,r in enumerate(vr) if r[field]==value])))
    for i,r in enumerate(vr):scopes.append(('view',r['view'],vi==i))
    rows=[]
    for scope,name,m in scopes:
        p=m&positive;n=m&negative
        counts.append(dict(scope=scope,group=name,nodes=int(m.sum()),positive=int(p.sum()),negative=int(n.sum()),positive_covered=int((p&covered).sum()),negative_covered=int((n&covered).sum()),positive_coverage=float(covered[p].mean()) if p.any() else None,negative_coverage=float(covered[n].mean()) if n.any() else None))
        if scope=='view' and not (p&covered).any():continue
        for j,col in enumerate(COLS[:18]):
            # The two change descriptors require comparable pairs. Other columns
            # use covered rows; coverage is separately reported over ALL nodes.
            valid=covered & ((x[:,12]==1) if j in (11,13) else True)
            a=x[p&valid,j];b=x[n&valid,j]
            sa=summary(a);sb=summary(b);A=auc(a,b)
            row=dict(scope=scope,group=name,column=col,validity='covered+influence_valid' if j in (11,13) else 'covered',**{'pos_'+k:v for k,v in sa.items()},**{'neg_'+k:v for k,v in sb.items()},auc_high=A,auc_separation=max(A,1-A) if A is not None else None)
            if scope!='view' and len(a) and len(b):
                row['ks']=float(ks_2samp(a,b,method='asymp').statistic)
                yy=np.r_[np.ones(len(a)),np.zeros(len(b))];vv=np.r_[a,b]
                row['ap_high']=float(average_precision_score(yy,vv));row['ap_low']=float(average_precision_score(yy,-vv));row['prevalence']=len(a)/len(yy)
            else:row.update(ks=None,ap_high=None,ap_low=None,prevalence=None)
            rows.append(row)
    # Within-view comparisons remove between-view score ordering only; they do
    # not match gate types or cut sizes and are descriptive, with no p-values.
    macro=[]
    for col in COLS[:18]:
        rr=[r for r in rows if r['scope']=='view' and r['column']==col and r['auc_high'] is not None]
        macro.append(dict(column=col,eligible_views=len(rr),macro_auc_high=float(np.mean([r['auc_high'] for r in rr])) if rr else None,macro_auc_separation=float(np.mean([r['auc_separation'] for r in rr])) if rr else None))
    profile=[]
    up,pc=np.unique(x[covered&positive,:18],axis=0,return_counts=True)
    un,nc=np.unique(x[covered&negative,:18],axis=0,return_counts=True)
    nd={tuple(a):int(b) for a,b in zip(un,nc)}
    for a,b in zip(up,pc):profile.append(dict(positive=int(b),negative=nd.get(tuple(a),0),values=a.tolist()))
    r=dict(created=datetime.datetime.now().astimezone().isoformat(),frozen_at=old['frozen_at'],snapshot_source=str(source.relative_to(R.ROOT)),completed_views=len(vr),counts=counts,columns=rows,within_view_macro=macro,positive_profiles=profile,bindings=bindings,graph=dict(path=str(graph_path.relative_to(R.ROOT)),size=graph_path.stat().st_size,mtime_ns=graph_path.stat().st_mtime_ns,label_binding='global_ids plus exact file_ids membership; per-view label digests'),current_test_labels_read=False,training_runs=0,new_sat_queries=0,limitations=['GLOBAL train completed snapshot only; repeated equivalence views are dependent observations.','AUC/AP are in-sample descriptive statistics, not held-out detection performance.','AUC separation chooses direction from these labels; not a validated direction.','Within-view audit does not control gate types, cut size or target role.','Change columns exclude influence_valid=0 rows; no-comparable is not zero influence.'])
    R.write_new(out/'comparison.json',r);savecsv(out/'coverage_by_label.csv',counts);savecsv(out/'feature_comparison.csv',rows);savecsv(out/'within_view_auc.csv',macro)
    plot(out,x,y,covered)
    write_report(out,r)
    print(str(out),flush=True)
    print(json.dumps(counts[:4],ensure_ascii=False),flush=True)

def plot(out,x,y,covered):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False,'font.size':10})
    features=[(0,'cut输入数 / 4'),(2,'可行模式比例'),(8,'决定行中输出1比例'),(10,'可比较输入对比例'),(11,'条件变化率（仅比较有效）'),(13,'最大单输入变化率（仅比较有效）')]
    fig,axes=plt.subplots(2,3,figsize=(13,7))
    for ax,(j,title) in zip(axes.flat,features):
        valid=covered&((x[:,12]==1) if j in (11,13) else True)
        for label,color,name in [(0,'#367ca5','负例'),(1,'#d66837','正例')]:
            z=x[valid&(y==label),j];u,c=np.unique(z,return_counts=True)
            if len(z):ax.step(np.r_[0,u,1],np.r_[0,np.cumsum(c)/len(z),1],where='post',color=color,label=f'{name} n={len(z):,}',linewidth=1.8)
        ax.set_title(title);ax.set_xlim(-.03,1.03);ax.set_ylim(-.03,1.03);ax.set_ylabel('各类内部累计比例');ax.legend(fontsize=8,loc='lower right');ax.grid(alpha=.2)
    fig.suptitle('已完成训练视图：节点正例与负例SAT特征分布（各类独立归一化）',fontsize=14)
    fig.tight_layout(rect=(0,0,1,.95));fig.savefig(out/'正负例特征对比.png',dpi=150);plt.close(fig)

def write_report(out,r):
    allc=r['counts'][0];rr=[a for a in r['columns'] if a['scope']=='all'];macro={a['column']:a for a in r['within_view_macro']}
    lines=['# 已完成SAT特征：节点正例与负例对比','',f"快照沿用{r['frozen_at']}的{r['completed_views']}个完成GLOBAL训练视图；按trans_graph.pt中节点y标签，经global_ids和file_ids逐节点核对。全部负例参与，没有负例抽样。",'',f"正例{allc['positive']:,}个，有效覆盖{allc['positive_covered']:,}（{allc['positive_coverage']:.2%}）；负例{allc['negative']:,}个，有效覆盖{allc['negative_covered']:,}（{allc['negative_coverage']:.2%}）。",'', '## 各列对比','', '| 特征 | 正例均值 | 负例均值 | 正例中位数 | 负例中位数 | 高值AUC | 同视图宏平均AUC |','|---|---:|---:|---:|---:|---:|---:|']
    for a in rr:
        ma=macro[a['column']]['macro_auc_high']
        lines.append(f"| {a['column']} | {a['pos_mean']:.4f} | {a['neg_mean']:.4f} | {a['pos_median']:.4f} | {a['neg_median']:.4f} | {a['auc_high']:.4f} | {ma:.4f} |")
    lines+=['','AUC按特征高值指向正例计算，0.5表示无排序区分；小于0.5表示方向相反。条件变化率与最大单输入变化率仅统计covered=1且influence_valid=1，其他内容列统计covered=1；无可比较输入对的填0不作真实变化率。','', '## 分宿主覆盖','', '| 宿主 | 正例/负例总数 | 正例覆盖 | 负例覆盖 |','|---|---:|---:|---:|']
    for c in r['counts']:
        if c['scope']=='host':lines.append(f"| {c['group']} | {c['positive']}/{c['negative']} | {c['positive_coverage']:.2%} | {c['negative_coverage']:.2%} |")
    lines+=['','## 正例摘要是否也出现在负例中','']
    pp=r['positive_profiles'];shared=sum(p['positive'] for p in pp if p['negative']>0)
    lines.append(f"正例共{len(pp)}种18维摘要，其中对应到负例已有摘要的正例{shared}/{allc['positive_covered']}（{shared/allc['positive_covered']:.2%}）。该统计只表示单节点摘要碰撞，不排除图邻域信息的作用。")
    lines+=['','## 解释边界','']+['- '+s for s in r['limitations']]
    lines+=['','没有拟合模型、追加SAT、读取当前测试标签或按正例重新选择候选。各列AP、KS、按宿主/配方/逐视图分布及有效样本数见feature_comparison.csv；覆盖见coverage_by_label.csv；完整绑定见comparison.json。图采用各类独立归一化的累计分布，避免负例数量占优势淹没正例。']
    (out/'正负例对比报告.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')

if __name__=='__main__':main()
