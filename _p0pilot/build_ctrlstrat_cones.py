"""Build all train control negative cones (full members) + v2c positives; seed1 all-control run."""
import csv, json
from pathlib import Path
import numpy as np
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FG=R/'_p0pilot/four_group_contract_20261109'
PREP=R/'_p0pilot/seed42_supervised_prep_20261109'; V2=R/'_p0pilot/lcone_v2c_20261110'
OUT=R/'_p0pilot/lcone_trainctl_20261110'; OUT.mkdir(exist_ok=True)
g=np.load(FG/'group_B.npz'); y=g['y']; ph=g['physical']; rows=g['rows']; loc={r:i for i,r in enumerate(rows.tolist())}
tr2=np.load(R/'_p0pilot/label_expand_20261031/trust_trans_v2_trainctl.npy')[rows]
ctrl=[]
with (PREP/'CONE_CACHE_V2.csv').open(encoding='utf-8-sig',newline='') as f:
    for r in csv.DictReader(f):
        if r['split']!='train' or r['kind']!='D' or int(r['n_phys'])<2 or 'ctl' not in r['view']: continue
        mem=[]
        for x in r['phys_rows'].split('|'):
            if not x: continue
            i=loc.get(int(x))
            if i is not None and ph[i]: mem.append(i)
        if len(mem)<2: continue
        mem=np.array(mem); t=tr2[mem]; yy=y[mem]
        if ((yy==1)&t).any(): continue
        if not (t.all() and (yy==0).all()): continue
        ctrl.append((mem, r['view']))
print('all control neg',len(ctrl),'mean',round(float(np.mean([len(x[0]) for x in ctrl])),2))
# combine v2c positives + all controls (no injected negatives)
c=np.load(V2/'cones_v2c_all_D.npz'); rr=c['rows']; pp=c['ptr']; ll=c['label']; vv=c['view']
flat=[]; ptr=[0]; lab=[]; view=[]
for i in range(len(ll)):
    if ll[i]!=1: continue
    mem=rr[pp[i]:pp[i+1]]; flat.extend(mem.tolist()); ptr.append(len(flat)); lab.append(1); view.append(str(vv[i]))
for mem, viewname in ctrl:
    flat.extend(mem.tolist()); ptr.append(len(flat)); lab.append(0); view.append(viewname)
np.savez_compressed(OUT/'cones_ctrlstrat_D.npz',rows=np.array(flat,np.int64),ptr=np.array(ptr,np.int64),label=np.array(lab,np.int8),view=np.array(view))
json.dump(dict(pos=int(sum(lab)),neg=len(ctrl),total=len(lab),neg_mean_members=float(np.mean([len(x[0]) for x in ctrl]))),open(OUT/'CTRLSTRAT_BUILD.json','w'))
print('combined',len(lab),'pos',sum(lab),'neg',len(lab)-sum(lab))
