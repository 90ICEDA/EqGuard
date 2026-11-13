"""Redundancy metrics for current vs weak-negative cones on held-out test cache."""
import os, sys, json, csv
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'): os.environ[k]='1'
os.environ['P2B_MASK']='old'
from pathlib import Path
import numpy as np
from sklearn.metrics import average_precision_score
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FG=R/'_p0pilot/four_group_contract_20261109'
OLD=R/'_p0pilot/seed42_nc_ablation_20261109'; OUT=R/'_p0pilot/lcone_phaseA_20261110'
z=np.load(FG/'run_B_N/best_testpred.npz'); s=z['scores']; rows=z['rows']; tr=z['trusted']; ph=z['physical']; y=z['y']
loc={r:i for i,r in enumerate(rows.tolist())}
def agg(sc):
    return dict(max=float(sc.max()),mean=float(sc.mean()),top3=float(np.sort(sc)[-min(3,len(sc)):].mean()))
def build(kind, f):
    pos=[]; cur=[]; weak=[]
    with (OLD/'CONE_CACHE_TEST.csv').open(encoding='utf-8-sig',newline='') as fh:
        for r in csv.DictReader(fh):
            if r['split']!='test' or r['kind']!=kind or int(r['n_phys'])<2: continue
            mem=[]
            for x in r['phys_rows'].split('|'):
                if not x: continue
                i=loc.get(int(x))
                if i is not None and ph[i]: mem.append(i)
            if len(mem)<2: continue
            t=tr[mem]; yy=y[mem]
            npos=int(((yy==1)&t).sum()); nneg=int(((yy==0)&t).sum())
            if npos>0: pos.append(mem)
            elif nneg==len(mem): cur.append(mem)
            elif nneg>=1 and nneg/len(mem)>=f: weak.append(mem)
    return pos,cur,weak
out={}
for kind in ('D','PO'):
    for f in (0.3,0.5):
        pos,cur,weak=build(kind,f)
        def score_set(neg):
            labels=np.array([1]*len(pos)+[0]*len(neg)); vals={k:[] for k in ('max','mean','top3')}
            for mem in pos+neg:
                a=agg(s[mem])
                for k in vals: vals[k].append(a[k])
            return dict(pos=len(pos),neg=len(neg),pos_size=float(np.mean([len(m) for m in pos])),neg_size=float(np.mean([len(m) for m in neg])),
                        ap={k:float(average_precision_score(labels,np.array(v))) for k,v in vals.items()})
        out[f'{kind}_f{f}']=dict(current=score_set(cur),weak=score_set(weak))
(OUT/'WEAK_NEG_REDUNDANCY.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False)[:2000])
