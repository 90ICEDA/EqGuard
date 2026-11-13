"""Three paired seeds:source-first means/sampleSD,no pooling views as replicates."""
import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import collections,csv,hashlib,json
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;SEEDS=[42,1,2];ARMS=['G0','GB','GM','GBM','GAll']
def folder(seed):return R/f'_p0pilot/control_five_seed{seed}_20261107'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def table(n,rr):
 if rr:
  with (O/n).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def summarize(rr,keys,metrics):
 g=collections.defaultdict(list)
 for r in rr:g[tuple(r[k] for k in keys)].append(r)
 out=[]
 for k,records in sorted(g.items()):
  assert len(records)==3 and {int(r['seed']) for r in records}==set(SEEDS),(k,len(records));result=dict(zip(keys,k),seeds=3)
  for col in metrics:
   vals=[float(r[col]) for r in records if r[col] not in ['',None]];assert len(vals) in [0,3],(k,col,len(vals));result[col+'_mean']=float(np.mean(vals)) if vals else None;result[col+'_sampleSD']=float(np.std(vals,ddof=1)) if vals else None;result[col+'_n_seeds']=len(vals)
  out.append(result)
 return out
def main():
 assert read(O/'PIPELINE_COMPLETE.json')['new_updates']==2000;protected=dict(read(O/'DERIVATION.json')['protected_seed42']);allsets={};selected=[]
 definitions=[('source_macro_metrics.csv',['arm','key','operation','scope','PO_bin','kind'],['FPR','recall','AP','AUC','normal_alarm'],'macro'),('per_source_scope_PO.csv',['arm','key','operation','scope','PO_bin','source','kind'],['FPR','recall','AP','AUC','normal_alarm'],'source'),('whole_normal_macro.csv',['arm','key','operation'],['alarm','alarm_fraction','source_any_alarm','G0_threshold_alarm'],'whole_macro'),('whole_normal_sources.csv',['arm','key','operation','source'],['alarm','alarm_fraction','source_any_alarm','G0_threshold_alarm'],'whole_source'),('role_source_macro.csv',['arm','key','operation','role_class'],['recall','mean_score'],'role_macro'),('role_per_source.csv',['arm','key','operation','source','role_class'],['recall','mean_score'],'role_source'),('paired_source_deltas.csv',['comparison','key','operation','scope','PO_bin','source','kind'],['FPR_difference','recall_difference','AP_difference','AUC_difference','normal_alarm_difference'],'paired_source'),('region_rank_per_source.csv',['arm','key','operation','source'],['best_rank_fraction','mean_rank_fraction','score_mean','max_score','G0_threshold_FPR'],'rank_source'),('PO_standardized.csv',['arm','key','operation','scope','metric'],['value'],'standardized'),('manufacturing_joint_per_source.csv',['arm','key','operation','normal_source','trojan_source'],['joint_success','normal_alarm','trojan_any_recalled'],'joint_source')]
 for seed in SEEDS:
  f=folder(seed);assert read(f/'VERIFIED.json')['passed'];done=read(f/'TRAINING_COMPLETE.json');assert done['seed']==seed and done['actual_updates']==1000
  for p in [f/'VERIFIED.json',f/'EXECUTION_CONTRACT.json',f/'TRAINING_COMPLETE.json',f/'frozen_role_assignments.csv',f/'role_coverage.csv']:
   protected[str(p.relative_to(R))]=sha(p)
  assert sha(f/'frozen_role_assignments.csv')==sha(folder(42)/'frozen_role_assignments.csv') and sha(f/'role_coverage.csv')==sha(folder(42)/'role_coverage.csv')
  for filename,keys,metrics,label in definitions:
   p=f/filename;protected[str(p.relative_to(R))]=sha(p);allsets.setdefault(label,[]).extend(dict(seed=seed,**r) for r in rows(p))
  for arm in ARMS:
   ev=read(f/arm/'EVALUATED.json');assert ev['seed']==seed and ev['arm']==arm and ev['updates']==200;assert ev['initial_sha']==sha(f/f'init_s{seed}.pt')
   selected.append(dict(seed=seed,arm=arm,selected_update=ev['selected']['epoch'],validation_selection_AP=ev['selected']['score'],initial_sha=ev['initial_sha'],checkpoint_sha=ev['checkpoint_sha']))
 for filename,keys,metrics,label in definitions:
  rr=allsets[label];table(label+'_all_seeds.csv',rr);table(label+'_meanSD.csv',summarize(rr,keys,metrics))
 table('selected_checkpoints.csv',selected)
 # One row perseed/arm/key/operation with every benefit/cost together.
 keyrows=[]
 for seed in SEEDS:
  for arm in ARMS:
   for key in ['orig_val','orig_test','trans_val','trans_test']:
    for mode in ['historical_fpr5','val_recall80','val_recall90']:
     base=[r for r in allsets['macro'] if r['seed']==seed and r['arm']==arm and r['key']==key and r['operation']==mode and r['PO_bin']=='all']
     def m(scope,col,kind=None):
      rr=[r for r in base if r['scope']==scope and (kind is None or r['kind']==kind)];assert len(rr)==1,(seed,arm,key,scope);return float(rr[0][col]) if rr[0][col] else None
     role={r['role_class']:float(r['recall']) for r in allsets['role_macro'] if r['seed']==seed and r['arm']==arm and r['key']==key and r['operation']==mode};whole=next(r for r in allsets['whole_macro'] if r['seed']==seed and r['arm']==arm and r['key']==key and r['operation']==mode)
     keyrows.append(dict(seed=seed,arm=arm,key=key,operation=mode,node_AP=m('trusted_all','AP','trojan'),normal_added_FPR=m('normal_primary_added','FPR'),normal_all_FPR=m('normal_all','FPR'),all_positive_recall=m('trojan_positive','recall','trojan'),trigger_recall=role.get('trigger'),payload_recall=role.get('payload'),payload_select_recall=role.get('payload_select'),whole_normal_view_alarm=float(whole['alarm']),whole_normal_source_alarm=float(whole['source_any_alarm'])))
 metrics=['node_AP','normal_added_FPR','normal_all_FPR','all_positive_recall','trigger_recall','payload_recall','payload_select_recall','whole_normal_view_alarm','whole_normal_source_alarm'];table('KEY_RESULTS_all_seeds.csv',keyrows);table('KEY_RESULTS_meanSD.csv',summarize(keyrows,['arm','key','operation'],metrics))
 # Pair differences before acrossseed SD,not independent-error propagation.
 diffs=[];lookup={(r['seed'],r['arm'],r['key'],r['operation']):r for r in keyrows}
 for seed in SEEDS:
  for a,b in [('GB','G0'),('GM','G0'),('GBM','G0'),('GBM','GB'),('GBM','GM'),('GAll','G0'),('GAll','GBM')]:
   for key in ['orig_val','orig_test','trans_val','trans_test']:
    for mode in ['historical_fpr5','val_recall80','val_recall90']:
     x,y=lookup[seed,a,key,mode],lookup[seed,b,key,mode];diffs.append(dict(seed=seed,comparison=a+'-'+b,key=key,operation=mode,**{k:None if x[k] is None or y[k] is None else x[k]-y[k] for k in metrics}))
 table('PAIRED_KEY_DELTAS_all_seeds.csv',diffs);summ=summarize(diffs,['comparison','key','operation'],metrics)
 for r in summ:
  rr=[x for x in diffs if all(x[k]==r[k] for k in ['comparison','key','operation'])]
  for col in metrics:
   vv=[x[col] for x in rr if x[col] is not None];r[col+'_improving_seeds']=sum(x< -1e-12 if col in ['normal_added_FPR','normal_all_FPR','whole_normal_view_alarm','whole_normal_source_alarm'] else x>1e-12 for x in vv);r[col+'_worsening_seeds']=sum(x>1e-12 if col in ['normal_added_FPR','normal_all_FPR','whole_normal_view_alarm','whole_normal_source_alarm'] else x< -1e-12 for x in vv)
 table('PAIRED_KEY_DELTAS_meanSD.csv',summ)
 source_direction=[];source_lookup=collections.defaultdict(list)
 source_keys=['comparison','key','operation','scope','PO_bin','source','kind']
 for x in allsets['paired_source']:source_lookup[tuple(x[k] for k in source_keys)].append(x)
 for r in rows(O/'paired_source_meanSD.csv'):
  if r['comparison'] not in ['GM-G0','GBM-G0'] or r['PO_bin']!='all':continue
  rr=source_lookup[tuple(r[k] for k in source_keys)];out={k:r[k] for k in ['comparison','key','operation','scope','source','kind']}
  for col in ['FPR_difference','recall_difference','AP_difference']:
   vals=[float(x[col]) for x in rr if x[col]!=''];out[col+'_negative_seeds']=sum(x< -1e-12 for x in vals);out[col+'_positive_seeds']=sum(x>1e-12 for x in vals);out[col+'_zero_seeds']=sum(abs(x)<=1e-12 for x in vals)
  source_direction.append(out)
 table('SOURCE_DIRECTION_COUNTS.csv',source_direction)
 role_deltas=[];rl={(r['seed'],r['arm'],r['key'],r['operation'],r['source'],r['role_class']):r for r in allsets['role_source']}
 for r in allsets['role_source']:
  if r['arm']=='G0':continue
  b=rl[r['seed'],'G0',r['key'],r['operation'],r['source'],r['role_class']];role_deltas.append(dict(seed=r['seed'],comparison=r['arm']+'-G0',**{k:r[k] for k in ['key','operation','source','role_class']},recall_delta=float(r['recall'])-float(b['recall']),mean_score_delta=float(r['mean_score'])-float(b['mean_score'])))
 role_keys=['comparison','key','operation','source','role_class'];role_lookup=collections.defaultdict(list)
 for x in role_deltas:role_lookup[tuple(x[k] for k in role_keys)].append(x['recall_delta'])
 table('PAIRED_ROLE_SOURCE_all_seeds.csv',role_deltas);rd=summarize(role_deltas,role_keys,['recall_delta','mean_score_delta'])
 for r in rd:
  vv=role_lookup[tuple(r[k] for k in role_keys)];r['recall_improving_seeds']=sum(x>1e-12 for x in vv);r['recall_worsening_seeds']=sum(x< -1e-12 for x in vv)
 table('PAIRED_ROLE_SOURCE_meanSD.csv',rd)
 for p,h in protected.items():assert sha(R/p)==h,p
 (O/'AGGREGATION_COMPLETE.json').write_text(json.dumps(dict(passed=True,seeds=SEEDS,arms=ARMS,seed42_reused=True,new_updates=2000,total_updates=3000,aggregation='view->source withinseed,then paired3seed mean andsampleSD ddof1;no view/seed pseudo independent pooling',source_rows=len(allsets['source']),protected_inputs=protected,SAT=0,EQ=0,single_host_perheldoutsplit=True),indent=2),encoding='utf-8');print('THREE_SEED_SOURCE_AGGREGATION_COMPLETE',flush=True)
if __name__=='__main__':main()
