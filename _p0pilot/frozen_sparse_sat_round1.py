"""Same trained weights, only swap bounded SAT values at inference. CUDA only.

Run after serial training has finished. Reproduce whole-graph preprocessing and
score softmax(class=1), rather than the historical raw class-1 logit shortcut.
"""
from __future__ import annotations
import json
import os
import sys
import time
from pathlib import Path
import numpy as np
import pandas as pd
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG',':4096:8')
import torch
import yaml

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from models.gin_net import GINDual
PT=ROOT/'generate_trans/folds/hosts_bt31/data/processed'
OUT=ROOT/'10.15/06_统一评测协议/N4_三向泛化/tables/sparse_sat_round1'


def main():
    torch.set_num_threads(4)
    torch.manual_seed(42)
    torch.backends.cudnn.deterministic=True
    torch.backends.cudnn.benchmark=False
    torch.use_deterministic_algorithms(True)
    t=time.perf_counter()
    device=torch.device('cuda:0')
    result=ROOT/'results/hosts_bt31_seed42mode4_allb1_fold_fghtl_SparseR1_real_bounded_s42'
    cfg=json.loads((result/'run_config.json').read_text())
    assert cfg['normalization']['extra']=='bounded' and cfg['in_channels']==47
    graph=torch.load(PT/'trans_graph.pt',map_location='cpu',weights_only=False,mmap=True)
    extra=torch.from_numpy(np.load(PT/'satrel_node_feats_sparseR1_real.npy')).float()
    x=torch.cat([graph.x.float(),extra],1).to(device)
    del extra
    edges=graph.edge_index.to(device)
    # Identical stride and reduction domain to the training normalization path.
    mu=torch.zeros((1,47),device=device)
    sd=torch.ones((1,47),device=device)
    mu[:,:39]=x[:,:39].mean(0,keepdim=True)
    sd[:,:39]=x[:,:39].std(0,keepdim=True).clamp_min(1e-6)
    x=torch.nan_to_num((x-mu)/sd,nan=0.,posinf=0.,neginf=0.).clamp_(-10,10)
    del mu,sd
    conf=yaml.safe_load((ROOT/'_devcfg/dual.yaml').read_text())['model']
    model=GINDual(47,int(conf['hidden_channels']),int(conf['out_channels']),
                  num_layers=int(conf['branch_layers']),split=int(conf['split']),fusion='gate').to(device)
    checkpoint=torch.load(result/'best_model_ALL.pt',map_location='cpu',weights_only=False)
    model.load_state_dict(checkpoint['state_dict'])
    model.eval()
    prior=np.load(ROOT/'_devcfg/gnn_sparseR1_real_bounded_s42.npz')
    idx=prior['idx'].astype(np.int64)
    selected=torch.from_numpy(idx).to(device)
    yy=graph.y.numpy().reshape(-1)[idx]>0
    test=prior['test'].astype(bool)
    rows=[]
    baseline=None
    for name,variant in [('real','real'),('perm','permuted'),('zero','zero')]:
        if variant!='real':
            raw=np.load(PT/f'satrel_node_feats_sparseR1_{variant}.npy',mmap_mode='r')
            swapped=torch.from_numpy(np.array(raw[:,2:6],copy=True)).to(device)
            x[:,41:45]=swapped
            del swapped,raw
        with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):
            logits=model(x,edges)
            scores=torch.softmax(logits.float(),dim=1)[:,1][selected].cpu().numpy()
        del logits
        if baseline is None:
            baseline=scores.copy()
            diff=np.abs(scores-prior['score'])
            max_abs=float(diff.max())
            (OUT/'frozen_baseline_integrity.json').write_text(json.dumps(dict(
                max_absolute_probability_diff_vs_training_dump=max_abs,
                mean_absolute_probability_diff=float(diff.mean()),
                quantiles=[float(v) for v in np.quantile(diff,[.5,.9,.99,.999])],
                fraction_exactly_equal=float((diff==0).mean()),
                deterministic_inference=True,
                explanation='training used non-deterministic GPU scatter; compare interventions only against this deterministic frozen baseline'),indent=2))
            np.savez(OUT/'frozen_diagnostic_baseline.npz',idx=idx,score=scores,test=prior['test'])
            with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):
                repeat=torch.softmax(model(x,edges).float(),dim=1)[:,1][selected].cpu().numpy()
            repeat_diff=np.abs(repeat-scores)
            (OUT/'frozen_repeat_integrity.json').write_text(json.dumps(dict(
                max_diff=float(repeat_diff.max()),mean_diff=float(repeat_diff.mean()),
                fraction_exactly_equal=float((repeat_diff==0).mean())),indent=2))
            # A rare maximum is not a valid identity guard against an original
            # non-deterministic scatter execution (independent repeat confirms
            # the same outliers). Require exact deterministic replay, plus tight
            # bulk agreement against the original prediction population.
            if repeat_diff.max()!=0 or diff.mean()>1e-4 or np.quantile(diff,.999)>.002:
                raise RuntimeError('deterministic replay or bulk score agreement failed; diagnostics saved')
        delta=np.abs(scores-baseline)
        rows.append(dict(variant=name,mean_abs_test_change=float(delta[test].mean()),
                         max_abs_test_change=float(delta[test].max()),
                         test_positive_scores_changed_gt_1e_minus6=int((delta[test&yy]>1e-6).sum()),
                         test_positives=int((test&yy).sum()),elapsed_s=time.perf_counter()-t))
        path=ROOT/f'_devcfg/gnn_sparseR1_frozen_{name}_s42.npz'
        if path.exists():
            raise FileExistsError(str(path))
        np.savez(path,idx=idx,score=scores,test=prior['test'])
        print(f'[frozen] {name} max_score_change={delta.max():.8f}',flush=True)
    pd.DataFrame(rows).to_csv(OUT/'frozen_score_changes.csv',index=False,encoding='utf-8-sig')
    print(pd.DataFrame(rows).to_string(index=False),flush=True)


if __name__=='__main__':
    main()
