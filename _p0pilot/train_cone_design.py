"""Cone design variants: lse, lse+node aux, lse+node aux+rank. seed42."""
import os,sys,json
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'): os.environ[k]='1'
os.environ['P2B_MASK']='old'
from pathlib import Path
import numpy as np, torch, torch.nn.functional as F
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FG=R/'_p0pilot/four_group_contract_20261109'; OUT=R/'_p0pilot/lcone_relaxed_20261111'; B=R/'_p0pilot/control_boundary_v3_20261104'; L=R/'_p0pilot/control_loader_po_20261105'
sys.path.insert(0,str(L)); sys.path.insert(0,str(R/'_p0pilot/control_best200_20261104')); sys.path.insert(0,str(R/'_p0pilot/seed42_nc_ablation_20261109'))
from supervision_loader import FiveGroupLoader
from evaluate import Model,T
import cone_loss as CL
from sklearn.metrics import average_precision_score
variant=sys.argv[1]; seed=int(sys.argv[2]); lam=float(sys.argv[3]) if len(sys.argv)>3 else 0.01; beta=float(sys.argv[4]) if len(sys.argv)>4 else 0.1; gamma=float(sys.argv[5]) if len(sys.argv)>5 else 0.05; tau=float(sys.argv[6]) if len(sys.argv)>6 else 0.5
posmax = ('posmax' in variant)
auxpos = ('auxpos' in variant)
posonly = ('posonly' in variant)
top1rank = ('top1rank' in variant)
g=np.load(FG/'group_B.npz'); c=np.load(OUT/'cones_relaxed_D.npz'); sup=np.load(FG/'sup_B.npz'); val=np.load(FG/'val_common.npz')
mean,std=g['mean'],g['std']
def norm(x):
 o=np.array(x,np.float32,copy=True); o[:,25:]=np.clip((o[:,25:]-mean)/std,-10,10); return o
x=torch.as_tensor(norm(g['x']),device='cuda'); e=torch.as_tensor(g['edge'],device='cuda'); y=torch.as_tensor(g['y'],device='cuda'); tr=torch.as_tensor(g['trusted'],device='cuda'); ph=torch.as_tensor(g['physical'],device='cuda')
vx=torch.as_tensor(val['x'],device='cuda'); ve=torch.as_tensor(val['edge'],device='cuda')
xo=torch.as_tensor(norm(np.load(B/'inputs/orig_train/x39.npy')),device='cuda'); eo=torch.as_tensor(np.load(B/'inputs/orig_train/edge_index.npy'),device='cuda'); yo=torch.as_tensor(np.load(B/'inputs/orig_train/y.npy'),device='cuda')
rows=torch.as_tensor(c['rows'],device='cuda'); seg=torch.repeat_interleave(torch.arange(len(c['label']),device='cuda'),torch.as_tensor(np.diff(c['ptr']),device='cuda')); lab=torch.as_tensor(c['label'],dtype=torch.float32,device='cuda'); cnt=torch.bincount(seg,minlength=len(lab)).float()
ct=dict(rows=list(range(len(c['label']))),idx=rows,seg=seg,lab=lab)
vc=np.load(OUT/'val_cones_D.npz'); vrows=torch.as_tensor(vc['rows'],device='cuda'); vseg=torch.repeat_interleave(torch.arange(len(vc['label']),device='cuda'),torch.as_tensor(np.diff(vc['ptr']),device='cuda')); vlab=torch.as_tensor(vc['label'],dtype=torch.float32,device='cuda')
def cone_loss_lse(logits):
 m=(logits.float()[:,1]-logits.float()[:,0]); v=m.index_select(0,rows)
 if posonly:
  pm=((y[rows]==1)&tr[rows]).float(); ex=torch.exp(v/tau)*pm
  s=torch.zeros(len(lab),device='cuda').index_add_(0,seg,ex)
  cp=torch.zeros(len(lab),device='cuda').index_add_(0,seg,pm)
  fallback=torch.zeros(len(lab),device='cuda').index_add_(0,seg,torch.exp(v/tau)); fallback=tau*torch.log(fallback/cnt)
  has=cp>0
  lse=tau*torch.log(torch.clamp(s,min=1e-12)/torch.clamp(cp,min=1))
  s=torch.where(has,lse,fallback)
  mx=torch.full((len(lab),),-1e9,device='cuda'); mx.scatter_reduce_(0,seg,v,reduce='amax')
  s=torch.where(lab==1,s,mx)
 else:
  ex=torch.exp(v/tau); s=torch.zeros(len(lab),device='cuda').index_add_(0,seg,ex); s=tau*(torch.log(s/cnt))
  if posmax:
   mx=torch.full((len(lab),),-1e9,device='cuda'); mx.scatter_reduce_(0,seg,v,reduce='amax')
   s=torch.where(lab==1,s,mx)
 return F.binary_cross_entropy_with_logits(s,lab,pos_weight=torch.tensor(10.,device='cuda'))
def node_aux(logits):
 m=(logits.float()[:,1]-logits.float()[:,0])
 if auxpos:
  sel=rows[(tr[rows])&(ph[rows])&(y[rows]==1)]
 else:
  sel=rows[(tr[rows])&(ph[rows])]
 if len(sel)==0: return torch.tensor(0.,device='cuda')
 return F.binary_cross_entropy_with_logits(m[sel],y[sel].float())
def val_cone_ap(logits):
 m=(logits.float()[:,1]-logits.float()[:,0]); vv=m.index_select(0,vrows)
 mx=torch.full((len(vlab),),-1e9,device='cuda'); mx.scatter_reduce_(0,vseg,vv,reduce='amax')
 return average_precision_score(vlab.cpu().numpy(),mx.cpu().numpy())
def rank_loss(logits):

 m=(logits.float()[:,1]-logits.float()[:,0]); ps=[]
 for i in range(len(lab)):
  if lab[i].item()!=1: continue
  mem=rows[c['idx'][i]:c['idx'][i+1]] if False else None
 # need ptr; use c ptr numpy
 ptr=c['ptr']; rr=c['rows']; vals=[]
 for i in range(len(lab)):
  if lab[i].item()!=1: continue
  mem=rr[ptr[i]:ptr[i+1]]; mi=m[mem]; yy=y[mem]; tt=tr[mem]; pp=mi[(yy==1)&tt]; nn=mi[(yy==0)&tt]
  if len(pp) and len(nn):
   if top1rank: vals.append(F.relu(nn.max()-pp.max()+gamma))
   else: vals.append(F.relu(nn[:,None]-pp[None,:]+gamma).mean())
 return torch.stack(vals).mean() if vals else torch.tensor(0.,device='cuda')
loader=FiveGroupLoader(); T.seed(seed); model=Model().cuda(); model.load_state_dict(torch.load(R/f'_p0pilot/control_v3_eligible_20261104/init_s{seed}.pt',map_location='cuda',weights_only=True)); opt=torch.optim.Adam(model.parameters(),lr=2e-4,weight_decay=1e-3)
outdir=OUT/f'run_design_{variant}_lam{lam}_s{seed}'; outdir.mkdir(exist_ok=True); logs=[]; best=dict(score=-1,step=-1,state=None,opt=None)
for step in range(200):
 T.seed(seed+step); model.train(); opt.zero_grad(set_to_none=True)
 io=np.array(loader.step('orig','G0',step).indices,copy=True)
 with torch.autocast('cuda',dtype=torch.bfloat16):
  lo=model(xo,eo); l_o=T.domain_loss(lo,yo,torch.as_tensor(io,device='cuda'))
 l_o.backward()
 with torch.autocast('cuda',dtype=torch.bfloat16):
  lt=model(x,e); l_t=T.domain_loss(lt,y,torch.as_tensor(sup['idx'][step],device='cuda'))
  l_c=cone_loss_lse(lt); l_a=node_aux(lt) if 'aux' in variant else torch.tensor(0.,device='cuda'); l_r=rank_loss(lt) if 'rank' in variant else torch.tensor(0.,device='cuda')
  loss=l_t+lam*l_c+beta*l_a+gamma*l_r
 loss.backward(); gn=float(torch.nn.utils.clip_grad_norm_(model.parameters(),1.0)); opt.step()
 rec=dict(step=step+1,node_orig=float(l_o),node_trans=float(l_t),cone=float(l_c),aux=float(l_a),rank=float(l_r),grad_norm=gn,finite=bool(np.isfinite(float(l_o)) and np.isfinite(float(l_t)) and np.isfinite(float(l_c)) and np.isfinite(float(l_a)) and np.isfinite(float(l_r)) and np.isfinite(gn)))
 assert rec['finite']; logs.append(rec)
 if (step+1)%5==0 or step==199:
  model.eval()
  with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16): lg=model(vx,ve).float(); s=(lg[:,1]-lg[:,0]).cpu().numpy()
  import json as J
  c2=J.loads((B/'input_contract.json').read_text(encoding='utf-8')); vv={z['view']:z for z in c2['shared_inputs']['trans_val']['views']}; aps=[]
  for v in val['views']:
   lay=vv[str(v)]; a,b=np.searchsorted(val['rows'],[lay['start'],lay['stop']]); yy,tt,ss=val['y'][a:b],val['trusted'][a:b],s[a:b]
   if len(np.unique(yy[tt]))>1: aps.append(average_precision_score(yy[tt],ss[tt]))
  ap=float(np.mean(aps)) if aps else None; logs[-1]['val_ap']=ap
  cap=float(val_cone_ap(lg)) if ap is not None else None; logs[-1]['val_cone_ap']=cap
  score=(ap+0.5*cap) if (ap is not None and cap is not None) else None
  if score is not None and score>best['score']: best=dict(score=score,step=step+1,state={k:v.detach().cpu().clone() for k,v in model.state_dict().items()},opt={k:(v.detach().cpu().clone() if torch.is_tensor(v) else v) for k,v in opt.state_dict().items()})
last={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
for point,st,op in (('best',best['state'],best['opt']),('last',last,opt.state_dict())):
 torch.save(dict(model=st,optimizer=op,completed=200,best_step=best['step'],variant=variant,seed=seed),outdir/f'{point}_resume.pt')
outdir.joinpath('LOG.json').write_text(json.dumps(dict(variant=variant,seed=seed,best_step=best['step'],best_score=best['score'],logs=logs),indent=2),encoding='utf-8')
print('DONE',variant,seed,best['step'],best['score'],flush=True)
