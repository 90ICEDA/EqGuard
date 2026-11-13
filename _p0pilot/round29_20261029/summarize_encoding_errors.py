import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
import json,csv,datetime,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from readonly_graph_arrays import arrays
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent;D=HERE/'encoding_error_audit';Q=HERE/'encoding_error_audit_v2'
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
v=pd.read_csv(D/'view_diagnostics.csv');r=pd.read_csv(D/'positive_node_ranks.csv');fp=pd.read_csv(D/'top_false_positive_neighbors.csv');groups=pd.read_csv(D/'score_groups.csv');enc=pd.read_csv(Q/'encoding_recompute_by_view.csv')
a,_=arrays(ROOT/'generate_trans/folds/hosts_bt31/data/processed/trans_graph.pt');x=a['x'];e=a['edge_index'];y=a['y'];vi=np.load(HERE/'frozen/view_index_all.npy',mmap_mode='r');names=json.loads((HERE/'frozen/manifest.json').read_text())['view_names'];views=json.loads((ROOT/'generate_trans/folds/hosts_bt31/views.json').read_text())
checks=[];thresholds=[];cond=[];case_ids=set();caseanchors=[]
for model,tag,pref in [('B39','v31a_A2','gnn_v31a_A2'),('region','v31r_l100','gnn_v31r_l100')]:
    for seed in [42,1,2]:
        folder=ROOT/'results'/f'hosts_bt31_seed{seed}mode4_allb1_fold_{tag}s{seed}';df=pd.read_csv(folder/'variant_level_summary.csv');df=df[df.Type=='TRANS'];check=v[(v.model==model)&(v.seed==seed)&(v.split=='test')].merge(df[['View','AP','Threshold']],left_on='view',right_on='View',suffixes=('_audit','_saved'))
        diff=np.abs(check.AP_audit-check.AP_saved);checks.append(dict(model=model,seed=seed,matched_test_views=len(check),positive_test_views=int(check.AP_audit.notna().sum()),max_abs_AP_difference=float(diff.max()),frozen_threshold=float(df.Threshold.iloc[0])))
        thr=float(df.Threshold.iloc[0]);dd=r[(r.model==model)&(r.seed==seed)].copy();dd['threshold']=thr;dd['predicted_positive']=dd.score>=thr;thresholds.append(dd)
        z=np.load(ROOT/'_devcfg'/f'{pref}_s{seed}.npz');idx=z['idx'];score=z['score']
        for view in views['val_views']:
            vid=names.index(view);ids=np.flatnonzero(vi==vid);lo=int(ids[0]);hi=int(ids[-1])+1;sl=slice(*np.searchsorted(idx,[lo,hi]));ss=score[sl];xx=x[lo:hi];yy=np.asarray(y[lo:hi]);gate=xx[:,:25].argmax(1)
            for gt in np.unique(gate):
                m=(yy==0)&(gate==gt)
                if m.sum()<20 or len(np.unique(xx[m,30]))<2 or len(np.unique(ss[m]))<2:continue
                rho=float(spearmanr(xx[m,30],ss[m]).statistic)
                cond.append(dict(model=model,seed=seed,view=view,gate=int(gt),negative=int(m.sum()),score_PO_spearman=rho))
            if seed==42 and model=='B39':
                # Retrospective examples: worst two positive ranks plus highest negative, fixed rules.
                rr=r[(r.model==model)&(r.seed==seed)&(r.view==view)].sort_values('rank_fraction',ascending=False)
                if rr.empty:continue
                anchors=[(int(t.node),'low_rank_positive') for t in rr.head(2).itertuples()]
                jj=int(np.flatnonzero(yy==0)[np.argmax(ss[yy==0])]);anchors.append((lo+jj,'highest_score_negative'))
                for node,kind in anchors:
                    if len(caseanchors)>=18:break
                    left,right=np.searchsorted(e[0],[node,node+1]);nb=e[1,left:right];case_ids.add(node);case_ids.update(int(i) for i in nb)
                    caseanchors.append(dict(view=view,node=node,kind=kind,score=float(ss[node-lo]),threshold=thr,predicted_positive=bool(ss[node-lo]>=thr),label=int(yy[node-lo]),neighbors=nb.tolist()))
allpos=pd.concat(thresholds,ignore_index=True);allpos.to_csv(D/'positive_ranks_with_frozen_threshold.csv',index=False,encoding='utf-8-sig');pd.DataFrame(checks).to_csv(D/'saved_prediction_metric_checks.csv',index=False,encoding='utf-8-sig');pd.DataFrame(cond).to_csv(D/'within_gate_negative_score_position.csv',index=False,encoding='utf-8-sig')
nodename={}
with (ROOT/'generate_trans/folds/hosts_bt31/data/processed/node_names_trans.txt').open(encoding='utf-8') as f:
    for i,line in enumerate(f):
        if i in case_ids:nodename[i]=line.strip()
neighbors=[]
for case in caseanchors:
    own=case.pop('neighbors');case['cell']=nodename[case['node']]
    for node in own:
        neighbors.append(dict(anchor=case['node'],anchor_cell=case['cell'],anchor_kind=case['kind'],view=case['view'],neighbor=node,neighbor_cell=nodename[node],neighbor_label=int(y[node]),neighbor_gate=int(x[node,:25].argmax()),neighbor_PI_distance=float(x[node,29]),neighbor_PO_distance=float(x[node,30])))
pd.DataFrame(caseanchors).to_csv(D/'error_case_anchors.csv',index=False,encoding='utf-8-sig');pd.DataFrame(neighbors).to_csv(D/'error_case_neighbors.csv',index=False,encoding='utf-8-sig')
totals={c:int(enc[c].sum()) for c in enc if c.endswith('_mismatch') or c=='nodes'}
summ=[]
for (model,split),df in r.groupby(['model','split']):
    dd=v[(v.model==model)&(v.split==split)];ff=fp[(fp.model==model)&(fp.split==split)];cc=pd.DataFrame(cond);cc=cc[cc.model==model]
    summ.append(dict(model=model,split=split,unique_positives=int(df[df.seed==42].node.nunique()),positive_records=len(df),mean_view_AP=float(dd.AP.mean()),mean_view_AP_seed_SD=float(dd.groupby('seed').AP.mean().std()),positive_median_rank_fraction=float(df.rank_fraction.median()),positive_same_gate_AUC=float(df.auc_same_gate.mean()),positive_same_gate_PO_AUC=float(df.auc_same_gate_PO_bin.mean()),positive_top1pct=float(df.in_top1pct.mean()),positive_is_region_top1=float((df.region_rank_best==1).mean()),median_positive_region_size=float(df.region_size.median()),top5_negative_XOR_fraction=float((ff.gate=='XORX').mean()),top5_negative_neighbor_positive_fraction=float((ff.neighbor_positive>0).mean()),top5_negative_positive_region_fraction=float((ff.region_positive>0).mean()),within_view_negative_position_rho_median=float(dd.score_PO_spearman_negative.median()),validation_within_gate_negative_position_rho_median=float(cc.score_PO_spearman.median())))
write(D/'diagnostic_summary.json',dict(time=datetime.datetime.now().astimezone().isoformat(),encoding_totals=totals,models=summ,prediction_checks=checks,caveats=['Positive records repeat seeds and equivalent views.','Top5 negatives per view are ranking errors, not necessarily threshold false alarms.','Conditional AUC excludes positive nodes without matched negatives and does not fit models.','B39 vs region differs in cone5 as well as region supervision, not a clean region ablation.','All threshold decisions use frozen historical thresholds.']))
print(json.dumps(dict(encoding_totals=totals,models=summ,prediction_checks=checks),ensure_ascii=False,indent=2))
