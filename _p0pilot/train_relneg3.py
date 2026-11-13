"""Relative top3 margin compression, q50 anchor, two-stage, val node+cone selection, 3 seeds."""
import os,sys,json
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'): os.environ[k]='1'
os.environ['P2B_MASK']='old'
from pathlib import Path
import numpy as np, torch, torch.nn.functional as F
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FG=R/'_p0pilot/four_group_contract_20261109'; OUT=R/'_p0pilot/lcone_relaxed_20261111'; B=R/'_p0pilot/control_boundary_v3_20261104'
sys.path.insert(0,str(R/'_p0pilot/control_loader_po_20261105')); sys.path.insert(0,str(R/'_p0pilot/control_best200_20261104')); sys.path.insert(0,str(R/'_p0pilot/seed42_nc_ablation_20261109'))
from supervision_loader import FiveGroupLoader
from evaluate import Model,T
from sklearn.metrics import average_precision_score
seed=int(sys.argv[1]); beta=0.05; margin=0.5; warm=100
g=np.load(FG/'group_B.npz'); c=np.load(OUT/'cones_relaxed_D.npz'); sup=np.load(FG/'sup_B.npz'); val=np.load(FG/'val_common.npz'); mean,std=g['mean'],g['std']
def norm(x):
 o=np.array(x,np.float32,copy=True); o[:,25:]=np.clip((o[:,25:]-mean)/std,-10,10); return o
x=torch.as_tensor(norm(g['x']),device='cuda'); e=torch.as_tensor(g['edge'],device='cuda'); y=torch.as_tensor(g['y'].astype(np.int64),device='cuda')
vx=torch.as_tensor(val['x'],device='cuda'); ve=torch.as_tensor(val['edge'],device='cuda')
xo=torch.as_tensor(norm(np.load(B/'inputs/orig_train/x39.npy')),device='cuda'); eo=torch.as_tensor(np.load(B/'inputs/orig_train/edge_index.npy'),device='cuda'); yo=torch.as_tensor(np.load(B/'inputs/orig_train/y.npy').astype(np.int64),device='cuda')
rows=torch.as_tensor(c['rows'],device='cuda'); seg=torch.repeat_interleave(torch.arange(len(c['label']),device='cuda'),torch.as_tensor(np.diff(c['ptr']),device='cuda')); lab=torch.as_tensor(c['label'],dtype=torch.float32,device='cuda')
vc=np.load(OUT/'val_cones_D.npz'); vrows=torch.as_tensor(vc['rows'],device='cuda'); vseg=torch.repeat_interleave(torch.arange(len(vc['label']),device='cuda'),torch.as_tensor(np.diff(vc['ptr']),device='cuda')); vlab=torch.as_tensor(vc['label'],dtype=torch.float32,device='cuda')
def cone_scores(logits):
 m=(logits.float()[:,1]-logits.float()[:,0]); v=m.index_select(0,rows)
 mx=torch.full((len(lab),),-1e9,device='cuda'); mx.scatter_reduce_(0,seg,v,reduce='amax')
 return m,v,mx
def top3_mean(v,mx):
 mask=(v==mx[seg]); v1=v.masked_fill(mask,-1e9); m2=torch.full((len(lab),),-1e9,device='cuda'); m2.scatter_reduce_(0,seg,v1,reduce='amax')
 mask2=(v1==m2[seg]); v2=v1.masked_fill(mask2,-1e9); m3=torch.full((len(lab),),-1e9,device='cuda'); m3.scatter_reduce_(0,seg,v2,reduce='amax')
 cnt=torch.bincount(seg,minlength=len(lab)).float(); m3=torch.where(cnt>=3,m3,torch.zeros_like(m3))
 return (mx+m2+m3)/torch.clamp(cnt,max=3)
def losses(logits):
 m,v,mx=cone_scores(logits); bce=F.binary_cross_entropy_with_logits(mx,lab,pos_weight=torch.tensor(10.,device='cuda'))
 anchor=torch.quantile(mx[lab==1],0.25); t3=top3_mean(v,mx); comp=F.relu(t3[lab==0]-anchor+margin).mean()
 return bce,comp,mx,anchor
def val_cone_ap(logits):
 m=(logits.float()[:,1]-logits.float()[:,0]); vv=m.index_select(0,vrows); mx=torch.full((len(vlab),),-1e9,device='cuda'); mx.scatter_reduce_(0,vseg,vv,reduce='amax')
 return average_precision_score(vlab.cpu().numpy(),mx.cpu().numpy())
loader=FiveGroupLoader(); T.seed(seed); m=Model().cuda(); m.load_state_dict(torch.load(R/f'_p0pilot/control_v3_eligible_20261104/init_s{seed}.pt',map_location='cuda',weights_only=True)); opt=torch.optim.Adam(m.parameters(),lr=2e-4,weight_decay=1e-3)
outdir=OUT/f'run_relneg3_s{seed}'; outdir.mkdir(exist_ok=True); logs=[]; best=dict(score=-1,step=-1,state=None)
for step in range(200):
 T.seed(seed+step); m.train(); opt.zero_grad(set_to_none=True)
 io=np.array(loader.step('orig','G0',step).indices,copy=True)
 with torch.autocast('cuda',dtype=torch.bfloat16): lo=m(xo,eo); l_o=T.domain_loss(lo,yo,torch.as_tensor(io,device='cuda'))
 l_o.backward()
 with torch.autocast('cuda',dtype=torch.bfloat16): lt=m(x,e); l_t=T.domain_loss(lt,y,torch.as_tensor(sup['idx'][step],device='cuda')); l_bce,l_comp,mx,anchor=losses(lt); loss=l_t+0.01*l_bce+(beta*l_comp if step<warm else 0.0)
 loss.backward(); gn=float(torch.nn.utils.clip_grad_norm_(m.parameters(),1.0)); opt.step(); nm=mx[lab==0].detach(); rec=dict(step=step+1,l_o=float(l_o),l_t=float(l_t),bce=float(l_bce),comp=float(l_comp),anchor=float(anchor),negmax_mean=float(nm.mean()),negmax_p90=float(torch.quantile(nm,.9)),grad=gn,finite=bool(np.isfinite(float(l_o)) and np.isfinite(float(l_t)) and np.isfinite(float(l_bce)) and np.isfinite(float(l_comp)) and np.isfinite(gn))); assert rec['finite']; logs.append(rec)
 if (step+1)%5==0 or step==199:
  m.eval()
  with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16): lg=m(vx,ve).float(); sv=(lg[:,1]-lg[:,0]).cpu().numpy()
  c2=json.load(open(B/'input_contract.json',encoding='utf-8')); vv={z['view']:z for z in c2['shared_inputs']['trans_val']['views']}; aps=[]
  for v in val['views']:
   lay=vv[str(v)]; a,b=np.searchsorted(val['rows'],[lay['start'],lay['stop']]); yy,tt,ss=val['y'][a:b],val['trusted'][a:b],sv[a:b]
   if len(np.unique(yy[tt]))>1: aps.append(average_precision_score(yy[tt],ss[tt]))
  nap=float(np.mean(aps)) if aps else None
  cap=float(val_cone_ap(lg)) if nap is not None else None; score=nap+0.3*cap if (nap is not None and cap is not None) else None
  logs[-1]['val_ap']=nap; logs[-1]['val_cone_ap']=cap
  if score is not None and score>best['score']: best=dict(score=score,step=step+1,state={k:v.detach().cpu().clone() for k,v in m.state_dict().items()},nap=nap,cap=cap)
outdir.joinpath('LOG.json').write_text(json.dumps(dict(seed=seed,best_step=best['step'],best_score=best['score'],logs=logs),indent=2),encoding='utf-8'); torch.save(dict(model=best['state'],best_step=best['step'],seed=seed),outdir/'best_resume.pt')
print('DONE',seed,best['step'],best['score'],flush=True)
