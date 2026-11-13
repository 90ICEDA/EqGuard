import os,sys,json
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'): os.environ[k]='1'
os.environ['P2B_MASK']='old'
from pathlib import Path
import numpy as np,torch
from sklearn.metrics import average_precision_score
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FG=R/'_p0pilot/four_group_contract_20261109'; OUT=R/'_p0pilot/lcone_relaxed_20261111'; B=R/'_p0pilot/control_boundary_v3_20261104'
sys.path.insert(0,str(R/'_p0pilot/control_best200_20261104')); sys.path.insert(0,str(R/'_p0pilot/seed42_nc_ablation_20261109')); from evaluate import Model
mode=sys.argv[1]; run=Path(sys.argv[2]); point=sys.argv[3] if len(sys.argv)>3 else 'best'
c=json.load(open(B/'input_contract.json',encoding='utf-8')); views=c['shared_inputs']['trans_test']['views']; vs={v['view']:v for v in views}
f=B/'inputs/trans_test'; x=np.load(f/'x39.npy'); y=np.load(f/'y.npy'); tr=np.load(f/'trusted.npy'); ph=np.load(f/'physical.npy')
rows=np.concatenate([np.arange(vs[v]['start'],vs[v]['stop']) for v in vs]); o2n=np.full(len(y),-1,np.int64); o2n[rows]=np.arange(len(rows))
g=np.load(FG/'group_B.npz'); mean,std=g['mean'],g['std']; va=np.load(OUT/'coneedge_variants.npz')
if mode in ('B','D'):
 key='ring' if mode=='B' else 'rand'; e=va[f'test_{key}']
else:
 e=va['test_star']
m=(o2n[e[0]]>=0)&(o2n[e[1]]>=0); ee=np.stack([o2n[e[0][m]],o2n[e[1][m]]])
xx=np.array(x[rows],np.float32,copy=True); xx[:,25:]=np.clip((xx[:,25:]-mean)/std,-10,10); tx=torch.as_tensor(xx,device='cuda'); te=torch.as_tensor(ee,device='cuda')
ck=torch.load(run/f'{point}_resume.pt',map_location='cuda',weights_only=False); md=Model().cuda(); md.load_state_dict(ck['model']); md.eval()
with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16): s=(md(tx,te).float()[:,1]-md(tx,te).float()[:,0]).cpu().numpy()
ap={}
for v,lay in vs.items():
 a,b=np.searchsorted(rows,[lay['start'],lay['stop']]); yy,tt,ss=y[a:b],tr[a:b],s[a:b]
 if len(np.unique(yy[tt]))>1: ap.setdefault(v.split('__')[-1],[]).append(average_precision_score(yy[tt],ss[tt]))
ap={k:float(np.mean(v)) for k,v in ap.items()}; base=float(np.mean([ap[r] for r in ('ys_abc','ys_id','ys_opt') if r in ap])); add=float(np.mean([ap[r] for r in ('ys_aig','ys_nand') if r in ap]))
print(json.dumps(dict(mode=mode,run=str(run),base=base,add=add,ap=ap),indent=2))
