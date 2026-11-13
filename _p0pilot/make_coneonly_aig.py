"""Direction 1: cone-only held-out aig — build node-sup excluding aig, and aig cone set."""
import os, sys, json
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'): os.environ[k]='1'
os.environ['P2B_MASK']='old'
from pathlib import Path
import numpy as np
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FG=R/'_p0pilot/four_group_contract_20261109'
V2=R/'_p0pilot/lcone_v2c_20261110'; OUT=R/'_p0pilot/lcone_directions_20261110'; OUT.mkdir(exist_ok=True)
B=R/'_p0pilot/control_boundary_v3_20261104'
g=np.load(FG/'group_B.npz'); rows=g['rows']; n=len(g['y'])
c=json.loads((B/'input_contract.json').read_text(encoding='utf-8'))
vs={v['view']:v for v in c['shared_inputs']['trans_train']['views']}
rec=np.empty(n,dtype=object); rec[:]='other'
for v,lay in vs.items():
    a,b=np.searchsorted(rows,[lay['start'],lay['stop']])
    rec[a:b]=v.split('__')[-1]
aig=np.where(rec=='ys_aig')[0]; print('aig nodes',len(aig))
sup=np.load(FG/'sup_B.npz')
idx=[]; sh=[]
for i in range(200):
    ids=sup['idx'][i]
    keep=ids[rec[ids]!='ys_aig']
    idx.append(keep); sh.append(sup['stepsha'][i])
np.savez_compressed(OUT/'sup_no_aig.npz',idx=np.array(idx,dtype=object),stepsha=np.array(sh))
# aig cones
cc=np.load(V2/'cones_v2c_all_D.npz'); view=cc['view']; lab=cc['label']; cr=cc['rows']; cp=cc['ptr']
sel=[i for i,v in enumerate(view) if str(v).split('__')[-1]=='ys_aig']
flat=[]; p=[0]; labels=[]
for i in sel:
    flat.extend(cr[cp[i]:cp[i+1]].tolist()); p.append(len(flat)); labels.append(int(lab[i]))
np.savez_compressed(OUT/'cones_aig_D.npz',rows=np.array(flat,np.int64),ptr=np.array(p,np.int64),label=np.array(labels,np.int8),view=np.array([str(view[i]) for i in sel]))
print('aig cones',len(sel),'pos',sum(labels),'neg',len(labels)-sum(labels),'node steps',len(idx),'avg',np.mean([len(x) for x in idx]))
