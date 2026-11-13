"""Offline descriptive diagnosis of frozen round18 evidence; no model fitting."""
import collections
import csv
import functools
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np
import torch

ROOT=Path(__file__).resolve().parents[2]
OLD=ROOT/'10.15/06_统一评测协议/N4_三向泛化/tables/sat_small_round18'
OUT=OLD.parent/'sat_diagnosis_round19'
RUN=ROOT/'results_sat_small_r18'


def scalar_json(value):
    if isinstance(value,np.generic):return value.item()
    raise TypeError(type(value).__name__)
def write(name,obj):(OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=scalar_json),encoding='utf-8')
def digest(x):return hashlib.sha256(np.ascontiguousarray(x).tobytes()).hexdigest()
def dump_csv(name,rows):
    if not rows:return
    with (OUT/name).open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


@functools.lru_cache(None)
def canonical(k,values):
    # Input permutation only: no input/output inversion, no equivalence claim.
    patterns=list(itertools.product((0,1),repeat=k));index={p:i for i,p in enumerate(patterns)}
    forms=[]
    for order in itertools.permutations(range(k)):
        forms.append(tuple(values[index[tuple(p[j] for j in order)]] for p in patterns))
    return min(forms)


def main():
    records=json.loads((OLD/'records.json').read_text());by_node={r['local_node']:r for r in records}
    assert len(by_node)==len(records)==2435
    z=np.load(OLD/'base_inputs.npz');ids=z['global_ids'];x=z['x'];edges=z['edge_index'];plan=json.loads((OLD/'plan.json').read_text())
    real=np.load(OLD/'real.npy');perm=np.load(OLD/'permuted_stratified.npy');norm=np.load(OLD/'normalization.npz')
    base=np.nan_to_num((x-norm['mu'])/norm['sd']).clip(-10,10).astype(np.float32)
    g=torch.load(ROOT/'generate_trans/folds/hosts_bt31/data/processed/trans_graph.pt',map_location='cpu',weights_only=False,mmap=True)
    y=g.y[torch.tensor(ids)].numpy();assert set(np.unique(y))<={0,1}
    states={('infeasible','not_applicable'):0,('feasible','0'):1,('feasible','1'):2,('feasible','undecided'):3,('unknown','unknown'):4}
    profile={};raw={};can={};per_stats={}
    groups=collections.defaultdict(list)
    for n,r in by_node.items():
        if not real[n,18]:continue
        profile[n]=digest(real[n,:18]);values=tuple(states[tuple(v)] for p,v in sorted(r['table'].items()))
        raw[n]=(r['k'],values);can[n]=(r['k'],canonical(r['k'],values))
        per_stats[n]=tuple(sorted((round(i['pair_coverage'],12),round(i['change_fraction'],12)) for i in r['inputs']))
        groups[profile[n]].append(n)
    collision_groups=[];examples=[]
    for prof,nodes in sorted(groups.items()):
        functions={can[n] for n in nodes};role_sets=collections.defaultdict(set)
        for n in nodes:role_sets[by_node[n]['target_role']].add(can[n])
        if len(functions)>1:
            collision_groups.append(dict(profile=prof,nodes=len(nodes),distinct_permutation_canonical_tables=len(functions),
                                         different_input_stat_distributions=len({per_stats[n] for n in nodes}),
                                         same_role_collision=any(len(v)>1 for v in role_sets.values())))
            if len(examples)<5:
                strict=collections.defaultdict(list)
                for n in nodes:strict[(by_node[n]['driver_type'],by_node[n]['target_role'])].append(n)
                candidates=next((ns for ns in strict.values() if len({can[n] for n in ns})>1),nodes)
                a=candidates[0];b=next(n for n in candidates if can[n]!=can[a])
                def witness(n):
                    r=by_node[n]
                    return {k:r[k] for k in ('cell','view','local_node','target_role','k','cut_bits','target_bit','table','features','inputs','evidence')}
                examples.append(dict(a=witness(a),b=witness(b),same_18d=bool(np.array_equal(real[a,:18],real[b,:18])),
                                     same_input_permutation_class=False))
    train_ids=np.array([n for n,r in by_node.items() if r['split']=='train'])
    feature_cols=json.loads((OLD/'coverage.json').read_text())['columns'][:18]
    covered_train=train_ids[real[train_ids,18]>0]
    ranges=[]
    for j,name in enumerate(feature_cols):
        u=np.unique(real[covered_train,j]);ranges.append(dict(index=j,name=name,unique=len(u),min=float(u.min()),max=float(u.max()),constant=int(len(u)==1)))
    typed=collections.defaultdict(list)
    for n in profile:typed[(profile[n],by_node[n]['driver_type'],by_node[n]['target_role'])].append(n)
    strict_collision=[ns for ns in typed.values() if len({can[n] for n in ns})>1]
    feature_analysis=dict(covered_nodes=len(profile),unique_18d_profiles=len(groups),
                          unique_exact_order_tables=len(set(raw.values())),unique_permutation_canonical_tables=len(set(can.values())),
                          collision_profile_groups=len(collision_groups),nodes_in_collision_profiles=sum(r['nodes'] for r in collision_groups),
                          collision_fraction=sum(r['nodes'] for r in collision_groups)/len(profile),
                          groups_losing_per_input_stat_distribution=sum(r['different_input_stat_distributions']>1 for r in collision_groups),
                          collision_groups_same_profile_gate_and_role=len(strict_collision),
                          nodes_in_same_profile_gate_role_collisions=sum(len(ns) for ns in strict_collision),
                          train_constant_columns=[r['name'] for r in ranges if r['constant']],
                          exact_redundancies=dict(forced_equals_feasible=bool(np.array_equal(real[:,3],real[:,2])),
                                                full_plus_restricted_equals_covered=bool(np.array_equal(real[:,14]+real[:,15],real[:,18]))),
                          scope='descriptive compression collision, not signal equivalence or predictive-gain proof')
    write('summary_loss.json',feature_analysis);write('collision_examples.json',examples)
    dump_csv('collision_groups.csv',collision_groups);dump_csv('feature_ranges.csv',ranges)
    # Pure label-free 4-round neighborhood hashing using the ACTUAL normalized input.
    h=[digest(np.round(v,6)) for v in base]
    neighbors=[[] for _ in range(len(ids))]
    for a,b in edges.T:neighbors[int(b)].append(int(a))
    for depth in range(4):
        h=[hashlib.sha256((h[n]+'|'+','.join(sorted(h[j] for j in neighbors[n]))).encode()).hexdigest() for n in range(len(ids))]
    basekey={n:digest(np.round(base[n],6)) for n in range(len(ids))}
    representations={'sat18':profile,'canonical_table':can,'base39':basekey,'base39_plus_sat18':{n:(basekey[n],profile[n]) for n in profile},
                     'base39_plus_canonical_table':{n:(basekey[n],can[n]) for n in can},'WL4_base39':dict(enumerate(h))}
    splits={s:np.array([n for n,r in by_node.items() if r['split']==s]) for s in ('train','val','test')}
    novelty=[];positive_rows=[];class_distribution=[]
    for split,ix in splits.items():
        positive=ix[y[ix]==1];negative=ix[y[ix]==0]
        types=collections.Counter(by_node[int(n)]['driver_type'] for n in positive)
        roles=collections.Counter(by_node[int(n)]['target_role'] for n in positive)
        class_distribution.append(dict(split=split,nodes=len(ix),positives=len(positive),covered_positive=sum(real[n,18]>0 for n in positive),
                                       positive_types=dict(types),positive_roles=dict(roles)))
        for name,keys in representations.items():
            trp={keys[n] for n in train_ids if y[n] and n in keys};trn={keys[n] for n in train_ids if not y[n] and n in keys}
            pp=[int(n) for n in positive if n in keys];nn=[int(n) for n in negative if n in keys]
            conflict_set={keys[n] for n in negative if n in keys}
            novelty.append(dict(split=split,representation=name,positive_evaluable=len(pp),
                                positives_same_as_local_negative=sum(keys[n] in conflict_set for n in pp),
                                positives_seen_train_positive=sum(keys[n] in trp for n in pp),
                                positives_seen_train_negative=sum(keys[n] in trn for n in pp),
                                positives_unseen_train=sum(keys[n] not in trp|trn for n in pp),
                                negative_evaluable=len(nn)))
        if split!='train':
            trp=train_ids[y[train_ids]==1];trn=train_ids[y[train_ids]==0]
            for n in positive:
                dp=np.sqrt(((base[trp]-base[n])**2).sum(1));dn=np.sqrt(((base[trn]-base[n])**2).sum(1))
                positive_rows.append(dict(split=split,local_node=int(n),global_node=int(ids[n]),cell=by_node[int(n)]['cell'],
                                          driver_type=by_node[int(n)]['driver_type'],role=by_node[int(n)]['target_role'],covered=bool(real[n,18]),
                                          closest_train_positive_l2=float(dp.min()),closest_train_negative_l2=float(dn.min()),
                                          closer_to_negative=bool(dn.min()<dp.min()),sat18_seen_train_positive=bool(n in profile and profile[n] in {profile[i] for i in trp if i in profile}),
                                          sat18_seen_train_negative=bool(n in profile and profile[n] in {profile[i] for i in trn if i in profile})))
    # Compare each matched control/injected normal cell by exact library-cell name.
    counterparts=[]
    for family in ('alpha','beta','epsilon','zeta'):
        rr=[r for r in records if r['family']==family]
        inj={r['cell']:r for r in rr if '__inj' in r['view']};ctl={r['cell']:r for r in rr if '__ctl' in r['view']}
        positive=[r for r in rr if y[r['local_node']]]
        counterparts.append(dict(family=family,positives=len(positive),positive_cell_name_in_control=sum(r['cell'] in ctl for r in positive),
                                 normal_cell_name_overlap=len(set(inj)&set(ctl))))
    dump_csv('novelty_and_label_collisions.csv',novelty);dump_csv('positive_structural_distance.csv',positive_rows)
    write('label_distributions.json',class_distribution);write('matched_control_structure.json',counterparts)
    # Saved prediction diagnosis: threshold-independent ranks, not new model fitting.
    results=json.loads((RUN/'results.json').read_text());prediction_rows=[];per_view=[]
    for run in results['results']:
        folder=RUN/f'{run["arm"]}_seed{run["seed"]}'
        for split,filename,key in [('val','val_predictions.npz','best'),('test','test_predictions.npz','probability')]:
            pred=np.load(folder/filename);p=pred[key];labels=pred['labels'];global_to_local={int(v):n for n,v in enumerate(ids)}
            local=np.array([global_to_local[int(n)] for n in pred['global_ids']]);assert np.array_equal(y[local],labels)
            for row_index in np.flatnonzero(labels):
                value=p[row_index];rank_lo=1+int((p>value).sum());rank_hi=int((p>=value).sum())
                n=int(local[row_index]);prediction_rows.append(dict(arm=run['arm'],seed=run['seed'],split=split,local_node=n,
                    cell=by_node[n]['cell'],score=float(value),rank_best=rank_lo,rank_worst=rank_hi,
                    threshold=float(run['val_best']['threshold']),predicted=bool(value>run['val_best']['threshold'])))
            for view in sorted({by_node[int(n)]['view'] for n in local}):
                select=np.array([by_node[int(n)]['view']==view for n in local]);pp=p[select];yy=labels[select]
                per_view.append(dict(arm=run['arm'],seed=run['seed'],split=split,view=view,nodes=int(select.sum()),positives=int(yy.sum()),
                                     score_mean=float(pp.mean()),score_max=float(pp.max()),positive_score_mean=float(pp[yy==1].mean()) if yy.sum() else None))
    dump_csv('positive_prediction_ranks.csv',prediction_rows);dump_csv('view_score_distribution.csv',per_view)
    trust_path=ROOT/'generate_trans/folds/hosts_bt31/data/for_train/trust_trans.npy'
    if trust_path.exists():
        trust=np.load(trust_path,mmap_mode='r');trust_stats=[]
        if len(trust)==g.num_nodes:
            for s,ix in splits.items():trust_stats.append(dict(split=s,all_trusted=int(np.asarray(trust[ids[ix]]).sum()),nodes=len(ix),positive_trusted=int(np.asarray(trust[ids[ix[y[ix]==1]]]).sum()),positives=int(y[ix].sum())))
            write('trust_audit.json',trust_stats)
    evidence=dict(summary_loss=feature_analysis,class_distribution=class_distribution,novelty=novelty,
                  positive_distance_summary={s:dict(positives=sum(r['split']==s for r in positive_rows),
                       closer_to_negative=sum(r['split']==s and r['closer_to_negative'] for r in positive_rows),
                       median_nearest_positive=float(np.median([r['closest_train_positive_l2'] for r in positive_rows if r['split']==s])),
                       median_nearest_negative=float(np.median([r['closest_train_negative_l2'] for r in positive_rows if r['split']==s]))) for s in ('val','test')},
                  matched_controls=counterparts,new_sat_queries=0,new_training_runs=0,test_status='already observed in round18; this is posthoc development diagnosis',
                  input_hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [OLD/'records.json',OLD/'real.npy',OLD/'permuted_stratified.npy',RUN/'results.json']})
    write('analysis.json',evidence)
    print(json.dumps({k:v for k,v in evidence.items() if k not in ('novelty','input_hashes')},ensure_ascii=False,indent=2,default=scalar_json))


if __name__=='__main__':main()
