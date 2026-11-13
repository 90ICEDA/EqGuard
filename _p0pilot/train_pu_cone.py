"""PU learning: nnPU risk on unlabeled nodes, seed."""
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
lam=float(sys.argv[1]); pi=float(sys.argv[2]); seed=int(sys.argv[3]) if len(sys.argv)>3 else 42
g=np.load(FG/'group_B.npz'); sup=np.load(FG/'sup_B.npz'); v=np.load(FG/'val_common.npz'); mean,std=g['mean'],g['std']
def norm(x):
 o=np.array(x,np.float32,copy=True); o[:,25:]=np.clip((o[:,25:]-mean)/std,-10,10); return o
x=torch.as_tensor(norm(g['x']),device='cuda'); e=torch.as_tensor(g['edge'],device='cuda'); y=torch.as_tensor(g['y'].astype(np.int64),device='cuda'); tr=g['trusted']
xo=torch.as_tensor(norm(np.load(B/'inputs/orig_train/x39.npy')),device='cuda'); eo=torch.as_tensor(np.load(B/'inputs/orig_train/edge_index.npy'),device='cuda'); yo=torch.as_tensor(np.load(B/'inputs/orig_train/y.npy').astype(np.int64),device='cuda')
vx=torch.as_tensor(v['x'],device='cuda'); ve=torch.as_tensor(v['edge'],device='cuda')
tx=np.load(B/'inputs/trans_test/x39.npy'); ty=np.load(B/'inputs/trans_test/y.npy'); tt=np.load(B/'inputs/trans_test/trusted.npy'); tp=np.load(B/'inputs/trans_test/physical.npy'); tx=torch.as_tensor(norm(tx),device='cuda'); te=torch.as_tensor(np.load(B/'inputs/trans_test/edge_index.npy'),device='cuda')
pos=np.where((g['y']==1)&tr)[0]; neg=np.where((g['y']==0)&tr)[0]; c=np.load(OUT/'cones_relaxed_D.npz'); mem=np.concatenate([c['rows'][c['ptr'][i]:c['ptr'][i+1]] for i in range(len(c['label'])) if c['label'][i]==1]); unk=np.array(sorted(set(mem[~tr[mem]].tolist())),dtype=np.int64); print('counts',len(pos),len(neg),len(unk),flush=True)
loader=FiveGroupLoader(); T.seed(seed); m=Model().cuda(); m.load_state_dict(torch.load(R/f'_p0pilot/control_v3_eligible_20261104/init_s{seed}.pt',map_location='cuda',weights_only=True)); opt=torch.optim.Adam(m.parameters(),lr=2e-4,weight_decay=1e-3); rng=np.random.default_rng(seed)
outdir=OUT/f'run_pucone_lam{lam}_pi{pi}_s{seed}'; outdir.mkdir(exist_ok=True); logs=[]; best=dict(score=-1,step=-1,state=None)
for step in range(200):
 T.seed(seed+step); m.train(); opt.zero_grad(set_to_none=True)
 io=np.array(loader.step('orig','G0',step).indices,copy=True); ids=np.asarray(sup['idx'][step],dtype=np.int64)
 with torch.autocast('cuda',dtype=torch.bfloat16): lo=m(xo,eo); l_o=T.domain_loss(lo,yo,torch.as_tensor(io,device='cuda'))
 l_o.backward()
 ub=rng.choice(unk,min(8192,len(unk)),replace=False)
 with torch.autocast('cuda',dtype=torch.bfloat16):
  lt=m(x,e); l_t=T.domain_loss(lt,y,torch.as_tensor(ids,device='cuda')); s=(lt.float()[:,1]-lt.float()[:,0])
  lp=F.binary_cross_entropy_with_logits(s[torch.as_tensor(pos,device='cuda')],torch.ones(len(pos),device='cuda'))
  lu=F.binary_cross_entropy_with_logits(s[torch.as_tensor(ub,device='cuda')],torch.zeros(len(ub),device='cuda'))
  l_pu=pi*lp+F.relu(lu-pi*lp.detach())
  loss=l_t+lam*l_pu
 loss.backward(); gn=float(torch.nn.utils.clip_grad_norm_(m.parameters(),1.0)); opt.step(); logs.append(dict(step=step+1,l_o=float(l_o),l_t=float(l_t),lp=float(lp),lu=float(lu),l_pu=float(l_pu),grad=gn,finite=bool(np.isfinite(float(l_o)) and np.isfinite(float(l_t)) and np.isfinite(float(lp)) and np.isfinite(float(lu)) and np.isfinite(gn)))); assert logs[-1]['finite']
 if (step+1)%5==0 or step==199:
  m.eval()
  with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16): sv=(m(vx,ve).float()[:,1]-m(vx,ve).float()[:,0]).cpu().numpy()
  aps=[]
  for z in json.load(open(B/'input_contract.json',encoding='utf-8'))['shared_inputs']['trans_val']['views']:
   a,b=np.searchsorted(v['rows'],[z['start'],z['stop']]); yy,tt2,ss=v['y'][a:b],v['trusted'][a:b],sv[a:b]
   if len(np.unique(yy[tt2]))>1: aps.append(average_precision_score(yy[tt2],ss[tt2]))
  ap=float(np.mean(aps)) if aps else None; logs[-1]['val_ap']=ap
  if ap is not None and ap>best['score']: best=dict(score=ap,step=step+1,state={k:vv.detach().cpu().clone() for k,vv in m.state_dict().items()})
torch.save(dict(model=best['state'],best_step=best['step'],seed=seed),outdir/'best_resume.pt'); outdir.joinpath('LOG.json').write_text(json.dumps(dict(seed=seed,lam=lam,pi=pi,best_step=best['step'],best_score=best['score'],logs=logs),indent=2),encoding='utf-8')
m.load_state_dict(best['state']); m.eval()
with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16): ts=(m(tx,te).float()[:,1]-m(tx,te).float()[:,0]).cpu().numpy()
taps=[]
for z in [z for z in json.load(open(B/'input_contract.json',encoding='utf-8'))['shared_inputs']['trans_test']['views'] if 'ctl' not in z['view']]:
 a,b=z['start'],z['stop']; yy,tt2,ss=ty[a:b],tt[a:b],ts[a:b]
 if len(np.unique(yy[tt2]))>1: taps.append(average_precision_score(yy[tt2],ss[tt2]))
outdir.joinpath('EVAL.json').write_text(json.dumps(dict(seed=seed,lam=lam,pi=pi,best_step=best['step'],test_ap=float(np.mean(taps)),test_views=len(taps)),indent=2),encoding='utf-8')
print('DONE',lam,pi,seed,best['step'],float(np.mean(taps)),flush=True)
