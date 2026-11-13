import os,sys,json
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'): os.environ[k]='1'
os.environ['P2B_MASK']='old'
from pathlib import Path
import numpy as np, torch, torch.nn.functional as F
from sklearn.metrics import average_precision_score
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); L=R/'_p0pilot/control_loader_po_20261105'; OLD=R/'_p0pilot/seed42_nc_ablation_20261109'
sys.path.insert(0,str(L)); sys.path.insert(0,str(R/'_p0pilot/control_best200_20261104')); sys.path.insert(0,str(OLD))
from evaluate import Model
g=np.load(R/'_p0pilot/four_group_contract_20261109/group_B.npz'); c=np.load(R/'_p0pilot/lcone_relaxed_20261111/cones_relaxed_D.npz')
x=np.array(g['x'],np.float32,copy=True); mean=x[:,25:].mean(0); std=x[:,25:].std(0); std=np.where(std<1e-6,1,std); x[:,25:]=np.clip((x[:,25:]-mean)/std,-10,10)
x=torch.as_tensor(x,device='cuda'); e=torch.as_tensor(g['edge'],device='cuda'); rows=c['rows']; ptr=c['ptr']; lab=c['label']
def score(ck):
 m=Model().cuda(); m.load_state_dict(torch.load(ck,map_location='cuda',weights_only=False)['model']); m.eval()
 with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16): s=(m(x,e).float()[:,1]-m(x,e).float()[:,0]).cpu().numpy()
 mx=np.array([s[rows[ptr[i]:ptr[i+1]]].max() for i in range(len(lab))]); mn=np.array([s[rows[ptr[i]:ptr[i+1]]].min() for i in range(len(lab))])
 loss=F.binary_cross_entropy_with_logits(torch.tensor(mx),torch.tensor(lab,dtype=torch.float32),pos_weight=torch.tensor(10.)).item()
 pos=mx[lab==1]; neg=mx[lab==0]; pp=[]
 for i in range(len(lab)):
  if lab[i]!=1: continue
  mem=rows[ptr[i]:ptr[i+1]]; yy=g['y'][mem]; tt=g['trusted'][mem]; ps=s[mem][(yy==1)&tt]; ns=s[mem][(yy==0)&tt]
  if len(ps)==0 or len(ns)==0: continue
  order=np.argsort(-s[mem]); top=yy[order[:3]]; pp.append((ps.mean()-ns.mean(), bool(yy[order[0]]==1), top.sum()/len(top)))
 return dict(loss=loss,ap=float(average_precision_score(lab,mx)),pos_mean=float(pos.mean()),neg_mean=float(neg.mean()),gap=float(pos.mean()-neg.mean()),within_std=float((mx-mn).mean()),
  intra_n=len(pp),intra_gap=float(np.mean([p[0] for p in pp])),top1=float(np.mean([p[1] for p in pp])),top3=float(np.mean([p[2] for p in pp])))
out={}
for lam in ('0.03','0.1'):
 out[lam]=score(R/f'_p0pilot/lcone_relaxed_20261111/run_relaxed_s42_lam{lam}/best_resume.pt')
json.dump(out,open(R/'_p0pilot/lcone_relaxed_20261111/CONE_SCORE_DIAG_LAM.json','w'),indent=2); print(json.dumps(out,indent=2))
