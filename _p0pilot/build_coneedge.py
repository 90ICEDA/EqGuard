import numpy as np,csv,json
from pathlib import Path
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FG=R/'_p0pilot/four_group_contract_20261109'; OUT=R/'_p0pilot/lcone_relaxed_20261111'; B=R/'_p0pilot/control_boundary_v3_20261104'
g=np.load(FG/'group_B.npz'); c=np.load(OUT/'cones_relaxed_D.npz')
def add_star(edge,rows,ptr):
    add=[]; r=np.asarray(rows); p=np.asarray(ptr)
    for i in range(len(p)-1):
        mem=r[p[i]:p[i+1]]
        if len(mem)<2: continue
        a=int(mem[0])
        for m in mem[1:]:
            add.append((a,int(m))); add.append((int(m),a))
    if not add: return edge
    add=np.array(add,dtype=np.int64).T
    return np.concatenate([edge,add],axis=1)
# train
etr=add_star(g['edge'],c['rows'],c['ptr'])
# val
v=np.load(FG/'val_common.npz'); vc=np.load(OUT/'val_cones_D.npz'); ev=add_star(v['edge'],vc['rows'],vc['ptr'])
# test
tx=np.load(B/'inputs/trans_test/x39.npy'); te=np.load(B/'inputs/trans_test/edge_index.npy'); trows=[]; tptr=[0]; tlab=[]
with (R/'_p0pilot/seed42_nc_ablation_20261109/CONE_CACHE_TEST.csv').open(encoding='utf-8-sig',newline='') as f:
    for r0 in csv.DictReader(f):
        if r0['kind'] not in ('D','PO') or int(r0['label'])<0 or int(r0['n_phys'])<2: continue
        mem=[int(z) for z in r0['phys_rows'].split('|') if z]
        if len(mem)>=2: trows.extend(mem); tptr.append(len(trows))
et=add_star(te,trows,tptr)
np.savez_compressed(OUT/'coneedge_assets.npz',train_edge=etr,val_edge=ev,test_edge=et)
print('edges',g['edge'].shape[1],etr.shape[1],'val',v['edge'].shape[1],ev.shape[1],'test',te.shape[1],et.shape[1])
