import numpy as np,csv
from pathlib import Path
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FG=R/'_p0pilot/four_group_contract_20261109'; OUT=R/'_p0pilot/lcone_relaxed_20261111'; B=R/'_p0pilot/control_boundary_v3_20261104'
g=np.load(FG/'group_B.npz'); c=np.load(OUT/'cones_relaxed_D.npz')
def star(rows,ptr):
 e=[]; r=np.asarray(rows); p=np.asarray(ptr)
 for i in range(len(p)-1):
  m=r[p[i]:p[i+1]]
  if len(m)<2: continue
  a=int(m[0])
  for z in m[1:]: e.append((a,int(z))); e.append((int(z),a))
 return np.array(e,dtype=np.int64).T if e else np.zeros((2,0),np.int64)
def ring(rows,ptr):
 e=[]; r=np.asarray(rows); p=np.asarray(ptr)
 for i in range(len(p)-1):
  m=r[p[i]:p[i+1]]
  if len(m)<2: continue
  if len(m)==2: e.append((int(m[0]),int(m[1]))); e.append((int(m[1]),int(m[0]))); continue
  for j in range(len(m)):
   a=int(m[j]); b=int(m[(j+1)%len(m)]); e.append((a,b)); e.append((b,a))
 return np.array(e,dtype=np.int64).T if e else np.zeros((2,0),np.int64)
def concat(base,extra): return np.concatenate([base,extra],axis=1) if extra.size else base
# train
etr=star(c['rows'],c['ptr']); rtr=ring(c['rows'],c['ptr'])
# val
v=np.load(FG/'val_common.npz'); vc=np.load(OUT/'val_cones_D.npz'); ev=star(vc['rows'],vc['ptr']); rv=ring(vc['rows'],vc['ptr'])
# test
te0=np.load(B/'inputs/trans_test/edge_index.npy'); tr=[]; ptr=[0]
with (R/'_p0pilot/seed42_nc_ablation_20261109/CONE_CACHE_TEST.csv').open(encoding='utf-8-sig',newline='') as f:
 for r0 in csv.DictReader(f):
  if r0['kind'] not in ('D','PO') or int(r0['label'])<0 or int(r0['n_phys'])<2: continue
  m=[int(z) for z in r0['phys_rows'].split('|') if z]
  if len(m)>=2: tr.extend(m); ptr.append(len(tr))
et=star(tr,ptr); rt=ring(tr,ptr)
# random endpoint permutation preserving degree sequence
rng=np.random.default_rng(20261111)
def rand_edges(ec,n):
 p=rng.permutation(n); return p[ec]
ertr=rand_edges(etr,len(g['y'])); erv=rand_edges(ev,len(v['y'])); ert=rand_edges(et,len(np.load(B/'inputs/trans_test/x39.npy')))
# weights for star cone edges: 1/sqrt(deg_i*deg_j), cone degree
def weights(ec,n):
 deg=np.bincount(ec[0],minlength=n); w=1.0/np.sqrt(np.maximum(deg[ec[0]],1)*np.maximum(deg[ec[1]],1)); return w.astype(np.float32)
wtr=weights(etr,len(g['y'])); wv=weights(ev,len(v['y'])); wt=weights(et,len(np.load(B/'inputs/trans_test/x39.npy')))
np.savez_compressed(OUT/'coneedge_variants.npz',
 train_star=concat(g['edge'],etr),train_ring=concat(g['edge'],rtr),train_rand=concat(g['edge'],ertr),
 val_star=concat(v['edge'],ev),val_ring=concat(v['edge'],rv),val_rand=concat(v['edge'],erv),
 test_star=concat(te0,et),test_ring=concat(te0,rt),test_rand=concat(te0,ert),
 w_star=wtr,w_val=wv,w_test=wt)
print('star',etr.shape,'ring',rtr.shape,'weights',wtr.shape)
