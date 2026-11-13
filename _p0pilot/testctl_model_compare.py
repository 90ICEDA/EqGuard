"""Compare N-B vs control-only model on test control negative cones (fixed B95 threshold)."""
import csv, json, collections
from pathlib import Path
import numpy as np
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FG=R/'_p0pilot/four_group_contract_20261109'
OLD=R/'_p0pilot/seed42_nc_ablation_20261109'; OUT=R/'_p0pilot/lcone_testctl_20261110'
z0=np.load(FG/'run_B_N/best_testpred.npz'); rows=z0['rows']; y=z0['y']; tr=z0['trusted']; ph=z0['physical']
loc={r:i for i,r in enumerate(rows.tolist())}
pos=np.where(tr&ph&(y==1))[0]; thr=float(np.quantile(z0['scores'][pos],0.05))
cones=[]; view_members=collections.defaultdict(set)
with (OLD/'CONE_CACHE_TEST.csv').open(encoding='utf-8-sig',newline='') as f:
    for r in csv.DictReader(f):
        if 'ctl' not in r['view'] or r['kind'] not in ('D','PO') or int(r['n_phys'])<2: continue
        mem=[]
        for x in r['phys_rows'].split('|'):
            if not x: continue
            i=loc.get(int(x))
            if i is not None and ph[i]: mem.append(i)
        if len(mem)>=2:
            cones.append(dict(view=r['view'],kind=r['kind'],mem=np.array(mem)))
            view_members[r['view']].update(mem)
models={'NB':FG/'run_B_N/best_testpred.npz','ctrlonly':R/'_p0pilot/lcone_trainctl_20261110/run_ctrlonly_s1_lam0.1/best_testpred.npz','ctrlall':R/'_p0pilot/lcone_trainctl_20261110/run_ctrlall_s1_lam0.1/best_testpred.npz','ctrlmean':R/'_p0pilot/lcone_trainctl_20261110/run_ctrlmean_s1_lam0.1/best_testpred.npz','ctrlw':R/'_p0pilot/lcone_trainctl_20261110/run_ctrlw_s1_lam0.1/best_testpred.npz','ctrlstrat':R/'_p0pilot/lcone_trainctl_20261110/run_ctrlstrat_s1_lam0.1/best_testpred.npz','Nctl':R/'_p0pilot/lcone_trainctl_20261110/run_Nctl_s1/best_testpred.npz','ctrlstrat_last':R/'_p0pilot/lcone_trainctl_20261110/run_ctrlstrat_s1_lam0.1/last_testpred.npz'}
res={}
for name,path in models.items():
    s=np.load(path)['scores']; rec=[]
    for c in cones:
        sc=s[c['mem']]; mx=float(sc.max()); ss=np.sort(sc); second=float(ss[-2]) if len(ss)>1 else mx
        rec.append(dict(view=c['view'],kind=c['kind'],size=len(sc),max=mx,gap=mx-second,
                        zmax=(mx-float(sc.mean()))/(float(sc.std())+1e-6),n_high=int((sc>=thr).sum())))
    hit=[x for x in rec if x['n_high']>0]
    vs={}
    for v,mem in view_members.items():
        sc=s[np.array(sorted(mem))]; vs[v]=dict(nodes=len(mem),max=float(sc.max()),n_high=int((sc>=thr).sum()))
    res[name]=dict(threshold=thr,control_views=len(vs),control_nodes=sum(x['nodes'] for x in vs.values()),
        control_cones=len(rec),hit_cones=len(hit),hit_frac=round(len(hit)/len(rec),4),
        hit_one_high=sum(1 for x in hit if x['n_high']==1),hit_one_high_frac=round(sum(1 for x in hit if x['n_high']==1)/max(1,len(hit)),4),
        mean_size=round(float(np.mean([x['size'] for x in rec])),2),mean_max=round(float(np.mean([x['max'] for x in rec])),3),
        hit_mean_max=round(float(np.mean([x['max'] for x in hit])),3) if hit else None,
        hit_mean_nhigh=round(float(np.mean([x['n_high'] for x in hit])),2) if hit else None,
        mean_zmax=round(float(np.mean([x['zmax'] for x in rec])),3),
        alarm_views=sum(1 for x in vs.values() if x['n_high']>0),alarm_view_frac=round(sum(1 for x in vs.values() if x['n_high']>0)/len(vs),4),
        node_fp=sum(x['n_high'] for x in vs.values()),node_fpr=round(sum(x['n_high'] for x in vs.values())/max(1,sum(x['nodes'] for x in vs.values())),4),
        top_views=sorted(vs.items(),key=lambda kv:-kv[1]['max'])[:5])
(OUT/'TESTCTL_MODEL_COMPARE.json').write_text(json.dumps(res,indent=2),encoding='utf-8')
print(json.dumps(res,ensure_ascii=False)[:2500])
