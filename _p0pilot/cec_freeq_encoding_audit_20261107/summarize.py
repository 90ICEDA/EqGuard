"""Summarize all predefined frozen diagnostic maps and implicit target constraints."""
from pathlib import Path
import collections,csv,json
import numpy as np
from cache_analysis import query_records,read,write,table
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;OLD=R/'_p0pilot/cec_freeq_zrp_seed42_20261107';C=R/'_p0pilot/cec_po_contract_20261106'
def rows(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def main():
 assert read(O/'FROZEN_COMPLETE.json')['passed'];pp=read(OLD/'EVALUATION_PANELS.json');units=[u for u in pp['val_boundary_all'] if u['tier']=='H3'];code_rows=[];source_rows=[]
 for tag in range(9000,9006):
  for arm in ['INIT','Z','R','P']:
   path=(OLD if tag in [9000,9001] else O)/f'val_{arm}_tag{tag}.npz';z=np.load(path);q=query_records(units,z['cone_ids'].tolist(),z['root64'].astype(float));wins={u['unit_id']:np.mean([r['win'] for r in q if r['unit_id']==u['unit_id']]) for u in units};code_rows.append(dict(tag=tag,arm=arm,units=85,win=float(np.mean(list(wins.values())))))
   for source in sorted({u['source'] for u in units}):source_rows.append(dict(tag=tag,arm=arm,source=source,units=sum(u['source']==source for u in units),win=float(np.mean([wins[u['unit_id']] for u in units if u['source']==source]))))
 table('six_code_metrics.csv',code_rows);table('six_code_by_source.csv',source_rows);diff=[]
 for tag in range(9000,9006):
  r={v['arm']:v['win'] for v in code_rows if v['tag']==tag};diff.append(dict(tag=tag,RminusP=r['R']-r['P'],RminusZ=r['R']-r['Z'],RminusINIT=r['R']-r['INIT']))
 table('six_code_differences.csv',diff);summary=[]
 for arm in ['INIT','Z','R','P']:
  x=[r['win'] for r in code_rows if r['arm']==arm];summary.append(dict(arm=arm,maps=6,mean=float(np.mean(x)),sampleSD_across_maps=float(np.std(x,ddof=1)),minimum=float(np.min(x)),maximum=float(np.max(x))))
 table('six_code_variation.csv',summary)
 # Add the ENCODER-imposed true-pair equalities before checking P component conflicts.
 tr=pp['train_frozen_pool'];ties={r['pair_id'] for r in rows(O/'root_encoder_hardties.csv') if r['panel']=='train21' and r['identical_typed_unfolded_expression']=='True'};allnegative=set();edges={a:set() for a in ['R','P']};implicit=set();source_by_edge={}
 for u in tr:
  n=u['functions'];shift=1+int(__import__('hashlib').sha256(json.dumps(['permutation_orientation',u['unit_id']],sort_keys=True,separators=(',',':')).encode()).hexdigest(),16)%2
  # Read the actual frozen targets,do not reconstruct their seed convention.
  entry=next(e for step in read(C/'SCHEDULE_SEED42.json') for e in step['units'] if e['unit_id']==u['unit_id'])
  for a,cc,r,p in zip(entry['anchors'],entry['candidates'],entry['real_targets'],entry['permuted_targets']):edges['R'].add(tuple(sorted([a,cc[r]])));edges['P'].add(tuple(sorted([a,cc[p]])))
  for a,b in entry['common_negative_edges']:e=tuple(sorted([a,b]));allnegative.add(e);source_by_edge[e]=u['source']
  for j,pid in enumerate(u['pair_ids']):
   if pid in ties:implicit.add(tuple(sorted(u['cones'][2*j:2*j+2])))
 conflicts=[]
 for arm in ['R','P']:
  for addties in [False,True]:
   parent={}
   def find(x):
    parent.setdefault(x,x)
    if parent[x]!=x:parent[x]=find(parent[x])
    return parent[x]
   for a,b in edges[arm]|(implicit if addties else set()):parent[find(a)]=find(b)
   bad=[e for e in allnegative if find(e[0])==find(e[1])];conflicts.append(dict(arm=arm,include_encoder_implied_equalities=addties,positive_edges=len(edges[arm]),implicit_true_equalities=len(implicit) if addties else 0,common_negative_edges=len(allnegative),inconsistent_negative_edges=len(bad),sources=';'.join(sorted({source_by_edge[e] for e in bad}))))
 table('encoder_augmented_target_conflicts.csv',conflicts)
 g=rows(O/'component_gradient_summary.csv');gs=[]
 for arm in ['INIT','Z','R','P']:
  ss=[r for r in g if r['checkpoint']==arm]
  for field in ['common_over_real','common_over_wrong','real_common_cos','wrong_common_cos','Rtotal_Ptotal_cos','Rtotal_Ztotal_cos','real_CE_directional_slope_under_common_descent','wrong_CE_directional_slope_under_common_descent']:
   a=[float(r[field]) for r in ss];gs.append(dict(checkpoint=arm,metric=field,minimum=min(a),maximum=max(a),mean=float(np.mean(a))))
 table('gradient_ranges.csv',gs)
 write('SUMMARY_COMPLETE.json',dict(passed=True,maps=6,R_above_P_maps=sum(r['RminusP']>0 for r in diff),R_above_Z_maps=sum(r['RminusZ']>0 for r in diff),R_above_INIT_maps=sum(r['RminusINIT']>0 for r in diff),mean_RminusP=float(np.mean([r['RminusP'] for r in diff])),mean_RminusZ=float(np.mean([r['RminusZ'] for r in diff])),mean_RminusINIT=float(np.mean([r['RminusINIT'] for r in diff])),P_negative_conflicts_after_encoder_equalities=next(r['inconsistent_negative_edges'] for r in conflicts if r['arm']=='P' and r['include_encoder_implied_equalities']),scope='frozen-code variation is NOT seed replication or revised primary;do not infer significance from six maps',training=0,SAT=0,model_forwards_added=0))
 print('FROZEN_AUDIT_SUMMARIZED',flush=True)
if __name__=='__main__':main()
