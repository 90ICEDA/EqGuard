"""Conditional, support-respecting feature importance of EXISTING checkpoints.

No optimizer, training or SAT. Replacements are features of actual peer tables
with every unperturbed field equal, within split/role/gate/k. Therefore no
inconsistent feasible/forced/validity mixtures are manufactured. This is model
dependence, not a retraining or generalization experiment.
"""
import os
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG',':4096:8')
import collections
import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import average_precision_score

ROOT=Path(__file__).resolve().parents[2]
OLD=ROOT/'10.15/06_统一评测协议/N4_三向泛化/tables/sat_small_round18'
OUT=OLD.parent/'sat_importance_round20';RUN=ROOT/'results_sat_small_r18'
sys.path.insert(0,str(ROOT))
from models.gin_net import GINNodeClassifier

GROUPS={
    'domain_and_comparability':[2,3,5,10,14,15],
    'output_one_fraction':[8],
    'influence_strength_joint':[11,13],
    'comparable_pair_fraction':[10],
    'mean_change_fraction':[11],
    'max_input_influence':[13],
    'feasible_fraction_alone':[2],
    'forced_fraction_alone':[3],
    'all_function_content':list(range(1,18)),
}
PERTURB_SEEDS=[11,23,37,53,71]


def conditional_mapping(real,rows,ids,columns,seed):
    keep=[i for i in range(real.shape[1]) if i not in columns]
    groups=collections.defaultdict(list)
    for n in ids:
        r=rows[int(n)]
        if real[n,18]:groups[(r['split'],r['target_role'],r['driver_type'],r['k'],real[n,keep].tobytes())].append(int(n))
    mapping=np.arange(len(real));rng=np.random.default_rng(seed)
    for ix in groups.values():
        src=np.array(ix)[rng.permutation(len(ix))]
        if len(ix)>1 and np.array_equal(src,ix):src=np.roll(src,1)
        mapping[ix]=src
    x=real.copy();x[:,columns]=real[mapping][:,columns]
    assert np.array_equal(x[:,keep],real[:,keep])
    # Because all complementary fields match, each entire vector is a peer's
    # real vector, not a synthetic invalid combination.
    assert np.array_equal(x,real[mapping])
    changed=np.any(x!=real,axis=1)
    return x,mapping,changed


def main():
    if (OUT/'results.json').exists():raise RuntimeError('Existing diagnostics must not be overwritten')
    torch.set_num_threads(4)
    if not torch.cuda.is_available():raise RuntimeError('GPU inference required')
    torch.use_deterministic_algorithms(True);torch.backends.cuda.matmul.allow_tf32=False
    z=np.load(OLD/'base_inputs.npz');norm=np.load(OLD/'normalization.npz');real=np.load(OLD/'real.npy')
    base=np.nan_to_num((z['x']-norm['mu'])/norm['sd']).clip(-10,10).astype(np.float32)
    records={r['local_node']:r for r in json.loads((OLD/'records.json').read_text())}
    plan=json.loads((OLD/'plan.json').read_text());results=[];baselines=[];mappings={};forward_passes=0
    protocol=dict(model_seeds=[42,1,2],perturbation_seeds=PERTURB_SEEDS,groups=GROUPS,
                  rule='Within split/role/gate/k and EXACT equality of every remaining feature; real peer replacement only',
                  new_training_runs=0,optimizer_steps=0,new_sat_queries=0,
                  scope='posthoc conditional model dependence, not unique causal effect or trained ablation; zeta is development evidence')
    (OUT/'protocol.json').write_text(json.dumps(protocol,ensure_ascii=False,indent=2),encoding='utf-8')
    prepared={}
    for split in ('val','test'):
        vi=[i for i,v in enumerate(plan['views']) if v['split']==split];mask=np.isin(z['view_index'],vi);ix=np.flatnonzero(mask)
        rev=np.full(len(mask),-1,np.int64);rev[ix]=np.arange(len(ix));ei=z['edge_index'];keep=mask[ei[0]]&mask[ei[1]]
        edge=torch.tensor(rev[ei[:,keep]],device='cuda',dtype=torch.long)
        prepared[split]=dict(ix=ix,edge=edge,perturbations={})
        for name,cols in GROUPS.items():
            for ps in PERTURB_SEEDS:
                x,m,changed=conditional_mapping(real,records,ix,cols,ps)
                prepared[split]['perturbations'][(name,ps)]=(x,changed,m)
                mappings[f'{split}_{name}_{ps}']=m
    for seed in (42,1,2):
        folder=RUN/f'real_seed{seed}';ck=torch.load(folder/'best.pt',weights_only=False,map_location='cpu')
        model=GINNodeClassifier(58,64,2,4).cuda();model.load_state_dict(ck['state_dict']);model.eval();model.requires_grad_(False)
        for split,prep in prepared.items():
            ix,edge=prep['ix'],prep['edge'];saved=np.load(folder/('val_predictions.npz' if split=='val' else 'test_predictions.npz'))
            labels=saved['labels'];original=saved['best' if split=='val' else 'probability']
            xx=torch.tensor(np.concatenate([base[ix],real[ix]],1),device='cuda')
            with torch.no_grad():p=torch.softmax(model(xx,edge).float(),dim=1)[:,1].cpu().numpy()
            forward_passes+=1;assert np.max(np.abs(p-original))<1e-6
            ap=float(average_precision_score(labels,p));baselines.append(dict(seed=seed,split=split,AP=ap,reproduction_max_abs=float(np.max(np.abs(p-original)))))
            for (name,ps),(extra,changed,mapping) in prep['perturbations'].items():
                if not changed.any():
                    pp=p.copy()
                else:
                    xx=torch.tensor(np.concatenate([base[ix],extra[ix]],1),device='cuda')
                    with torch.no_grad():pp=torch.softmax(model(xx,edge).float(),dim=1)[:,1].cpu().numpy()
                    forward_passes+=1
                new_ap=float(average_precision_score(labels,pp))
                results.append(dict(model_seed=seed,split=split,group=name,perturbation_seed=ps,
                                    changed_nodes=int(changed.sum()),covered_nodes=int(real[ix,18].sum()),
                                    changed_positive_nodes=int(changed[ix][labels==1].sum()),
                                    AP_baseline=ap,AP_perturbed=new_ap,AP_drop=ap-new_ap,
                                    probability_change_mean=float(np.mean(np.abs(pp-p))),
                                    positive_probability_change_mean=float(np.mean(np.abs(pp[labels==1]-p[labels==1]))),
                                    identifiable=bool(changed.any()),mapping_sha=hashlib.sha256(mapping.tobytes()).hexdigest()))
    summary=[]
    for split in ('val','test'):
        for name in GROUPS:
            rr=[r for r in results if r['split']==split and r['group']==name];drops=np.array([r['AP_drop'] for r in rr])
            drops=np.where(np.abs(drops)<1e-12,0.,drops)
            summary.append(dict(split=split,group=name,columns=GROUPS[name],identifiable=any(r['identifiable'] for r in rr),
                                mean_changed_nodes=float(np.mean([r['changed_nodes'] for r in rr])),
                                mean_changed_positive_nodes=float(np.mean([r['changed_positive_nodes'] for r in rr])),
                                mean_AP_drop=float(drops.mean()),sd_AP_drop=float(drops.std(ddof=1)),
                                positive_drop_runs=int((drops>0).sum()),runs=len(rr),
                                mean_probability_change=float(np.mean([r['probability_change_mean'] for r in rr]))))
    for filename,rr in [('runs.csv',results),('summary.csv',summary)]:
        with (OUT/filename).open('w',newline='',encoding='utf-8-sig') as f:
            w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
    np.savez_compressed(OUT/'conditional_mappings.npz',**mappings)
    info=dict(protocol=protocol,baselines=baselines,summary=summary,actual_forward_passes=forward_passes,
              input_hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [OLD/'real.npy',OLD/'records.json',RUN/'results.json']},
              notes=['AP drop >0 means current fixed model lost AP under an admissible feature change.',
                     'A zero changed-node count is not identifiable, NOT proof the feature is useless.',
                     'Groups differ in perturbable support and overlap; do not sum or compare as unbiased causal effects.',
                     '15 observations are correlated repeated diagnoses, not 15 independent insertion groups.'])
    (OUT/'results.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(summary=summary,actual_forward_passes=forward_passes),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
