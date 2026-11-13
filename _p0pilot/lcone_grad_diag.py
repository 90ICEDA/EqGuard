"""Offline gradient-conflict diagnostic for L_cone on N-B at step0."""
import os, sys, json
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'): os.environ[k]='1'
os.environ['P2B_MASK']='old'
from pathlib import Path
import numpy as np, torch
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FG=R/'_p0pilot/four_group_contract_20261109'
B=R/'_p0pilot/control_boundary_v3_20261104'; L=R/'_p0pilot/control_loader_po_20261105'
sys.path.insert(0,str(L)); sys.path.insert(0,str(R/'_p0pilot/control_best200_20261104')); sys.path.insert(0,str(R/'_p0pilot/seed42_nc_ablation_20261109'))
from evaluate import Model,T
import cone_loss as CL
from supervision_loader import FiveGroupLoader
g=np.load(FG/'group_B.npz'); sup=np.load(FG/'sup_B.npz'); val=np.load(FG/'val_common.npz')
mean,std=g['mean'],g['std']
def norm(x):
    o=np.array(x,np.float32,copy=True); o[:,25:]=np.clip((o[:,25:]-mean)/std,-10,10); return o
x=torch.as_tensor(norm(g['x']),device='cuda'); e=torch.as_tensor(g['edge'],device='cuda'); y=torch.as_tensor(g['y'],device='cuda')
xo=torch.as_tensor(norm(np.load(B/'inputs/orig_train/x39.npy')),device='cuda'); eo=torch.as_tensor(np.load(B/'inputs/orig_train/edge_index.npy'),device='cuda'); yo=torch.as_tensor(np.load(B/'inputs/orig_train/y.npy'),device='cuda')
loader=FiveGroupLoader(); T.seed(42)
m=Model().cuda(); m.load_state_dict(torch.load(FG/'run_B_N/best_resume.pt',map_location='cuda',weights_only=False)['model']); m.train()
params=[p for p in m.parameters() if p.requires_grad]
out={}
for arm in ('base','all'):
    c=np.load(FG.parent/'lcone_v2c_20261110'/f'cones_v2c_{arm}_D.npz')
    ct=dict(rows=list(range(len(c['label']))),idx=torch.as_tensor(c['rows'],device='cuda'),
            seg=torch.repeat_interleave(torch.arange(len(c['label']),device='cuda'),torch.as_tensor(np.diff(c['ptr']),device='cuda')),
            lab=torch.as_tensor(c['label'],dtype=torch.float32,device='cuda'))
    io=torch.as_tensor(np.array(loader.step('orig','G0',0).indices,copy=True),device='cuda')
    with torch.autocast('cuda',dtype=torch.bfloat16):
        lo=m(xo,eo); l_o=T.domain_loss(lo,yo,io)
    l_o.backward()
    with torch.autocast('cuda',dtype=torch.bfloat16):
        lt=m(x,e); l_t=T.domain_loss(lt,y,torch.as_tensor(sup['idx'][0],device='cuda')); l_c=CL.cone_loss(lt,ct,pos_weight=10.0)
    gn=torch.autograd.grad(l_t,params,retain_graph=True,allow_unused=True)
    gc=torch.autograd.grad(l_c,params,retain_graph=True,allow_unused=True)
    def flat(gs): return torch.cat([q.reshape(-1) for q in gs if q is not None])
    vn,vc=flat(gn),flat(gc)
    cos=float(torch.dot(vn,vc)/(vn.norm()*vc.norm()+1e-12))
    proj=float(torch.dot(vn,vc)/(vn.norm()**2+1e-12))
    res=(vc-proj*vn).norm()
    out[arm]=dict(node_norm=float(vn.norm()),cone_norm=float(vc.norm()),ratio=float(vc.norm()/vn.norm()),
                  cosine=cos,proj_coeff=proj,residual_frac=float(res/(vc.norm()+1e-12)),
                  loss_node=float(l_t),loss_cone=float(l_c),cones=int(len(c['label'])),pos=int(c['label'].sum()))
(FG.parent/'lcone_grad_diag_20261110').mkdir(exist_ok=True)
(FG.parent/'lcone_grad_diag_20261110'/'GRAD_DIAG.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False))
