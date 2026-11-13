"""Control FPR at init/best/last for control-negative runs."""
import os, sys, csv, json, collections
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'): os.environ[k]='1'
os.environ['P2B_MASK']='old'
from pathlib import Path
import numpy as np, torch
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FG=R/'_p0pilot/four_group_contract_20261109'
B=R/'_p0pilot/control_boundary_v3_20261104'; OLD=R/'_p0pilot/seed42_nc_ablation_20261109'
OUT=R/'_p0pilot/lcone_testctl_20261110'
sys.path.insert(0,str(R/'_p0pilot/control_best200_20261104'))
from evaluate import Model
c=json.loads((B/'input_contract.json').read_text(encoding='utf-8'))
vs={v['view']:v for v in c['shared_inputs']['trans_test']['views']}
f=B/'inputs/trans_test'; x=np.load(f/'x39.npy'); edge=np.load(f/'edge_index.npy'); y=np.load(f/'y.npy'); tr=np.load(f/'trusted.npy'); ph=np.load(f/'physical.npy')
rows=np.concatenate([np.arange(vs[v]['start'],vs[v]['stop']) for v in vs]); o2n=np.full(len(y),-1,np.int64); o2n[rows]=np.arange(len(rows)); m=(o2n[edge[0]]>=0)&(o2n[edge[1]]>=0)
val=np.load(FG/'val_common.npz'); mean,std=val['mean'],val['std']; xx=np.array(x[rows],np.float32,copy=True); xx[:,25:]=np.clip((xx[:,25:]-mean)/std,-10,10)
tx=torch.as_tensor(xx,device='cuda'); te=torch.as_tensor(np.stack([o2n[edge[0][m]],o2n[edge[1][m]]]),device='cuda')
loc={r:i for i,r in enumerate(rows.tolist())}; cones=[]; view_members=collections.defaultdict(set)
with (OLD/'CONE_CACHE_TEST.csv').open(encoding='utf-8-sig',newline='') as fh:
    for r in csv.DictReader(fh):
        if 'ctl' not in r['view'] or r['kind'] not in ('D','PO') or int(r['n_phys'])<2: continue
        mem=[]
        for z in r['phys_rows'].split('|'):
            if not z: continue
            i=loc.get(int(z))
            if i is not None and ph[i]: mem.append(i)
        if len(mem)>=2: cones.append(np.array(mem)); view_members[r['view']].update(mem)
pos=np.where(tr&ph&(y==1))[0]; neg=np.where(tr&ph&(y==0))[0]; thr=float(np.quantile(np.load(FG/'run_B_N/best_testpred.npz')['scores'][pos],0.05))
def metrics(s):
    hit=[]; 
    for mem in cones:
        sc=s[mem]; n=int((sc>=thr).sum());
        if n: hit.append((float(sc.max()),n,len(mem)))
    fp=sum(1 for mem in view_members.values() for i in mem if s[i]>=thr)
    nodes=sum(len(v) for v in view_members.values())
    return dict(fpr=round(fp/nodes,4),hit_frac=round(len(hit)/len(cones),4),mean_max=round(float(np.mean([h[0] for h in hit])),3) if hit else None,
                hit_one_frac=round(sum(1 for h in hit if h[1]==1)/len(hit),4) if hit else None,hit_nhigh=round(float(np.mean([h[1] for h in hit])),2) if hit else None,
                alarm_views=sum(1 for mem in view_members.values() if max(s[i] for i in mem)>=thr))
models={
 'init_s1':R/'_p0pilot/control_v3_eligible_20261104/init_s1.pt',
 'NB_best':FG/'run_B_N/best_resume.pt',
 'ctrlall_best':R/'_p0pilot/lcone_trainctl_20261110/run_ctrlall_s1_lam0.1/best_resume.pt',
 'ctrlall_last':R/'_p0pilot/lcone_trainctl_20261110/run_ctrlall_s1_lam0.1/last_resume.pt',
 'ctrlmean_best':R/'_p0pilot/lcone_trainctl_20261110/run_ctrlmean_s1_lam0.1/best_resume.pt',
 'ctrlmean_last':R/'_p0pilot/lcone_trainctl_20261110/run_ctrlmean_s1_lam0.1/last_resume.pt',
}
res={}
for name,path in models.items():
    ck=torch.load(path,map_location='cuda',weights_only=False); model=Model().cuda(); model.load_state_dict(ck['model'] if 'model' in ck else ck); model.eval()
    with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):
        lg=model(tx,te).float(); s=(lg[:,1]-lg[:,0]).cpu().numpy()
    res[name]=metrics(s); print(name,res[name])
(OUT/'CONTROL_FPR_TRAJ.json').write_text(json.dumps(res,indent=2),encoding='utf-8')
