"""No-keep41 N smoke: node-only 3 seeds, trusted train mask, check NaN."""
import os,sys,json
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'): os.environ[k]='1'
os.environ['P2B_MASK']='old'
from pathlib import Path
import numpy as np, torch
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); F=R/'generate_trans/folds/nokeep41'; OUT=R/'_p0pilot/nokeep41_runs'; OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(R/'_p0pilot/control_loader_po_20261105')); sys.path.insert(0,str(R/'_p0pilot/control_best200_20261104')); sys.path.insert(0,str(R/'_p0pilot/seed42_nc_ablation_20261109'))
from evaluate import Model,T
from sklearn.metrics import average_precision_score
d=torch.load(F/'data/processed/trans_graph_trusted.pt',map_location='cpu',weights_only=False)
x=d.x.float(); e=d.edge_index.long(); y=d.y.long(); tr=d.trusted.bool(); train=d.train_mask.bool(); val=d.val_mask.bool(); ids=d.file_ids
x=torch.as_tensor(x,device='cuda'); e=torch.as_tensor(e,device='cuda'); y=torch.as_tensor(y,device='cuda'); tr=torch.as_tensor(tr,device='cuda'); tm=torch.as_tensor(train,device='cuda'); vm=torch.as_tensor(val,device='cuda')
mask=tm&tr
for seed in (42,1,2):
 T.seed(seed); m=Model().cuda(); m.load_state_dict(torch.load(R/f'_p0pilot/control_v3_eligible_20261104/init_s{seed}.pt',map_location='cuda',weights_only=True)); opt=torch.optim.Adam(m.parameters(),lr=2e-4,weight_decay=1e-3)
 logs=[]; best=dict(score=-1,step=-1,state=None)
 for step in range(200):
  T.seed(seed+step); m.train(); opt.zero_grad(set_to_none=True)
  with torch.autocast('cuda',dtype=torch.bfloat16):
   lo=m(x,e); loss=T.domain_loss(lo,y,mask)
  loss.backward(); gn=float(torch.nn.utils.clip_grad_norm_(m.parameters(),1.0)); opt.step()
  rec=dict(step=step+1,loss=float(loss),grad=gn,finite=bool(np.isfinite(float(loss)) and np.isfinite(gn))); assert rec['finite']; logs.append(rec)
  if (step+1)%5==0 or step==199:
   m.eval()
   with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16): lg=m(x,e).float(); s=(lg[:,1]-lg[:,0]).cpu().numpy()
   aps=[]
   for v in sorted(set(ids)):
    idx=[i for i,z in enumerate(ids) if z==v and val[i] and tr[i].item()]
    if len(idx)<2: continue
    yy=y[idx].cpu().numpy(); ss=s[idx]
    if len(np.unique(yy))>1: aps.append(average_precision_score(yy,ss))
   ap=float(np.mean(aps)) if aps else None; logs[-1]['val_ap']=ap
   if ap is not None and ap>best['score']: best=dict(score=ap,step=step+1,state={k:v.detach().cpu().clone() for k,v in m.state_dict().items()})
 out=OUT/f'N_s{seed}'; out.mkdir(exist_ok=True)
 torch.save(dict(model=best['state'],best_step=best['step'],seed=seed),out/'best_resume.pt')
 out.joinpath('LOG.json').write_text(json.dumps(dict(seed=seed,best_step=best['step'],best_score=best['score'],logs=logs),indent=2),encoding='utf-8')
 print('DONE N',seed,'best',best['step'],best['score'],flush=True)
