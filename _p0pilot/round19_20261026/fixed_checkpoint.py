"""Existing real-arm checkpoints only: eval/no_grad, no optimizer or updates.

Input removal can be out of distribution; this diagnoses dependence, not the
benefit of training a new representation. All test outputs are posthoc.
"""
import os
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG',':4096:8')
import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import average_precision_score,roc_auc_score

ROOT=Path(__file__).resolve().parents[2]
OLD=ROOT/'10.15/06_统一评测协议/N4_三向泛化/tables/sat_small_round18'
OUT=OLD.parent/'sat_diagnosis_round19';RUN=ROOT/'results_sat_small_r18'
sys.path.insert(0,str(ROOT))
from models.gin_net import GINNodeClassifier


def main():
    torch.set_num_threads(4)
    if not torch.cuda.is_available():raise RuntimeError('Existing-checkpoint GPU inference required')
    torch.use_deterministic_algorithms(True);torch.backends.cuda.matmul.allow_tf32=False
    z=np.load(OLD/'base_inputs.npz');norm=np.load(OLD/'normalization.npz')
    base=np.nan_to_num((z['x']-norm['mu'])/norm['sd']).clip(-10,10).astype(np.float32)
    real=np.load(OLD/'real.npy');zero=np.load(OLD/'zero.npy');perm=np.load(OLD/'permuted_stratified.npy');meta=zero.copy();meta[:,0]=real[:,0]
    plan=json.loads((OLD/'plan.json').read_text());records=[]
    train_views=[i for i,v in enumerate(plan['views']) if v['split']=='train']
    covered_train=np.isin(z['view_index'],train_views)&(real[:,18]>0)
    constants=[j for j in range(18) if len(np.unique(real[covered_train,j]))==1]
    valid=zero.copy();valid[:,[0]+constants]=real[:,[0]+constants]
    for seed in (42,1,2):
        folder=RUN/f'real_seed{seed}';ck=torch.load(folder/'best.pt',weights_only=False,map_location='cpu')
        model=GINNodeClassifier(58,64,2,4).cuda();model.load_state_dict(ck['state_dict']);model.eval();model.requires_grad_(False)
        ck_sha=hashlib.sha256((folder/'best.pt').read_bytes()).hexdigest()
        for split in ('val','test'):
            vi=[i for i,v in enumerate(plan['views']) if v['split']==split];mask=np.isin(z['view_index'],vi);ix=np.flatnonzero(mask)
            rev=np.full(len(mask),-1,np.int64);rev[ix]=np.arange(len(ix));edge=z['edge_index'];keep=mask[edge[0]]&mask[edge[1]]
            ei=torch.tensor(rev[edge[:,keep]],device='cuda',dtype=torch.long)
            saved=np.load(folder/('val_predictions.npz' if split=='val' else 'test_predictions.npz'));labels=saved['labels']
            original=saved['best' if split=='val' else 'probability'];assert np.array_equal(saved['global_ids'],z['global_ids'][ix])
            for name,extra in [('real',real),('permuted',perm),('zero',zero),('cut_k_only',meta),('constant_validity_and_k',valid)]:
                x=torch.tensor(np.concatenate([base[ix],extra[ix]],1),device='cuda')
                with torch.no_grad():p=torch.softmax(model(x,ei).float(),dim=1)[:,1].cpu().numpy()
                if name=='real':assert np.max(np.abs(p-original))<1e-6
                d=np.abs(p-original);pred=p>ck['threshold']
                records.append(dict(seed=seed,split=split,input=name,checkpoint_sha=ck_sha,
                                    AP=float(average_precision_score(labels,p)),AUC=float(roc_auc_score(labels,p)),
                                    mean_probability_change=float(d.mean()),max_probability_change=float(d.max()),
                                    positive_mean_change=float(d[labels==1].mean()),
                                    positive_mean_score=float(p[labels==1].mean()),
                                    recall=float(pred[labels==1].mean()),FPR=float(pred[labels==0].mean()),
                                    predicted_changes=int(np.count_nonzero(pred!=(original>ck['threshold'])))))
    with (OUT/'fixed_checkpoint_inputs.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
    info=dict(records=records,new_training_runs=0,optimizer_steps=0,new_sat_queries=0,
              operation='eval/no_grad on existing real-arm best checkpoints only',
              scope='posthoc dependence diagnosis; zero/k-only may be OOD; not a newly trained ablation')
    (OUT/'fixed_checkpoint.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
    for split in ('val','test'):
        print(split,{arm:{metric:float(np.mean([r[metric] for r in records if r['split']==split and r['input']==arm])) for metric in ['AP','mean_probability_change','positive_mean_change','recall']} for arm in ('real','permuted','zero','cut_k_only','constant_validity_and_k')},flush=True)


if __name__=='__main__':main()
