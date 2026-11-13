"""Cone size distribution and aggregation-function comparison on N-B scores."""
import os, sys, json, csv
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'): os.environ[k]='1'
os.environ['P2B_MASK']='old'
from pathlib import Path
import numpy as np
from sklearn.metrics import average_precision_score
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FG=R/'_p0pilot/four_group_contract_20261109'
V2=R/'_p0pilot/lcone_v2c_20261110'; OLD=R/'_p0pilot/seed42_nc_ablation_20261109'
OUT=R/'_p0pilot/lcone_phaseA_20261110'; OUT.mkdir(exist_ok=True)
# current train cone sizes
sizes={}
for arm in ('base','all'):
    c=np.load(V2/f'cones_v2c_{arm}_D.npz'); ptr=c['ptr']; lab=c['label']; s=np.diff(ptr)
    sizes[arm]=dict(n=int(len(lab)),pos=int(lab.sum()),neg=int((lab==0).sum()),
                    pos_mean=float(s[lab==1].mean()),neg_mean=float(s[lab==0].mean()),
                    pos_min=int(s[lab==1].min()),pos_max=int(s[lab==1].max()),
                    neg_min=int(s[lab==0].min()),neg_max=int(s[lab==0].max()),
                    size_hist={int(k):int(v) for k,v in zip(*np.unique(s,return_counts=True))},
                    single=int((s==1).sum()),two=int((s==2).sum()),ge10=int((s>=10).sum()))
# test cone aggregation
z=np.load(FG/'run_B_N/best_testpred.npz'); scores=z['scores']; rows=z['rows']; tr=z['trusted']; ph=z['physical']
loc={r:i for i,r in enumerate(rows.tolist())}
res={}
for kind in ('D','PO'):
    cones=[]
    with (OLD/'CONE_CACHE_TEST.csv').open(encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            if r['split']!='test' or r['kind']!=kind or int(r['label'])<0 or int(r['n_phys'])<2: continue
            mem=[]
            for x in r['phys_rows'].split('|'):
                if not x: continue
                i=loc.get(int(x))
                if i is not None and bool(tr[i]) and bool(ph[i]): mem.append(i)
            if len(mem)>=2: cones.append((int(r['label']),np.array(mem)))
    lab=np.array([x[0] for x in cones]); vals={k:[] for k in ('max','mean','top3','top5','median','logsumexp','top10pct')}
    for y,mem in cones:
        sc=scores[mem]
        vals['max'].append(float(sc.max())); vals['mean'].append(float(sc.mean()))
        for k in (3,5):
            m=min(k,len(sc)); vals[f'top{k}'].append(float(np.sort(sc)[-m:].mean()))
        vals['median'].append(float(np.median(sc)))
        vals['logsumexp'].append(float(np.log(np.exp(sc-sc.max()).sum())+sc.max()))
        k=max(1,int(np.ceil(0.1*len(sc)))); vals['top10pct'].append(float(np.sort(sc)[-k:].mean()))
    res[kind]=dict(cones=int(len(lab)),pos=int(lab.sum()),neg=int((lab==0).sum()),
                   sizes=dict(mean=float(np.mean([len(m) for _,m in cones])),median=float(np.median([len(m) for _,m in cones])),
                              min=int(min(len(m) for _,m in cones)),max=int(max(len(m) for _,m in cones))),
                   ap={k:float(average_precision_score(lab,np.array(v))) for k,v in vals.items()})
json.dump(dict(train_sizes=sizes,test_agg=res),open(OUT/'CONE_SIZE_AGG.json','w'),indent=2)
print(json.dumps(dict(train_sizes=sizes,test_agg=res),ensure_ascii=False)[:1800])
