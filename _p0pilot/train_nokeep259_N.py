"""N-only nokeep259 3seed: trusted-only node loss, val/test AP, NaN check."""
import os,sys,json
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'): os.environ[k]='1'
os.environ['P2B_MASK']='old'
from pathlib import Path
import numpy as np, torch
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); F=R/'generate_trans/folds/nokeep41'; B=R/'_p0pilot/control_boundary_v3_20261104'; OUT=R/'_p0pilot/nokeep259_runs'; OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(R/'_p0pilot/control_loader_po_20261105')); sys.path.insert(0,str(R/'_p0pilot/control_best200_20261104')); sys.path.insert(0,str(R/'_p0pilot/seed42_nc_ablation_20261109'))
from evaluate import Model,T
from sklearn.metrics import average_precision_score
g=np.load(F/'group_nokeep259.npz'); val=np.load(R/'_p0pilot/four_group_contract_20261109/val_common.npz')
mean,std=g['mean'],g['std']
def norm(x):
 o=np.array(x,np.float32,copy=True); o[:,25:]=np.clip((o[:,25:]-mean)/std,-10,10); return o
x=torch.as_tensor(norm(g['x']),device='cuda'); e=torch.as_tensor(g['edge'],device='cuda'); y=torch.as_tensor(g['y'].astype(np.int64),device='cuda'); tr=torch.as_tensor(g['trusted'],device='cuda')
vx=torch.as_tensor(val['x'],device='cuda'); ve=torch.as_tensor(val['edge'],device='cuda')
tx=np.load(B/'inputs/trans_test/x39.npy'); te=np.load(B/'inputs/trans_test/edge_index.npy'); ty=np.load(B/'inputs/trans_test/y.npy'); tt=np.load(B/'inputs/trans_test/trusted.npy')
tx=torch.as_tensor(norm(tx),device='cuda'); te=torch.as_tensor(te,device='cuda'); ty=torch.as_tensor(ty.astype(np.int64),device='cuda'); tt=torch.as_tensor(tt,device='cuda')
c=json.load(open(B/'input_contract.json',encoding='utf-8')); vv={z['view']:z for z in c['shared_inputs']['trans_val']['views']}; tv=[z for z in c['shared_inputs']['trans_test']['views'] if 'ctl' not in z['view']]
for seed in (3,4):
 T.seed(seed); m=Model().cuda(); m.load_state_dict(torch.load(R/f'_p0pilot/control_v3_eligible_20261104/init_s{seed}.pt',map_location='cuda',weights_only=True)); opt=torch.optim.Adam(m.parameters(),lr=2e-4,weight_decay=1e-3)
 logs=[]; best=dict(score=-1,step=-1,state=None)
 for step in range(200):
  T.seed(seed+step); m.train(); opt.zero_grad(set_to_none=True)
  with torch.autocast('cuda',dtype=torch.bfloat16): lo=m(x,e); loss=T.domain_loss(lo,y,tr)
  loss.backward(); gn=float(torch.nn.utils.clip_grad_norm_(m.parameters(),1.0)); opt.step()
  rec=dict(step=step+1,loss=float(loss),grad=gn,finite=bool(np.isfinite(float(loss)) and np.isfinite(gn))); assert rec['finite']; logs.append(rec)
  if (step+1)%5==0 or step==199:
   m.eval()
   with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):
    vs=(m(vx,ve).float()[:,1]-m(vx,ve).float()[:,0]).cpu().numpy(); ts=(m(tx,te).float()[:,1]-m(tx,te).float()[:,0]).cpu().numpy()
   aps=[]
   for v in val['views']:
    lay=vv[str(v)]; a,b=np.searchsorted(val['rows'],[lay['start'],lay['stop']]); yy,ttm,ss=val['y'][a:b],val['trusted'][a:b],vs[a:b]
    if len(np.unique(yy[ttm]))>1: aps.append(average_precision_score(yy[ttm],ss[ttm]))
   ap=float(np.mean(aps)) if aps else None; logs[-1]['val_ap']=ap
   if ap is not None and ap>best['score']: best=dict(score=ap,step=step+1,state={k:v.detach().cpu().clone() for k,v in m.state_dict().items()})
 out=OUT/f'N_s{seed}'; out.mkdir(exist_ok=True)
 torch.save(dict(model=best['state'],best_step=best['step'],seed=seed),out/'best_resume.pt')
 # test
 m.load_state_dict(best['state']); m.eval()
 with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16): ts=(m(tx,te).float()[:,1]-m(tx,te).float()[:,0]).cpu().numpy()
 tyn=ty.cpu().numpy(); ttn=tt.cpu().numpy(); taps=[]; vaps2=[]
 for z in tv:
  a,b=z['start'],z['stop']; yy,ttm,ss=tyn[a:b],ttn[a:b],ts[a:b]
  if len(np.unique(yy[ttm]))>1: taps.append(average_precision_score(yy[ttm],ss[ttm]))
 for v in val['views']:
  lay=vv[str(v)]; a,b=np.searchsorted(val['rows'],[lay['start'],lay['stop']]); yy,ttm,ss=val['y'][a:b],val['trusted'][a:b],vs[a:b]
  if len(np.unique(yy[ttm]))>1: vaps2.append(average_precision_score(yy[ttm],ss[ttm]))
 ev=dict(seed=seed,best_step=best['step'],val_ap=float(np.mean(vaps2)),test_ap=float(np.mean(taps)),test_views=len(taps),n_test_pos=int(((tyn==1)&ttn).sum()))
 out.joinpath('EVAL.json').write_text(json.dumps(ev,indent=2),encoding='utf-8'); out.joinpath('LOG.json').write_text(json.dumps(dict(seed=seed,logs=logs),indent=2),encoding='utf-8')
 print('DONE',seed,ev,flush=True)
