"""Seed42 P2-A controlled encoding comparison. Uses ginvenv_gpu, no SAT."""
import os
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'):os.environ[k]='1'
import sys,json,time,random,hashlib,csv,importlib.util,gc
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import torch
from sklearn.metrics import average_precision_score,roc_auc_score
ROOT=Path(__file__).resolve().parents[2];H=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from models.gin_net import GINNodeClassifier
spec=importlib.util.spec_from_file_location('legacy22',ROOT/'train_test2.2.py');L=importlib.util.module_from_spec(spec);spec.loader.exec_module(L)
torch.set_num_threads(2)
CONTRACT=json.loads((H/'input_contract.json').read_text());NORM=np.load(H/'normalization.npz')
PRIM=torch.from_numpy(np.load(H/'primitive_matrix.npy')).cuda()
DEVICE='cuda';EPOCHS=100;SEED=42
def write(p,x):
    tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8');os.replace(tmp,p)
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def seed(s):
    random.seed(s);np.random.seed(s);torch.manual_seed(s);torch.cuda.manual_seed_all(s)
def arrays(key):
    folder=ROOT/CONTRACT['shared_inputs'][key]['folder']
    return {name:np.load(folder/(name+'.npy'),mmap_mode='r') for name in ('x39','edge_index','y','trusted','physical')}
def load(key,arm):
    a=arrays(key);x=torch.tensor(np.asarray(a['x39']),device=DEVICE)
    structural=((x[:,25:]-torch.tensor(NORM['mean'][25:],device=DEVICE))/torch.tensor(NORM['std'][25:],device=DEVICE)).clamp(-10,10)
    x=torch.cat((x[:,:25] if arm=='base39' else x[:,:25]@PRIM,structural),1)
    return dict(x=x,edge=torch.tensor(np.asarray(a['edge_index']),device=DEVICE),
        y=torch.tensor(np.asarray(a['y']),device=DEVICE),mask=torch.tensor(np.asarray(a['trusted']),device=DEVICE))
def domain_loss(logits,y,mask):
    selected=logits[mask].float();labels=y[mask]
    task=L.compute_task_loss(selected,labels,loss_type='asl')
    recall=L.calc_soft_f1_metrics(torch.softmax(selected/.5,1),labels)[3]
    return task+1.4*(1-recall).square()
def loss_check():
    seed(SEED)
    a=torch.randn(11,2,requires_grad=True);b=torch.randn(13,2,requires_grad=True)
    ya=torch.tensor([0,1,0,0,0,1,0,0,1,0,0]);yb=torch.tensor([0,1,0,0,0,1,0,0,0,0,0,0,1])
    ma=torch.ones(11,dtype=torch.bool);mb=torch.ones(13,dtype=torch.bool)
    o=SimpleNamespace(train_mask=ma,x=torch.ones(11,39));t=SimpleNamespace(train_mask=mb,x=torch.ones(13,39),alignment=torch.empty(2,0,dtype=torch.long))
    old=L.siamese_loss(a,b,ya,yb,o,t,lambda_const=0,lambda_det=1.4,lambda_pos=0,lambda_nor=0,trojan_w=6,loss_type='asl',include_trans_loss=True)[0]
    new=domain_loss(a,ya,ma)+domain_loss(b,yb,mb)
    assert torch.allclose(old,new,atol=1e-7)
    go=torch.autograd.grad(old,(a,b),retain_graph=True);gn=torch.autograd.grad(new,(a,b))
    assert all(torch.allclose(x,y,atol=1e-7) for x,y in zip(go,gn))
    return dict(passed=True,legacy_loss=float(old.detach()),new_loss=float(new.detach()),max_gradient_difference=max(float((x-y).abs().max()) for x,y in zip(go,gn)),feature_index_reads=False)
def metrics(scores,key,threshold=.5):
    a=arrays(key);yy=a['y'];rows=[]
    for view in CONTRACT['shared_inputs'][key]['views']:
        lo,hi=view['start'],view['stop']
        for scope,mask in [('trusted',a['trusted'][lo:hi]),('legacy',a['physical'][lo:hi])]:
            y=yy[lo:hi][mask];p=scores[lo:hi][mask];pos=int(y.sum());neg=len(y)-pos
            row=dict(view=view['view'],scope=scope,n=len(y),positive=pos,negative=neg,
                ap=float(average_precision_score(y,p)) if pos else None,
                auc=float(roc_auc_score(y,p)) if pos and neg else None,
                fpr=float((p[y==0]>=threshold).mean()) if neg else None,
                threshold=threshold,recall=float((p[y==1]>=threshold).mean()) if pos else None)
            for budget in (.01,.05):
                k=max(1,int(len(y)*budget));order=np.argsort(-p,kind='stable')
                row['r'+str(int(budget*100))]=float(y[order[:k]].sum()/pos) if pos else None
            rows.append(row)
    summary={}
    for scope in ('trusted','legacy'):
        inj=[r for r in rows if r['scope']==scope and '__inj' in r['view'] and r['positive']]
        summary[scope]={k:float(np.mean([r[k] for r in inj if r[k] is not None])) for k in ('ap','auc','r1','r5','recall')}
        summary[scope]['views']=len(inj)
        controls=[r for r in rows if r['scope']==scope and '__inj' not in r['view'] and r['negative']]
        summary[scope]['control_fpr']=float(np.mean([r['fpr'] for r in controls])) if controls else None
    return summary,rows
def predict(model,key,arm):
    d=load(key,arm);model.eval()
    with torch.no_grad(),torch.autocast('cuda',dtype=torch.bfloat16):p=model(d['x'],d['edge'])
    score=torch.softmax(p.float(),1)[:,1].cpu().numpy();del p,d;gc.collect();torch.cuda.empty_cache()
    assert np.isfinite(score).all()
    return score
def model_for(arm):
    seed(SEED);return GINNodeClassifier(39 if arm=='base39' else 21,64,2,4).cuda()
def train_arm(arm):
    out=H/'runs'/arm;out.mkdir(parents=True,exist_ok=True)
    if (out/'SELECTED.json').exists():return json.loads((out/'SELECTED.json').read_text())
    model=model_for(arm);common=H/'common_init.pt'
    if common.exists():
        reference=torch.load(common,map_location=DEVICE,weights_only=True)
        current=model.state_dict();matched={k:v for k,v in reference.items() if current[k].shape==v.shape};current.update(matched);model.load_state_dict(current)
    else:torch.save({k:v.cpu() for k,v in model.state_dict().items()},common)
    initial={k:v.detach().cpu() for k,v in model.state_dict().items()};torch.save(initial,out/'initial.pt')
    opt=torch.optim.Adam(model.parameters(),lr=.0002,weight_decay=.001)
    start=0;best=dict(score=-1,epoch=-1,path=None);records=[]
    checkpoints=sorted(out.glob('checkpoint_*.pt'))
    if checkpoints:
        ck=torch.load(checkpoints[-1],map_location=DEVICE,weights_only=False);model.load_state_dict(ck['model']);opt.load_state_dict(ck['optimizer']);start=ck['epoch']+1;best=ck['best'];records=ck['records']
    o=load('orig_train',arm);t=load('trans_train',arm)
    assert o['x'].shape[1]==t['x'].shape[1]==(39 if arm=='base39' else 21)
    assert (o['y'][o['mask']]>=0).all() and (t['y'][t['mask']]>=0).all()
    config=dict(arm=arm,seed=SEED,epochs=EPOCHS,updates_per_epoch=1,model='single GIN 4 layers hidden64 dropout0.2',
        parameters=sum(p.numel() for p in model.parameters()),device=torch.cuda.get_device_name(),python=sys.executable,torch=torch.__version__,amp='bfloat16',
        loss='ASL(gamma_pos=1,gamma_neg=4,clip=.05) orig + trans + 1.4*(soft miss orig^2 + soft miss trans^2)',
        mode=2,auxiliary_losses=dict(consistency=0,position=0,region=0,pair=0,SAT=0),
        label_mask='same trusted physical masks; unknown/virtual excluded',validation_every=5,
        selection='validation mean per-view AP over injection views using trusted labels',
        graph=CONTRACT['graph'],normalization=CONTRACT['normalization'],common_parameter_init='all equal-shaped parameters copied from common_init.pt',
        implementation_note='Orig and trans backprop separately then one optimizer step; train-only graphs avoid val/test participation in BatchNorm. Historical A0 is not an exact protocol match.')
    write(out/'config.json',config)
    for epoch in range(start,EPOCHS):
        begin=time.perf_counter();seed(SEED+epoch);model.train();opt.zero_grad(set_to_none=True)
        losses=[]
        for d in (o,t):
            with torch.autocast('cuda',dtype=torch.bfloat16):logits=model(d['x'],d['edge'])
            loss=domain_loss(logits,d['y'],d['mask']);assert torch.isfinite(loss)
            loss.backward();losses.append(float(loss.detach()));del loss,logits
        grads=[p.grad for p in model.parameters() if p.grad is not None]
        assert all(bool(torch.isfinite(g).all()) for g in grads)
        norm=float(torch.nn.utils.clip_grad_norm_(model.parameters(),1.0));opt.step()
        rec=dict(epoch=epoch+1,updates=epoch+1,loss=sum(losses),loss_orig=losses[0],loss_trans=losses[1],gradient_norm=norm,finite=True,seconds=time.perf_counter()-begin)
        if (epoch+1)%5==0:
            scores=predict(model,'trans_val',arm);summary,_=metrics(scores,'trans_val');score=summary['trusted']['ap'];rec['validation']=summary
            if score>best['score']:
                path=out/f'best_epoch_{epoch+1:03d}.pt';torch.save(model.state_dict(),path);best=dict(score=score,epoch=epoch+1,path=str(path.relative_to(ROOT)))
            records.append(rec)
            torch.save(dict(epoch=epoch,model=model.state_dict(),optimizer=opt.state_dict(),best=best,records=records),out/f'checkpoint_{epoch+1:03d}.pt')
        else:records.append(rec)
        write(out/'progress.json',dict(time=time.time(),last=rec,best=best));print(arm,json.dumps(rec),flush=True)
    write(out/'train_log.json',records);write(out/'SELECTED.json',dict(**best,updates=100,peak_vram_mib=torch.cuda.max_memory_allocated()/2**20,config_sha=sha(out/'config.json')))
    del model,opt,o,t;gc.collect();torch.cuda.empty_cache()
    return best
def save_rows(path,rows):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def main():
    assert torch.cuda.is_available() and 'ginvenv_gpu' in sys.executable
    check=loss_check();write(H/'loss_equivalence.json',check)
    for path,digest in CONTRACT['files'].items():assert sha(ROOT/path)==digest
    # The shared 14 structural columns are identical by construction before and after normalization.
    smoke={}
    for arm in ('base39','primitive21'):
        m=model_for(arm);a=load('orig_train',arm);m.train()
        with torch.autocast('cuda',dtype=torch.bfloat16):p=m(a['x'],a['edge'])
        loss=domain_loss(p,a['y'],a['mask']);loss.backward()
        assert torch.isfinite(loss) and all(torch.isfinite(q.grad).all() for q in m.parameters() if q.grad is not None)
        smoke[arm]=dict(finite_loss=float(loss.detach()),parameters=sum(p.numel() for p in m.parameters()),width=a['x'].shape[1])
        del m,a,p,loss;gc.collect();torch.cuda.empty_cache()
    write(H/'gpu_preflight.json',dict(passed=True,smoke=smoke,loss_equivalence=check,files_verified=True,new_SAT=0))
    for arm in ('base39','primitive21'):train_arm(arm)
    # Both validation selections are fixed before final test evaluation.
    summaries={}
    for arm in ('base39','primitive21'):
        out=H/'runs'/arm;selected=json.loads((out/'SELECTED.json').read_text());m=model_for(arm)
        m.load_state_dict(torch.load(ROOT/selected['path'],map_location=DEVICE,weights_only=True))
        v=predict(m,'trans_val',arm);va=arrays('trans_val');neg=v[va['trusted']&(va['y']==0)]
        threshold=float(np.nextafter(np.quantile(neg,.95),np.inf))
        summaries[arm]=dict(selected=selected,threshold=threshold)
        for key in ('trans_val','trans_test'):
            scores=v if key=='trans_val' else predict(m,key,arm)
            summary,rows=metrics(scores,key,threshold);summaries[arm][key]=summary
            np.save(out/(key+'_scores.npy'),scores);save_rows(out/(key+'_per_view.csv'),rows)
        del m;gc.collect();torch.cuda.empty_cache()
    write(H/'comparison.json',summaries);write(H/'COMPLETE.json',dict(completed=True,arms=2,seed=42,updates_each=100,new_SAT=0,comparison_sha=sha(H/'comparison.json')))
    print('COMPLETE',json.dumps(summaries),flush=True)
if __name__=='__main__':main()
