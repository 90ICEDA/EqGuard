"""Gradient-level cone mix: g_node + beta*||g_node||/||g_cone||*g_cone, seed2."""
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
import cone_loss as CL
beta=float(sys.argv[1]); seed=int(sys.argv[2]) if len(sys.argv)>2 else 2
g=np.load(FG/'group_B.npz'); c=np.load(OUT/'cones_relaxed_D.npz'); sup=np.load(FG/'sup_B.npz'); val=np.load(FG/'val_common.npz'); mean,std=g['mean'],g['std']
def norm(x):
 o=np.array(x,np.float32,copy=True); o[:,25:]=np.clip((o[:,25:]-mean)/std,-10,10); return o
x=torch.as_tensor(norm(g['x']),device='cuda'); e=torch.as_tensor(g['edge'],device='cuda'); y=torch.as_tensor(g['y'].astype(np.int64),device='cuda')
xo=torch.as_tensor(norm(np.load(B/'inputs/orig_train/x39.npy')),device='cuda'); eo=torch.as_tensor(np.load(B/'inputs/orig_train/edge_index.npy'),device='cuda'); yo=torch.as_tensor(np.load(B/'inputs/orig_train/y.npy').astype(np.int64),device='cuda')
vx=torch.as_tensor(val['x'],device='cuda'); ve=torch.as_tensor(val['edge'],device='cuda')
ct=dict(rows=list(range(len(c['label']))),idx=torch.as_tensor(c['rows'],device='cuda'),seg=torch.repeat_interleave(torch.arange(len(c['label']),device='cuda'),torch.as_tensor(np.diff(c['ptr']),device='cuda')),lab=torch.as_tensor(c['label'],dtype=torch.float32,device='cuda'))
loader=FiveGroupLoader(); T.seed(seed); m=Model().cuda(); m.load_state_dict(torch.load(R/f'_p0pilot/control_v3_eligible_20261104/init_s{seed}.pt',map_location='cuda',weights_only=True)); opt=torch.optim.Adam(m.parameters(),lr=2e-4,weight_decay=1e-3)
outdir=OUT/f'run_gradmix_b{beta}_s{seed}'; outdir.mkdir(exist_ok=True); logs=[]; best=dict(score=-1,step=-1,state=None)
for step in range(200):
 T.seed(seed+step); m.train(); opt.zero_grad(set_to_none=True)
 io=np.array(loader.step('orig','G0',step).indices,copy=True); ids=np.asarray(sup['idx'][step],dtype=np.int64)
 with torch.autocast('cuda',dtype=torch.bfloat16):
  lo=m(xo,eo); l_o=T.domain_loss(lo,yo,torch.as_tensor(io,device='cuda'))
  lt=m(x,e); l_t=T.domain_loss(lt,y,torch.as_tensor(ids,device='cuda')); l_c=CL.cone_loss(lt,ct,pos_weight=10.0)
  l_node=l_o+l_t
 params=[p for p in m.parameters() if p.requires_grad]
 gn=torch.autograd.grad(l_node,params,retain_graph=True,allow_unused=True); gc=torch.autograd.grad(l_c,params,retain_graph=False,allow_unused=True)
 gn=[torch.zeros_like(p) if z is None else z for z,p in zip(gn,params)]; gc=[torch.zeros_like(p) if z is None else z for z,p in zip(gc,params)]
 def dot(a,b): return sum((x*y).sum() for x,y in zip(a,b))
 nn=torch.sqrt(sum((x*x).sum() for x in gn))+1e-12; nc=torch.sqrt(sum((x*x).sum() for x in gc))+1e-12; cos=float(dot(gn,gc)/(nn*nc))
 scale=beta*nn/(nc+1e-12)
 for p,a,b in zip(params,gn,gc): p.grad=a+scale*b
 gn_after=float(torch.nn.utils.clip_grad_norm_(m.parameters(),1.0)); opt.step()
 logs.append(dict(step=step+1,l_o=float(l_o),l_t=float(l_t),cone=float(l_c),gn=float(nn),gc=float(nc),cos=cos,beta=beta,grad=gn_after,finite=bool(np.isfinite(float(l_o)) and np.isfinite(float(l_t)) and np.isfinite(float(l_c)) and np.isfinite(float(nn)) and np.isfinite(float(nc)) and np.isfinite(gn_after)))); assert logs[-1]['finite']
 if (step+1)%5==0 or step==199:
  m.eval()
  with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16): sv=(m(vx,ve).float()[:,1]-m(vx,ve).float()[:,0]).cpu().numpy()
  aps=[]
  for z in json.load(open(B/'input_contract.json',encoding='utf-8'))['shared_inputs']['trans_val']['views']:
   a,b=np.searchsorted(val['rows'],[z['start'],z['stop']]); yy,tt2,ss=val['y'][a:b],val['trusted'][a:b],sv[a:b]
   if len(np.unique(yy[tt2]))>1: aps.append(average_precision_score(yy[tt2],ss[tt2]))
  ap=float(np.mean(aps)) if aps else None; logs[-1]['val_ap']=ap
  if ap is not None and ap>best['score']: best=dict(score=ap,step=step+1,state={k:vv.detach().cpu().clone() for k,vv in m.state_dict().items()})
torch.save(dict(model=best['state'],best_step=best['step'],seed=seed,beta=beta),outdir/'best_resume.pt'); outdir.joinpath('LOG.json').write_text(json.dumps(dict(seed=seed,beta=beta,best_step=best['step'],best_score=best['score'],logs=logs),indent=2),encoding='utf-8')
print('DONE',beta,seed,best['step'],best['score'],flush=True)
