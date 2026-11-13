import numpy as np,json,csv
from pathlib import Path
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FG=R/'_p0pilot/four_group_contract_20261109'; OUT=R/'_p0pilot/lcone_relaxed_20261111'; B=R/'_p0pilot/control_boundary_v3_20261104'
def comps(n,e):
 a=coo_matrix((np.ones(e.shape[1],np.int8),(e[0],e[1])),shape=(n,n)); k,l=connected_components(a,directed=False); return k,l
def ring_from_labels(n,labels,rng):
 e=[]
 for c in np.unique(labels):
  m=np.where(labels==c)[0]
  if len(m)<2: continue
  m=m[rng.permutation(len(m))]
  for i in range(len(m)):
   a=int(m[i]); b=int(m[(i+1)%len(m)]); e.append((a,b)); e.append((b,a))
 return np.array(e,dtype=np.int64).T if e else np.zeros((2,0),np.int64)
# train
g=np.load(FG/'group_B.npz'); ntr=len(g['y']); ktr,ltr=comps(ntr,g['edge']); rng=np.random.default_rng(20261111); etr=ring_from_labels(ntr,ltr,rng); ertr=ring_from_labels(ntr,rng.permutation(ltr),rng)
# val
v=np.load(FG/'val_common.npz'); nv=len(v['y']); kv,lv=comps(nv,v['edge']); ev=ring_from_labels(nv,lv,rng); erv=ring_from_labels(nv,rng.permutation(lv),rng)
# test compact
c=json.load(open(B/'input_contract.json',encoding='utf-8')); vs=c['shared_inputs']['trans_test']['views']; rows=np.concatenate([np.arange(z['start'],z['stop']) for z in vs]); o2n=np.full(len(np.load(B/'inputs/trans_test/y.npy')),-1,np.int64); o2n[rows]=np.arange(len(rows))
te=np.load(B/'inputs/trans_test/edge_index.npy'); m=(o2n[te[0]]>=0)&(o2n[te[1]]>=0); ete=np.stack([o2n[te[0][m]],o2n[te[1][m]]]); nt=len(rows); kt,lt=comps(nt,ete); et=ring_from_labels(nt,lt,rng); ert=ring_from_labels(nt,rng.permutation(lt),rng)
np.savez_compressed(OUT/'label_free_assets.npz',train_ring=np.concatenate([g['edge'],etr],axis=1),train_rand=np.concatenate([g['edge'],ertr],axis=1),val_ring=np.concatenate([v['edge'],ev],axis=1),val_rand=np.concatenate([v['edge'],erv],axis=1),test_ring=np.concatenate([ete,et],axis=1),test_rand=np.concatenate([ete,ert],axis=1),test_rows=rows)
print('train comps',ktr,'edges',etr.shape,'val comps',kv,ev.shape,'test comps',kt,et.shape)
print('deg train pos/neg',np.bincount(etr[0],minlength=ntr)[g['y']==1].mean(),np.bincount(etr[0],minlength=ntr)[g['y']==0].mean())
