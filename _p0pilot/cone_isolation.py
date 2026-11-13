"""Analyze within-cone score isolation for N-B vs NC, on test D/PO cones."""
import os, sys, json, csv
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'): os.environ[k]='1'
from pathlib import Path
import numpy as np
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FG=R/'_p0pilot/four_group_contract_20261109'
OLD=R/'_p0pilot/seed42_nc_ablation_20261109'; OUT=R/'_p0pilot/lcone_isolation_20261110'; OUT.mkdir(exist_ok=True)
models={
 'NB':FG/'run_B_N/best_testpred.npz',
 'NCweak001':R/'_p0pilot/lcone_weak_20261110/run_weak_s42_lam0.001/best_testpred.npz',
}
# use one score/rows mapping; same test graph
base=np.load(models['NB']); rows=base['rows']; y=base['y']; tr=base['trusted']; ph=base['physical']
loc={r:i for i,r in enumerate(rows.tolist())}
cones={}
for kind in ('D','PO'):
    arr=[]
    with (OLD/'CONE_CACHE_TEST.csv').open(encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            if r['split']!='test' or r['kind']!=kind or int(r['n_phys'])<2 or int(r['label'])<0: continue
            mem=[]
            for x in r['phys_rows'].split('|'):
                if not x: continue
                i=loc.get(int(x))
                if i is not None and ph[i]: mem.append(i)
            if len(mem)>=2: arr.append((int(r['label']),np.array(mem)))
    cones[kind]=arr
res={}
for name,path in models.items():
    z=np.load(path); s=z['scores']; res[name]={}
    for kind,arr in cones.items():
        rec={1:[],0:[]}
        for lab,mem in arr:
            sc=s[mem]; mx=float(sc.max()); mean=float(sc.mean()); sd=float(sc.std()+1e-6)
            zmax=(mx-mean)/sd
            ss=np.sort(sc); gap=float(ss[-1]-ss[-2]) if len(ss)>1 else 0.0
            p=np.exp(sc-sc.max()); p=p/p.sum(); eff=float(1.0/np.sum(p*p))
            rec[lab].append(dict(max=mx,zmax=zmax,gap=gap,eff=eff,high=float((sc>0).mean()),n=len(sc)))
        def summ(v):
            return dict(n=len(v),mean_max=float(np.mean([x['max'] for x in v])),mean_zmax=float(np.mean([x['zmax'] for x in v])),
                        frac_z_gt1_5=float(np.mean([x['zmax']>1.5 for x in v])),frac_gap_gt0_5=float(np.mean([x['gap']>0.5 for x in v])),
                        mean_eff=float(np.mean([x['eff'] for x in v])),mean_high=float(np.mean([x['high'] for x in v])))
        res[name][kind]={str(k):summ(v) for k,v in rec.items()}
(OUT/'ISOLATION.json').write_text(json.dumps(res,indent=2),encoding='utf-8')
print(json.dumps(res,ensure_ascii=False)[:2000])
