"""Two-stage v2: top20/30% candidates + GNN embedding + local structure reranker."""
import os,sys,json
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'): os.environ[k]='1'
os.environ['P2B_MASK']='old'
from pathlib import Path
import numpy as np, torch, torch.nn.functional as F
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FG=R/'_p0pilot/four_group_contract_20261109'; OUT=R/'_p0pilot/lcone_relaxed_20261111'; B=R/'_p0pilot/control_boundary_v3_20261104'
sys.path.insert(0,str(R/'_p0pilot/control_best200_20261104')); sys.path.insert(0,str(R/'_p0pilot/seed42_nc_ablation_20261109')); from evaluate import Model,T
from sklearn.metrics import average_precision_score
frac=float(sys.argv[1]) if len(sys.argv)>1 else 0.2
g=np.load(FG/'group_B.npz'); v=np.load(FG/'val_common.npz'); mean,std=g['mean'],g['std']
def norm(x):
 o=np.array(x,np.float32,copy=True); o[:,25:]=np.clip((o[:,25:]-mean)/std,-10,10); return o
base=Model().cuda(); base.load_state_dict(torch.load(OUT/'run_relaxed_s42_lam0.01/best_resume.pt',map_location='cuda',weights_only=False)['model']); base.eval()
def embed(x,e):
 with torch.autocast('cuda',dtype=torch.bfloat16):
  x=x+F.relu(base.mix(x)); a=base._run(base.enc_s,x[:,:base.split],e); b=base._run(base.enc_f,x[:,base.split:],e)
  h=base.fuse(torch.cat((a,b),1)); h=F.relu(base.post(h,e)); return h.float()
@torch.inference_mode()
def pred(x,e):
 tx=torch.as_tensor(norm(x),device='cuda'); te=torch.as_tensor(e,device='cuda'); lg=base(tx,te).float(); return (lg[:,1]-lg[:,0]).cpu().numpy(), embed(tx,te).cpu().numpy()
s,emb=pred(g['x'],g['edge']); deg=np.bincount(g['edge'][0],minlength=len(g['y']))
vs,vemb=pred(v['x'],v['edge']); vdeg=np.bincount(v['edge'][0],minlength=len(v['y']))
tx=np.load(B/'inputs/trans_test/x39.npy'); ty=np.load(B/'inputs/trans_test/y.npy'); tt=np.load(B/'inputs/trans_test/trusted.npy'); tp=np.load(B/'inputs/trans_test/physical.npy'); te=np.load(B/'inputs/trans_test/edge_index.npy'); ts,temb=pred(tx,te); tdeg=np.bincount(te[0],minlength=len(ty))
def candidates(score,frac):
 return np.argsort(-score)[:int(len(score)*frac)]
cand=candidates(s,frac); cand=np.unique(np.concatenate([cand,np.where((g['y']==1)&g['trusted'])[0]]))
vcand=candidates(vs,frac); tcand=candidates(ts,frac)
print('coverage train pos',int(((g['y'][cand]==1)&g['trusted'][cand]).sum()),'test pos',int(((ty[tcand]==1)&tt[tcand]).sum()),'of',int(((ty==1)&tt).sum()),flush=True)
def feat(x,emb_,score,deg,idx):
 return np.concatenate([norm(x)[idx],emb_[idx],score[idx,None],deg[idx,None],np.log1p(deg[idx,None])],1).astype(np.float32)
X=feat(g['x'],emb,s,deg,cand); Y=(g['y'][cand]==1).astype(np.float32)
VX=feat(v['x'],vemb,vs,vdeg,vcand); VY=(v['y'][vcand]==1).astype(np.float32)
TX=feat(tx,temb,ts,tdeg,tcand); TY=(ty[tcand]==1); TTR=tt[tcand]
net=torch.nn.Sequential(torch.nn.Linear(X.shape[1],128),torch.nn.ReLU(),torch.nn.Dropout(.2),torch.nn.Linear(128,64),torch.nn.ReLU(),torch.nn.Linear(64,1)).cuda(); opt=torch.optim.Adam(net.parameters(),lr=1e-3,weight_decay=1e-4)
xt=torch.tensor(X,device='cuda'); yt=torch.tensor(Y,device='cuda'); vxt=torch.tensor(VX,device='cuda'); vyt=torch.tensor(VY,device='cuda'); best=(-1,None)
for ep in range(300):
 net.train(); opt.zero_grad(); o=net(xt).squeeze(); w=torch.where(yt>0,torch.tensor(10.,device='cuda'),torch.tensor(1.,device='cuda')); loss=(F.binary_cross_entropy_with_logits(o,yt,reduction='none')*w).mean(); loss.backward(); opt.step()
 if ep%10==0:
  net.eval()
  with torch.inference_mode(): p=net(vxt).squeeze().cpu().numpy()
  ap=average_precision_score(VY,p) if len(np.unique(VY))>1 else 0
  if ap>best[0]: best=(ap,{k:v.detach().cpu().clone() for k,v in net.state_dict().items()})
net.load_state_dict(best[1]); net.eval()
with torch.inference_mode(): p=net(torch.tensor(TX,device='cuda')).squeeze().cpu().numpy()
full=np.full(len(ty),-1e9,np.float32); full[tcand]=p
c=json.load(open(B/'input_contract.json',encoding='utf-8')); ap={}
for z in c['shared_inputs']['trans_test']['views']:
 a,b=z['start'],z['stop']; yy,tt2,ss=ty[a:b],tt[a:b],full[a:b]
 if len(np.unique(yy[tt2]))>1: ap.setdefault(z['view'].split('__')[-1],[]).append(average_precision_score(yy[tt2],ss[tt2]))
ap={k:float(np.mean(vv)) for k,vv in ap.items()}; baseap=float(np.mean([ap[r] for r in ('ys_abc','ys_id','ys_opt') if r in ap])); add=float(np.mean([ap[r] for r in ('ys_aig','ys_nand') if r in ap])); print('RESULT',frac,baseap,add,'cand',len(tcand),'cov',int(TY.sum()),flush=True)
out=OUT/f'run_rerank2_frac{frac}'; out.mkdir(exist_ok=True); (out/'EVAL.json').write_text(json.dumps(dict(frac=frac,base=baseap,add=add,ap=ap,cand=len(tcand),test_pos_covered=int(TY.sum())),indent=2),encoding='utf-8'); torch.save(dict(model=net.state_dict()),out/'reranker.pt')
