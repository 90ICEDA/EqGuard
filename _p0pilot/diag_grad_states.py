"""Phase A1: gradient scale/direction of cone vs node loss across N-B states."""
import os, sys, json
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'): os.environ[k]='1'
os.environ['P2B_MASK']='old'
from pathlib import Path
import numpy as np, torch
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FG=R/'_p0pilot/four_group_contract_20261109'
B=R/'_p0pilot/control_boundary_v3_20261104'; L=R/'_p0pilot/control_loader_po_20261105'
V2=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train\_p0pilot\lcone_v2c_20261110')
OUT=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train\_p0pilot\lcone_phaseA_20261110'); OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(L)); sys.path.insert(0,str(R/'_p0pilot/control_best200_20261104')); sys.path.insert(0,str(R/'_p0pilot/seed42_nc_ablation_20261109'))
from evaluate import Model,T
import cone_loss as CL
from supervision_loader import FiveGroupLoader
g=np.load(FG/'group_B.npz'); sup=np.load(FG/'sup_B.npz')
mean,std=g['mean'],g['std']
def norm(x):
    o=np.array(x,np.float32,copy=True); o[:,25:]=np.clip((o[:,25:]-mean)/std,-10,10); return o
x=torch.as_tensor(norm(g['x']),device='cuda'); e=torch.as_tensor(g['edge'],device='cuda'); y=torch.as_tensor(g['y'],device='cuda')
xo=torch.as_tensor(norm(np.load(B/'inputs/orig_train/x39.npy')),device='cuda'); eo=torch.as_tensor(np.load(B/'inputs/orig_train/edge_index.npy'),device='cuda'); yo=torch.as_tensor(np.load(B/'inputs/orig_train/y.npy'),device='cuda')
loader=FiveGroupLoader(); io=torch.as_tensor(np.array(loader.step('orig','G0',0).indices,copy=True),device='cuda')
def flat(gs): return torch.cat([q.reshape(-1) for q in gs if q is not None])
def load_state(path):
    ck=torch.load(path,map_location='cuda',weights_only=False); m=Model().cuda(); m.load_state_dict(ck['model'] if 'model' in ck else ck); m.train(); return m
states={
 'init42':R/'_p0pilot/control_v3_eligible_20261104/init_s42.pt',
 'NB_best42':FG/'run_B_N/best_resume.pt',
 'NB_last42':FG/'run_B_N/last_resume.pt',
 'NB_best1':FG/'run_B_N_s1/best_resume.pt',
 'NB_best2':FG/'run_B_N_s2/best_resume.pt',
}
cone_sets={}
for arm in ('base','all'):
    c=np.load(V2/f'cones_v2c_{arm}_D.npz')
    cone_sets[arm]=c
res={}
for sname,path in states.items():
    m=load_state(path); params=[p for p in m.parameters() if p.requires_grad]
    io_t=io; it=torch.as_tensor(sup['idx'][0],device='cuda')
    with torch.autocast('cuda',dtype=torch.bfloat16):
        lo=m(xo,eo); l_o=T.domain_loss(lo,yo,io_t)
    l_o.backward()
    res[sname]={}
    for arm,c in cone_sets.items():
        ct=dict(rows=list(range(len(c['label']))),idx=torch.as_tensor(c['rows'],device='cuda'),
                seg=torch.repeat_interleave(torch.arange(len(c['label']),device='cuda'),torch.as_tensor(np.diff(c['ptr']),device='cuda')),
                lab=torch.as_tensor(c['label'],dtype=torch.float32,device='cuda'))
        with torch.autocast('cuda',dtype=torch.bfloat16):
            lt=m(x,e); l_t=T.domain_loss(lt,y,it); l_c=CL.cone_loss(lt,ct,pos_weight=10.0)
        gn=torch.autograd.grad(l_t,params,retain_graph=True,allow_unused=True)
        gc=torch.autograd.grad(l_c,params,retain_graph=True,allow_unused=True)
        vn,vc=flat(gn),flat(gc)
        cos=float(torch.dot(vn,vc)/(vn.norm()*vc.norm()+1e-12))
        proj=float(torch.dot(vn,vc)/(vn.norm()**2+1e-12))
        res[sname][arm]=dict(node_norm=float(vn.norm()),cone_norm=float(vc.norm()),ratio=float(vc.norm()/vn.norm()),
                             cosine=cos,residual_frac=float((vc-proj*vn).norm()/(vc.norm()+1e-12)),
                             loss_node=float(l_t),loss_cone=float(l_c),cones=int(len(c['label'])))
        del lt,l_c,gn,gc,vn,vc; torch.cuda.empty_cache()
    del m,l_o,lo; torch.cuda.empty_cache()
(OUT/'GRAD_STATES.json').write_text(json.dumps(res,indent=2),encoding='utf-8')
print(json.dumps(res,ensure_ascii=False)[:2000])
