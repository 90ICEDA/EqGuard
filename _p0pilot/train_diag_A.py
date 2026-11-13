"""True per-cone p90 compression with per-view positive-p90 anchor, seed."""
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
seed=int(sys.argv[1]); beta=0.03; margin=0.5
g=np.load(FG/'group_B.npz'); c=np.load(OUT/'cones_relaxed_D.npz'); sup=np.load(FG/'sup_B.npz'); val=np.load(FG/'val_common.npz'); mean,std=g['mean'],g['std']
def norm(x):
 o=np.array(x,np.float32,copy=True); o[:,25:]=np.clip((o[:,25:]-mean)/std,-10,10); return o
x=torch.as_tensor(norm(g['x']),device='cuda'); e=torch.as_tensor(g['edge'],device='cuda'); y=torch.as_tensor(g['y'].astype(np.int64),device='cuda')
vx=torch.as_tensor(val['x'],device='cuda'); ve=torch.as_tensor(val['edge'],device='cuda')
xo=torch.as_tensor(norm(np.load(B/'inputs/orig_train/x39.npy')),device='cuda'); eo=torch.as_tensor(np.load(B/'inputs/orig_train/edge_index.npy'),device='cuda'); yo=torch.as_tensor(np.load(B/'inputs/orig_train/y.npy').astype(np.int64),device='cuda')
rows=torch.as_tensor(c['rows'],device='cuda'); seg=torch.repeat_interleave(torch.arange(len(c['label']),device='cuda'),torch.as_tensor(np.diff(c['ptr']),device='cuda')); lab=torch.as_tensor(c['label'],dtype=torch.float32,device='cuda')
views=np.array(c['view']); uniq=sorted(set(views)); vids=torch.as_tensor([uniq.index(v) for v in views],device='cuda'); ncones=len(lab); M=len(rows); pos=torch.arange(M,device='cuda')
def p90_cone(v):
 order=torch.argsort(seg*1e6-v); ss=seg[order]; vv=v[order]; start=torch.full((ncones,),M,device='cuda'); start.scatter_reduce_(0,ss,pos,reduce='amin'); cnt=torch.bincount(seg,minlength=ncones); k=torch.clamp(((cnt-1)*0.1).long(),min=0); rank=pos-start[ss]; sel=rank==k[ss]; out=torch.zeros(ncones,device='cuda'); out[ss[sel]]=vv[sel]; return out
def anchor_vec(p90):
 a=torch.zeros(len(uniq),device='cuda')
 for i in range(len(uniq)):
  vals=p90[(vids==i)&(lab==1)]
  if len(vals): a[i]=torch.quantile(vals,0.25)
 return a[vids]
def losses(logits):
 m=(logits.float()[:,1]-logits.float()[:,0]); mx=torch.full((ncones,),-1e9,device='cuda'); mx.scatter_reduce_(0,seg,m.index_select(0,rows),reduce='amax'); bce=F.binary_cross_entropy_with_logits(mx,lab,pos_weight=torch.tensor(10.,device='cuda'))
 p=p90_cone(m.index_select(0,rows)); av=anchor_vec(p); sel=(lab==0)&(p>av)
 comp=F.relu(p[sel]-av[sel]+margin).pow(2).mean() if sel.sum() else torch.tensor(0.,device='cuda')
 return bce,comp,p,mx
loader=FiveGroupLoader(); T.seed(seed); m=Model().cuda(); m.load_state_dict(torch.load(R/f'_p0pilot/control_v3_eligible_20261104/init_s{seed}.pt',map_location='cuda',weights_only=True)); opt=torch.optim.Adam(m.parameters(),lr=2e-4,weight_decay=1e-3)
outdir=OUT/f'run_diag_A_w50_s{seed}'; outdir.mkdir(exist_ok=True); logs=[]; best=dict(score=-1,step=-1,state=None)
for step in range(200):
 T.seed(seed+step); m.train(); opt.zero_grad(set_to_none=True)
 io=np.array(loader.step('orig','G0',step).indices,copy=True)
 with torch.autocast('cuda',dtype=torch.bfloat16): lo=m(xo,eo); l_o=T.domain_loss(lo,yo,torch.as_tensor(io,device='cuda'))
 l_o.backward()
 with torch.autocast('cuda',dtype=torch.bfloat16): lt=m(x,e); l_t=T.domain_loss(lt,y,torch.as_tensor(sup['idx'][step],device='cuda')); l_bce,l_comp,p,mx=losses(lt); loss=l_t+0.01*l_bce+(beta*l_comp if step<50 else 0.0)
 loss.backward(); gn=float(torch.nn.utils.clip_grad_norm_(m.parameters(),1.0)); opt.step(); nm=mx[lab==0].detach(); np90=p[lab==0].detach(); logs.append(dict(step=step+1,l_o=float(l_o),l_t=float(l_t),bce=float(l_bce),comp=float(l_comp),negmax=float(nm.mean()),negp90=float(np90.mean()),grad=gn,finite=bool(np.isfinite(float(l_o)) and np.isfinite(float(l_t)) and np.isfinite(float(l_bce)) and np.isfinite(float(l_comp)) and np.isfinite(gn)))); assert logs[-1]['finite']
 if (step+1)%5==0 or step==199:
  m.eval()
  with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16): lg=m(vx,ve).float(); sv=(lg[:,1]-lg[:,0]).cpu().numpy()
  c2=json.load(open(B/'input_contract.json',encoding='utf-8')); vv={z['view']:z for z in c2['shared_inputs']['trans_val']['views']}; aps=[]
  for v in val['views']:
   lay=vv[str(v)]; a,b=np.searchsorted(val['rows'],[lay['start'],lay['stop']]); yy,tt,ss=val['y'][a:b],val['trusted'][a:b],sv[a:b]
   if len(np.unique(yy[tt]))>1: aps.append(average_precision_score(yy[tt],ss[tt]))
  ap=float(np.mean(aps)) if aps else None; logs[-1]['val_ap']=ap
  if ap is not None and ap>best['score']: best=dict(score=ap,step=step+1,state={k:v.detach().cpu().clone() for k,v in m.state_dict().items()})
outdir.joinpath('LOG.json').write_text(json.dumps(dict(seed=seed,best_step=best['step'],best_score=best['score'],logs=logs),indent=2),encoding='utf-8'); torch.save(dict(model=best['state'],best_step=best['step'],seed=seed),outdir/'best_resume.pt')
print('DONE',seed,best['step'],best['score'],flush=True)
