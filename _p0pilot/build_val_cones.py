import numpy as np,csv
from pathlib import Path
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); v=np.load(R/'_p0pilot/four_group_contract_20261109/val_common.npz',allow_pickle=True); loc={int(r):i for i,r in enumerate(v['rows'])}
rows=[]; ptr=[0]; labs=[]; views=[]
with (R/'_p0pilot/seed42_supervised_prep_20261109/CONE_CACHE_V2.csv').open(encoding='utf-8-sig',newline='') as f:
 for r in csv.DictReader(f):
  if r['split']!='val' or r['kind']!='D' or int(r['label'])<0 or int(r['n_phys'])<2 or 'ctl' in r['view']: continue
  mem=[]
  for z in r['phys_rows'].split('|'):
   if z and int(z) in loc: mem.append(loc[int(z)])
  if len(mem)<2: continue
  rows.extend(mem); ptr.append(len(rows)); labs.append(int(r['label'])); views.append(r['view'])
np.savez_compressed(R/'_p0pilot/lcone_relaxed_20261111/val_cones_D.npz',rows=np.array(rows,np.int64),ptr=np.array(ptr,np.int64),label=np.array(labs,np.int8),view=np.array(views))
print(len(labs),sum(labs),len(rows))
