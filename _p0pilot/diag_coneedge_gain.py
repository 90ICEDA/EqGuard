import os,sys,json,numpy as np,torch
from pathlib import Path
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'): os.environ[k]='1'
os.environ['P2B_MASK']='old'
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); B=R/'_p0pilot/control_boundary_v3_20261104'; OUT=R/'_p0pilot/lcone_relaxed_20261111'
sys.path.insert(0,str(R/'_p0pilot/control_best200_20261104')); sys.path.insert(0,str(R/'_p0pilot/seed42_nc_ablation_20261109')); from evaluate import Model
from sklearn.metrics import average_precision_score
g=np.load(R/'_p0pilot/four_group_contract_20261109/group_B.npz'); mean,std=g['mean'],g['std']; ea=np.load(OUT/'coneedge_assets.npz')
tx=np.load(B/'inputs/trans_test/x39.npy'); o=np.array(tx,np.float32,copy=True); o[:,25:]=np.clip((o[:,25:]-mean)/std,-10,10); tx=torch.as_tensor(o,device='cuda'); te=torch.as_tensor(ea['test_edge'],device='cuda'); ty=np.load(B/'inputs/trans_test/y.npy'); tt=np.load(B/'inputs/trans_test/trusted.npy'); tp=np.load(B/'inputs/trans_test/physical.npy')
c=json.load(open(B/'input_contract.json',encoding='utf-8'));views=c['shared_inputs']['trans_test']['views']
# degree in cone edges (total edge count)
deg=np.bincount(ea['test_edge'][0],minlength=len(ty))
for s in (1,2,42):
 m=Model().cuda(); m.load_state_dict(torch.load(OUT/f'run_coneedge5_s{s}/best_resume.pt',map_location='cuda',weights_only=False)['model']); m.eval()
 with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16): sc=(m(tx,te).float()[:,1]-m(tx,te).float()[:,0]).cpu().numpy()
 mask=tt&tp; pos=mask&(ty==1); neg=mask&(ty==0); print('seed',s,'pos mean/med',float(sc[pos].mean()),float(np.median(sc[pos])),'neg',float(sc[neg].mean()),float(np.median(sc[neg])),'posdeg',float(deg[pos].mean()),'negdeg',float(deg[neg].mean()))
 for z in views:
  if 'ctl' in z['view']: continue
  a,b=z['start'],z['stop']; mk=tt[a:b]&tp[a:b]; yy=ty[a:b][mk]; ss=sc[a:b][mk]
  if len(np.unique(yy))>1: print(' ',z['view'],round(float(average_precision_score(yy,ss)),3))