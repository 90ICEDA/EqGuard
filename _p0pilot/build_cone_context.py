import numpy as np,csv
from pathlib import Path
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FG=R/'_p0pilot/four_group_contract_20261109'; OUT=R/'_p0pilot/lcone_relaxed_20261111'; B=R/'_p0pilot/control_boundary_v3_20261104'
def ctx(x,rows,ptr,alpha=.5):
    c=np.zeros_like(x); cnt=np.zeros(len(x),np.float32); r=np.asarray(rows); p=np.asarray(ptr)
    for i in range(len(p)-1):
        mem=r[p[i]:p[i+1]]
        if len(mem)<2: continue
        c[mem]+=x[mem].mean(0); cnt[mem]+=1
    c=c/np.maximum(cnt,1)[:,None]
    return (x+alpha*c).astype(np.float32)
g=np.load(FG/'group_B.npz'); c=np.load(OUT/'cones_relaxed_D.npz'); xtr=ctx(g['x'],c['rows'],c['ptr'])
v=np.load(FG/'val_common.npz'); vc=np.load(OUT/'val_cones_D.npz'); xv=ctx(v['x'],vc['rows'],vc['ptr'])
tx=np.load(B/'inputs/trans_test/x39.npy'); tr=[]; ptr=[0]
with (R/'_p0pilot/seed42_nc_ablation_20261109/CONE_CACHE_TEST.csv').open(encoding='utf-8-sig',newline='') as f:
    for r0 in csv.DictReader(f):
        if r0['kind'] not in ('D','PO') or int(r0['label'])<0 or int(r0['n_phys'])<2: continue
        mem=[int(z) for z in r0['phys_rows'].split('|') if z]
        if len(mem)>=2: tr.extend(mem); ptr.append(len(tr))
xt=ctx(tx,tr,ptr)
np.savez_compressed(OUT/'cone_context_assets.npz',train_x=xtr,val_x=xv,test_x=xt)
print(xtr.shape,xv.shape,xt.shape)
