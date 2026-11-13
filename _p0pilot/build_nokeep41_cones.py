import json,sys,numpy as np
from pathlib import Path
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); sys.path.insert(0,str(R/'_p0pilot/endpoint_cone_build_20261109'))
import cone_builder as B
F=R/'generate_trans/folds/nokeep41'; labdir=R/'_p0pilot/nokeep41_20261111/labels'
# graph file_ids
import torch
d=torch.load(F/'data/processed/trans_graph_trusted.pt',map_location='cpu',weights_only=False); ids=list(d.file_ids)
con_rows=[]; ptr=[0]; labels=[]; views=[]; skipped=[]
for v in sorted(set(ids)):
 gidx=[i for i,x in enumerate(ids) if x==v]; p=labdir/f'{v}.npz'; l=np.load(p,allow_pickle=True)
 if len(gidx)!=len(l['cell']): skipped.append(v); continue
 cmap={str(c):(gidx[i],i) for i,c in enumerate(l['cell'])}; yy=l['y']; tt=l['trusted']
 try: b=B.build(F/'trans'/f'{v}.v')
 except Exception as e: skipped.append(v); print('builderr',v,e); continue
 for c in b['cones']:
  if c['kind']!='D': continue
  mem=[]; loc=[]
  for m in c['members']:
   z=cmap.get(str(m['cell']))
   if z is not None: mem.append(z[0]); loc.append(z[1])
  if len(mem)<2: continue
  t=tt[loc]; y=yy[loc]
  if ((y==1)&t).any(): lab=1
  elif len(t)>=1 and t.all() and (y[t]==0).all(): lab=0
  else: continue
  con_rows.extend(mem); ptr.append(len(con_rows)); labels.append(lab); views.append(v)
np.savez_compressed(R/'_p0pilot/nokeep41_20261111/cones_nokeep41_D.npz',rows=np.array(con_rows,np.int64),ptr=np.array(ptr,np.int64),label=np.array(labels,np.int8),view=np.array(views))
print('cones',len(labels),'pos',sum(labels),'neg',sum(1 for x in labels if x==0),'rows',len(con_rows),'skipped',len(skipped)); print('skipped',skipped[:10])
