"""Independent, read-only review of existing rounds 21-26. No SAT/training."""
import collections
import csv
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score
import k4_runtime as R

T=R.TABLES
OUT=R.fresh_dir(Path(__file__).parent/'result_reviews','review')
report=dict(errors=[],warnings=[],training={},panels={},comparisons={},new_sat_queries=0,new_training_runs=0)


def check(condition, message):
    if not condition:report['errors'].append(message)


def matched(d, feature, keys):
    strict=[];ties=[];adjusted=[]
    for _,m in d.groupby(keys):
        p=m.loc[m.label.eq(1),feature].to_numpy(float)
        n=m.loc[m.label.eq(0),feature].to_numpy(float)
        if not len(p) or len(n)<5:continue
        a=float((p[:,None]>n[None,:]).mean());b=float((p[:,None]==n[None,:]).mean())
        strict.append(a);ties.append(b);adjusted.append(a+.5*b)
    return dict(groups=len(strict),strict_median=float(np.median(strict)) if strict else None,
                tie_median=float(np.median(ties)) if ties else None,
                tie_adjusted_median=float(np.median(adjusted)) if adjusted else None)


def review_training():
    root=T/'sat_round21';rows=list(csv.DictReader((root/'runs.csv').open()))
    errors=[];maximum=0.;threshold_error=0.;ap=collections.defaultdict(list)
    features=np.load(root/'features.npz');folds=json.loads((root/'folds.json').read_text())['folds']
    gids=features['global_ids'];family=features['family'];fmap={f['fold']:f for f in folds}
    for row in rows:
        d=R.ROOT/'results_sat_r21'/row['fold']/f"{row['arm']}_seed{row['seed']}"
        check(R.sha(d/'final.pt')==row['ckpt_sha'],f'R21 checkpoint digest {d}')
        fold=fmap[row['fold']];vp=np.load(d/'val_predictions.npz');tp=np.load(d/'test_predictions.npz')
        for split,z,key,prefix in [('val',vp,'final','val_final'),('test',tp,'probability','test')]:
            y=z['labels'].astype(int);p=z[key].astype(float);thr=float(row[prefix+'_threshold'])
            check(np.array_equal(z['global_ids'],gids[fold[split+'_indices']]),f'R21 {d} {split} IDs')
            check(np.isfinite(p).all() and ((p>=0)&(p<=1)).all(),f'R21 {d} probability range')
            pred=p>thr;pos=y==1;neg=~pos
            metrics=dict(AP=average_precision_score(y,p),ROC_AUC=roc_auc_score(y,p),
                         TP=int((pred&pos).sum()),FP=int((pred&neg).sum()),
                         FN=int((~pred&pos).sum()),TN=int((~pred&neg).sum()),
                         recall=float(pred[pos].mean()),FPR=float(pred[neg].mean()))
            maximum=max(maximum,max(abs(float(v)-float(row[prefix+'_'+k])) for k,v in metrics.items()))
        expected=float(np.quantile(vp['final'][vp['labels']==0],.95,method='higher'))
        threshold_error=max(threshold_error,abs(expected-float(row['test_threshold'])))
        ap[row['arm']].append(float(row['test_AP']))
    check(maximum<1e-7 and threshold_error<1e-7,'R21 metric/validation threshold mismatch')
    mapping=json.loads((T/'sat_small_round18/permutation_stratified.json').read_text())
    transfers=[]
    for fold in folds:
        membership=np.empty(len(gids),dtype='<U5')
        for split in ('train','val','test'):membership[fold[split+'_indices']]=split
        cross=collections.Counter();changed=collections.Counter()
        for row in mapping:
            d,s=int(row['destination']),int(row['source'])
            if membership[d]!=membership[s]:
                cross[membership[s]+'->'+membership[d]]+=1
                if not np.array_equal(features['real'][d,:80],features['real'][s,:80]) or not np.array_equal(features['real'][d,98:110],features['real'][s,98:110]):
                    changed[membership[s]+'->'+membership[d]]+=1
        transfers.append(dict(fold=fold['fold'],cross_split_donors=dict(cross),changed_cross_split_content=dict(changed)))
    report['training']=dict(runs=len(rows),max_metric_error=maximum,max_threshold_error=threshold_error,
        mean_test_AP={k:float(np.mean(v)) for k,v in ap.items()},permutation_fold_transfers=transfers,
        scope='Existing predictions only; metrics checked, no forward/optimizer')
    if any(x['cross_split_donors'] for x in transfers):
        report['warnings'].append('R21 permutation donors are grouped by ORIGINAL R18 split, not current LOFO fold; cross-fold feature-content transfer exists. No label transfer established; strict within-fold permutation claim invalid.')


def review_panels():
    spec=importlib.util.spec_from_file_location('review_k8',R.ROOT/'_p0pilot/round24_20261027/sat_boundary_semantics_k8.py')
    semantics=importlib.util.module_from_spec(spec);spec.loader.exec_module(semantics)
    configs=[('sat_s15850_round22','merged_s15850',4),('sat_k4_rs232_round23','merged_rs232_k4',4),
        ('sat_k6_rs232_round23','merged_rs232_k6',8),('sat_k8_rs232_round24','merged_rs232_k8',8),
        ('sat_k8_s15850_round25','merged_s15850_k8',8),('sat_k6_s15850_round26','merged_s15850_k6',8)]
    frames={}
    for name,stem,denominator in configs:
        folder=T/name;df=pd.read_csv(folder/(stem+'.csv'));summary=json.loads((folder/'merged_summary.json').read_text())
        covered=df[df.covered].copy();frames[name]=covered
        cols=list(semantics.COLS);cols[0]='k_over_4' if denominator==4 else 'k_over_8'
        check(df.global_node.is_unique,name+' duplicate IDs')
        check(np.isfinite(df[cols].to_numpy(float)).all(),name+' nonfinite features')
        for key,n in [('rows',len(df)),('covered',len(covered)),('positives',int(df.label.sum())),
                      ('positives_covered',int(covered.label.sum()))]:check(summary[key]==n,name+' '+key)
        check(np.allclose(covered[cols[0]],covered.k/denominator),name+' k denominator')
        with np.load(folder/(stem+'.npz')) as z:
            check(np.array_equal(z['global_ids'],df.global_node.to_numpy()),name+' NPZ IDs')
            check(np.array_equal(z['labels'],df.label.to_numpy()),name+' NPZ labels')
            check(np.allclose(z['features'][:,:18],df[cols].to_numpy(float),atol=1e-7),name+' NPZ features')
        record_count=0;edge_bad=[];nonlocal_flags=[];query_paths=set();replayed=0
        for view,part in df.groupby('view',sort=False):
            vf=folder/'views'/view;rp=vf/(view+'.records.json')
            if not rp.exists():rp=vf/'records.json'
            records=json.loads(rp.read_text());by_global={int(r['global_node']):r for r in records}
            check(len(records)==len(part),name+' '+view+' record length')
            with np.load(vf/'base_inputs.npz') as z:
                edges=z['edge_index']
                if edges.ndim!=2 or edges.shape[0]!=2:edge_bad.append(view)
            for row in part.itertuples():
                r=by_global[row.global_node];record_count+=1
                if not row.covered:continue
                tab=r['table'];f,inputs=semantics.summarize(tab,r['k'])
                f[cols[0]]=r['k']/denominator
                expected=[f[c] for c in cols]
                actual=[getattr(row,c) for c in cols]
                check(np.allclose(expected,actual,atol=1e-7),name+' table replay '+str(row.global_node))
                check(inputs==r['inputs'],name+' per-input replay '+str(row.global_node))
                query_paths.add(r['evidence']);replayed+=1
            if view in {v['view'] for v in summary['views']}:
                sv=next(v for v in summary['views'] if v['view']==view)
                effective=sum(bool(r.get('nonlocal_cut')) for r in records if any(
                    int(r['global_node'])==int(g) for g in part.loc[part.covered,'global_node'])) if name=='sat_k8_s15850_round25' else None
                if effective is not None and sv.get('nonlocal_nodes')!=effective:
                    nonlocal_flags.append(dict(view=view,reported=sv.get('nonlocal_nodes'),covered_nonlocal=effective))
        pool={c:float(roc_auc_score(covered.label,covered[c])) for c in ['change_on_comparable','max_input_influence','ones_on_forced']}
        grouped={c:matched(covered,c,['view','driver_type']) for c in pool}
        for path in query_paths:
            check((R.ROOT/path).exists(),name+' missing query evidence '+path)
        report['panels'][name]=dict(rows=len(df),covered=len(covered),positives=int(df.label.sum()),
            positives_covered=int(covered.label.sum()),replayed_records=replayed,query_batches=len(query_paths),
            control_views=int(sum('__inj' not in v for v in df.view.unique())),
            legacy_edge_shape_views=len(edge_bad),edge_shape_examples=edge_bad[:3],
            pooled_auc=pool,matched_tie_review=grouped,nonlocal_count_scope_mismatches=nonlocal_flags,
            plan_sha=R.sha(folder/'plan.json'),merged_sha=R.sha(folder/(stem+'.csv')))
        if edge_bad:report['warnings'].append(name+f': {len(edge_bad)} legacy per-view bases have nonstandard edge shape; statistics unaffected, graph inputs need normalization before training.')
        if nonlocal_flags:report['warnings'].append(name+': nonlocal_nodes counts structural candidates outside the extracted sample, not effective SAT support.')
    for other,base in [('sat_k6_rs232_round23','sat_k4_rs232_round23'),
                       ('sat_k8_rs232_round24','sat_k4_rs232_round23'),
                       ('sat_k8_s15850_round25','sat_s15850_round22'),
                       ('sat_k6_s15850_round26','sat_s15850_round22')]:
        joined=frames[other].merge(frames[base],on=['view','global_node'],suffixes=('_new','_k4'))
        check(len(joined)==len(frames[other]),other+' k4 support alignment')
        check(np.array_equal(joined.label_new,joined.label_k4),other+' labels differ')
        report['comparisons'][other]=dict(common_nodes=len(joined),
            change_auc_k4=float(roc_auc_score(joined.label_new,joined.change_on_comparable_k4)),
            change_auc_new=float(roc_auc_score(joined.label_new,joined.change_on_comparable_new)))


if __name__=='__main__':
    review_training();review_panels()
    report['warnings'].append('Historical matched win rates use strict > and omit half credit for ties; values below 0.5 are not by themselves evidence of reverse association.')
    R.write_new(OUT/'review.json',report)
    print(json.dumps(dict(output=str(OUT),errors=len(report['errors']),warnings=report['warnings'],
        training=report['training'],panels={k:{a:v for a,v in x.items() if a in ('rows','covered','positives','legacy_edge_shape_views','pooled_auc','matched_tie_review')} for k,x in report['panels'].items()}),ensure_ascii=False))
    if report['errors']:raise SystemExit(1)
