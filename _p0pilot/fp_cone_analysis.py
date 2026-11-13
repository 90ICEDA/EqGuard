"""Analyze N-B false-positive nodes in negative test cones: isolated vs group FP."""
import os, sys, json, csv
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'): os.environ[k]='1'
from pathlib import Path
import numpy as np
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FG=R/'_p0pilot/four_group_contract_20261109'
OLD=R/'_p0pilot/seed42_nc_ablation_20261109'; OUT=R/'_p0pilot/lcone_isolation_20261110'
z=np.load(FG/'run_B_N/best_testpred.npz'); s=z['scores']; rows=z['rows']; y=z['y']; tr=z['trusted']; ph=z['physical']
loc={r:i for i,r in enumerate(rows.tolist())}
node_cones={}
cones=[]
for kind in ('D','PO'):
    with (OLD/'CONE_CACHE_TEST.csv').open(encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            if r['split']!='test' or r['kind']!=kind or int(r['n_phys'])<2 or int(r['label'])<0: continue
            mem=[]
            for x in r['phys_rows'].split('|'):
                if not x: continue
                i=loc.get(int(x))
                if i is not None and ph[i]: mem.append(i)
            if len(mem)<2: continue
            cid=len(cones); cones.append(dict(kind=kind,label=int(r['label']),mem=np.array(mem)))
            for i in mem: node_cones.setdefault(i,[]).append(cid)
neg=np.where(tr&ph&(y==0))[0]; pos=np.where(tr&ph&(y==1))[0]
print('neg',len(neg),'pos',len(pos),'cones',len(cones))
def analyze(nodes, frac):
    thr=np.quantile(s[nodes],1-frac) if frac<1 else -np.inf
    fp=nodes[s[nodes]>=thr]
    out=dict(nodes=int(len(nodes)),fp=int(len(fp)),threshold=float(thr),in_any=0,in_neg=0,in_pos=0,no_cone=0)
    neg_stats=[]; pos_stats=[]
    for i in fp:
        cs=node_cones.get(int(i),[])
        if not cs: out['no_cone']+=1; continue
        out['in_any']+=1
        nc=[c for c in cs if cones[c]['label']==0]; pc=[c for c in cs if cones[c]['label']==1]
        if nc:
            out['in_neg']+=1
            best=max(nc,key=lambda c: s[cones[c]['mem']].max())
            mem=cones[best]['mem']; sc=s[mem]; order=np.argsort(-sc); mx=float(sc[order[0]]); second=float(sc[order[1]]) if len(order)>1 else mx
            neg_stats.append(dict(max=mx,gap=mx-second,n_high=int((sc>0).sum()),size=len(sc),rank=int(np.where(order==np.where(mem==i)[0][0])[0][0]) if False else 0))
        if pc:
            out['in_pos']+=1
            best=max(pc,key=lambda c: s[cones[c]['mem']].max()); sc=s[cones[best]['mem']]
            pos_stats.append(dict(max=float(sc.max()),gap=float(sc.max()-np.sort(sc)[-2]) if len(sc)>1 else 0.0,n_high=int((sc>0).sum()),size=len(sc)))
    for name,arr in (('neg',neg_stats),('pos',pos_stats)):
        if arr:
            out[name]=dict(n=len(arr),mean_max=float(np.mean([x['max'] for x in arr])),mean_gap=float(np.mean([x['gap'] for x in arr])),
                           mean_nhigh=float(np.mean([x['n_high'] for x in arr])),frac_one_high=float(np.mean([x['n_high']==1 for x in arr])))
    return out
res={str(f):analyze(neg,f) for f in (0.001,0.01,0.05)}
# negative cone-level: cones with at least one negative FP (score>=0)
neg_cone=[]
for c in cones:
    if c['label']!=0: continue
    sc=s[c['mem']]; neg_cone.append(dict(max=float(sc.max()),n_high=int((sc>0).sum()),n=len(sc)))
res['negative_cones']=dict(n=len(neg_cone),mean_max=float(np.mean([x['max'] for x in neg_cone])),frac_max_gt0=float(np.mean([x['max']>0 for x in neg_cone])),
    frac_one_high=float(np.mean([x['n_high']==1 for x in neg_cone])),mean_nhigh=float(np.mean([x['n_high'] for x in neg_cone])))
(OUT/'FP_CONE_ANALYSIS.json').write_text(json.dumps(res,indent=2),encoding='utf-8')
print(json.dumps(res,ensure_ascii=False)[:2000])
