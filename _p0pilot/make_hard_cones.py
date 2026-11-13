"""Build hard-cone subset from N-B scores; save npz."""
import os, sys, json
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'): os.environ[k]='1'
os.environ['P2B_MASK']='old'
from pathlib import Path
import numpy as np, torch
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FG=R/'_p0pilot/four_group_contract_20261109'
V2=R/'_p0pilot/lcone_v2c_20261110'; OUT=R/'_p0pilot/lcone_directions_20261110'; OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(R/'_p0pilot/control_loader_po_20261105')); sys.path.insert(0,str(R/'_p0pilot/control_best200_20261104'))
from evaluate import Model
g=np.load(FG/'group_B.npz'); mean,std=g['mean'],g['std']
def norm(x):
    o=np.array(x,np.float32,copy=True); o[:,25:]=np.clip((o[:,25:]-mean)/std,-10,10); return o
x=torch.as_tensor(norm(g['x']),device='cuda'); e=torch.as_tensor(g['edge'],device='cuda')
ck=torch.load(FG/'run_B_N/best_resume.pt',map_location='cuda',weights_only=False)
m=Model().cuda(); m.load_state_dict(ck['model']); m.eval()
with torch.inference_mode(), torch.autocast('cuda',dtype=torch.bfloat16):
    lg=m(x,e).float(); s=(lg[:,1]-lg[:,0]).cpu().numpy()
c=np.load(V2/'cones_v2c_all_D.npz'); rows,ptr,lab,view=c['rows'],c['ptr'],c['label'],c['view']
score=np.array([s[rows[ptr[i]:ptr[i+1]]].max() for i in range(len(lab))])
pos=np.where(lab==1)[0]; neg=np.where(lab==0)[0]
# hard: lowest 25% positives, highest 25% negatives (279/279 approx)
n=min(len(pos),len(neg))//2
sel_pos=pos[np.argsort(score[pos])[:n]]; sel_neg=neg[np.argsort(-score[neg])[:n]]
sel=np.concatenate([sel_pos,sel_neg])
flat=[]; p=[0]; labels=[]; views=[]
for i in sel:
    flat.extend(rows[ptr[i]:ptr[i+1]].tolist()); p.append(len(flat)); labels.append(int(lab[i])); views.append(str(view[i]))
np.savez_compressed(OUT/'cones_hard_D.npz',rows=np.array(flat,np.int64),ptr=np.array(p,np.int64),label=np.array(labels,np.int8),view=np.array(views))
json.dump(dict(n=n,total=len(sel),pos=int(n),neg=int(n),selection='lowest pos / highest neg by N-B max score'),open(OUT/'HARD_CONES.json','w'))
print(json.dumps(dict(n=n,total=len(sel),pos=int(n),neg=int(n))))
