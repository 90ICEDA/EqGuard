import os,sys,json,csv
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'): os.environ[k]='1'
os.environ['P2B_MASK']='old'
from pathlib import Path
import numpy as np, torch, torch.nn.functional as F
from sklearn.metrics import average_precision_score
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); sys.path.insert(0,str(R/'_p0pilot/control_loader_po_20261105')); sys.path.insert(0,str(R/'_p0pilot/control_best200_20261104')); sys.path.insert(0,str(R/'_p0pilot/seed42_nc_ablation_20261109'))
from evaluate import Model
g=np.load(R/'_p0pilot/four_group_contract_20261109/group_B.npz'); c=np.load(R/'_p0pilot/lcone_relaxed_20261111/cones_relaxed_D.npz')
mean,std=g['mean'],g['std']
def norm(x):
 o=np.array(x,np.float32,copy=True); o[:,25:]=np.clip((o[:,25:]-mean)/std,-10,10); return o
x=torch.as_tensor(norm(g['x']),device='cuda'); e=torch.as_tensor(g['edge'],device='cuda'); rows=c['rows']; ptr=c['ptr']; lab=c['label']; y=g['y']; tr=g['trusted']
# test graph
B=R/'_p0pilot/control_boundary_v3_20261104'; tx=np.load(B/'inputs/trans_test/x39.npy'); te=np.load(B/'inputs/trans_test/edge_index.npy'); ty=np.load(B/'inputs/trans_test/y.npy'); tt=np.load(B/'inputs/trans_test/trusted.npy')
tx=torch.as_tensor(norm(tx),device='cuda'); te=torch.as_tensor(te,device='cuda'); gloc={i:i for i in range(len(ty))}
trows=[]; tptr=[0]; tlab=[]; tkind=[]
with (R/'_p0pilot/seed42_nc_ablation_20261109/CONE_CACHE_TEST.csv').open(encoding='utf-8-sig',newline='') as f:
 for r in csv.DictReader(f):
  if r['kind'] not in ('D','PO') or int(r['label'])<0 or int(r['n_phys'])<2: continue
  mem=[int(z) for z in r['phys_rows'].split('|') if z]
  if len(mem)<2: continue
  trows.extend(mem); tptr.append(len(trows)); tlab.append(int(r['label'])); tkind.append(r['kind'])
tlab=np.array(tlab); trows=np.array(trows); tptr=np.array(tptr)
def train_metrics(s):
 mx=np.array([s[rows[ptr[i]:ptr[i+1]]].max() for i in range(len(lab))]); mn=np.array([s[rows[ptr[i]:ptr[i+1]]].min() for i in range(len(lab))]); pos=mx[lab==1]; neg=mx[lab==0]; pp=[]
 for i in range(len(lab)):
  if lab[i]!=1: continue
  mem=rows[ptr[i]:ptr[i+1]]; yy=y[mem]; ttr=tr[mem]; ps=s[mem][(yy==1)&ttr]; ns=s[mem][(yy==0)&ttr]
  if len(ps)==0 or len(ns)==0: continue
  order=np.argsort(-s[mem]); top=yy[order[:3]]; pp.append((ps.mean()-ns.mean(),bool(yy[order[0]]==1),top.sum()/len(top)))
 return dict(ap=float(average_precision_score(lab,mx)),gap=float(pos.mean()-neg.mean()),within=float((mx-mn).mean()),intra=float(np.mean([p[0] for p in pp])),top1=float(np.mean([p[1] for p in pp])),top3=float(np.mean([p[2] for p in pp])),negmax=float(neg.mean()),negp90=float(np.quantile(neg,.9)))
def test_metrics(s):
 mx=np.array([s[trows[tptr[i]:tptr[i+1]]].max() for i in range(len(tlab))]); out={}
 for kind in ('D','PO'):
  idx=np.array([i for i,k in enumerate(tkind) if k==kind]); ll=tlab[idx]; vv=mx[idx]
  out[kind]=dict(n=int(len(idx)),pos=int(ll.sum()),ap=float(average_precision_score(ll,vv)) if len(set(ll))>1 else None)
 out['all']=dict(n=int(len(tlab)),pos=int(tlab.sum()),ap=float(average_precision_score(tlab,mx)))
 return out
paths={'max':R/'_p0pilot/lcone_relaxed_20261111/run_relaxed_s42_lam0.01/best_resume.pt','cone-first-posonly':R/'_p0pilot/lcone_relaxed_20261111/run_cone_first_posonly_s42/best_resume.pt','negcomp':R/'_p0pilot/lcone_relaxed_20261111/run_negcomp_s42/best_resume.pt'}
out={}
for k,p in paths.items():
 if not p.exists(): continue
 m=Model().cuda(); m.load_state_dict(torch.load(p,map_location='cuda',weights_only=False)['model']); m.eval()
 with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16): ss=(m(x,e).float()[:,1]-m(x,e).float()[:,0]).cpu().numpy(); st=(m(tx,te).float()[:,1]-m(tx,te).float()[:,0]).cpu().numpy()
 out[k]=dict(train=train_metrics(ss),test=test_metrics(st)); print(k,out[k])
json.dump(out,open(R/'_p0pilot/lcone_relaxed_20261111/TRAIN_TEST_CONE_DIAG.json','w'),indent=2)
