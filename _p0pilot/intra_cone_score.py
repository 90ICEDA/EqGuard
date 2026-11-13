import os,sys,json
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'): os.environ[k]='1'
os.environ['P2B_MASK']='old'
from pathlib import Path
import numpy as np, torch
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); L=R/'_p0pilot/control_loader_po_20261105'; OLD=R/'_p0pilot/seed42_nc_ablation_20261109'
sys.path.insert(0,str(L)); sys.path.insert(0,str(R/'_p0pilot/control_best200_20261104')); sys.path.insert(0,str(OLD))
from evaluate import Model
g=np.load(R/'_p0pilot/four_group_contract_20261109/group_B.npz'); c=np.load(R/'_p0pilot/lcone_relaxed_20261111/cones_relaxed_D.npz')
x=np.array(g['x'],np.float32,copy=True); mean=x[:,25:].mean(0); std=x[:,25:].std(0); std=np.where(std<1e-6,1,std); x[:,25:]=np.clip((x[:,25:]-mean)/std,-10,10)
x=torch.as_tensor(x,device='cuda'); e=torch.as_tensor(g['edge'],device='cuda')
m=Model().cuda(); m.load_state_dict(torch.load(R/'_p0pilot/lcone_relaxed_20261111/_tmp_s42.pt',map_location='cuda',weights_only=True)); m.eval()
with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):
 s=(m(x,e).float()[:,1]-m(x,e).float()[:,0]).cpu().numpy()
y=g['y']; tr=g['trusted']
rows=c['rows']; ptr=c['ptr']; lab=c['label']; pos=[]
for i in range(len(lab)):
 if lab[i]!=1: continue
 mem=rows[ptr[i]:ptr[i+1]]; yy=y[mem]; tt=tr[mem]; ps=s[mem][(yy==1)&tt]; ns=s[mem][(yy==0)&tt]
 if len(ps)==0 or len(ns)==0: continue
 order=np.argsort(-s[mem]); top=yy[order[:3]]; top1=bool(yy[order[0]]==1)
 pos.append(dict(n=len(mem),p=len(ps),nneg=len(ns),gap=float(ps.mean()-ns.mean()),top1=top1,top3=float(top.sum()/max(1,len(top))),top3n=int(len(top))))
out=dict(npos=len(pos),mean_members=float(np.mean([p['n'] for p in pos])),mean_gap=float(np.mean([p['gap'] for p in pos])),
 top1=float(np.mean([p['top1'] for p in pos])),top3_precision=float(np.mean([p['top3'] for p in pos])),
 pos_above_neg=float(np.mean([p['gap']>0 for p in pos])))
json.dump(out,open(R/'_p0pilot/lcone_relaxed_20261111/INTRA_POS_CONE_SCORE.json','w'),indent=2); print(json.dumps(out,indent=2))
