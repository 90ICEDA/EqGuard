"""N baseline only 10 steps, 5 seeds, test add/base."""
import os,sys,json
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'): os.environ[k]='1'
os.environ['P2B_MASK']='old'
from pathlib import Path
import numpy as np, torch
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FG=R/'_p0pilot/four_group_contract_20261109'; OUT=R/'_p0pilot/lcone_relaxed_20261111'; B=R/'_p0pilot/control_boundary_v3_20261104'
sys.path.insert(0,str(R/'_p0pilot/control_loader_po_20261105')); sys.path.insert(0,str(R/'_p0pilot/control_best200_20261104')); sys.path.insert(0,str(R/'_p0pilot/seed42_nc_ablation_20261109'))
from supervision_loader import FiveGroupLoader
from evaluate import Model,T
from sklearn.metrics import average_precision_score
g=np.load(FG/'group_B.npz'); v=np.load(FG/'val_common.npz'); sup=np.load(FG/'sup_B.npz'); mean,std=g['mean'],g['std']
def norm(x):
 o=np.array(x,np.float32,copy=True); o[:,25:]=np.clip((o[:,25:]-mean)/std,-10,10); return o
x=torch.as_tensor(norm(g['x']),device='cuda'); e=torch.as_tensor(g['edge'],device='cuda'); y=torch.as_tensor(g['y'].astype(np.int64),device='cuda')
xo=torch.as_tensor(norm(np.load(B/'inputs/orig_train/x39.npy')),device='cuda'); eo=torch.as_tensor(np.load(B/'inputs/orig_train/edge_index.npy'),device='cuda'); yo=torch.as_tensor(np.load(B/'inputs/orig_train/y.npy').astype(np.int64),device='cuda')
vx=torch.as_tensor(v['x'],device='cuda'); ve=torch.as_tensor(v['edge'],device='cuda')
tx=np.load(B/'inputs/trans_test/x39.npy'); ty=np.load(B/'inputs/trans_test/y.npy'); tt=np.load(B/'inputs/trans_test/trusted.npy'); tx=torch.as_tensor(norm(tx),device='cuda'); te=torch.as_tensor(np.load(B/'inputs/trans_test/edge_index.npy'),device='cuda')
c2=json.load(open(B/'input_contract.json',encoding='utf-8')); tv=[z for z in c2['shared_inputs']['trans_test']['views'] if 'ctl' not in z['view']]
loader=FiveGroupLoader()
for seed in (42,1,2,43,44):
 T.seed(seed); m=Model().cuda(); m.load_state_dict(torch.load(R/f'_p0pilot/control_v3_eligible_20261104/init_s{seed}.pt',map_location='cuda',weights_only=True)); opt=torch.optim.Adam(m.parameters(),lr=2e-4,weight_decay=1e-3)
 for step in range(10):
  T.seed(seed+step); m.train(); opt.zero_grad(set_to_none=True)
  io=np.array(loader.step('orig','G0',step).indices,copy=True)
  with torch.autocast('cuda',dtype=torch.bfloat16): lo=m(xo,eo); l_o=T.domain_loss(lo,yo,torch.as_tensor(io,device='cuda'))
  ids=np.asarray(sup['idx'][step],dtype=np.int64)
  with torch.autocast('cuda',dtype=torch.bfloat16): lt=m(x,e); l_t=T.domain_loss(lt,y,torch.as_tensor(ids,device='cuda')); loss=l_o+l_t
  loss.backward(); torch.nn.utils.clip_grad_norm_(m.parameters(),1.0); opt.step()
 m.eval()
 with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16): ts=(m(tx,te).float()[:,1]-m(tx,te).float()[:,0]).cpu().numpy()
 taps=[]
 for z in tv:
  a,b=z['start'],z['stop']; yy,tt2,ss=ty[a:b],tt[a:b],ts[a:b]
  if len(np.unique(yy[tt2]))>1: taps.append(average_precision_score(yy[tt2],ss[tt2]))
 out=OUT/f'run_n10_s{seed}'; out.mkdir(exist_ok=True); torch.save(dict(model=m.state_dict(),steps=10,seed=seed),out/'last_resume.pt'); out.joinpath('EVAL.json').write_text(json.dumps(dict(seed=seed,steps=10,test_ap=float(np.mean(taps)),test_views=len(taps)),indent=2),encoding='utf-8')
 print('DONE',seed,float(np.mean(taps)),flush=True)
