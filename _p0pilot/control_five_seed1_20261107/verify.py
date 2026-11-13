"""CPU independent optimizer,supervision and source/role/PO evaluation audit."""
import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import collections,csv,hashlib,json,math,sys
import numpy as np
import torch
from sklearn.metrics import average_precision_score
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;L=R/'_p0pilot/control_loader_po_20261105';C=R/'_p0pilot/control_boundary_v3_20261104';sys.path.insert(0,str(L));from supervision_loader import FiveGroupLoader
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def main():
 assert read(O/'TRAINING_COMPLETE.json')['actual_updates']==1000;contract=read(O/'EXECUTION_CONTRACT.json');binding=hashlib.sha256(json.dumps(contract,sort_keys=True).encode()).hexdigest();initial=torch.load(O/'init_s1.pt',map_location='cpu',weights_only=True);assert sha(O/'init_s1.pt')==contract['initial_sha'];loader=FiveGroupLoader();ledger={(r['domain'],r['arm'],int(r['update'])):r for r in rows(O/'integrated_indices_ledger.csv')};stepcheck=0;checkpoints=[]
 for arm in contract['arms']:
  ck=torch.load(O/arm/'resume.pt',map_location='cpu',weights_only=False);h=ck['history'];ev=read(O/arm/'EVALUATED.json');assert ck['binding']==ev['binding']==binding and ck['completed']==200 and [r['update'] for r in h]==list(range(1,201));assert ev['initial_sha']==sha(O/'init_s1.pt') and ev['checkpoint_sha']==sha(O/arm/'best.pt');assert all(torch.isfinite(x).all() for x in ck['model'].values());opt=ck['optimizer'];assert len(opt['param_groups'])==1 and opt['param_groups'][0]['lr']==.0002 and opt['param_groups'][0]['weight_decay']==.001
  # Model has two unused fn_head parameters;every actually optimized parameter must have200steps.
  names=[n for n in initial if not any(k in n for k in ['running_mean','running_var','num_batches_tracked']) and not n.endswith('.eps')];pids=opt['param_groups'][0]['params'];assert len(names)==len(pids);steps={n:int(opt['state'][pid]['step']) if pid in opt['state'] else 0 for n,pid in zip(names,pids)}
  assert all(v==(0 if n.startswith('fn_head.') else 200) for n,v in steps.items()),steps
  checks=[r for r in h if 'val_ap' in r];assert [r['update'] for r in checks]==list(range(5,201,5));chosen=max(checks,key=lambda r:r['val_ap']);assert chosen['update']==ev['selected']['epoch'] and chosen['val_ap']==ev['selected']['score'];best=torch.load(O/arm/'best.pt',map_location='cpu',weights_only=True)
  for n in ck['model']:
   if n.endswith('num_batches_tracked'):assert int(ck['model'][n])-int(initial[n])==400 and int(best[n])-int(initial[n])==2*chosen['update']
  for r in h:
   assert all(math.isfinite(r[k]) for k in ['orig_loss','trans_loss','grad_norm'])
   for dm in ['orig','trans']:
    q=loader.step(dm,arm,r['update']-1);hh=hashlib.sha256(q.indices.tobytes()).hexdigest();assert hh==r[dm+'_indices_sha']==ledger[dm,arm,r['update']]['index_sha'];stepcheck+=1
  va=loader.arrays('trans','val');p=np.load(O/arm/'trans_val_scores.npy');pos=p[va['trusted']&(va['y']==1)];neg=p[va['trusted']&(va['y']==0)];expected=dict(val_recall80=float(np.quantile(pos,.2,method='lower')),val_recall90=float(np.quantile(pos,.1,method='lower')),historical_fpr5=float(np.nextafter(np.quantile(neg,.95),np.inf)));assert ev['thresholds']==expected
  aps=[]
  for v in loader.feature_contract['shared_inputs']['trans_val']['views']:
   lo,hi=v['start'],v['stop'];m=va['trusted'][lo:hi];y=va['y'][lo:hi][m]
   if '__inj' in v['view'] and y.sum():aps.append(average_precision_score(y,p[lo:hi][m]))
  assert abs(float(np.mean(aps))-chosen['val_ap'])<1e-12
  for key,hh in ev['prediction_sha'].items():assert sha(O/arm/(key+'_scores.npy'))==hh
  checkpoints.append(dict(arm=arm,updates=200,selected_update=chosen['update'],active_parameters_steps200=True,unused_fn_head_steps0=True))
 # Rebuild source means and per-view basic fractions from saved membership,not the analysis grouping code.
 fc=loader.feature_contract;views={(r['key'],r['view']):r for r in rows(L/'view_dictionary.csv')};data={};members={};pred={}
 for key in fc['shared_inputs']:
  dm,sp=key.split('_');a=loader.arrays(dm,sp);data[key]=a
  with np.load(L/f'PO_membership_{key}.npz') as z:members[key]={k:z[k] for k in z.files}
 for arm in contract['arms']:
  for key in data:pred[arm,key]=np.load(O/arm/(key+'_scores.npy'),mmap_mode='r')
 pv=rows(O/'per_view_scope_PO.csv');checkview=0;apchecks=0
 for r in pv:
  if r['PO_bin']!='all':continue
  arm,key,view,scope=r['arm'],r['key'],r['view'],r['scope'];v=views[key,view];lo,hi=int(v['start']),int(v['physical_stop']);a=data[key];m=members[key][scope][lo:hi]&a['physical'][lo:hi];y=a['y'][lo:hi][m];p=pred[arm,key][lo:hi][m];hit=p>=float(r['threshold']);assert len(y)==int(r['nodes']);n=y==0;pp=y==1
  if n.any():assert int(np.sum(hit&n))==int(r['FP']) and abs(float(hit[n].mean())-float(r['FPR']))<1e-12
  if pp.any():assert int(np.sum(hit&pp))==int(r['TP']) and abs(float(hit[pp].mean())-float(r['recall']))<1e-12
  if n.any() and pp.any():assert abs(average_precision_score(y,p)-float(r['AP']))<1e-12;apchecks+=1
  checkview+=1
 # Source first,then macro: never pool transformed views as independent sources.
 sourcegroups=collections.defaultdict(list)
 for r in pv:sourcegroups[tuple(r[k] for k in ['arm','key','operation','scope','PO_bin','source','kind'])].append(r)
 source=rows(O/'per_source_scope_PO.csv');aggchecks=0
 for r in source:
  rr=sourcegroups[tuple(r[k] for k in ['arm','key','operation','scope','PO_bin','source','kind'])]
  for col in ['FPR','recall','AP','AUC','normal_alarm']:
   vals=[(float(x[col]) if col!='normal_alarm' else float(x[col]=='True')) for x in rr if x[col]!='']
   assert (not vals and r[col]=='') or abs(float(np.mean(vals))-float(r[col]))<1e-12
  aggchecks+=1
 wholechecks=0
 for r in rows(O/'whole_normal_views.csv'):
  v=views[r['key'],r['view']];lo,hi=int(v['start']),int(v['physical_stop']);p=pred[r['arm'],r['key']][lo:hi][data[r['key']]['physical'][lo:hi]];tau=read(O/r['arm']/'EVALUATED.json')['thresholds'][r['operation']];assert int((p>=tau).sum())==int(r['alarm_nodes']) and int(np.any(p>=tau))==int(r['alarm']);wholechecks+=1
 # Each role node appears once;unclassified/mixed remain explicit and total equals all trusted positives.
 assignments=rows(O/'frozen_role_assignments.csv');rolelookup=collections.defaultdict(dict)
 for r in assignments:assert int(r['row']) not in rolelookup[r['key']];rolelookup[r['key']][int(r['row'])]=r['role_class']
 rolechecks=0
 for r in rows(O/'role_per_view.csv'):
  v=views[r['key'],r['view']];lo,hi=int(v['start']),int(v['physical_stop']);a=data[r['key']];idx=np.flatnonzero(a['trusted'][lo:hi]&a['physical'][lo:hi]&(a['y'][lo:hi]==1))+lo;idx=np.array([i for i in idx if rolelookup[r['key']].get(i,'unclassified')==r['role_class']],np.int64);assert len(idx)==int(r['nodes']);tau=read(O/r['arm']/'EVALUATED.json')['thresholds'][r['operation']];assert abs(float(np.mean(pred[r['arm'],r['key']][idx]>=tau))-float(r['recall']))<1e-12;rolechecks+=1
 for r in rows(O/'role_coverage.csv'):assert int(r['classified_nodes'])+int(r['unclassified_nodes'])+int(r['mixed_nodes'])==int(r['positive_nodes'])
 std=rows(O/'PO_standardized.csv');assert all(r['value']=='' for r in std if r['missing_support']);assert any(r['value']=='' and r['scope']=='normal_primary_added' and r['key']=='trans_val' for r in std)
 for p,h in contract['protected_files'].items():assert sha(R/p)==h,p
 for p,h in read(O/'EVALUATION_INPUTS.json').items():assert sha(R/p)==h,p
 result=dict(passed=True,actual_updates=1000,seed=1,runs=checkpoints,actual_supervision_steps_verified=stepcheck,perview_fractions_verified=checkview,AP_sets_verified=apchecks,source_aggregation_sets_verified=aggchecks,whole_normal_view_alarms_verified=wholechecks,role_view_recalls_verified=rolechecks,thresholds_train_selection_verified=True,old_files_unchanged=True,missing_PO_support_NA=True,SAT=0,EQ=0,single_seed_limit=True)
 (O/'VERIFIED.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
if __name__=='__main__':main()
