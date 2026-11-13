"""Phase A2: cone label redundancy from N-B scores; max/mean/top3 aggregation."""
import os, sys, json
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'): os.environ[k]='1'
os.environ['P2B_MASK']='old'
from pathlib import Path
import numpy as np, torch
from sklearn.metrics import average_precision_score
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FG=R/'_p0pilot/four_group_contract_20261109'
V2=R/'_p0pilot/lcone_v2c_20261110'; L=R/'_p0pilot/control_loader_po_20261105'
OUT=R/'_p0pilot/lcone_phaseA_20261110'; OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(L)); sys.path.insert(0,str(R/'_p0pilot/control_best200_20261104'))
from evaluate import Model
g=np.load(FG/'group_B.npz'); mean,std=g['mean'],g['std']
def norm(x):
    o=np.array(x,np.float32,copy=True); o[:,25:]=np.clip((o[:,25:]-mean)/std,-10,10); return o
x=torch.as_tensor(norm(g['x']),device='cuda'); e=torch.as_tensor(g['edge'],device='cuda')
def load(path):
    ck=torch.load(path,map_location='cuda',weights_only=False); m=Model().cuda(); m.load_state_dict(ck['model'] if 'model' in ck else ck); m.eval(); return m
states={'init42':R/'_p0pilot/control_v3_eligible_20261104/init_s42.pt','NB_best42':FG/'run_B_N/best_resume.pt'}
res={}
for sname,path in states.items():
    m=load(path)
    with torch.inference_mode(), torch.autocast('cuda',dtype=torch.bfloat16):
        lg=m(x,e).float(); s=(lg[:,1]-lg[:,0]).cpu().numpy()
    res[sname]={}
    for arm in ('base','all'):
        c=np.load(V2/f'cones_v2c_{arm}_D.npz'); rows=c['rows']; ptr=c['ptr']; lab=c['label']; views=c['view']
        vals={k:[] for k in ('max','mean','top3')}; recs={}
        for i in range(len(lab)):
            mem=rows[ptr[i]:ptr[i+1]]; sc=s[mem]
            vals['max'].append(float(sc.max())); vals['mean'].append(float(sc.mean()))
            k=min(3,len(sc)); vals['top3'].append(float(np.sort(sc)[-k:].mean()))
        for key in ('max','mean','top3'):
            arr=np.array(vals[key]); res[sname][f'{arm}_{key}']=float(average_precision_score(lab,arr))
            dev={}
            for r in ('ys_abc','ys_id','ys_opt','ys_aig','ys_nand'):
                idx=[i for i,v in enumerate(views) if str(v).split('__')[-1]==r]
                if idx and len(set(lab[idx]))>1: dev[r]=float(average_precision_score(lab[idx],arr[idx]))
            res[sname][f'{arm}_{key}_recipe']=dev
        res[sname][f'{arm}_stats']=dict(cones=int(len(lab)),pos=int(lab.sum()),
            pos_members=float(np.mean([len(rows[ptr[i]:ptr[i+1]]) for i in range(len(lab)) if lab[i]==1])),
            neg_members=float(np.mean([len(rows[ptr[i]:ptr[i+1]]) for i in range(len(lab)) if lab[i]==0])))
        del c,rows,ptr,lab,views
    del m; torch.cuda.empty_cache()
(OUT/'CONE_REDUNDANCY.json').write_text(json.dumps(res,indent=2),encoding='utf-8')
print(json.dumps(res,ensure_ascii=False)[:1800])
