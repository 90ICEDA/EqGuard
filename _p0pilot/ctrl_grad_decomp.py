"""Gradient decomposition: positive vs negative cone loss at best checkpoints."""
import os, sys, json
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'): os.environ[k]='1'
os.environ['P2B_MASK']='old'
from pathlib import Path
import numpy as np, torch
import torch.nn.functional as F
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FG=R/'_p0pilot/four_group_contract_20261109'
B=R/'_p0pilot/control_boundary_v3_20261104'; L=R/'_p0pilot/control_loader_po_20261105'; OUT=R/'_p0pilot/lcone_trainctl_20261110'
sys.path.insert(0,str(L)); sys.path.insert(0,str(R/'_p0pilot/control_best200_20261104')); sys.path.insert(0,str(R/'_p0pilot/seed42_nc_ablation_20261109'))
from evaluate import Model,T
from supervision_loader import FiveGroupLoader
g=np.load(FG/'group_B.npz'); sup=np.load(FG/'sup_B.npz'); mean,std=g['mean'],g['std']
def norm(x):
 o=np.array(x,np.float32,copy=True); o[:,25:]=np.clip((o[:,25:]-mean)/std,-10,10); return o
x=torch.as_tensor(norm(g['x']),device='cuda'); e=torch.as_tensor(g['edge'],device='cuda'); y=torch.as_tensor(g['y'],device='cuda')
c=np.load(OUT/'cones_ctrlall_D.npz'); ct=dict(rows=list(range(len(c['label']))),idx=torch.as_tensor(c['rows'],device='cuda'),
 seg=torch.repeat_interleave(torch.arange(len(c['label']),device='cuda'),torch.as_tensor(np.diff(c['ptr']),device='cuda')),
 lab=torch.as_tensor(c['label'],dtype=torch.float32,device='cuda'))
def flat(gs): return torch.cat([q.reshape(-1) for q in gs if q is not None])
res={}
for name,path,mode in (('ctrlall',OUT/'run_ctrlall_s1_lam0.1/best_resume.pt','max'),('ctrlmean',OUT/'run_ctrlmean_s1_lam0.1/best_resume.pt','mean')):
 ck=torch.load(path,map_location='cuda',weights_only=False); m=Model().cuda(); m.load_state_dict(ck['model']); m.train(); params=[p for p in m.parameters() if p.requires_grad]
 with torch.autocast('cuda',dtype=torch.bfloat16):
  lt=m(x,e); l_t=T.domain_loss(lt,y,torch.as_tensor(sup['idx'][0],device='cuda')); mar=lt.float()[:,1]-lt.float()[:,0]
  n=len(c['label']); cmax=torch.full((n,),-1e9,device='cuda'); cmax.scatter_reduce_(0,ct['seg'],mar.index_select(0,ct['idx']),reduce='amax',include_self=True)
  sums=torch.zeros(n,device='cuda').index_add_(0,ct['seg'],mar.index_select(0,ct['idx'])); counts=torch.bincount(ct['seg'],minlength=n).clamp_min(1); cmean=sums/counts
  pos=ct['lab']==1; neg=~pos
  lp=F.binary_cross_entropy_with_logits(cmax[pos],torch.ones_like(cmax[pos]),pos_weight=torch.tensor(10.0,device='cuda'))
  ln=F.binary_cross_entropy_with_logits((cmax[neg] if mode=='max' else cmean[neg]),torch.zeros_like(cmax[neg] if mode=='max' else cmean[neg]))
 gn=flat(torch.autograd.grad(l_t,params,retain_graph=True,allow_unused=True)); gp=flat(torch.autograd.grad(lp,params,retain_graph=True,allow_unused=True)); gq=flat(torch.autograd.grad(ln,params,retain_graph=True,allow_unused=True))
 res[name]=dict(node_norm=float(gn.norm()),pos_norm=float(gp.norm()),neg_norm=float(gq.norm()),pos_over_node=float(gp.norm()/gn.norm()),neg_over_node=float(gq.norm()/gn.norm()),neg_over_pos=float(gq.norm()/gp.norm()),loss_node=float(l_t),loss_pos=float(lp),loss_neg=float(ln),mode=mode)
 del m; torch.cuda.empty_cache()
(OUT/'GRAD_DECOMP.json').write_text(json.dumps(res,indent=2),encoding='utf-8')
print(json.dumps(res,ensure_ascii=False))
