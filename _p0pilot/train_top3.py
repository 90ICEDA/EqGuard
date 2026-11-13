"""L_cone max + top3 listwise/ranking loss, 3 seeds."""
import os,sys,json
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'): os.environ[k]='1'
os.environ['P2B_MASK']='old'
from pathlib import Path
import numpy as np, torch, torch.nn.functional as F
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FG=R/'_p0pilot/four_group_contract_20261109'; OUT=R/'_p0pilot/lcone_relaxed_20261111'; B=R/'_p0pilot/control_boundary_v3_20261104'
sys.path.insert(0,str(R/'_p0pilot/control_loader_po_20261105')); sys.path.insert(0,str(R/'_p0pilot/control_best200_20261104')); sys.path.insert(0,str(R/'_p0pilot/seed42_nc_ablation_20261109'))
from supervision_loader import FiveGroupLoader
from evaluate import Model,T
import cone_loss as CL
from sklearn.metrics import average_precision_score
seed=int(sys.argv[1]); gamma=float(sys.argv[2]) if len(sys.argv)>2 else 0.01; lam=0.01
g=np.load(FG/'group_B.npz'); c=np.load(OUT/'cones_relaxed_D.npz'); sup=np.load(FG/'sup_B.npz'); val=np.load(FG/'val_common.npz'); mean,std=g['mean'],g['std']
def norm(x):
 o=np.array(x,np.float32,copy=True); o[:,25:]=np.clip((o[:,25:]-mean)/std,-10,10); return o
x=torch.as_tensor(norm(g['x']),device='cuda'); e=torch.as_tensor(g['edge'],device='cuda'); y=torch.as_tensor(g['y'].astype(np.int64),device='cuda'); tr=torch.as_tensor(g['trusted'],device='cuda')
vx=torch.as_tensor(val['x'],device='cuda'); ve=torch.as_tensor(val['edge'],device='cuda')
xo=torch.as_tensor(norm(np.load(B/'inputs/orig_train/x39.npy')),device='cuda'); eo=torch.as_tensor(np.load(B/'inputs/orig_train/edge_index.npy'),device='cuda'); yo=torch.as_tensor(np.load(B/'inputs/orig_train/y.npy').astype(np.int64),device='cuda')
ct=dict(rows=list(range(len(c['label']))),idx=torch.as_tensor(c['rows'],device='cuda'),seg=torch.repeat_interleave(torch.arange(len(c['label']),device='cuda'),torch.as_tensor(np.diff(c['ptr']),device='cuda')),lab=torch.as_tensor(c['label'],dtype=torch.float32,device='cuda'))
ptr=c['ptr']; rr=c['rows']
def top3_loss(logits):
 m=(logits.float()[:,1]-logits.float()[:,0]); vals=[]
 for i in range(len(c['label'])):
  if int(c['label'][i])!=1: continue
  mem=rr[ptr[i]:ptr[i+1]]; mi=m[mem]; yy=y[mem]; tt=tr[mem]; pp=mi[(yy==1)&tt]; nn=mi[(yy==0)&tt]
  if len(pp)==0 or len(nn)==0: continue
  k=min(3,len(pp)); posk=torch.topk(pp,k).values[-1]; negmax=nn.max()
  vals.append(F.relu(negmax-posk+gamma))
 return torch.stack(vals).mean() if vals else torch.tensor(0.,device='cuda')
loader=FiveGroupLoader(); T.seed(seed); m=Model().cuda(); m.load_state_dict(torch.load(R/f'_p0pilot/control_v3_eligible_20261104/init_s{seed}.pt',map_location='cuda',weights_only=True)); opt=torch.optim.Adam(m.parameters(),lr=2e-4,weight_decay=1e-3)
outdir=OUT/f'run_top3_s{seed}'; outdir.mkdir(exist_ok=True); logs=[]; best=dict(score=-1,step=-1,state=None)
for step in range(200):
 T.seed(seed+step); m.train(); opt.zero_grad(set_to_none=True)
 io=np.array(loader.step('orig','G0',step).indices,copy=True)
 with torch.autocast('cuda',dtype=torch.bfloat16): lo=m(xo,eo); l_o=T.domain_loss(lo,yo,torch.as_tensor(io,device='cuda'))
 l_o.backward()
 with torch.autocast('cuda',dtype=torch.bfloat16):
  lt=m(x,e); l_t=T.domain_loss(lt,y,torch.as_tensor(sup['idx'][step],device='cuda')); l_c=CL.cone_loss(lt,ct,10.0); l_3=top3_loss(lt); loss=l_t+lam*l_c+gamma*l_3
 loss.backward(); gn=float(torch.nn.utils.clip_grad_norm_(m.parameters(),1.0)); opt.step(); rec=dict(step=step+1,l_o=float(l_o),l_t=float(l_t),l_c=float(l_c),l_3=float(l_3),gamma=gamma,grad=gn,finite=bool(np.isfinite(float(l_o)) and np.isfinite(float(l_t)) and np.isfinite(float(l_c)) and np.isfinite(float(l_3)) and np.isfinite(gn))); assert rec['finite']; logs.append(rec)
 if (step+1)%5==0 or step==199:
  m.eval()
  with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16): lg=m(vx,ve).float(); s=(lg[:,1]-lg[:,0]).cpu().numpy()
  c2=json.load(open(B/'input_contract.json',encoding='utf-8')); vv={z['view']:z for z in c2['shared_inputs']['trans_val']['views']}; aps=[]
  for v in val['views']:
   lay=vv[str(v)]; a,b=np.searchsorted(val['rows'],[lay['start'],lay['stop']]); yy,tt,ss=val['y'][a:b],val['trusted'][a:b],s[a:b]
   if len(np.unique(yy[tt]))>1: aps.append(average_precision_score(yy[tt],ss[tt]))
  ap=float(np.mean(aps)) if aps else None; logs[-1]['val_ap']=ap
  if ap is not None and ap>best['score']: best=dict(score=ap,step=step+1,state={k:v.detach().cpu().clone() for k,v in m.state_dict().items()})
outdir.joinpath('LOG.json').write_text(json.dumps(dict(seed=seed,gamma=gamma,best_step=best['step'],best_score=best['score'],logs=logs),indent=2),encoding='utf-8'); torch.save(dict(model=best['state'],best_step=best['step'],seed=seed),outdir/'best_resume.pt')
print('DONE',seed,best['step'],best['score'],flush=True)
