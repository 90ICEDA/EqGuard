import os,sys,json,csv
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'): os.environ[k]='1'
os.environ['P2B_MASK']='old'
from pathlib import Path
import numpy as np,torch
from sklearn.metrics import average_precision_score
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); B=R/'_p0pilot/control_boundary_v3_20261104'; OUT=R/'_p0pilot/lcone_relaxed_20261111'; OLD=R/'_p0pilot/seed42_nc_ablation_20261109'
sys.path.insert(0,str(R/'_p0pilot/control_best200_20261104')); sys.path.insert(0,str(OLD)); from evaluate import Model
g=np.load(R/'_p0pilot/four_group_contract_20261109/group_B.npz'); mean,std=g['mean'],g['std']
def norm(x):
 o=np.array(x,np.float32,copy=True); o[:,25:]=np.clip((o[:,25:]-mean)/std,-10,10); return o
tx=np.load(B/'inputs/trans_test/x39.npy'); ty=np.load(B/'inputs/trans_test/y.npy'); tt=np.load(B/'inputs/trans_test/trusted.npy'); tp=np.load(B/'inputs/trans_test/physical.npy'); tx=torch.as_tensor(norm(tx),device='cuda'); te=torch.as_tensor(np.load(B/'inputs/trans_test/edge_index.npy'),device='cuda')
c=json.load(open(B/'input_contract.json',encoding='utf-8')); views=c['shared_inputs']['trans_test']['views']; tset={z['view'] for z in views if 'ctl' not in z['view']}
m=Model().cuda(); m.load_state_dict(torch.load(R/'_p0pilot/lcone_relaxed_20261111/run_relaxed_s42_lam0.01/best_resume.pt',map_location='cuda',weights_only=False)['model']); m.eval()
with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16): s=(m(tx,te).float()[:,1]-m(tx,te).float()[:,0]).cpu().numpy()
print('counts',dict(total=len(ty),phys=int(tp.sum()),trusted=int(tt.sum()),pos=int((ty==1).sum()),neg=int((ty==0).sum()),unk=int((ty==-1).sum()),trusted_pos=int(((ty==1)&tt).sum()),trusted_neg=int(((ty==0)&tt).sum())))
mask=tt&tp
pos=mask&(ty==1); neg=mask&(ty==0)
print('trusted pos/neg',int(pos.sum()),int(neg.sum()),'score pos mean/med',float(s[pos].mean()),float(np.median(s[pos])),'neg',float(s[neg].mean()),float(np.median(s[neg])))
print('pos quantiles',np.quantile(s[pos],[0,.1,.25,.5,.75,.9,1])); print('neg quantiles',np.quantile(s[neg],[0,.1,.5,.9,.99,1]))
print('AP trusted',average_precision_score(ty[mask],s[mask]))
# top-k precision among trusted
for k in (10,20,50,100,200):
 idx=np.argsort(-s[mask])[:k]; print('top',k,'prec',float((ty[mask][idx]==1).mean()))
# per recipe
for z in views:
 if 'ctl' in z['view']: continue
 a,b=z['start'],z['stop']; mk=tt[a:b]&tp[a:b]; yy=ty[a:b][mk]; ss=s[a:b][mk]
 if len(np.unique(yy))>1: print('view',z['view'],'n',len(yy),'pos',int((yy==1).sum()),'ap',round(float(average_precision_score(yy,ss)),4))
# cone coverage
trows=[]; tptr=[0]; tlab=[]; tv=[]
with (OLD/'CONE_CACHE_TEST.csv').open(encoding='utf-8-sig',newline='') as f:
 for r in csv.DictReader(f):
  if r['kind'] not in ('D','PO') or int(r['label'])<0 or int(r['n_phys'])<2: continue
  mem=[int(z) for z in r['phys_rows'].split('|') if z]
  if len(mem)>=2: trows.extend(mem); tptr.append(len(trows)); tlab.append(int(r['label'])); tv.append(r['view'])
trows=np.array(trows); tptr=np.array(tptr); tlab=np.array(tlab)
poscone=np.zeros(len(ty),bool)
for i,l in enumerate(tlab):
 if l==1: poscone[trows[tptr[i]:tptr[i+1]]]=True
print('trusted pos in any poscone',int((poscone&(ty==1)&tt).sum()),'of',int(((ty==1)&tt).sum()),'all pos in poscone',int((poscone&(ty==1)).sum()),'of',int((ty==1).sum()))
# positive cone purity
pur=[]
for i,l in enumerate(tlab):
 if l!=1: continue
 mem=trows[tptr[i]:tptr[i+1]]; pur.append((int((ty[mem]==1).sum()),int(((ty[mem]==0)&tt[mem]).sum()),len(mem)))
pur=np.array(pur); print('poscone members pos/trustedneg/total mean',pur.mean(0),'frac cones with 0 pos',float((pur[:,0]==0).mean()))
