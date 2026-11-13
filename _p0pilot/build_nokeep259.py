import json,numpy as np,torch
from pathlib import Path
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FG=R/'_p0pilot/four_group_contract_20261109'; F=R/'generate_trans/folds/nokeep41'
g=np.load(FG/'group_B.npz'); c=json.load(open(R/'_p0pilot/control_boundary_v3_20261104/input_contract.json',encoding='utf-8')); loc={int(r):i for i,r in enumerate(g['rows'])}
# original 41 views present in group_B
m=json.load(open(R/'_p0pilot/nokeep41_20261111/NOKEEP41_MANIFEST.json',encoding='utf-8')); names={v['view'] for v in m['views']}
vs=[v for v in c['shared_inputs']['trans_train']['views'] if v['view'] in names]
assert len(vs)==41,(len(vs))
keep=np.ones(len(g['rows']),bool)
for v in vs:
 for gi in range(v['start'],v['stop']):
  i=loc.get(gi)
  if i is not None: keep[i]=False
idx=np.where(keep)[0]; mp=np.full(len(keep),-1,np.int64); mp[idx]=np.arange(len(idx))
ee=g['edge'][:, (mp[g['edge'][0]]>=0)&(mp[g['edge'][1]]>=0)]; ee=np.stack([mp[ee[0]],mp[ee[1]]])
# new graph
d=torch.load(F/'data/processed/trans_graph_trusted.pt',map_location='cpu',weights_only=False)
nx=d.x.numpy(); ne=d.edge_index.numpy(); ny=d.y.numpy(); nt=d.trusted.numpy(); nph=np.ones(len(nx),bool)
n0=len(idx); ne=ne+n0
x=np.concatenate([g['x'][idx],nx]); y=np.concatenate([g['y'][idx],ny]).astype(np.int8); tr=np.concatenate([g['trusted'][idx],nt]).astype(bool); ph=np.concatenate([g['physical'][idx],nph]).astype(bool)
e=np.concatenate([ee,ne],axis=1)
np.savez_compressed(F/'group_nokeep259.npz',x=x.astype(np.float32),edge=e.astype(np.int64),y=y,trusted=tr,physical=ph,mean=g['mean'],std=g['std'],base_n=n0,new_n=len(nx))
print('base_n',n0,'new_n',len(nx),'total',len(y),'pos',int(((y==1)&tr).sum()),'trusted',int(tr.sum()),'edges',e.shape[1])
