import os,sys,json
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'): os.environ[k]='1'
os.environ['P2B_MASK']='old'
from pathlib import Path
import numpy as np, torch, torch.nn.functional as F
from sklearn.metrics import average_precision_score
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); sys.path.insert(0,str(R/'_p0pilot/control_loader_po_20261105')); sys.path.insert(0,str(R/'_p0pilot/control_best200_20261104')); sys.path.insert(0,str(R/'_p0pilot/seed42_nc_ablation_20261109'))
from evaluate import Model
g=np.load(R/'_p0pilot/four_group_contract_20261109/group_B.npz'); c=np.load(R/'_p0pilot/lcone_relaxed_20261111/cones_relaxed_D.npz'); x=np.array(g['x'],np.float32,copy=True); mean=x[:,25:].mean(0); std=x[:,25:].std(0); std=np.where(std<1e-6,1,std); x[:,25:]=np.clip((x[:,25:]-mean)/std,-10,10); x=torch.as_tensor(x,device='cuda'); e=torch.as_tensor(g['edge'],device='cuda'); rows=c['rows']; ptr=c['ptr']; lab=c['label']; y=g['y']; tr=g['trusted']
def score(p):
 m=Model().cuda(); m.load_state_dict(torch.load(p,map_location='cuda',weights_only=False)['model']); m.eval()
 with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16): s=(m(x,e).float()[:,1]-m(x,e).float()[:,0]).cpu().numpy()
 mx=np.array([s[rows[ptr[i]:ptr[i+1]]].max() for i in range(len(lab))]); mn=np.array([s[rows[ptr[i]:ptr[i+1]]].min() for i in range(len(lab))]); pos=mx[lab==1]; neg=mx[lab==0]
 return dict(loss=F.binary_cross_entropy_with_logits(torch.tensor(mx),torch.tensor(lab,dtype=torch.float32),pos_weight=torch.tensor(10.)).item(),ap=float(average_precision_score(lab,mx)),gap=float(pos.mean()-neg.mean()),within=float((mx-mn).mean()))
out={}
for name in ('lse','lse_aux','lse_aux_rank'):
 out[name]=score(R/f'_p0pilot/lcone_relaxed_20261111/run_design_{name}_s42/best_resume.pt'); print(name,out[name],flush=True)
json.dump(out,open(R/'_p0pilot/lcone_relaxed_20261111/CONE_DESIGN_METRICS_S42.json','w'),indent=2)
