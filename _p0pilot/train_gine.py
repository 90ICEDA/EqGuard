"""A/C with GINEConv edge weights, seed2."""
import os,sys,json
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'): os.environ[k]='1'
os.environ['P2B_MASK']='old'
from pathlib import Path
import numpy as np, torch, torch.nn.functional as F
from torch_geometric.nn import GINEConv
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FG=R/'_p0pilot/four_group_contract_20261109'; OUT=R/'_p0pilot/lcone_relaxed_20261111'; B=R/'_p0pilot/control_boundary_v3_20261104'
sys.path.insert(0,str(R/'_p0pilot/control_loader_po_20261105')); sys.path.insert(0,str(R/'_p0pilot/control_best200_20261104')); sys.path.insert(0,str(R/'_p0pilot/seed42_nc_ablation_20261109'))
from supervision_loader import FiveGroupLoader
from evaluate import Model,T
from sklearn.metrics import average_precision_score
mode=sys.argv[1]; seed=int(sys.argv[2]) if len(sys.argv)>2 else 2
g=np.load(FG/'group_B.npz'); v=np.load(FG/'val_common.npz'); sup=np.load(FG/'sup_B.npz'); va=np.load(OUT/'coneedge_variants.npz'); mean,std=g['mean'],g['std']
def norm(x):
 o=np.array(x,np.float32,copy=True); o[:,25:]=np.clip((o[:,25:]-mean)/std,-10,10); return o
x=torch.as_tensor(norm(g['x']),device='cuda'); y=torch.as_tensor(g['y'].astype(np.int64),device='cuda'); e=torch.as_tensor(va['train_star'],device='cuda')
xo=torch.as_tensor(norm(np.load(B/'inputs/orig_train/x39.npy')),device='cuda'); eo=torch.as_tensor(np.load(B/'inputs/orig_train/edge_index.npy'),device='cuda'); yo=torch.as_tensor(np.load(B/'inputs/orig_train/y.npy').astype(np.int64),device='cuda')
vx=torch.as_tensor(v['x'],device='cuda'); ve=torch.as_tensor(va['val_star'],device='cuda')
tx=np.load(B/'inputs/trans_test/x39.npy'); ty=np.load(B/'inputs/trans_test/y.npy'); tt=np.load(B/'inputs/trans_test/trusted.npy'); tx=torch.as_tensor(norm(tx),device='cuda'); te=torch.as_tensor(va['test_star'],device='cuda')
fac=1.0 if mode=='A' else 0.1
w=torch.cat([torch.ones(g['edge'].shape[1],device='cuda'),torch.as_tensor(va['w_star'],device='cuda')*fac]).float()
wv=torch.cat([torch.ones(v['edge'].shape[1],device='cuda'),torch.as_tensor(va['w_val'],device='cuda')*fac]).float()
wt=torch.cat([torch.ones(np.load(B/'inputs/trans_test/edge_index.npy').shape[1],device='cuda'),torch.as_tensor(va['w_test'],device='cuda')*fac]).float()
class MG(Model):
 def __init__(self):
  super().__init__()
  for enc in (self.enc_s,self.enc_f):
   for i,c in enumerate(enc):
    enc[i]=GINEConv(c.nn,eps=float(c.eps),train_eps=isinstance(c.eps,torch.nn.Parameter),edge_dim=1)
  self.post=GINEConv(self.post.nn,eps=float(self.post.eps),train_eps=isinstance(self.post.eps,torch.nn.Parameter),edge_dim=1)
 def _runw(self,enc,x,e,w):
  for c in enc: x=F.dropout(F.relu(c(x,e,edge_attr=w.unsqueeze(1))),p=.2,training=self.training)
  return x
 def forward(self,x,e,w=None):
  if w is None: w=torch.ones(e.shape[1],device=x.device)
  x=x+F.relu(self.mix(x)); a=self._runw(self.enc_s,x[:,:self.split],e,w); b=self._runw(self.enc_f,x[:,self.split:],e,w)
  h=self.fuse(torch.cat((a,b),1)); h=F.dropout(F.relu(self.post(h,e,edge_attr=w.unsqueeze(1))),p=.2,training=self.training)
  return self.classifier(h)
loader=FiveGroupLoader(); T.seed(seed); m=MG().cuda(); st=torch.load(R/f'_p0pilot/control_v3_eligible_20261104/init_s{seed}.pt',map_location='cuda',weights_only=True); print(m.load_state_dict(st,strict=False)); opt=torch.optim.Adam(m.parameters(),lr=2e-4,weight_decay=1e-3)
outdir=OUT/f'run_gine{mode}_s{seed}'; outdir.mkdir(exist_ok=True); logs=[]; best=dict(score=-1,step=-1,state=None)
for step in range(200):
 T.seed(seed+step); m.train(); opt.zero_grad(set_to_none=True)
 io=np.array(loader.step('orig','G0',step).indices,copy=True); ids=np.asarray(sup['idx'][step],dtype=np.int64)
 with torch.autocast('cuda',dtype=torch.bfloat16): lo=m(xo,eo); l_o=T.domain_loss(lo,yo,torch.as_tensor(io,device='cuda'))
 with torch.autocast('cuda',dtype=torch.bfloat16): lt=m(x,e,w); l_t=T.domain_loss(lt,y,torch.as_tensor(ids,device='cuda')); loss=l_o+l_t
 loss.backward(); gn=float(torch.nn.utils.clip_grad_norm_(m.parameters(),1.0)); opt.step(); logs.append(dict(step=step+1,l_o=float(l_o),l_t=float(l_t),grad=gn,finite=bool(np.isfinite(float(l_o)) and np.isfinite(float(l_t)) and np.isfinite(gn)))); assert logs[-1]['finite']
 if (step+1)%5==0 or step==199:
  m.eval()
  with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16): sv=(m(vx,ve,wv).float()[:,1]-m(vx,ve,wv).float()[:,0]).cpu().numpy()
  aps=[]
  for z in json.load(open(B/'input_contract.json',encoding='utf-8'))['shared_inputs']['trans_val']['views']:
   a,b=np.searchsorted(v['rows'],[z['start'],z['stop']]); yy,tt2,ss=v['y'][a:b],v['trusted'][a:b],sv[a:b]
   if len(np.unique(yy[tt2]))>1: aps.append(average_precision_score(yy[tt2],ss[tt2]))
  ap=float(np.mean(aps)) if aps else None; logs[-1]['val_ap']=ap
  if ap is not None and ap>best['score']: best=dict(score=ap,step=step+1,state={k:vv.detach().cpu().clone() for k,vv in m.state_dict().items()})
torch.save(dict(model=best['state'],best_step=best['step'],seed=seed),outdir/'best_resume.pt'); outdir.joinpath('LOG.json').write_text(json.dumps(dict(seed=seed,mode=mode,best_step=best['step'],best_score=best['score'],logs=logs),indent=2),encoding='utf-8')
m.load_state_dict(best['state']); m.eval()
with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16): ts=(m(tx,te,wt).float()[:,1]-m(tx,te,wt).float()[:,0]).cpu().numpy()
taps=[]
for z in [z for z in json.load(open(B/'input_contract.json',encoding='utf-8'))['shared_inputs']['trans_test']['views'] if 'ctl' not in z['view']]:
 a,b=z['start'],z['stop']; yy,tt2,ss=ty[a:b],tt[a:b],ts[a:b]
 if len(np.unique(yy[tt2]))>1: taps.append(average_precision_score(yy[tt2],ss[tt2]))
outdir.joinpath('EVAL.json').write_text(json.dumps(dict(seed=seed,mode=mode,best_step=best['step'],test_ap=float(np.mean(taps)),test_views=len(taps)),indent=2),encoding='utf-8')
print('DONE',mode,seed,best['step'],best['score'],float(np.mean(taps)),flush=True)
