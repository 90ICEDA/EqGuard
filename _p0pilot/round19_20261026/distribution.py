"""Offline permutation strength, input drift and saved-rank checks."""
import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

ROOT=Path(__file__).resolve().parents[2]
OLD=ROOT/'10.15/06_统一评测协议/N4_三向泛化/tables/sat_small_round18'
OUT=OLD.parent/'sat_diagnosis_round19';RUN=ROOT/'results_sat_small_r18'


def main():
    records=json.loads((OLD/'records.json').read_text());rr={r['local_node']:r for r in records}
    z=np.load(OLD/'base_inputs.npz');ids=z['global_ids'];norm=np.load(OLD/'normalization.npz');raw=(z['x']-norm['mu'])/norm['sd'];base=raw.clip(-10,10)
    y=np.full(len(ids),-1,np.int64)
    # Train labels can be read from prior descriptive audit data only by indexing
    # the already saved positive list? Use the existing graph, no model fitting.
    import torch
    g=torch.load(ROOT/'generate_trans/folds/hosts_bt31/data/processed/trans_graph.pt',weights_only=False,map_location='cpu',mmap=True)
    y=g.y[torch.tensor(ids)].numpy()
    name={25:'log_input_pins',26:'log_degree',27:'PI_connected',28:'PO_connected',29:'distance_PI',30:'distance_PO',31:'log_2hop_fanin',32:'log_2hop_fanout',33:'DFF_reset_distance_PI',34:'DFF_reset_distance_PO',35:'DFF_reset_2hop_fanin',36:'DFF_reset_2hop_fanout',37:'in_cycle',38:'log_SCC_size'}
    ranges=[]
    tr=np.array([n for n,r in rr.items() if r['split']=='train']);tp=tr[y[tr]==1]
    for s in ('val','test'):
        ix=np.array([n for n,r in rr.items() if r['split']==s]);pp=ix[y[ix]==1]
        for j in range(39):
            ranges.append(dict(split=s,column=j,name=name.get(j,'gate_onehot_'+str(j)),
                               train_positive_min=float(z['x'][tp,j].min()),train_positive_max=float(z['x'][tp,j].max()),
                               positive_median=float(np.median(z['x'][pp,j])),
                               positives_outside_training_positive_range=int(((z['x'][pp,j]<z['x'][tp,j].min())|(z['x'][pp,j]>z['x'][tp,j].max())).sum()),
                               positives_outside_training_all_range=int(((z['x'][pp,j]<z['x'][tr,j].min())|(z['x'][pp,j]>z['x'][tr,j].max())).sum()),
                               clipped_positive=int((np.abs(raw[pp,j])>10).sum())))
    pd.DataFrame(ranges).to_csv(OUT/'structural_feature_shift.csv',index=False,encoding='utf-8-sig')
    real=np.load(OLD/'real.npy');perm=np.load(OLD/'permuted_stratified.npy');mapping=json.loads((OLD/'permutation_stratified.json').read_text())
    cols=json.loads((OLD/'coverage.json').read_text())['columns'];col_stats=[];map_stats=[]
    for s in ('train','val','test'):
        ix=[n for n,r in rr.items() if r['split']==s and real[n,18]]
        for j,c in enumerate(cols):col_stats.append(dict(split=s,column=c,changed=int((real[ix,j]!=perm[ix,j]).sum()),covered=len(ix)))
        meaningful=unchanged_summary=0;different_per_input=0
        from analyze import canonical
        states={('infeasible','not_applicable'):0,('feasible','0'):1,('feasible','1'):2,('feasible','undecided'):3,('unknown','unknown'):4}
        def signature(r):return canonical(r['k'],tuple(states[tuple(v)] for _,v in sorted(r['table'].items())))
        for m in mapping:
            if m['stratum'][0]!=s:continue
            a,b=rr[m['destination']],rr[m['source']]
            if signature(a)!=signature(b):
                meaningful+=1
                unchanged_summary+=int(np.array_equal(real[a['local_node'],:18],real[b['local_node'],:18]))
            aa=tuple(sorted((p['pair_coverage'],p['change_fraction']) for p in a['inputs']))
            bb=tuple(sorted((p['pair_coverage'],p['change_fraction']) for p in b['inputs']))
            different_per_input+=int(aa!=bb)
        map_stats.append(dict(split=s,covered=len(ix),different_canonical_table=meaningful,table_changed_but_same18=unchanged_summary,different_per_input_distribution=different_per_input))
    pd.DataFrame(col_stats).to_csv(OUT/'permutation_column_changes.csv',index=False,encoding='utf-8-sig')
    ranks=pd.read_csv(OUT/'positive_prediction_ranks.csv');rank_stats=[]
    for (arm,s),df in ranks.groupby(['arm','split']):
        rank_stats.append(dict(arm=arm,split=s,positive_predictions=len(df),median_positive_rank=float(df.rank_best.median()),min_positive_rank=int(df.rank_best.min()),max_positive_rank=int(df.rank_worst.max()),mean_positive_score=float(df.score.mean()),mean_threshold=float(df.threshold.mean()),above_threshold=int(df.predicted.sum())))
    result=json.loads((RUN/'results.json').read_text());selection=[]
    for r in result['results']:
        folder=RUN/f'{r["arm"]}_seed{r["seed"]}';pred=np.load(folder/'val_predictions.npz');log=pd.read_csv(folder/'train_log.csv')
        selection.append(dict(arm=r['arm'],seed=r['seed'],best_epoch=r['best_epoch'],validation_checks=int(log.val_AP.notna().sum()),best_AP=r['val_best']['AP'],final_AP=float(average_precision_score(pred['labels'],pred['final'])),best_minus_final=r['val_best']['AP']-float(average_precision_score(pred['labels'],pred['final']))))
    info=dict(permutation_semantics=map_stats,rank_summary=rank_stats,validation_selection=selection,
              clipping={s:dict(positive_clipped_any=sum(np.any(np.abs(raw[n])>10) for n,r in rr.items() if r['split']==s and y[n]),
                               positive_nodes=sum(r['split']==s and bool(y[n]) for n,r in rr.items())) for s in ('train','val','test')},
              caveat='Nearest distance/feature shift is descriptive; not an identified causal explanation')
    (OUT/'distribution.json').write_text(json.dumps(info,ensure_ascii=False,indent=2,default=lambda x:x.item()),encoding='utf-8')
    print(json.dumps(info,ensure_ascii=False,indent=2,default=lambda x:x.item()))


if __name__=='__main__':main()
