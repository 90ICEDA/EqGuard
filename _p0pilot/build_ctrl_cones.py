"""Build train-control negative cones (v2 trust) and combine with v2c pos/neg for a seed42 run."""
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
        # cap 20
        if len(mem)>20:
            rng=np.random.default_rng(len(mem)); mem=np.sort(rng.choice(mem,20,replace=False))
        ctrl.append(mem)
rng=np.random.default_rng(42); rng.shuffle(ctrl); ctrl=ctrl[:558]
print('control neg',len(ctrl),'mean size',np.mean([len(x) for x in ctrl]))
# combine v2c all + control
c=np.load(V2/'cones_v2c_all_D.npz'); rows0=c['rows']; ptr0=c['ptr']; lab0=c['label']; view0=c['view']
flat=[]; ptr=[0]; lab=[]; view=[]
for i in range(len(lab0)):
    mem=rows0[ptr0[i]:ptr0[i+1]]; flat.extend(mem.tolist()); ptr.append(len(flat)); lab.append(int(lab0[i])); view.append(str(view0[i]))
for mem in ctrl:
    flat.extend(mem.tolist()); ptr.append(len(flat)); lab.append(0); view.append('train_control')
np.savez_compressed(OUT/'cones_ctrl_D.npz',rows=np.array(flat,np.int64),ptr=np.array(ptr,np.int64),label=np.array(lab,np.int8),view=np.array(view))
json.dump(dict(pos=int(sum(1 for x in lab if x==1)),neg_inj=int(sum(1 for x in lab0 if x==0)),neg_control=len(ctrl),total=len(lab)),open(OUT/'CTRL_BUILD.json','w'))
print('combined',len(lab),'pos',sum(lab),'neg',len(lab)-sum(lab))
