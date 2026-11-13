"""Three fixed seeds x three same-capacity arms on disjoint small netlists.

Training forward/BatchNorm sees TRAIN graphs only, validation is separate,
and test labels/inference are accessed only after every model is selected.
"""
import os
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG', ':4096:8')
import copy
import csv
import hashlib
import json
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from sklearn.metrics import average_precision_score,roc_auc_score

ROOT=Path(__file__).resolve().parents[2]
T=ROOT/'10.15/06_统一评测协议/N4_三向泛化/tables/sat_small_round18'
RUNS=ROOT/'results_sat_small_r18'
sys.path.insert(0,str(ROOT))
from models.gin_net import GINNodeClassifier


def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def state_sha(state):
    h=hashlib.sha256()
    for key,value in sorted(state.items()):h.update(key.encode());h.update(value.detach().cpu().contiguous().numpy().tobytes())
    return h.hexdigest()
def seed(n):
    random.seed(n);np.random.seed(n);torch.manual_seed(n);torch.cuda.manual_seed_all(n)
def threshold(y,p):return float(np.quantile(p[y==0],.95,method='higher'))
def metrics(y,p,thr):
    pred=p>thr;positive=y==1;negative=y==0
    tp=int((pred&positive).sum());fp=int((pred&negative).sum());fn=int((~pred&positive).sum());tn=int((~pred&negative).sum())
    both=bool(positive.any() and negative.any())
    return dict(n=len(y),positives=int(positive.sum()),prevalence=float(positive.mean()),
                AP=float(average_precision_score(y,p)) if positive.any() else None,
                ROC_AUC=float(roc_auc_score(y,p)) if both else None,
                TP=tp,FP=fp,FN=fn,TN=tn,recall=tp/(tp+fn) if tp+fn else None,
                FPR=fp/(fp+tn) if fp+tn else None,precision=tp/(tp+fp) if tp+fp else None,
                threshold=float(thr))


def main():
    torch.set_num_threads(4)
    if not torch.cuda.is_available():raise RuntimeError('GPU training required; no CPU fallback')
    if RUNS.exists():raise RuntimeError('Fresh experiment directory required')
    RUNS.mkdir()
    gate=json.loads((T/'pretrain_gate.json').read_text());assert gate['gate_passed']
    plan=json.loads((T/'plan.json').read_text());z=np.load(T/'base_inputs.npz')
    x=z['x'].astype(np.float32);edges=z['edge_index'];vi=z['view_index'];ids=z['global_ids']
    masks={s:np.isin(vi,[i for i,v in enumerate(plan['views']) if v['split']==s]) for s in ('train','val','test')}
    assert not any(np.any(masks[a]&masks[b]) for a,b in [('train','val'),('train','test'),('val','test')])
    mu=x[masks['train']].mean(0,keepdims=True);sd=x[masks['train']].std(0,keepdims=True,ddof=1).clip(1e-6)
    base=np.nan_to_num((x-mu)/sd).clip(-10,10).astype(np.float32)
    np.savez(T/'normalization.npz',mu=mu,sd=sd)
    features={a:np.load(T/f) for a,f in [('zero','zero.npy'),('real','real.npy'),('permuted','permuted_stratified.npy')]}
    assert all(hashlib.sha256((T/f).read_bytes()).hexdigest()==gate['training_features'][a] for a,f in [('zero','zero.npy'),('real','real.npy'),('permuted','permuted_stratified.npy')])
    g=torch.load(ROOT/'generate_trans/folds/hosts_bt31/data/processed/trans_graph.pt',map_location='cpu',weights_only=False,mmap=True)
    # Only train/val label values are read here. Test is deferred below.
    labels={s:g.y[torch.tensor(ids[masks[s]])].numpy().astype(np.int64) for s in ('train','val')}
    pos=int(labels['train'].sum());neg=len(labels['train'])-pos
    if not pos or not neg or not labels['val'].sum():raise RuntimeError('Unusable frozen train/val labels; report without changing selection')
    weight=torch.tensor([1.,neg/pos],device='cuda')
    per_split={}
    for s in ('train','val','test'):
        ix=np.flatnonzero(masks[s]);rev=np.full(len(ids),-1,np.int64);rev[ix]=np.arange(len(ix))
        keep=masks[s][edges[0]]&masks[s][edges[1]]
        per_split[s]=dict(ix=ix,edge=torch.tensor(rev[edges[:,keep]],device='cuda',dtype=torch.long))
    torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True
    torch.backends.cuda.matmul.allow_tf32=False
    torch.use_deterministic_algorithms(True)
    seed(42);probe=GINNodeClassifier(58,64,2,num_layers=4).cuda()
    tr_ix=per_split['train']['ix'];va_ix=per_split['val']['ix']
    tr_y=torch.tensor(labels['train'],device='cuda')
    preflight=dict(deterministic_supported=True)
    try:
        xx=torch.tensor(np.concatenate([base[tr_ix],features['zero'][tr_ix]],1),device='cuda')
        loss=F.cross_entropy(probe(xx,per_split['train']['edge']),tr_y,weight=weight);loss.backward()
    except RuntimeError as exc:
        if 'determin' not in str(exc).lower():raise
        preflight=dict(deterministic_supported=False,reason=str(exc))
        torch.use_deterministic_algorithms(False)
    del probe
    protocol=dict(original_plan_sha=plan['plan_sha'],gate_sha=sha(T/'pretrain_gate.json'),
                  seeds=[42,1,2],arms=['zero','real','permuted'],epochs=250,val_every=10,
                  lr=.001,weight_decay=.001,class_weight=[1,neg/pos],class_weight_fit='training labels only',
                  hidden=64,layers=4,precision='float32',device=torch.cuda.get_device_name(0),
                  interpreter=sys.executable,torch_version=torch.__version__,
                  deterministic=preflight,selection='max val AP; exact ties keep earliest',
                  test_policy='all validation selection completed before any test labels/predictions',
                  train_nodes=len(tr_ix),val_nodes=len(va_ix),train_positives=pos,val_positives=int(labels['val'].sum()),
                  normalization_sha=sha(T/'normalization.npz'),train_code_sha=sha(Path(__file__)),
                  feature_hashes=gate['training_features'],model_code_sha=sha(ROOT/'models/gin_net.py'))
    write(RUNS/'protocol.json',protocol)
    results=[];init_by_seed={};start=time.perf_counter()
    for s in protocol['seeds']:
        for arm in protocol['arms']:
            seed(s);folder=RUNS/f'{arm}_seed{s}';folder.mkdir()
            model=GINNodeClassifier(58,64,2,num_layers=4).cuda()
            init=state_sha(model.state_dict());assert init_by_seed.setdefault(s,init)==init
            opt=torch.optim.Adam(model.parameters(),lr=.001,weight_decay=.001)
            xtr=torch.tensor(np.concatenate([base[tr_ix],features[arm][tr_ix]],1),device='cuda')
            xva=torch.tensor(np.concatenate([base[va_ix],features[arm][va_ix]],1),device='cuda')
            best=-1.;best_epoch=-1;best_state=None;best_p=None;logs=[];wall=time.perf_counter()
            for epoch in range(1,251):
                model.train();opt.zero_grad(set_to_none=True)
                logits=model(xtr,per_split['train']['edge']);loss=F.cross_entropy(logits,tr_y,weight=weight)
                if not torch.isfinite(loss):raise RuntimeError('Nonfinite loss')
                loss.backward()
                grad=float(torch.nn.utils.clip_grad_norm_(model.parameters(),float('inf')))
                if not np.isfinite(grad):raise RuntimeError('Nonfinite gradients')
                opt.step()
                row=dict(epoch=epoch,train_loss=float(loss.detach()),grad_norm=grad)
                if epoch%10==0:
                    model.eval()
                    with torch.no_grad():
                        p=torch.softmax(model(xva,per_split['val']['edge']).float(),dim=1)[:,1].cpu().numpy()
                    ap=float(average_precision_score(labels['val'],p));row['val_AP']=ap
                    if ap>best:best=ap;best_epoch=epoch;best_state={k:v.detach().cpu().clone() for k,v in model.state_dict().items()};best_p=p.copy()
                logs.append(row)
                if epoch%100==0 or epoch==250:print(f'[TRAIN] {arm} seed={s} step={epoch} loss={row["train_loss"]:.5f} bestAP={best:.5f}@{best_epoch}',flush=True)
            final_state={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
            model.eval()
            with torch.no_grad():
                final_p=torch.softmax(model(xva,per_split['val']['edge']).float(),dim=1)[:,1].cpu().numpy()
                train_p=torch.softmax(model(xtr,per_split['train']['edge']).float(),dim=1)[:,1].cpu().numpy()
            thr=threshold(labels['val'],best_p)
            model.load_state_dict(best_state);model.eval()
            with torch.no_grad():repeat=torch.softmax(model(xva,per_split['val']['edge']).float(),dim=1)[:,1].cpu().numpy()
            assert np.allclose(repeat,best_p,atol=1e-6,rtol=1e-5)
            checkpoint=dict(state_dict=best_state,threshold=thr,epoch=best_epoch,arm=arm,seed=s,protocol_sha=sha(RUNS/'protocol.json'),init_sha=init)
            torch.save(checkpoint,folder/'best.pt');torch.save(dict(state_dict=final_state,epoch=250),folder/'final.pt')
            np.savez_compressed(folder/'val_predictions.npz',global_ids=ids[va_ix],labels=labels['val'],best=best_p,final=final_p)
            with (folder/'train_log.csv').open('w',newline='',encoding='utf-8') as f:
                w=csv.DictWriter(f,fieldnames=['epoch','train_loss','grad_norm','val_AP']);w.writeheader();w.writerows(logs)
            row=dict(arm=arm,seed=s,init_sha=init,best_epoch=best_epoch,updates=250,
                     val_best=metrics(labels['val'],best_p,thr),val_final=metrics(labels['val'],final_p,threshold(labels['val'],final_p)),
                     train_final=metrics(labels['train'],train_p,thr),wall_s=time.perf_counter()-wall,
                     final_loss=logs[-1]['train_loss'],checkpoint_sha=sha(folder/'best.pt'),repeat_max_abs=float(np.max(np.abs(repeat-best_p))))
            write(folder/'summary.json',row);results.append(row)
            print('[DONE]',arm,s,'valAP',best,'trainAP',row['train_final']['AP'],flush=True)
            del model,opt,xtr,xva
    # Commit all model choices BEFORE test label access.
    write(RUNS/'validation_selection_complete.json',dict(results=results,elapsed_s=time.perf_counter()-start,test_labels_read=False))
    test_ix=per_split['test']['ix'];test_y=g.y[torch.tensor(ids[test_ix])].numpy().astype(np.int64)
    for row in results:
        arm,s=row['arm'],row['seed'];folder=RUNS/f'{arm}_seed{s}'
        ck=torch.load(folder/'best.pt',weights_only=False,map_location='cpu')
        model=GINNodeClassifier(58,64,2,num_layers=4).cuda();model.load_state_dict(ck['state_dict']);model.eval()
        xt=torch.tensor(np.concatenate([base[test_ix],features[arm][test_ix]],1),device='cuda')
        with torch.no_grad():p=torch.softmax(model(xt,per_split['test']['edge']).float(),dim=1)[:,1].cpu().numpy()
        row['test']=metrics(test_y,p,ck['threshold'])
        np.savez_compressed(folder/'test_predictions.npz',global_ids=ids[test_ix],labels=test_y,probability=p)
        write(folder/'summary.json',row)
        del model,xt
    aggregate={}
    for arm in protocol['arms']:
        rr=[r for r in results if r['arm']==arm];aggregate[arm]={}
        for split in ['val_best','test']:
            aggregate[arm][split]={}
            for metric in ['AP','ROC_AUC','recall','FPR']:
                values=[r[split][metric] for r in rr]
                aggregate[arm][split][metric]=dict(mean=float(np.mean(values)),std=float(np.std(values,ddof=1)),values=values)
    paired={}
    for other in ('zero','permuted'):
        paired[other]={}
        for split in ('val_best','test'):
            values=[next(r[split]['AP'] for r in results if r['arm']=='real' and r['seed']==s)-next(r[split]['AP'] for r in results if r['arm']==other and r['seed']==s) for s in protocol['seeds']]
            paired[other][split]=dict(deltas=values,mean=float(np.mean(values)),std=float(np.std(values,ddof=1)))
    write(RUNS/'results.json',dict(protocol=protocol,results=results,aggregate=aggregate,paired_AP=paired,wall_s=time.perf_counter()-start,
                                  limitations='single rs232 host, ys_abc only, shared host backbone, two train and one val/test insertion-control families; not cross-host/implementation generalization'))
    print(json.dumps(dict(aggregate=aggregate,paired_AP=paired,wall_s=time.perf_counter()-start),indent=2),flush=True)


if __name__=='__main__':main()
