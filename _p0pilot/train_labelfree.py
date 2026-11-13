"""Label-free component ring vs random, node-only, compact test eval, seed."""
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
mode=sys.argv[1]; seed=int(sys.argv[2]); key='ring' if mode=='ring' else 'rand'
g=np.load(FG/'group_B.npz'); v=np.load(FG/'val_common.npz'); sup=np.load(FG/'sup_B.npz'); a=np.load(OUT/'label_free_assets.npz'); mean,std=g['mean'],g['std']
def norm(x):
 o=np.array(x,np.float32,copy=True); o[:,25:]=np.clip((o[:,25:]-mean)/std,-10,10); return o
x=torch.as_tensor(norm(g['x']),device='cuda'); e=torch.as_tensor(a[f'train_{key}'],device='cuda'); y=torch.as_tensor(g['y'].astype(np.int64),device='cuda')
xo=torch.as_tensor(norm(np.load(B/'inputs/orig_train/x39.npy')),device='cuda'); eo=torch.as_tensor(np.load(B/'inputs/orig_train/edge_index.npy'),device='cuda'); yo=torch.as_tensor(np.load(B/'inputs/orig_train/y.npy').astype(np.int64),device='cuda')
vx=torch.as_tensor(v['x'],device='cuda'); ve=torch.as_tensor(a[f'val_{key}'],device='cuda')
c=json.load(open(B/'input_contract.json',encoding='utf-8')); rows=a['test_rows']; o=np.array(np.load(B/'inputs/trans_test/x39.npy')[rows],np.float32,copy=True); o[:,25:]=np.clip((o[:,25:]-mean)/std,-10,10); tx=torch.as_tensor(o,device='cuda'); te=torch.as_tensor(a[f'test_{key}'],device='cuda'); ty=np.load(B/'inputs/trans_test/y.npy')[rows]; tt=np.load(B/'inputs/trans_test/trusted.npy')[rows]; tp=np.load(B/'inputs/trans_test/physical.npy')[rows]
loader=FiveGroupLoader(); T.seed(seed); m=Model().cuda(); m.load_state_dict(torch.load(R/f'_p0pilot/control_v3_eligible_20261104/init_s{seed}.pt',map_location='cuda',weights_only=True)); opt=torch.optim.Adam(m.parameters(),lr=2e-4,weight_decay=1e-3)
outdir=OUT/f'run_labelfree_{mode}_s{seed}'; outdir.mkdir(exist_ok=True); logs=[]; best=dict(score=-1,step=-1,state=None)
for step in range(200):
 T.seed(seed+step); m.train(); opt.zero_grad(set_to_none=True)
 io=np.array(loader.step('orig','G0',step).indices,copy=True); ids=np.asarray(sup['idx'][step],dtype=np.int64)
 with torch.autocast('cuda',dtype=torch.bfloat16): lo=m(xo,eo); l_o=T.domain_loss(lo,yo,torch.as_tensor(io,device='cuda'))
 with torch.autocast('cuda',dtype=torch.bfloat16): lt=m(x,e); l_t=T.domain_loss(lt,y,torch.as_tensor(ids,device='cuda')); loss=l_o+l_t
 loss.backward(); gn=float(torch.nn.utils.clip_grad_norm_(m.parameters(),1.0)); opt.step(); logs.append(dict(step=step+1,l_o=float(l_o),l_t=float(l_t),grad=gn,finite=bool(np.isfinite(float(l_o)) and np.isfinite(float(l_t)) and np.isfinite(gn)))); assert logs[-1]['finite']
 if (step+1)%5==0 or step==199:
  m.eval()
  with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16): sv=(m(vx,ve).float()[:,1]-m(vx,ve).float()[:,0]).cpu().numpy()
  aps=[]
  for z in c['shared_inputs']['trans_val']['views']:
   aa,bb=np.searchsorted(v['rows'],[z['start'],z['stop']]); yy,tt2,ss=v['y'][aa:bb],v['trusted'][aa:bb],sv[aa:bb]
   if len(np.unique(yy[tt2]))>1: aps.append(average_precision_score(yy[tt2],ss[tt2]))
  ap=float(np.mean(aps)) if aps else None; logs[-1]['val_ap']=ap
  if ap is not None and ap>best['score']: best=dict(score=ap,step=step+1,state={k:vv.detach().cpu().clone() for k,vv in m.state_dict().items()})
torch.save(dict(model=best['state'],best_step=best['step'],seed=seed),outdir/'best_resume.pt'); outdir.joinpath('LOG.json').write_text(json.dumps(dict(seed=seed,mode=mode,best_step=best['step'],best_score=best['score'],logs=logs),indent=2),encoding='utf-8')
m.load_state_dict(best['state']); m.eval()
with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16): s=(m(tx,te).float()[:,1]-m(tx,te).float()[:,0]).cpu().numpy()
ap={}
for z in c['shared_inputs']['trans_test']['views']:
 aa,bb=np.searchsorted(rows,[z['start'],z['stop']]); yy,tt2,ss=ty[aa:bb],tt[aa:bb],s[aa:bb]
 if len(np.unique(yy[tt2]))>1: ap.setdefault(z['view'].split('__')[-1],[]).append(average_precision_score(yy[tt2],ss[tt2]))
ap={k:float(np.mean(vv)) for k,vv in ap.items()}; base=float(np.mean([ap[r] for r in ('ys_abc','ys_id','ys_opt') if r in ap])); add=float(np.mean([ap[r] for r in ('ys_aig','ys_nand') if r in ap]))
outdir.joinpath('EVAL.json').write_text(json.dumps(dict(seed=seed,mode=mode,best_step=best['step'],base=base,add=add,ap=ap),indent=2),encoding='utf-8')
print('DONE',mode,seed,best['step'],best['score'],base,add,flush=True)
