"""C2 held-out runner: 3 folds x N/NC x seeds 42/1/2, 200 updates, fold assets."""
import argparse
import copy
import os, sys, json, csv, hashlib, time
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'): os.environ[k]='1'
os.environ['P2B_MASK']='old'
from pathlib import Path
import numpy as np, torch
from sklearn.metrics import average_precision_score
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); A=R/'_p0pilot/c2_heldout_20261111'
B=R/'_p0pilot/control_boundary_v3_20261104'; L=R/'_p0pilot/control_loader_po_20261105'
OLD=R/'_p0pilot/seed42_nc_ablation_20261109'
sys.path.insert(0,str(L)); sys.path.insert(0,str(R/'_p0pilot/control_best200_20261104')); sys.path.insert(0,str(OLD))
from evaluate import Model,T
from supervision_loader import FiveGroupLoader
import cone_loss as CL
from c2_p90_anchor import CompressionLoss, load_cones

SEEDS=(42,1,2); FOLDS=('ys_abc','ys_aig','ys_nand')
c=json.load(open(B/'input_contract.json',encoding='utf-8'))
orig_x=np.load(B/'inputs/orig_train/x39.npy'); orig_e=np.load(B/'inputs/orig_train/edge_index.npy'); orig_y=np.load(B/'inputs/orig_train/y.npy')
loader=FiveGroupLoader()
# test cone cache mapped per fold
cache=list(csv.DictReader(open(OLD/'CONE_CACHE_TEST.csv',encoding='utf-8-sig',newline='')))

def norm(raw,mean,std):
    o=np.array(raw,np.float32,copy=True); o[:,25:]=np.clip((o[:,25:]-mean)/std,-10,10); return o

def build_test_cones(h, test):
    # map global test rows to local h-test rows
    tev=[v for v in c['shared_inputs']['trans_test']['views'] if v['view'].split('__')[-1]==h and 'ctl' not in v['view']]
    # local view ranges from asset
    vmap={str(v):(int(s),int(t)) for v,s,t in zip(test['view'],test['start'],test['stop'])}
    g2l={}
    for v in tev:
        ls,le=vmap[v['view']]
        for gi in range(v['start'],v['stop']): g2l[gi]=ls+(gi-v['start'])
    arr=[]
    for r in cache:
        if r['view'] not in vmap or r['kind'] not in ('D','PO') or int(r['n_phys'])<2 or int(r['label'])<0: continue
        mem=[]
        for z in r['phys_rows'].split('|'):
            if not z: continue
            li=g2l.get(int(z))
            if li is not None: mem.append(li)
        if len(mem)>=2: arr.append(dict(kind=r['kind'],label=int(r['label']),mem=np.array(mem)))
    return arr

def eval_ckpt(model,val,test,test_cones,fold,seed,arm):
    vx=torch.as_tensor(norm(val['x'],val['mean'],val['std']),device='cuda'); ve=torch.as_tensor(val['edge'],device='cuda')
    tx=torch.as_tensor(norm(test['x'],test['mean'],test['std']),device='cuda'); te=torch.as_tensor(test['edge'],device='cuda')
    model.eval()
    with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):
        vs=(model(vx,ve).float()[:,1]-model(vx,ve).float()[:,0]).cpu().numpy()
        ts=(model(tx,te).float()[:,1]-model(tx,te).float()[:,0]).cpu().numpy()
    vaps=[]; taps=[]
    for v,s,t in zip(val['view'],val['start'],val['stop']):
        yy,tt,ss=val['y'][s:t],val['trusted'][s:t],vs[s:t]
        if len(np.unique(yy[tt]))>1: vaps.append(average_precision_score(yy[tt],ss[tt]))
    for v,s,t in zip(test['view'],test['start'],test['stop']):
        yy,tt,ss=test['y'][s:t],test['trusted'][s:t],ts[s:t]
        if len(np.unique(yy[tt]))>1: taps.append(average_precision_score(yy[tt],ss[tt]))
    # thresholds from val negatives at target FPR
    vn=vs[(val['trusted']&val['physical']&(val['y']==0))]
    tp=(test['trusted']&test['physical']&(test['y']==1)); tn=(test['trusted']&test['physical']&(test['y']==0))
    recalls={}
    for fpr in (1e-4,1e-3,1e-2):
        thr=float(np.quantile(vn,1-fpr)); recalls[str(fpr)]=float((ts[tp]>=thr).mean()) if tp.sum() else None
    # cone ap
    cone={}
    for kind in ('D','PO'):
        arr=[x for x in test_cones if x['kind']==kind]; lab=np.array([x['label'] for x in arr]); vals=np.array([float(ts[x['mem']].max()) for x in arr])
        cone[kind]=dict(n=int(len(arr)),pos=int(lab.sum()),neg=int((lab==0).sum()),ap=float(average_precision_score(lab,vals)) if len(set(lab))>1 else None)
    return dict(fold=fold,seed=seed,arm=arm,val_ap=float(np.mean(vaps)) if vaps else None,test_node_ap=float(np.mean(taps)) if taps else None,
                recall_at_fpr=recalls,cone_ap=cone,test_pos=int(tp.sum()),test_neg=int(tn.sum()),val_views=len(val['view']),test_views=len(test['view']))

def run(fold,arm,seed,anchor_mode='legacy',rank_mode='legacy'):
    if rank_mode == 'exact':
        run_dir = 'runs_p90_exact_zero' if anchor_mode == 'legacy' else 'runs_p90_exact_view_q25'
    else:
        run_dir = 'runs_p90' if anchor_mode == 'legacy' else 'runs_p90_view_q25'
    out=A/run_dir/f'{fold}_{arm}_s{seed}'; out.mkdir(parents=True,exist_ok=True)
    if (out/'EVAL.json').exists():
        print('REUSE',fold,arm,seed,flush=True); return
    tr=np.load(A/f'{fold}_train.npz',allow_pickle=True); sup=np.load(A/f'{fold}_sup.npz',allow_pickle=True)
    co = load_cones(A, fold, 'view-q25' if rank_mode == 'exact' else anchor_mode)
    val=np.load(A/f'{fold}_val.npz',allow_pickle=True); test=np.load(A/f'{fold}_test.npz',allow_pickle=True)
    x=torch.as_tensor(norm(tr['x'],tr['mean'],tr['std']),device='cuda'); e=torch.as_tensor(tr['edge'],device='cuda'); y=torch.as_tensor(tr['y'],device='cuda')
    ox=torch.as_tensor(norm(orig_x,tr['mean'],tr['std']),device='cuda'); oe=torch.as_tensor(orig_e,device='cuda'); oy=torch.as_tensor(orig_y,device='cuda')
    p90_losses = CompressionLoss(co, tr['view'], anchor_mode, 'cuda', rank_mode)
    T.seed(seed); model=Model().cuda(); model.load_state_dict(torch.load(R/f'_p0pilot/control_v3_eligible_20261104/init_s{seed}.pt',map_location='cuda',weights_only=True))
    opt=torch.optim.Adam(model.parameters(),lr=2e-4,weight_decay=1e-3)
    logs=[]; best=dict(score=-1,step=-1,state=None,opt=None)
    for step in range(200):
        T.seed(seed+step); model.train(); opt.zero_grad(set_to_none=True)
        io=np.array(loader.step('orig','G0',step).indices,copy=True)
        with torch.autocast('cuda',dtype=torch.bfloat16):
            lo=model(ox,oe); l_o=T.domain_loss(lo,oy,torch.as_tensor(io,device='cuda'))
        l_o.backward()
        ids=np.asarray(sup['idx'][step],dtype=np.int64)
        with torch.autocast('cuda',dtype=torch.bfloat16):
            lt=model(x,e); l_t=T.domain_loss(lt,y,torch.as_tensor(ids,device='cuda'))
            if arm=='N': bce=torch.tensor(0.,device='cuda'); comp=torch.tensor(0.,device='cuda'); loss=l_t
            else:
                bce,comp=p90_losses(lt); loss=l_t+0.01*bce+(0.03*comp if step<100 else 0.0)
        loss.backward(); gn=float(torch.nn.utils.clip_grad_norm_(model.parameters(),1.0)); opt.step()
        rec=dict(step=step+1,node_orig=l_o.detach().item(),node_trans=l_t.detach().item(),
                 bce=bce.detach().item(),comp=comp.detach().item(),grad_norm=gn,
                 orig_sample_sha256=hashlib.sha256(io.tobytes()).hexdigest(),
                 trans_sample_sha256=hashlib.sha256(ids.tobytes()).hexdigest())
        rec['finite'] = bool(np.isfinite([rec[k] for k in ('node_orig','node_trans','bce','comp','grad_norm')]).all())
        assert rec['finite']; logs.append(rec)
        if (step+1)%5==0 or step==199:
            model.eval(); vx=torch.as_tensor(norm(val['x'],val['mean'],val['std']),device='cuda'); ve=torch.as_tensor(val['edge'],device='cuda')
            with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):
                vs=(model(vx,ve).float()[:,1]-model(vx,ve).float()[:,0]).cpu().numpy()
            aps=[]
            for v,s,t in zip(val['view'],val['start'],val['stop']):
                yy,tt,ss=val['y'][s:t],val['trusted'][s:t],vs[s:t]
                if len(np.unique(yy[tt]))>1: aps.append(average_precision_score(yy[tt],ss[tt]))
            ap=float(np.mean(aps)) if aps else None; logs[-1]['val_ap']=ap
            if ap is not None and ap>best['score']:
                best=dict(score=ap,step=step+1,state={k:v.detach().cpu().clone() for k,v in model.state_dict().items()},
                          opt=copy.deepcopy(opt.state_dict()))
    last={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
    for point,st,op in (('best',best['state'],best['opt']),('last',last,opt.state_dict())):
        torch.save(dict(model=st,optimizer=op,completed=200,best_step=best['step'],fold=fold,arm=arm,seed=seed),out/f'{point}_resume.pt')
    test_cones=build_test_cones(fold,test)
    ev={}
    for point in ('best','last'):
        ck=torch.load(out/f'{point}_resume.pt',map_location='cuda',weights_only=False); model.load_state_dict(ck['model'])
        ev[point]=eval_ckpt(model,val,test,test_cones,fold,seed,arm); ev[point]['best_step']=best['step']
    out.joinpath('LOG.json').write_text(json.dumps(dict(fold=fold,arm=arm,seed=seed,anchor_mode=anchor_mode,rank_mode=rank_mode,best_step=best['step'],best_score=best['score'],logs=logs),indent=2),encoding='utf-8')
    out.joinpath('EVAL.json').write_text(json.dumps(ev,indent=2),encoding='utf-8')
    print('DONE',fold,arm,seed,best['step'],best['score'],ev['best']['test_node_ap'],flush=True)
    del model; torch.cuda.empty_cache()

if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--fold', choices=FOLDS, action='append')
    parser.add_argument('--arm', choices=('N', 'NC'), action='append')
    parser.add_argument('--seed', choices=SEEDS, type=int, action='append')
    parser.add_argument('--anchor', choices=('legacy', 'view-q25'), default='legacy')
    parser.add_argument('--rank', choices=('legacy', 'exact'), default='legacy')
    args = parser.parse_args()
    for fold in args.fold or FOLDS:
        for arm in args.arm or ('N', 'NC'):
            for seed in args.seed or SEEDS:
                run(fold,arm,seed,args.anchor,args.rank)
