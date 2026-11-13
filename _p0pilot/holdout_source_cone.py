"""Cheap source hold-out cone GT: train on other sources, test on held-out source."""
import os,sys,json
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'): os.environ[k]='1'
os.environ['P2B_MASK']='old'
from pathlib import Path
import numpy as np, torch
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FG=R/'_p0pilot/four_group_contract_20261109'; OUT=R/'_p0pilot/lcone_relaxed_20261111'; B=R/'_p0pilot/control_boundary_v3_20261104'
sys.path.insert(0,str(R/'_p0pilot/control_loader_po_20261105')); sys.path.insert(0,str(R/'_p0pilot/control_best200_20261104')); sys.path.insert(0,str(R/'_p0pilot/seed42_nc_ablation_20261109'))
from evaluate import Model,T
import cone_loss as CL
from sklearn.metrics import average_precision_score
holdout=sys.argv[1]; arm=sys.argv[2]; seed=int(sys.argv[3]); lam=0.01
if '|' in holdout: hh,mm=holdout.split('|',1); is_hold=lambda v: str(v).startswith(hh) and mm in str(v)
else: is_hold=lambda v: str(v).startswith(holdout)
g=np.load(FG/'group_B.npz'); c=np.load(OUT/'cones_relaxed_D.npz'); val=np.load(FG/'val_common.npz')
mean,std=g['mean'],g['std']
def norm(x):
 o=np.array(x,np.float32,copy=True); o[:,25:]=np.clip((o[:,25:]-mean)/std,-10,10); return o
x=torch.as_tensor(norm(g['x']),device='cuda'); e=torch.as_tensor(g['edge'],device='cuda'); y=torch.as_tensor(g['y'].astype(np.int64),device='cuda'); tr=torch.as_tensor(g['trusted'],device='cuda')
vx=torch.as_tensor(val['x'],device='cuda'); ve=torch.as_tensor(val['edge'],device='cuda')
# node mask by source
c2=json.load(open(B/'input_contract.json',encoding='utf-8')); rows=g['rows']; loc={int(r):i for i,r in enumerate(rows)}; nmask=np.zeros(len(rows),bool); testmask=np.zeros(len(rows),bool)
for v in c2['shared_inputs']['trans_train']['views']:
 if 'ctl' in v['view']: continue
 dest=testmask if is_hold(v['view']) else nmask
 for gi in range(v['start'],v['stop']):
  i=loc.get(gi)
  if i is not None: dest[i]=True
nmask=torch.as_tensor(nmask,device='cuda'); testmask=torch.as_tensor(testmask,device='cuda')
# cone subset by view prefix
views=c['view']; keep=np.array([not is_hold(v) for v in views]); idxs=np.where(keep)[0]
flat=[]; ptr=[0]; lab=[]
for i in idxs:
 mem=c['rows'][c['ptr'][i]:c['ptr'][i+1]]; flat.extend(mem.tolist()); ptr.append(len(flat)); lab.append(int(c['label'][i]))
ct=dict(rows=list(range(len(lab))),idx=torch.as_tensor(flat,device='cuda'),seg=torch.repeat_interleave(torch.arange(len(lab),device='cuda'),torch.as_tensor(np.diff(ptr),device='cuda')),lab=torch.as_tensor(lab,dtype=torch.float32,device='cuda'))
# test cones
flat2=[]; ptr2=[0]; lab2=[]
for i in np.where(~keep)[0]:
 mem=c['rows'][c['ptr'][i]:c['ptr'][i+1]]; flat2.extend(mem.tolist()); ptr2.append(len(flat2)); lab2.append(int(c['label'][i]))
tidx=torch.as_tensor(flat2,device='cuda'); tseg=torch.repeat_interleave(torch.arange(len(lab2),device='cuda'),torch.as_tensor(np.diff(ptr2),device='cuda')); tlab=torch.as_tensor(lab2,dtype=torch.float32,device='cuda')
T.seed(seed); m=Model().cuda(); m.load_state_dict(torch.load(R/f'_p0pilot/control_v3_eligible_20261104/init_s{seed}.pt',map_location='cuda',weights_only=True)); opt=torch.optim.Adam(m.parameters(),lr=2e-4,weight_decay=1e-3)
logs=[]; best=dict(score=-1,step=-1,state=None)
for step in range(200):
 T.seed(seed+step); m.train(); opt.zero_grad(set_to_none=True)
 with torch.autocast('cuda',dtype=torch.bfloat16): lo=m(x,e); loss=T.domain_loss(lo,y,tr&nmask)
 if arm=='NC':
  with torch.autocast('cuda',dtype=torch.bfloat16): loss=loss+lam*CL.cone_loss(lo,ct,10.0)
 loss.backward(); gn=float(torch.nn.utils.clip_grad_norm_(m.parameters(),1.0)); opt.step(); logs.append(dict(step=step+1,loss=float(loss),grad=gn,finite=bool(np.isfinite(float(loss)) and np.isfinite(gn)))); assert logs[-1]['finite']
 if (step+1)%5==0 or step==199:
  m.eval()
  with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16): lg=m(vx,ve).float(); s=(lg[:,1]-lg[:,0]).cpu().numpy()
  aps=[]
  for v in val['views']:
   lay={z['view']:z for z in c2['shared_inputs']['trans_val']['views']}[str(v)]; a,b=np.searchsorted(val['rows'],[lay['start'],lay['stop']]); yy,tt,ss=val['y'][a:b],val['trusted'][a:b],s[a:b]
   if len(np.unique(yy[tt]))>1: aps.append(average_precision_score(yy[tt],ss[tt]))
  ap=float(np.mean(aps)) if aps else None; logs[-1]['val_ap']=ap
  if ap is not None and ap>best['score']: best=dict(score=ap,step=step+1,state={k:v.detach().cpu().clone() for k,v in m.state_dict().items()})
out=OUT/f"holdout_{holdout.replace('|','_')}_{arm}_s{seed}"; out.mkdir(exist_ok=True); torch.save(dict(model=best['state'],best_step=best['step'],seed=seed,holdout=holdout,arm=arm),out/'best_resume.pt')
# test cones/node
m.load_state_dict(best['state']); m.eval()
with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16): lg=m(x,e).float(); s=(lg[:,1]-lg[:,0]).cpu().numpy()
mx=np.array([s[c['rows'][c['ptr'][i]:c['ptr'][i+1]]].max() for i in np.where(~keep)[0]])
tap=float(average_precision_score(np.array(lab2),mx))
# heldout node AP per view
naps=[]
for v in c2['shared_inputs']['trans_train']['views']:
 if not is_hold(v['view']): continue
 a,b=np.searchsorted(rows,[v['start'],v['stop']]); yy=y.cpu().numpy()[a:b]; tt=tr.cpu().numpy()[a:b]; ss=s[a:b]
 if len(np.unique(yy[tt]))>1: naps.append(average_precision_score(yy[tt],ss[tt]))
ev=dict(holdout=holdout,arm=arm,seed=seed,best_step=best['step'],val_ap=best['score'],test_cone_ap=tap,test_cone_pos=int(sum(lab2)),test_cone_neg=int(len(lab2)-sum(lab2)),test_node_ap=float(np.mean(naps)) if naps else None)
out.joinpath('EVAL.json').write_text(json.dumps(ev,indent=2),encoding='utf-8'); out.joinpath('LOG.json').write_text(json.dumps(dict(logs=logs),indent=2),encoding='utf-8')
print('DONE',ev,flush=True)
