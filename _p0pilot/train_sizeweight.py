"""View-balanced negative cone sampling, max BCE, seed."""
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
K=int(sys.argv[1]); seed=int(sys.argv[2])
g=np.load(FG/'group_B.npz'); c=np.load(OUT/'cones_relaxed_D.npz'); sup=np.load(FG/'sup_B.npz'); v=np.load(FG/'val_common.npz'); mean,std=g['mean'],g['std']
def norm(x):
 o=np.array(x,np.float32,copy=True); o[:,25:]=np.clip((o[:,25:]-mean)/std,-10,10); return o
x=torch.as_tensor(norm(g['x']),device='cuda'); e=torch.as_tensor(g['edge'],device='cuda'); y=torch.as_tensor(g['y'].astype(np.int64),device='cuda')
xo=torch.as_tensor(norm(np.load(B/'inputs/orig_train/x39.npy')),device='cuda'); eo=torch.as_tensor(np.load(B/'inputs/orig_train/edge_index.npy'),device='cuda'); yo=torch.as_tensor(np.load(B/'inputs/orig_train/y.npy').astype(np.int64),device='cuda')
vx=torch.as_tensor(v['x'],device='cuda'); ve=torch.as_tensor(v['edge'],device='cuda')
tx=np.load(B/'inputs/trans_test/x39.npy'); ty=np.load(B/'inputs/trans_test/y.npy'); tt=np.load(B/'inputs/trans_test/trusted.npy'); tx=torch.as_tensor(norm(tx),device='cuda'); te=torch.as_tensor(np.load(B/'inputs/trans_test/edge_index.npy'),device='cuda')
rows=torch.as_tensor(c['rows'],device='cuda'); seg=torch.repeat_interleave(torch.arange(len(c['label']),device='cuda'),torch.as_tensor(np.diff(c['ptr']),device='cuda')); lab=c['label']; views=np.array(c['view']); uniq=sorted(set(views)); pos_idx=np.where(lab==1)[0]; neg_by={u:np.where((lab==0)&(views==u))[0] for u in uniq}
def sample_neg():
 sel=[]
 for u,idx in neg_by.items():
  if len(idx)==0: continue
  sel.append(np.random.choice(idx,min(K,len(idx)),replace=False))
 return np.concatenate(sel) if sel else np.array([],dtype=np.int64)
def cone_loss(logits,sel):
 m=(logits.float()[:,1]-logits.float()[:,0]); mx=torch.full((len(lab),),-1e9,device='cuda'); mx.scatter_reduce_(0,seg,m.index_select(0,rows),reduce='amax')
 idx=torch.as_tensor(np.concatenate([pos_idx,sel]),device='cuda'); cnt=torch.as_tensor(np.diff(c['ptr']),dtype=torch.float32,device='cuda'); w=1.0/torch.sqrt(cnt[idx]); w=w/w.mean(); bce=F.binary_cross_entropy_with_logits(mx[idx],torch.as_tensor(lab,dtype=torch.float32,device='cuda')[idx],pos_weight=torch.tensor(10.,device='cuda'),reduction='none'); return (bce*w).mean()
loader=FiveGroupLoader(); T.seed(seed); m=Model().cuda(); m.load_state_dict(torch.load(R/f'_p0pilot/control_v3_eligible_20261104/init_s{seed}.pt',map_location='cuda',weights_only=True)); opt=torch.optim.Adam(m.parameters(),lr=2e-4,weight_decay=1e-3); np.random.seed(seed)
outdir=OUT/f'run_sizeweight{K}_s{seed}'; outdir.mkdir(exist_ok=True); logs=[]; best=dict(score=-1,step=-1,state=None)
for step in range(200):
 T.seed(seed+step); m.train(); opt.zero_grad(set_to_none=True)
 io=np.array(loader.step('orig','G0',step).indices,copy=True)
 with torch.autocast('cuda',dtype=torch.bfloat16): lo=m(xo,eo); l_o=T.domain_loss(lo,yo,torch.as_tensor(io,device='cuda'))
 l_o.backward()
 ids=np.asarray(sup['idx'][step],dtype=np.int64); sel=sample_neg()
 with torch.autocast('cuda',dtype=torch.bfloat16): lt=m(x,e); l_t=T.domain_loss(lt,y,torch.as_tensor(ids,device='cuda')); l_c=cone_loss(lt,sel); loss=l_t+0.01*l_c
 loss.backward(); gn=float(torch.nn.utils.clip_grad_norm_(m.parameters(),1.0)); opt.step(); logs.append(dict(step=step+1,l_o=float(l_o),l_t=float(l_t),cone=float(l_c),nneg=int(len(sel)),grad=gn,finite=bool(np.isfinite(float(l_o)) and np.isfinite(float(l_t)) and np.isfinite(float(l_c)) and np.isfinite(gn)))); assert logs[-1]['finite']
 if (step+1)%5==0 or step==199:
  m.eval()
  with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16): sv=(m(vx,ve).float()[:,1]-m(vx,ve).float()[:,0]).cpu().numpy()
  aps=[]
  for z in json.load(open(B/'input_contract.json',encoding='utf-8'))['shared_inputs']['trans_val']['views']:
   a,b=np.searchsorted(v['rows'],[z['start'],z['stop']]); yy,tt2,ss=v['y'][a:b],v['trusted'][a:b],sv[a:b]
   if len(np.unique(yy[tt2]))>1: aps.append(average_precision_score(yy[tt2],ss[tt2]))
  ap=float(np.mean(aps)) if aps else None; logs[-1]['val_ap']=ap
  if ap is not None and ap>best['score']: best=dict(score=ap,step=step+1,state={k:vv.detach().cpu().clone() for k,vv in m.state_dict().items()})
torch.save(dict(model=best['state'],best_step=best['step'],seed=seed),outdir/'best_resume.pt'); outdir.joinpath('LOG.json').write_text(json.dumps(dict(seed=seed,K=K,best_step=best['step'],best_score=best['score'],logs=logs),indent=2),encoding='utf-8')
m.load_state_dict(best['state']); m.eval()
with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16): ts=(m(tx,te).float()[:,1]-m(tx,te).float()[:,0]).cpu().numpy()
taps=[]
for z in [z for z in json.load(open(B/'input_contract.json',encoding='utf-8'))['shared_inputs']['trans_test']['views'] if 'ctl' not in z['view']]:
 a,b=z['start'],z['stop']; yy,tt2,ss=ty[a:b],tt[a:b],ts[a:b]
 if len(np.unique(yy[tt2]))>1: taps.append(average_precision_score(yy[tt2],ss[tt2]))
outdir.joinpath('EVAL.json').write_text(json.dumps(dict(seed=seed,K=K,best_step=best['step'],test_ap=float(np.mean(taps)),test_views=len(taps)),indent=2),encoding='utf-8')
print('DONE',K,seed,best['step'],float(np.mean(taps)),flush=True)
