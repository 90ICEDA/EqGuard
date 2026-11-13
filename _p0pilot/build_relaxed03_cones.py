"""Build relaxed injected negative cones (f=0.5) + v2c positives; no controls."""
import csv,json
from pathlib import Path
import numpy as np
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FG=R/'_p0pilot/four_group_contract_20261109'
PREP=R/'_p0pilot/seed42_supervised_prep_20261109'; V2=R/'_p0pilot/lcone_v2c_20261110'
OUT=R/'_p0pilot/lcone_relaxed03_20261111'; OUT.mkdir(exist_ok=True)
g=np.load(FG/'group_B.npz'); y=g['y']; tr=g['trusted']; ph=g['physical']; rows=g['rows']; loc={r:i for i,r in enumerate(rows.tolist())}
pos=[]
c0=np.load(V2/'cones_v2c_all_D.npz')
for i in range(len(c0['label'])):
 if c0['label'][i]!=1: continue
 mem=c0['rows'][c0['ptr'][i]:c0['ptr'][i+1]]; pos.append((mem,str(c0['view'][i])))
neg=[]; noisy=0
with (PREP/'CONE_CACHE_V2.csv').open(encoding='utf-8-sig',newline='') as f:
 for r in csv.DictReader(f):
  if r['split']!='train' or r['kind']!='D' or int(r['n_phys'])<2 or 'ctl' in r['view']: continue
  mem=[]
  for x in r['phys_rows'].split('|'):
   if not x: continue
   i=loc.get(int(x))
   if i is not None and ph[i]: mem.append(i)
  if len(mem)<2: continue
  mem=np.array(mem); t=tr[mem]; yy=y[mem]; nneg=int(((yy==0)&t).sum())
  if ((yy==1)&t).any(): continue
  if nneg>=1 and nneg/len(mem)>=0.3:
   neg.append((mem,r['view']))
   if ((yy==1)&~t).any(): noisy+=1
print('pos',len(pos),'neg',len(neg),'noisy cones',noisy,'neg mean',round(float(np.mean([len(x[0]) for x in neg])),1))
flat=[]; p=[0]; lab=[]; view=[]
for mem,v in pos+neg:
 flat.extend(mem.tolist()); p.append(len(flat)); lab.append(1 if len(flat) and len(lab)<len(pos) else 0); view.append(v)
# fix labels explicitly
lab=[1]*len(pos)+[0]*len(neg)
np.savez_compressed(OUT/'cones_relaxed03_D.npz',rows=np.array(flat,np.int64),ptr=np.array(p,np.int64),label=np.array(lab,np.int8),view=np.array(view))
json.dump(dict(pos=len(pos),neg=len(neg),noisy=noisy,neg_mean=float(np.mean([len(x[0]) for x in neg]))),open(OUT/'BUILD03.json','w'))
