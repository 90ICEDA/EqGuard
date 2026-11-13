"""Fixed-population source/PO/role evaluation of five frozen selected checkpoints."""
import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import collections,csv,hashlib,json,re,sys
import numpy as np
from sklearn.metrics import average_precision_score,roc_auc_score
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;L=R/'_p0pilot/control_loader_po_20261105';C=R/'_p0pilot/control_boundary_v3_20261104';ARMS=['G0','GB','GM','GBM','GAll'];sys.path.insert(0,str(L));import po_policy as PO
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def table(n,rr):
 if rr:
  with (O/n).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def mean(v):
 a=[x for x in v if x is not None and np.isfinite(x)];return float(np.mean(a)) if a else None
def aggregate(rr,keys,cols):
 groups=collections.defaultdict(list)
 for r in rr:groups[tuple(r[k] for k in keys)].append(r)
 return [dict(zip(keys,k),records=len(v),nodes=sum(r.get('nodes',0) for r in v),**{c:mean([r[c] for r in v]) for c in cols}) for k,v in sorted(groups.items())]
def roleclass(s):
 if re.fullmatch(r'T(?:N|I|M|X|Y)?\d+',s):return 'trigger'
 if re.fullmatch(r'P\d+',s):return 'payload'
 if re.fullmatch(r'S\d+',s):return 'payload_select'
 if s=='HJ':return 'output_hijack'
 return 'unclassified'
def main():
 assert read(O/'TRAINING_COMPLETE.json')['actual_updates']==1000;fc=read(C/'input_contract.json');views=rows(L/'view_dictionary.csv');vm={(v['key'],v['view']):v for v in views};availability={(r['key'],r['scope']):r['available']=='True' for r in rows(L/'scope_availability.csv')};data={};members={};rolemap={};protected={}
 for key,q in fc['shared_inputs'].items():
  folder=R/q['folder'];data[key]={n:np.load(folder/(n+'.npy'),mmap_mode='r') for n in ['y','trusted','physical','x39']}
  with np.load(L/f'PO_membership_{key}.npz') as z:members[key]={k:z[k].copy() for k in z.files}
  rolemap[key]=collections.defaultdict(set)
 # Existing trans role descendants;deduplicate physical rows before computing recall.
 rolepath=R/'_p0pilot/control_roles_20261104/coordinate_manifest.csv';protected[str(rolepath.relative_to(R))]=sha(rolepath)
 for r in rows(rolepath):
  key=r['domain']+'_'+r['split'];cl=roleclass(r['role'])
  for i in r['trojan_ids'].split('|'):
   if i:rolemap[key][int(i)].add(cl)
 # Original validation/test have reliable source-instance coordinates available in saved manufacturing pairs.
 srpath=R/'_p0pilot/control_risk_20261104/source_node_pairs.csv';protected[str(srpath.relative_to(R))]=sha(srpath);sourcepairs=[r for r in rows(srpath) if r['role_pair']=='True'];needs=collections.defaultdict(set)
 for r in sourcepairs:
  key='orig_'+r['split'];view=r['trojan_source']
  if (key,view) in vm:needs[key,view].add(r['trojan_instance'])
 names=R/'_p0pilot/round32_20261029/orig_names/node_names_orig.txt';protected[str(names.relative_to(R))]=sha(names);spans=sorted((int(vm[k]['old_start']),int(vm[k]['old_stop']),k) for k in needs);resolved={};j=0
 with names.open(encoding='utf-8') as f:
  for gid,line in enumerate(f):
   while j<len(spans) and gid>=spans[j][1]:j+=1
   if j==len(spans):break
   lo,hi,k=spans[j];name=line.strip().lstrip('\\')
   if gid>=lo and name in needs[k]:resolved[k,name]=int(vm[k]['start'])+gid-lo
 for r in sourcepairs:
  k=('orig_'+r['split'],r['trojan_source']);i=resolved.get((k,r['trojan_instance']))
  if i is not None:rolemap[k[0]][i].add(roleclass(r['role_suffix']))
 role_assignments=[]
 for key,a in data.items():
  full=np.full(len(a['y']),'unclassified',dtype='<U20')
  for i,classes in rolemap[key].items():
   assert 0<=i<len(full)
   if not (a['physical'][i] and a['trusted'][i] and a['y'][i]==1):continue
   cl=next(iter(classes)) if len(classes)==1 else 'mixed_lineage';full[i]=cl;role_assignments.append(dict(key=key,row=i,role_class=cl))
  data[key]['roles']=full
 table('frozen_role_assignments.csv',role_assignments);(O/'EVALUATION_INPUTS.json').write_text(json.dumps(protected,indent=2),encoding='utf-8')
 source_raw=[];whole=[];role_raw=[];globalrows=[];rankrows=[];joint=[]
 pair_specs=read(L/'ROLE_PO_PAIRS.json');weights=rows(L/'evaluation_reference_weights.csv');modes=['historical_fpr5','val_recall80','val_recall90'];g0=read(O/'G0/EVALUATED.json')
 for arm in ARMS:
  ev=read(O/arm/'EVALUATED.json')
  for key,a in data.items():
   dm,split=key.split('_');path=O/arm/(key+'_scores.npy');assert sha(path)==ev['prediction_sha'][key];pred=np.load(path,mmap_mode='r');assert len(pred)==len(a['y']) and np.isfinite(pred).all();mem=members[key];vv=[v for v in views if v['key']==key]
   for mode in modes:
    cutoff=ev['thresholds'][mode];allids=np.flatnonzero(a['trusted']&a['physical']);mixed=PO.score_counts(a['y'][allids],pred[allids],cutoff);globalrows.append(dict(arm=arm,key=key,operation=mode,threshold=cutoff,scope='all_trusted_pooled',**mixed))
    for v in vv:
     lo,hi=int(v['start']),int(v['physical_stop']);y=a['y'][lo:hi];p=pred[lo:hi];physical=a['physical'][lo:hi];view=v['view'];source=v['source'];bins=mem['bin'][lo:hi]
     if v['kind']=='control':
      ids=np.flatnonzero(physical);scores=p[ids];whole.append(dict(arm=arm,key=key,operation=mode,view=view,source=source,physical_nodes=len(ids),alarm=int(np.any(scores>=cutoff)),alarm_nodes=int(np.sum(scores>=cutoff)),alarm_fraction=float(np.mean(scores>=cutoff)),max_score=float(scores.max()),G0_threshold_alarm=int(np.any(scores>=g0['thresholds'][mode])),interpretation='allphysical view alarm,no trusted-label promotion'))
     for scope in ['trusted_all','normal_all','normal_primary_added','normal_B','normal_M','normal_U','trojan_positive','trojan_background']:
      if not availability.get((key,scope),True):continue
      mask=mem[scope][lo:hi]&physical
      if not mask.any():continue
      for binid in [-1,0,1,2,3,4]:
       m=mask if binid==-1 else mask&(bins==binid)
       if not m.any():continue
       counts=PO.score_counts(y[m],p[m],cutoff);source_raw.append(dict(arm=arm,key=key,operation=mode,scope=scope,PO_bin='all' if binid==-1 else PO.BIN_NAMES[binid],view=view,source=source,kind=v['kind'],threshold=cutoff,**counts))
      if scope=='normal_primary_added':
       r=PO.worst_rank_fraction(p[physical],p[mask]);rankrows.append(dict(arm=arm,key=key,operation=mode,source=source,view=view,nodes=int(mask.sum()),best_rank_fraction=float(r.min()),mean_rank_fraction=float(r.mean()),score_mean=float(p[mask].mean()),max_score=float(p[mask].max()),G0_threshold_FPR=float(np.mean(p[mask]>=g0['thresholds'][mode]))))
     pos=a['trusted'][lo:hi]&physical&(y==1)
     for cl in sorted(set(a['roles'][lo:hi][pos].tolist())):
      m=pos&(a['roles'][lo:hi]==cl);role_raw.append(dict(arm=arm,key=key,operation=mode,source=source,view=view,role_class=cl,nodes=int(m.sum()),recall=float(np.mean(p[m]>=cutoff)),mean_score=float(p[m].mean()),threshold=cutoff))
    for spec in pair_specs:
     if spec['key']!=key:continue
     ni=np.asarray(spec['normal_rows']);ti=np.asarray(spec['trojan_rows']);joint.append(dict(arm=arm,key=key,operation=mode,normal_source=spec['normal_source'],trojan_source=spec['trojan_source'],view=spec['normal_view'],source_gate=spec['normal_source_gate'],normal_max=float(pred[ni].max()),trojan_max=float(pred[ti].max()),joint_success=int(pred[ni].max()<cutoff<=pred[ti].max()),normal_alarm=int(np.any(pred[ni]>=cutoff)),trojan_any_recalled=int(np.any(pred[ti]>=cutoff)),PO_signature=str([spec['normal_PO_bins'],spec['trojan_PO_bins']]),SAT_equivalent=False))
  print('ANALYZED',arm,flush=True)
 table('per_view_scope_PO.csv',source_raw);table('whole_normal_views.csv',whole);table('role_per_view.csv',role_raw);table('global_metrics.csv',globalrows);table('region_rank_per_view.csv',rankrows);table('manufacturing_joint_per_view.csv',joint)
 joint_roles=aggregate(joint,['arm','key','operation','normal_source','trojan_source','source_gate'],['joint_success','normal_alarm','trojan_any_recalled']);table('manufacturing_joint_per_source_role.csv',joint_roles)
 joint_sources=aggregate(joint_roles,['arm','key','operation','normal_source','trojan_source'],['joint_success','normal_alarm','trojan_any_recalled']);table('manufacturing_joint_per_source.csv',joint_sources)
 cols=['FPR','recall','AP','AUC','normal_alarm'];source=aggregate(source_raw,['arm','key','operation','scope','PO_bin','source','kind'],cols);table('per_source_scope_PO.csv',source)
 macro=aggregate(source,['arm','key','operation','scope','PO_bin','kind'],cols)
 for r in macro:r['sources']=r.pop('records')
 table('source_macro_metrics.csv',macro)
 ws=aggregate([dict(r,nodes=r['physical_nodes']) for r in whole],['arm','key','operation','source'],['alarm','alarm_fraction','max_score','G0_threshold_alarm'])
 for r in ws:
  raw=[x for x in whole if all(x[k]==r[k] for k in ['arm','key','operation','source'])];r['source_any_alarm']=int(any(x['alarm'] for x in raw))
 table('whole_normal_sources.csv',ws);wm=aggregate(ws,['arm','key','operation'],['alarm','alarm_fraction','source_any_alarm','G0_threshold_alarm']);table('whole_normal_macro.csv',wm)
 roles=aggregate(role_raw,['arm','key','operation','source','role_class'],['recall','mean_score']);table('role_per_source.csv',roles);role_summary=aggregate(roles,['arm','key','operation','role_class'],['recall','mean_score']);table('role_source_macro.csv',role_summary)
 ranks=aggregate(rankrows,['arm','key','operation','source'],['best_rank_fraction','mean_rank_fraction','score_mean','max_score','G0_threshold_FPR']);table('region_rank_per_source.csv',ranks)
 # Paired source deltas,unchanged populations,model-specific predeclared calibration rules.
 lookup={(r['arm'],r['key'],r['operation'],r['scope'],r['PO_bin'],r['source'],r['kind']):r for r in source};deltas=[]
 for a,b in [('GB','G0'),('GM','G0'),('GBM','G0'),('GBM','GB'),('GBM','GM'),('GAll','G0'),('GAll','GBM')]:
  for row in source:
   if row['arm']!=a:continue
   k=(b,*[row[x] for x in ['key','operation','scope','PO_bin','source','kind']]);ref=lookup[k];deltas.append(dict(comparison=a+'-'+b,**{x:row[x] for x in ['key','operation','scope','PO_bin','source','kind']},**{m+'_difference':None if row[m] is None or ref[m] is None else row[m]-ref[m] for m in cols}))
 table('paired_source_deltas.csv',deltas)
 # Frozen training-reference standardization;missing supported bins remain NA.
 standardized=[]
 for arm in ARMS:
  for key in data:
   dm,split=key.split('_')
   for mode in modes:
    for scope,col in [('normal_primary_added','FPR'),('normal_all','FPR'),('trojan_positive','recall')]:
     wr=[w for w in weights if w['domain']==dm and w['scope']==scope];ws=[float(next(w['weight'] for w in wr if w['PO_bin']==bn)) for bn in PO.BIN_NAMES];values=[]
     for bn in PO.BIN_NAMES:
      rr=[r[col] for r in macro if r['arm']==arm and r['key']==key and r['operation']==mode and r['scope']==scope and r['PO_bin']==bn];values.append(rr[0] if rr else None)
     standardized.append(dict(arm=arm,key=key,operation=mode,scope=scope,metric=col,value=PO.standardized(values,ws),missing_support='|'.join(bn for bn,v,w in zip(PO.BIN_NAMES,values,ws) if v is None and w>0)))
 table('PO_standardized.csv',standardized)
 coverage=[]
 for key,a in data.items():
  pos=a['trusted']&a['physical']&(a['y']==1);coverage.append(dict(key=key,positive_nodes=int(pos.sum()),classified_nodes=int(np.sum(pos&~np.isin(a['roles'],['unclassified','mixed_lineage']))),unclassified_nodes=int(np.sum(pos&(a['roles']=='unclassified'))),mixed_nodes=int(np.sum(pos&(a['roles']=='mixed_lineage')))))
 table('role_coverage.csv',coverage);(O/'ANALYSIS_COMPLETE.json').write_text(json.dumps(dict(arms=ARMS,source_rows=len(source),role_source_rows=len(roles),whole_normal_source_rows=len(rows(O/'whole_normal_sources.csv')),single_seed=True,updates=1000,SAT=0,EQ=0,test_exploratory=True,missing_PO_support_is_NA=True,role_scope='existing traceable manufacturing roles;unclassified positives explicit',normal_whole_scope='all physical scores without relabeling untrusted nodes'),indent=2),encoding='utf-8');print('FIVE_GROUP_ANALYSIS_COMPLETE',flush=True)
if __name__=='__main__':main()
