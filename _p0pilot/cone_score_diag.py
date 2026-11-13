"""Cone loss / within-vs-between score diagnostics for relaxed max."""
import os,sys,json
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'): os.environ[k]='1'
os.environ['P2B_MASK']='old'
from pathlib import Path
import numpy as np, torch, torch.nn.functional as F
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); L=R/'_p0pilot/control_loader_po_20261105'; OLD=R/'_p0pilot/seed42_nc_ablation_20261109'; PREP=R/'_p0pilot/seed42_supervised_prep_20261109'
sys.path.insert(0,str(L)); sys.path.insert(0,str(R/'_p0pilot/control_best200_20261104')); sys.path.insert(0,str(OLD))
from evaluate import Model,T
g=np.load(R/'_p0pilot/four_group_contract_20261109/group_B.npz'); c=np.load(R/'_p0pilot/lcone_relaxed_20261111/cones_relaxed_D.npz')
x=np.array(g['x'],np.float32,copy=True); mean=x[:,25:].mean(0); std=x[:,25:].std(0); std=np.where(std<1e-6,1,std)
x[:,25:]=np.clip((x[:,25:]-mean)/std,-10,10)
x=torch.as_tensor(x,device='cuda'); e=torch.as_tensor(g['edge'],device='cuda')
rows=torch.as_tensor(c['rows'],device='cuda'); ptr=torch.as_tensor(c['ptr'],device='cuda'); lab=torch.as_tensor(c['label'],dtype=torch.float32,device='cuda')
seg=torch.repeat_interleave(torch.arange(len(lab),device='cuda'),torch.diff(ptr))
out={}
def score(ckpt):
    m=Model().cuda(); m.load_state_dict(torch.load(ckpt,map_location='cuda',weights_only=True)); m.eval()
    with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):
        logits=m(x,e).float(); s=(logits[:,1]-logits[:,0])
    # cones
    sr=s[rows]
    mx=torch.full((len(lab),),-1e9,device='cuda'); mn=torch.full((len(lab),),1e9,device='cuda')
    mx.scatter_reduce_(0,seg,sr,reduce='amax'); mn.scatter_reduce_(0,seg,sr,reduce='amin')
    # per-cone mean
    sm=torch.zeros(len(lab),device='cuda'); sm.index_add_(0,seg,sr); cnt=torch.bincount(seg,minlength=len(lab)).float(); sm=sm/cnt
    loss=F.binary_cross_entropy_with_logits(mx,lab,pos_weight=torch.tensor(10.,device='cuda')).item()
    pos=mx[lab==1].cpu().numpy(); neg=mx[lab==0].cpu().numpy()
    return dict(loss=loss,ap=float(__import__('sklearn.metrics',fromlist=['average_precision_score']).average_precision_score(lab.cpu().numpy(),mx.cpu().numpy())),
        pos_mean=float(pos.mean()),neg_mean=float(neg.mean()),gap=float(pos.mean()-neg.mean()),
        within_std=float((mx-mn).mean()),within_std_std=float((mx-mn).std()),
        mean_std=float((sr-sm[seg]).pow(2).mean().sqrt()), pos_n=int(len(pos)),neg_n=int(len(neg)))
for name,p in [('init',R/'_p0pilot/control_v3_eligible_20261104/init_s42.pt'),('best',R/'_p0pilot/lcone_relaxed_20261111/run_relaxed_s42_lam0.01/best_resume.pt'),('last',R/'_p0pilot/lcone_relaxed_20261111/run_relaxed_s42_lam0.01/last_resume.pt')]:
    d=torch.load(p,map_location='cuda',weights_only=False) if name!='init' else {'model':torch.load(p,map_location='cuda',weights_only=True)}
    tmp=R/'_p0pilot/lcone_relaxed_20261111/_tmp_s42.pt'; torch.save(d['model'] if 'model' in d else d,tmp)
    out[name]=score(tmp)
json.dump(out,open(R/'_p0pilot/lcone_relaxed_20261111/CONE_SCORE_DIAG_S42.json','w'),indent=2)
print(json.dumps(out,indent=2))
