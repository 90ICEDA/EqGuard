"""Read-only feature audit. No fitting, SAT or training; holdout labels unread."""
import os
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'):os.environ[k]='1'
from pathlib import Path
import json,csv,datetime,gc
import numpy as np
import torch
from scipy.stats import rankdata
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
def save(p,rows):
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def stats(a):
    q=np.quantile(a,[.05,.5,.95])
    return dict(n=len(a),mean=float(a.mean(dtype=np.float64)),std=float(a.std(dtype=np.float64)),p05=float(q[0]),median=float(q[1]),p95=float(q[2]),minimum=float(a.min()),maximum=float(a.max()),zero_fraction=float(np.mean(a==0)),unique=len(np.unique(a)))
def main():
    out=HERE/'base39_audit';out.mkdir(exist_ok=False)
    graph=ROOT/'generate_trans/folds/hosts_bt31/data/processed/trans_graph.pt'
    frozen=json.loads((HERE/'frozen/manifest.json').read_text(encoding='utf-8'))
    vi=np.load(HERE/'frozen/view_index_all.npy',mmap_mode='r');names=frozen['view_names']
    views=json.loads((ROOT/'generate_trans/folds/hosts_bt31/views.json').read_text())
    lookup={v:i for i,v in enumerate(names)}
    masks={s:np.isin(vi,[lookup[v] for v in views[key]]) for s,key in [('train','train_views'),('val','val_views'),('test','test_views')]}
    torch.set_num_threads(1)
    g=torch.load(graph,map_location='cpu',weights_only=False,mmap=True);x=g.x.numpy()
    assert x.shape==(3220146,39)
    # Labels are gathered on train indices only, never on holdout rows.
    ti=np.flatnonzero(masks['train']);yt=g.y[torch.from_numpy(ti)].numpy().reshape(-1).astype(np.int8)
    gates=json.loads((ROOT/'generate_trans/folds/hosts_bt31/gatelookup_recommended.json').read_text())['simplified_gate_type_order']
    features=['gate_'+s for s in gates]+['log1p_input_ports','log1p_degree','touches_PI','touches_PO','dist_PI','dist_PO','log1p_fanin2','log1p_fanout2','reset_dist_PI','reset_dist_PO','reset_log1p_fanin2','reset_log1p_fanout2','in_comb_cycle','log1p_SCC_size']
    scopes=[('split',k,v) for k,v in masks.items()]
    for key,fn in [('host',lambda s:s.split('__')[0]),('recipe',lambda s:s.split('__')[-1])]:
        for val in sorted(set(fn(s) for s in names)):
            scopes.append((key,val,np.isin(vi,[i for i,s in enumerate(names) if fn(s)==val])))
    rows=[];norm=[];label=[]
    for j,f in enumerate(features):
        a=x[:,j]
        assert np.isfinite(a).all()
        for typ,name,m in scopes:rows.append(dict(scope=typ,group=name,column=j,feature=f,**stats(a[m])))
        ta=a[ti];p=ta[yt==1];n=ta[yt==0];r=rankdata(ta)
        auc=float((r[yt==1].sum()-len(p)*(len(p)+1)/2)/(len(p)*len(n)))
        for lab,b in [('positive',p),('negative',n)]:label.append(dict(label=lab,column=j,feature=f,auc_high=auc,**stats(b)))
        for fit,b in [('all',a),('train',ta)]:
            mu=float(b.mean(dtype=np.float64));sd=max(float(b.std(dtype=np.float64)),1e-6)
            for s,m in masks.items():
                z=(a[m]-mu)/sd
                norm.append(dict(fit=fit,split=s,column=j,feature=f,mu=mu,sd=sd,clipped=int((np.abs(z)>10).sum()),fraction=float((np.abs(z)>10).mean())))
        print(f'column {j} done',flush=True)
    save(out/'distribution_by_split_host_recipe.csv',rows);save(out/'train_positive_negative.csv',label);save(out/'normalization_clipping.csv',norm)
    # Cross-label exact base vectors: train positives queried against train negatives only.
    pp=x[ti[yt==1]];wanted={z.tobytes() for z in pp};found=set()
    negids=ti[yt==0]
    for start in range(0,len(negids),16384):
        for z in x[negids[start:start+16384]]:
            key=z.tobytes()
            if key in wanted:found.add(key)
    info=dict(time=datetime.datetime.now().astimezone().isoformat(),graph=str(graph),graph_size=graph.stat().st_size,graph_mtime_ns=graph.stat().st_mtime_ns,shape=list(x.shape),split_counts={s:int(m.sum()) for s,m in masks.items()},unlisted=int((vi<0).sum()),train_positive=len(pp),train_negative=len(negids),positive_unique_vectors=len(wanted),positive_nodes_with_identical_negative=sum(z.tobytes() in found for z in pp),unique_positive_vectors_with_negative=len(found),test_labels_read=False,validation_labels_read=False,new_training_runs=0,new_sat_queries=0,feature_names=features,limitations=['Raw stored base features; normalized distributions depend on actual run config.','Single-column train AUC is descriptive and not a GNN result.','Exact node input collisions do not imply identical GNN neighborhoods.','Repeated views are dependent; host and recipe aggregates are node weighted.'])
    (out/'summary.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(info,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
