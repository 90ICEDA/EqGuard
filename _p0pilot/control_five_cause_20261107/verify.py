"""Independent cached-only recomputation and exact additive identities."""
from pathlib import Path
import collections,csv,hashlib,json
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;OLD=R/'_p0pilot/control_five_seed42_20261107';L=R/'_p0pilot/control_loader_po_20261105';C=R/'_p0pilot/control_boundary_v3_20261104'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def ap(y,s):
 allv=np.sort(s);positive=np.sort(s[y==1]);return float(np.mean((len(positive)-np.searchsorted(positive,positive,'left'))/(len(allv)-np.searchsorted(allv,positive,'left'))))
def main():
 assert read(O/'COMPLETE.json')['passed'];fc=read(C/'input_contract.json');data={};mem={};pred={};roles=collections.defaultdict(dict);views={(r['key'],r['view']):r for r in rows(L/'view_dictionary.csv')};ev={a:read(OLD/a/'EVALUATED.json') for a in ['G0','GB','GM','GBM','GAll']}
 for key,q in fc['shared_inputs'].items():
  p=R/q['folder'];data[key]={n:np.load(p/(n+'.npy'),mmap_mode='r') for n in ['y','trusted','physical']}
  with np.load(L/f'PO_membership_{key}.npz') as z:mem[key]={k:z[k] for k in z.files}
  for a in ev:pred[a,key]=np.load(OLD/a/(key+'_scores.npy'),mmap_mode='r')
 for r in rows(OLD/'frozen_role_assignments.csv'):roles[r['key']][int(r['row'])]=r['role_class']
 checks=0;error=0
 for r in rows(O/'threshold_score_per_view.csv'):
  key,arm,scope=r['key'],r['arm'],r['scope'];v=views[key,r['view']];lo,hi=int(v['start']),int(v['physical_stop']);a=data[key];ids=np.arange(lo,hi)
  if scope.startswith('role/'):
   ids=np.array([i for i in ids if a['physical'][i] and a['trusted'][i] and a['y'][i]==1 and roles[key].get(int(i),'unclassified')==scope[5:]],np.int64)
  else:ids=ids[mem[key][scope][lo:hi]]
  assert len(ids)==int(r['nodes']);p0=pred['G0',key][ids];p1=pred[arm,key][ids];t0,t1=ev['G0']['thresholds'][r['operation']],ev[arm]['thresholds'][r['operation']];cells=[float(np.sum(p>=t)/len(ids)) for p,t in [(p0,t0),(p1,t0),(p0,t1),(p1,t1)]]
  for k,x in zip(['baseline','new_scores_old_threshold','old_scores_new_threshold','new'],cells):error=max(error,abs(x-float(r[k])));assert abs(x-float(r[k]))<1e-12
  a,b,c,d=cells;assert abs(float(r['score_effect'])+float(r['threshold_effect'])-(d-a))<1e-12 and abs(float(r['score_effect'])-(b-a+d-c)/2)<1e-12;checks+=1
 apchecks=0
 for r in rows(O/'AP_decomposition_per_view.csv'):
  key,arm=r['key'],r['arm'];v=views[key,r['view']];lo,hi=int(v['start']),int(v['physical_stop']);a=data[key];ids=np.arange(lo,hi)[a['trusted'][lo:hi]&a['physical'][lo:hi]];y=a['y'][ids];p0=pred['G0',key][ids];p1=pred[arm,key][ids];positive=y==1;vals=[ap(y,x) for x in [p0,p1,np.where(positive,p1,p0),np.where(positive,p0,p1)]]
  for k,x in zip(['AP0','AP1','new_positive_old_negative_AP','old_positive_new_negative_AP'],vals):assert abs(x-float(r[k]))<1e-12
  assert abs(float(r['positive_score_effect'])+float(r['negative_score_effect'])-float(r['AP_delta']))<1e-12;apchecks+=1
 # AP role contributions add exactly to each source AP change,including unclassified roles.
 roles=rows(O/'AP_role_contribution_per_source.csv');source=rows(O/'AP_decomposition_per_source.csv');rolechecks=0
 for r in source:
  ss=[float(x['AP_contribution_delta']) for x in roles if all(x[k]==r[k] for k in ['arm','key','source'])];assert abs(sum(ss)-float(r['AP_delta']))<1e-12;rolechecks+=1
 # Match all macro totals to previous independently verified five-group reports.
 previous=rows(OLD/'source_macro_metrics.csv');pr=rows(OLD/'role_source_macro.csv');macrochecks=0
 for r in rows(O/'threshold_score_macro.csv'):
  key,arm,scope,mode=r['key'],r['arm'],r['scope'],r['operation']
  def prev(a):
   if scope.startswith('role/'):return float(next(x['recall'] for x in pr if x['arm']==a and x['key']==key and x['operation']==mode and x['role_class']==scope[5:]))
   col='recall' if scope=='trojan_positive' else 'FPR';return float(next(x[col] for x in previous if x['arm']==a and x['key']==key and x['operation']==mode and x['scope']==scope and x['PO_bin']=='all'))
  assert abs(float(r['baseline'])-prev('G0'))<1e-12 and abs(float(r['new'])-prev(arm))<1e-12;macrochecks+=1
 for r in rows(O/'AP_decomposition_macro.csv'):
  def prev(a):return float(next(x['AP'] for x in previous if x['arm']==a and x['key']==r['key'] and x['operation']=='val_recall80' and x['scope']=='trusted_all' and x['PO_bin']=='all' and x['kind']=='trojan'))
  assert abs(float(r['AP0'])-prev('G0'))<1e-12 and abs(float(r['AP1'])-prev(r['arm']))<1e-12
 for r in rows(O/'manufacturing_coupling_per_view.csv'):
  assert abs(float(r['normal_score_effect'])+float(r['normal_threshold_effect'])-float(r['normal_FPR_delta']))<1e-12;assert abs(float(r['trojan_score_effect'])+float(r['trojan_threshold_effect'])-float(r['trojan_recall_delta']))<1e-12
 for p,h in read(O/'PROTECTED_INPUTS.json').items():assert sha(R/p)==h,p
 result=dict(passed=True,independent_threshold_views=checks,max_rate_error=error,independent_AP_views=apchecks,AP_role_additive_sources=rolechecks,macro_sets_match_prior_verified=macrochecks,model_forwards=0,training=0,SAT=0,old_files_unchanged=True,decomposition_not_training_causal=True)
 (O/'VERIFIED.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
if __name__=='__main__':main()
