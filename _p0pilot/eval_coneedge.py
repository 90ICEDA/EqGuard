import os,sys,json
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'): os.environ[k]='1'
os.environ['P2B_MASK']='old'
from pathlib import Path
import numpy as np,torch
from sklearn.metrics import average_precision_score
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); B=R/'_p0pilot/control_boundary_v3_20261104'; OUT=R/'_p0pilot/lcone_relaxed_20261111'; sys.path.insert(0,str(R/'_p0pilot/control_best200_20261104')); sys.path.insert(0,str(R/'_p0pilot/seed42_nc_ablation_20261109')); from evaluate import Model
g=np.load(R/'_p0pilot/four_group_contract_20261109/group_B.npz'); mean,std=g['mean'],g['std']; ea=np.load(OUT/'coneedge_assets.npz')
tx=np.load(B/'inputs/trans_test/x39.npy'); o=np.array(tx,np.float32,copy=True); o[:,25:]=np.clip((o[:,25:]-mean)/std,-10,10); tx=torch.as_tensor(o,device='cuda'); te=torch.as_tensor(ea['test_edge'],device='cuda'); ty=np.load(B/'inputs/trans_test/y.npy'); tt=np.load(B/'inputs/trans_test/trusted.npy')
c=json.load(open(B/'input_contract.json',encoding='utf-8')); views=c['shared_inputs']['trans_test']['views']
for s in (42,1,2):
 m=Model().cuda(); m.load_state_dict(torch.load(OUT/f'run_coneedge_s{s}/best_resume.pt',map_location='cuda',weights_only=False)['model']); m.eval()
 with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16): sc=(m(tx,te).float()[:,1]-m(tx,te).float()[:,0]).cpu().numpy()
 base=[]; add=[]
 for z in views:
  a,b=z['start'],z['stop']; yy,tt2,ss=ty[a:b],tt[a:b],sc[a:b]
  if len(np.unique(yy[tt2]))>1:
   v=average_precision_score(yy[tt2],ss[tt2]); base.append(v)
   if 'ctl' not in z['view']: add.append(v)
 print(s,float(np.mean(base)),float(np.mean(add)),flush=True)
