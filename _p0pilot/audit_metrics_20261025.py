"""One-load, paired-view evaluation; percentile pooled AP remains supplementary.

Reports all test views, including normal controls. No score threshold is fitted
on test labels. Recall budgets are per view; ties get fractional expected credit.
"""
import json
import sys
import time
from pathlib import Path
import numpy as np
import pandas as pd
import torch
from scipy.stats import rankdata
from sklearn.metrics import average_precision_score, roc_auc_score

ROOT=Path(__file__).resolve().parents[1]
PT=ROOT/'generate_trans/folds/hosts_bt31/data/processed'
OUT=ROOT/'10.15/06_统一评测协议/N4_三向泛化/tables/audit_20261025'


def budget_hits(y,s,fraction):
    k=max(1,int(np.ceil(len(y)*fraction)))
    boundary=np.partition(s,len(s)-k)[len(s)-k]
    high=s>boundary
    tie=s==boundary
    return float(y[high].sum()+y[tie].sum()*(k-high.sum())/max(tie.sum(),1))


def main(sources=None,output_dir=None,threshold_reference=None):
    global OUT
    if output_dir is not None:
        OUT=Path(output_dir)
    t=time.perf_counter()
    graph=torch.load(PT/'trans_graph.pt',map_location='cpu',weights_only=False,mmap=True)
    y=graph.y.numpy().reshape(-1).astype(np.int8)
    file_ids=json.loads((PT.parent/'for_train/metadata_trans.json').read_text(encoding='utf-8'))['file_ids']
    full_vid,views=pd.factorize(np.asarray(file_ids,dtype=object),sort=False)
    full_vid=full_vid.astype(np.int16)
    inj_by_view=np.asarray(['__inj' in v for v in views])
    del file_ids
    trust=np.load(PT/'trust_trans.npy',mmap_mode='r').reshape(-1).astype(bool)
    sources=sources if sources is not None else {
        'B39':ROOT/'_devcfg/gnn_v31a_A2_s42.npz',
        'core7':ROOT/'_devcfg/gnn_v4coreD_s42.npz',
        'safe_nomux':ROOT/'_devcfg/gnn_v4smuxD_s42.npz',
        'reach_plus_covered':ROOT/'_devcfg/gnn_audit_reach_s42_20261025.npz',
        'covered_matched42':ROOT/'_devcfg/gnn_audit_covered3_s42_20261025.npz',
    }
    rows=[]
    summary=[]
    identities={}
    thresholds={}
    threshold_reference=threshold_reference or {}
    for tag,path in sources.items():
        if not path.exists():
            print(f'[pending] {tag}: {path.name}',flush=True)
            continue
        z=np.load(path)
        idx=z['idx'].astype(np.int64)
        s=z['score'].astype(np.float64)
        mask=z['test'].astype(bool)
        assert len(idx)==len(s)==len(mask) and len(np.unique(idx))==len(idx) and np.isfinite(s).all()
        identities[tag]=np.sort(idx[mask])
        for scope,keep in [('all_labels',mask),('trusted_only',mask & trust[idx])]:
            ii=idx[keep]
            ss=s[keep]
            yy=y[ii]
            vv=full_vid[ii]
            pp=np.zeros(len(ii),dtype=np.float32)
            own=[]
            order=np.argsort(vv,kind='stable')
            boundaries=np.flatnonzero(np.diff(vv[order]))+1
            for m in np.split(order,boundaries):
                view=views[vv[m[0]]]
                sy,sc=yy[m],ss[m]
                npos=int(sy.sum())
                pp[m]=(rankdata(sc,method='average').astype(np.float32)-1)/max(len(sc)-1,1)
                row=dict(model=tag,scope=scope,view=view,nodes=len(sy),positives=npos,
                         AP=average_precision_score(sy,sc) if 0<npos<len(sy) else np.nan,
                         AUC=roc_auc_score(sy,sc) if 0<npos<len(sy) else np.nan,
                         recall_1pct=budget_hits(sy,sc,.01)/npos if npos else np.nan,
                         recall_5pct=budget_hits(sy,sc,.05)/npos if npos else np.nan,
                         normal_score_mean=float(sc.mean()) if not npos else np.nan,
                         is_inj='__inj' in view)
                rows.append(row)
                own.append(row)
            d=pd.DataFrame(own)
            inj=inj_by_view[vv]
            normal=~inj
            val_neg=(~mask) & trust[idx] & (y[idx]==0)
            threshold=float(np.quantile(s[val_neg],.99,method='higher')) if val_neg.any() else np.nan
            reference=threshold_reference.get(tag,tag)
            if reference!=tag:
                if reference not in thresholds:
                    raise ValueError(f'threshold reference {reference} must be evaluated first')
                threshold=thresholds[reference]
            thresholds[tag]=threshold
            summary.append(dict(model=tag,scope=scope,views=len(d),positive_views=int((d.positives>0).sum()),
                                viewmean_AP=float(d.AP.mean()),viewmedian_AP=float(d.AP.median()),
                                viewmean_recall_1pct=float(d.recall_1pct.mean()),viewmean_recall_5pct=float(d.recall_5pct.mean()),
                                inj_percentile_pooled_AP=average_precision_score(yy[inj],pp[inj]),
                                inj_percentile_pooled_AUC=roc_auc_score(yy[inj],pp[inj]),
                                normal_nodes=int(normal.sum()),
                                val_trusted_neg_threshold_1pct_FPR=threshold,
                                threshold_reference=reference,
                                val_trusted_neg_FPR=float((s[val_neg]>threshold).mean()),
                                normal_FPR_at_val_threshold=float((ss[normal]>threshold).mean()) if normal.any() else np.nan,
                                normal_rate_score_ge_0p5=float((ss[normal]>=.5).mean()) if normal.any() else np.nan,
                                normal_rate_score_ge_0p9=float((ss[normal]>=.9).mean()) if normal.any() else np.nan))
    checks={tag:bool(np.array_equal(ids,identities['B39'])) for tag,ids in identities.items()}
    OUT.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT/'model_view_metrics.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(summary).to_csv(OUT/'model_summary.csv',index=False,encoding='utf-8-sig')
    paired=[]
    allrows=pd.DataFrame(rows)
    if 'reach_plus_covered' in identities:
        for scope in ['all_labels','trusted_only']:
            d=allrows[allrows.scope==scope]
            base=d[d.model=='B39'].set_index('view')
            for tag in ['core7','safe_nomux','reach_plus_covered','covered_matched42']:
                if tag not in identities:
                    continue
                alt=d[d.model==tag].set_index('view')
                both=base.join(alt,lsuffix='_base',rsuffix='_alt',how='inner')
                for v,r in both.iterrows():
                    paired.append(dict(scope=scope,model=tag,view=v,delta_AP=r.AP_alt-r.AP_base,
                                       delta_recall_1pct=r.recall_1pct_alt-r.recall_1pct_base,
                                       delta_recall_5pct=r.recall_5pct_alt-r.recall_5pct_base))
        pd.DataFrame(paired).to_csv(OUT/'paired_view_deltas.csv',index=False,encoding='utf-8-sig')
    if 'covered_matched42' in identities:
        reach=allrows[allrows.model=='reach_plus_covered'].set_index(['scope','view'])
        covered=allrows[allrows.model=='covered_matched42'].set_index(['scope','view'])
        both=reach.join(covered,lsuffix='_reach',rsuffix='_covered',how='inner')
        result=pd.DataFrame(index=both.index)
        for key in ['AP','recall_1pct','recall_5pct']:
            result['delta_'+key]=both[key+'_reach']-both[key+'_covered']
        result.reset_index().to_csv(OUT/'paired_reach_vs_covered.csv',index=False,encoding='utf-8-sig')
    (OUT/'metrics_integrity.json').write_text(json.dumps(dict(test_node_identity_vs_B=checks,elapsed_s=time.perf_counter()-t),indent=2))
    print(pd.DataFrame(summary).to_string(index=False),flush=True)
    print(checks,flush=True)


if __name__=='__main__':
    main()
