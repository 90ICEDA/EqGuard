"""Offline-only role/source audit of frozen H/C predictions. No torch, training or solver."""
from pathlib import Path
import csv,json,collections,re,hashlib,sys
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent
B=R/'_p0pilot/control_v3_eligible_20261104';A=R/'_p0pilot/control_risk_20261104';P=R/'_p0pilot/round32_20261029';F=R/'generate_trans/folds/hosts_bt31'
def rows(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(n,a):
 if not a:return
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(a[0]));w.writeheader();w.writerows(a)
def avg(a):return float(np.mean(a))
def roleclass(s):
 if re.fullmatch(r'T(?:N|I|M|X|Y)?\d+',s):return 'trigger'
 if re.fullmatch(r'P\d+',s):return 'payload'
 if re.fullmatch(r'S\d+',s):return 'payload_select'
 if s=='HJ':return 'output_hijack'
 if s in ['PD','D0','Buf']:return 'normal_terminal'
 if re.fullmatch(r'X\d+',s):return 'deep_xor'
 if s.startswith('DUP'):return 'duplicate'
 return 'unclassified'
def main():
 O.mkdir(exist_ok=True);assert (B/'TRAINING_COMPLETE.json').exists()
 contract=read(P/'input_contract.json');co=[x for x in rows(R/'_p0pilot/control_retention_20261104/cohort_candidates.csv') if x['proposed_cohort']=='primary_candidate'];primary={x['view'] for x in co}
 roles=[x for x in rows(A/'trans_role_descendant_pairs_labelchecked.csv') if x['nodewise_training_candidate']=='True' and x['control_view'] in primary]
 sr=rows(A/'source_node_pairs.csv');source_lookup={(x['control_source'],x['control_instance']):x for x in sr}
 needs=collections.defaultdict(set);views={};ctx={}
 for key in ['orig_train','trans_train','trans_val','trans_test']:
  q=contract['shared_inputs'][key];d=R/q['folder'];ctx[key]={n:np.load(d/(n+'.npy'),mmap_mode='r') for n in ['x39','edge_index','y','trusted','physical']}
  for v in q['views']:views[(key,v['view'])]=v
 for x in roles:
  for side in ['control','trojan']:needs[('trans_'+x['split'],x[side+'_view'])].update(x[side+'_targets'].split('|'))
 # Original-side pairs are evaluated only where the same primary training source is traceable.
 eligible={x['control_source'] for x in roles if x['split']=='train'}
 orig=[x for x in sr if x['split']=='train' and x['role_pair']=='True' and x['control_source'] in eligible]
 for x in orig:
  needs[('orig_train',x['control_source'])].add(x['control_instance']);needs[('orig_train',x['trojan_source'])].add(x['trojan_instance'])
 # Include all full normal regions, including roles without a Trojan manufacturing counterpart.
 region_nodes=[x for x in rows(B/'seed1/H/historical_fpr5/region_nodes.csv')]
 for x in region_nodes:needs[(x['domain']+'_'+x['split'],x['view'])].add(x['instance'])
 idx={}
 for dm,path in [('trans',F/'data/processed/node_names_trans.txt'),('orig',P/'orig_names/node_names_orig.txt')]:
  spans=sorted((views[k]['old_start'],views[k]['old_stop'],k) for k in needs if k[0].startswith(dm));j=0
  with path.open(encoding='utf-8') as f:
   for gid,line in enumerate(f):
    while j<len(spans) and gid>=spans[j][1]:j+=1
    if j==len(spans):break
    lo,hi,k=spans[j];name=line.strip().lstrip('\\')
    if gid>=lo and name in needs[k]:idx[(k,name)]=views[k]['start']+gid-lo
 for k,ns in needs.items():assert all((k,n) in idx for n in ns),k
 spec=[]
 for x in roles:
  p=source_lookup[(x['control_source'],x['control_source_gate'])];key='trans_'+x['split']
  spec.append(dict(domain='trans',split=x['split'],source=x['control_source'],trojan_source=x['trojan_source'],view=x['control_view'],trojan_view=x['trojan_view'],role=p['role_suffix'],source_gate=x['control_source_gate'],role_class=roleclass(p['role_suffix']),normal_ids=sorted({idx[((key,x['control_view']),n)] for n in x['control_targets'].split('|')}),trojan_ids=sorted({idx[((key,x['trojan_view']),n)] for n in x['trojan_targets'].split('|')})))
 for x in orig:spec.append(dict(domain='orig',split='train',source=x['control_source'],trojan_source=x['trojan_source'],view=x['control_source'],trojan_view=x['trojan_source'],role=x['role_suffix'],source_gate=x['control_instance'],role_class=roleclass(x['role_suffix']),normal_ids=[idx[(('orig_train',x['control_source']),x['control_instance'])]],trojan_ids=[idx[(('orig_train',x['trojan_source']),x['trojan_instance'])]]))
 bindings={}
 scores={};ev={}
 for seed in [42,1,2]:
  for arm in ['H','C']:
   run=B/f'seed{seed}'/arm;ev[(seed,arm)]=read(run/'EVALUATED.json')
   for key in ctx:
    path=run/(key+'_scores.npy');assert sha(path)==ev[(seed,arm)]['prediction_sha'][key];scores[(seed,arm,key)]=np.load(path,mmap_mode='r');bindings[str(path.relative_to(R))]=sha(path)
   bindings[str((run/'EVALUATED.json').relative_to(R))]=sha(run/'EVALUATED.json')
 rr=[]
 for x in spec:
  key=x['domain']+'_'+x['split'];a=ctx[key];ni=np.array(x['normal_ids']);ti=np.array(x['trojan_ids']);assert a['trusted'][ni].all() and a['trusted'][ti].all() and a['physical'][ni].all() and a['physical'][ti].all() and (a['y'][ni]==0).all() and (a['y'][ti]==1).all()
  for seed in [42,1,2]:
   nh=np.asarray(scores[(seed,'H',key)][ni]);nc=np.asarray(scores[(seed,'C',key)][ni]);th=np.asarray(scores[(seed,'H',key)][ti]);tc=np.asarray(scores[(seed,'C',key)][ti])
   dn=float((nc-nh).mean());dt=float((tc-th).mean())
   for op in ['historical_fpr5','val_recall80','val_recall90']:
    hcut=ev[(seed,'H')]['thresholds'][op];ccut=ev[(seed,'C')]['thresholds'][op]
    rr.append(dict(seed=seed,operation=op,**{k:v for k,v in x.items() if k not in ['normal_ids','trojan_ids']},normal_nodes=len(ni),trojan_nodes=len(ti),normal_H=avg(nh),normal_C=avg(nc),normal_delta=dn,trojan_H=avg(th),trojan_C=avg(tc),trojan_delta=dt,mean_margin_H=avg(th)-avg(nh),mean_margin_C=avg(tc)-avg(nc),mean_margin_delta=dt-dn,both_scores_fall=int(dn<-1e-6 and dt<-1e-6),normal_fpr_H=avg(nh>=hcut),normal_fpr_C=avg(nc>=ccut),trojan_recall_H=avg(th>=hcut),trojan_recall_C=avg(tc>=ccut),joint_H=int(nh.max()<hcut<=th.max()),joint_C=int(nc.max()<ccut<=tc.max()),normal_margin_H=avg(nh)-hcut,normal_margin_C=avg(nc)-ccut,trojan_margin_H=avg(th)-hcut,trojan_margin_C=avg(tc)-ccut,threshold_H=hcut,threshold_C=ccut,normal_lower_T_lost=int(avg(nc>=ccut)<avg(nh>=hcut) and avg(tc>=ccut)<avg(th>=hcut)),normal_Hscores_Cthreshold=avg(nh>=ccut),normal_Cscores_Hthreshold=avg(nc>=hcut)))
 dump('role_view_seed.csv',rr)
 # Aggregate over implementations first, preserving each manufacturing source role.
 numeric=['normal_H','normal_C','normal_delta','trojan_H','trojan_C','trojan_delta','mean_margin_H','mean_margin_C','mean_margin_delta','both_scores_fall','normal_fpr_H','normal_fpr_C','trojan_recall_H','trojan_recall_C','joint_H','joint_C','normal_margin_H','normal_margin_C','trojan_margin_H','trojan_margin_C','normal_lower_T_lost','normal_Hscores_Cthreshold','normal_Cscores_Hthreshold']
 def aggregate(records,keys,cols):
  groups=collections.defaultdict(list)
  for x in records:groups[tuple(x[k] for k in keys)].append(x)
  return [dict(zip(keys,k),records=len(a),**{n:avg([x[n] for x in a]) for n in cols}) for k,a in sorted(groups.items())]
 source_roles=aggregate(rr,['seed','operation','domain','split','source','trojan_source','role','role_class'],numeric);dump('source_role_seed.csv',source_roles)
 across=aggregate(source_roles,['operation','domain','split','source','trojan_source','role','role_class'],numeric);dump('source_role_average.csv',across)
 source_classes=aggregate(source_roles,['seed','operation','domain','split','source','role_class'],numeric);dump('source_roleclass_seed.csv',source_classes)
 classes=aggregate(source_classes,['operation','domain','split','role_class'],numeric);dump('roleclass_summary.csv',classes)
 source=aggregate(source_roles,['seed','operation','domain','split','source'],numeric);dump('paired_source_summary.csv',source)
 # Full normal regions: observed scores, threshold effects, and per-node ranking change.
 nn=[]
 for seed in [42,1,2]:
  for x in region_nodes:
   key=x['domain']+'_'+x['split'];i=int(x['split_row']);assert idx[((key,x['view']),x['instance'])]==i
   h=float(scores[(seed,'H',key)][i]);c=float(scores[(seed,'C',key)][i]);v=views[(key,x['view'])];ph=ctx[key]['physical'][v['start']:v['stop']]
   for op in ['historical_fpr5','val_recall80','val_recall90']:
    ht=ev[(seed,'H')]['thresholds'][op];ct=ev[(seed,'C')]['thresholds'][op]
    nn.append(dict(seed=seed,operation=op,domain=x['domain'],split=x['split'],source=x['source_view'],view=x['view'],instance=x['instance'],row=i,score_H=h,score_C=c,score_delta=c-h,fpr_H=int(h>=ht),fpr_C=int(c>=ct),Hscores_Cthreshold=int(h>=ct),Cscores_Hthreshold=int(c>=ht),relative_delta=(c-ct)-(h-ht)))
 dump('normal_node_deltas.csv',nn)
 fullview=aggregate(nn,['seed','operation','domain','split','source','view'],['score_H','score_C','score_delta','fpr_H','fpr_C','Hscores_Cthreshold','Cscores_Hthreshold','relative_delta'])
 fullsource=aggregate(fullview,['seed','operation','domain','split','source'],['score_H','score_C','score_delta','fpr_H','fpr_C','Hscores_Cthreshold','Cscores_Hthreshold','relative_delta']);dump('normal_source_seed.csv',fullsource)
 fullavg=aggregate(fullsource,['operation','domain','split','source'],['score_H','score_C','score_delta','fpr_H','fpr_C','Hscores_Cthreshold','Cscores_Hthreshold','relative_delta']);dump('normal_source_average.csv',fullavg)
 # Frozen validation-calibrated recall curves. Test is descriptive, never used to choose weights.
 curves=[]
 for seed in [42,1,2]:
  for arm in ['H','C']:
   val=scores[(seed,arm,'trans_val')];a=ctx['trans_val'];positive=val[a['trusted']&(a['y']==1)]
   for target in [.5,.6,.7,.75,.8,.85,.9,.95]:
    cutoff=float(np.quantile(positive,1-target,method='lower'))
    for sp in ['val','test']:
     key='trans_'+sp;a=ctx[key];pred=scores[(seed,arm,key)];recalls=[]
     for (kk,vv),v in views.items():
      if kk!=key:continue
      ii=np.arange(v['start'],v['stop']);ii=ii[a['trusted'][ii]&(a['y'][ii]==1)]
      if len(ii):recalls.append(avg(pred[ii]>=cutoff))
     groups=collections.defaultdict(list)
     for x in co:
      if x['split']!=sp:continue
      ii=[idx[((key,x['view']),n)] for n in x['target_instances'].split('|')];groups[x['source_view']].append(avg(pred[ii]>=cutoff))
     fpr=avg([avg(a) for a in groups.values()]);curves.append(dict(seed=seed,arm=arm,split=sp,validation_target_pooled_recall=target,threshold=cutoff,trojan_macro_recall=avg(recalls),normal_source_fpr=fpr,sources=len(groups)))
 dump('validation_calibrated_curve.csv',curves)
 # Independent role-node feature and 3-hop incoming-context analysis is performed by context.py.
 dump('coordinate_manifest.csv',[dict(domain=x['domain'],split=x['split'],source=x['source'],trojan_source=x['trojan_source'],view=x['view'],trojan_view=x['trojan_view'],role=x['role'],role_class=x['role_class'],normal_ids='|'.join(map(str,x['normal_ids'])),trojan_ids='|'.join(map(str,x['trojan_ids']))) for x in spec])
 for p in [P/'input_contract.json',P/'normalization.npz',A/'trans_role_descendant_pairs_labelchecked.csv',A/'source_node_pairs.csv',R/'_p0pilot/control_retention_20261104/cohort_candidates.csv',B/'manifest.json',B/'TRAINING_COMPLETE.json',Path(__file__)]:bindings[str(p.relative_to(R))]=sha(p)
 (O/'analysis.json').write_text(json.dumps(dict(training=0,SAT=0,forward=0,role_specs=len(spec),role_rows=len(rr),source_role_rows=len(across),score_bindings=bindings,aggregation='implementations -> source role -> source class; seeds recorded, shared descendants not independent',role_classes=dict(collections.Counter(x['role_class'] for x in spec))),ensure_ascii=False,indent=2),encoding='utf-8')
 print('role specs',len(spec),'rows',len(rr));print('test roleclasses', [x for x in classes if x['domain']=='trans' and x['split']=='test' and x['operation']=='historical_fpr5'])
if __name__=='__main__':main()
