"""Offline H/C positive-loss audit. Saved predictions only; no torch, training or SAT."""
from pathlib import Path
import csv,json,collections,hashlib,sys,re
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;B=R/'_p0pilot/control_v3_eligible_20261104';V=R/'_p0pilot/control_boundary_v3_20261104';F=R/'generate_trans/folds/hosts_bt31'
sys.path.insert(0,str(R/'_p0pilot/control_retention_20261104'));from audit import cells,norm
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(n,a):
 if not a:return
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(a[0]));w.writeheader();w.writerows(a)
def roleclass(s):
 if re.fullmatch(r'T(?:N|I|M|X|Y)?\d+',s):return 'trigger'
 if re.fullmatch(r'P\d+',s):return 'payload'
 if re.fullmatch(r'S\d+',s):return 'payload_select'
 if s=='HJ':return 'output_hijack'
 return 'other'
def avg(a):return float(np.mean(a))
def aggregate(records,keys,cols):
 groups=collections.defaultdict(list)
 for r in records:groups[tuple(r[k] for k in keys)].append(r)
 return [dict(zip(keys,k),records=len(aa),**{n:avg([float(x[n]) for x in aa]) for n in cols}) for k,aa in sorted(groups.items())]
def main():
 O.mkdir(exist_ok=True);assert (B/'COMPLETE.json').exists();c=read(V/'input_contract.json');meta={r['view']:r for r in rows(F/'views_meta.csv')};keys=['orig_train','trans_train','trans_val','trans_test'];data={};views={};positive={};inputs={};pred={};ev={}
 for key in keys:
  folder=R/c['shared_inputs'][key]['folder'];data[key]={n:np.load(folder/(n+'.npy'),mmap_mode='r') for n in ['x39','y','trusted','physical']};a=data[key];positive[key]=np.flatnonzero(a['trusted']&a['physical']&(a['y']==1))
  for v in c['shared_inputs'][key]['views']:views[(key,v['view'])]=v
  for n in ['x39','y','trusted','physical']:inputs[str((folder/(n+'.npy')).relative_to(R))]=sha(folder/(n+'.npy'))
 for seed in [42,1,2]:
  for arm in ['H','C']:
   path=B/f'seed{seed}'/arm;ev[(seed,arm)]=read(path/'EVALUATED.json')
   for key in keys:
    p=path/(key+'_scores.npy');assert sha(p)==ev[(seed,arm)]['prediction_sha'][key];pred[(seed,arm,key)]=np.load(p,mmap_mode='r');inputs[str(p.relative_to(R))]=sha(p)
   inputs[str((path/'EVALUATED.json').relative_to(R))]=sha(path/'EVALUATED.json')
 # Resolve exact physical instance coordinates; keep all positive labels including dead descendants.
 node_names={}
 for dm,path in [('orig',R/'_p0pilot/round32_20261029/orig_names/node_names_orig.txt'),('trans',F/'data/processed/node_names_trans.txt')]:
  spans=sorted((v['old_start'],v['old_stop'],key,view,v['start']) for (key,view),v in views.items() if key.startswith(dm));j=0;need={key:set(map(int,ids)) for key,ids in positive.items()}
  with path.open(encoding='utf-8') as f:
   for gid,line in enumerate(f):
    while j<len(spans) and gid>=spans[j][1]:j+=1
    if j==len(spans):break
    lo,hi,key,view,start=spans[j];i=start+gid-lo
    if gid>=lo and i in need[key]:node_names[(key,i)]=norm(line)
  inputs[str(path.relative_to(R))]=sha(path)
 prov=collections.defaultdict(list)
 for p in (R/'generate_trans').glob('hosts*/*/provenance.json'):
  try:
   a=read(p)
   if isinstance(a,list):
    for x in a:
     if x.get('view'):prov[x['view']].append((p,x))
  except (OSError,ValueError):pass
 factory={};annotations={};view_pos={};factory_rows=[];source_labels={};orig_names=(R/'_p0pilot/round32_20261029/orig_names/node_names_orig.txt').read_text(encoding='utf-8').splitlines()
 for (key,view),v in views.items():
  ids=positive[key];ids=ids[(ids>=v['start'])&(ids<v['physical_stop'])]
  if not len(ids):continue
  src=view if key.startswith('orig') else meta[view]['src_view'];view_pos[(key,view)]=ids
  if src not in factory:
   sc,_=cells(F/'orig'/(src+'.v'));choices=[(p,x) for p,x in prov[src] if x.get('new_gates') and all(norm(n) in sc for n in x['new_gates'])];assert choices,src;assert len({tuple(sorted(x['new_gates'])) for p,x in choices})==1
   pp,pd=choices[0];factory[src]=(pd,sc);inputs[str(pp.relative_to(R))]=sha(pp);inputs[str((F/'orig'/(src+'.v')).relative_to(R))]=sha(F/'orig'/(src+'.v'))
  pd,sc=factory[src];prefix=pd['prefix'];new={norm(n) for n in pd['new_gates']};rev=collections.defaultdict(set)
  if src not in source_labels:
   oq=c['shared_inputs']['orig_'+key.split('_')[1]];ov=next(v for v in oq['views'] if v['view']==src);yp=R/oq['folder']/'y.npy';oy=np.load(yp,mmap_mode='r');on=[norm(n) for n in orig_names[ov['old_start']:ov['old_stop']]];source_labels[src]=dict(zip(on,map(int,oy[ov['start']:ov['physical_stop']])));inputs[str(yp.relative_to(R))]=sha(yp)
  if key.startswith('trans'):
   path=F/'mappings'/(view+'.json');mp=read(path);assert mp['src_view']==src and mp['rw_view']==view
   for p,nn in mp['node_alignment'].items():
    for n in nn:rev[norm(n)].add(norm(p))
   inputs[str(path.relative_to(R))]=sha(path)
  for i in ids:
   name=node_names[(key,int(i))];parents={name} if key.startswith('orig') else rev[name];owned=parents&new;roles=sorted({p[len(prefix):] if p.startswith(prefix) else p for p in owned});classes={roleclass(x) for x in roles};cl=next(iter(classes)) if len(classes)==1 else 'mixed_lineage' if classes else 'unresolved_origin'
   assert parents and all(p in source_labels[src] for p in parents),(src,name,parents)
   parent_labels={source_labels[src][p] for p in parents};mixed=len(parent_labels)>1;reachable=bool(data[key]['x39'][i,30]>=0)
   annotations[(key,int(i))]=dict(source=src,view=view,instance=name,source_gates='|'.join(sorted(parents)),source_parent_labels='|'.join(str(x) for x in sorted(parent_labels)),mixed_label_sources=mixed,manufacturing_roles='|'.join(roles),role_class=cl,PO_reachable=reachable,gate_type=c['columns39'][int(np.argmax(data[key]['x39'][i,:25]))],proposed_positive_aux_eligibility='hold_mixed_label_lineage' if mixed else 'origin_loss_only_dead_branch' if not reachable else 'structural_positive_unproved')
   factory_rows.append(dict(key=key,row=int(i),**annotations[(key,int(i))]))
 dump('positive_coordinates_and_roles.csv',factory_rows)
 guard_groups=collections.defaultdict(list)
 for x in factory_rows:guard_groups[(x['key'],x['proposed_positive_aux_eligibility'])].append(x)
 dump('positive_aux_eligibility_counts.csv',[dict(key=k[0],status=k[1],physical_positive_nodes=len(aa),sources=len({x['source'] for x in aa})) for k,aa in sorted(guard_groups.items())])
 records=[];perview=[];macro_checks=[]
 for seed in [42,1,2]:
  for key in keys:
   dm,sp=key.split('_');pH=pred[(seed,'H',key)];pC=pred[(seed,'C',key)];nonempty=[v for (kk,v),ii in view_pos.items() if kk==key];nviews=len(nonempty)
   for op in ['historical_fpr5','val_recall80','val_recall90']:
    ht=ev[(seed,'H')]['thresholds'][op];ct=ev[(seed,'C')]['thresholds'][op]
    for view in nonempty:
     ids=view_pos[(key,view)];h=np.asarray(pH[ids]);cc=np.asarray(pC[ids]);hh=(h>=ht).astype(int);ch=(cc>=ht).astype(int);hc=(h>=ct).astype(int);ccc=(cc>=ct).astype(int);score=.5*((ch-hh)+(ccc-hc));threshold=.5*((hc-hh)+(ccc-ch));assert np.array_equal(score+threshold,ccc-hh)
     rec=dict(seed=seed,operation=op,domain=dm,split=sp,source=annotations[(key,int(ids[0]))]['source'],view=view,positive_nodes=len(ids),H_recall=avg(hh),C_recall=avg(ccc),recall_delta=avg(ccc-hh),score_component=avg(score),threshold_component=avg(threshold),lost=int(((hh==1)&(ccc==0)).sum()),gained=int(((hh==0)&(ccc==1)).sum()),threshold_H=ht,threshold_C=ct)
     perview.append(rec)
     for k,i in enumerate(ids):
      lost=bool(hh[k] and not ccc[k]);why='not_lost'
      if lost:why='score_reference_crossing' if not ch[k] and hc[k] else 'threshold_reference_crossing' if ch[k] and not hc[k] else 'both_reference_crossings' if not ch[k] and not hc[k] else 'combined_small_changes_cross'
      records.append(dict(seed=seed,operation=op,domain=dm,split=sp,row=int(i),**annotations[(key,int(i))],H_score=float(h[k]),C_score=float(cc[k]),score_delta=float(cc[k]-h[k]),threshold_H=ht,threshold_C=ct,threshold_delta=ct-ht,H_hit=int(hh[k]),C_hit=int(ccc[k]),lost=int(lost),gained=int(not hh[k] and ccc[k]),loss_description=why,score_component=float(score[k]),threshold_component=float(threshold[k]),macro_recall_contribution=float(ccc[k]-hh[k])/(len(ids)*nviews)))
    vv=[r for r in perview if (r['seed'],r['domain'],r['split'],r['operation'])==(seed,dm,sp,op)];h=avg([x['H_recall'] for x in vv]);cc=avg([x['C_recall'] for x in vv])
    if dm=='trans' and sp in ['val','test']:
     assert abs(h-ev[(seed,'H')][sp][op]['trusted']['recall'])<1e-12 and abs(cc-ev[(seed,'C')][sp][op]['trusted']['recall'])<1e-12
    macro_checks.append(dict(seed=seed,key=key,operation=op,H_recall=h,C_recall=cc,score_component=avg([x['score_component'] for x in vv]),threshold_component=avg([x['threshold_component'] for x in vv]),lost_nodes=sum(x['lost'] for x in vv),gained_nodes=sum(x['gained'] for x in vv)))
 dump('positive_node_changes.csv',records);dump('positive_view_changes.csv',perview);dump('global_recall_decomposition.csv',macro_checks)
 cols=['H_recall','C_recall','recall_delta','score_component','threshold_component'];source_seed=aggregate(perview,['seed','operation','domain','split','source'],cols);dump('positive_source_seed.csv',source_seed);dump('positive_source_average.csv',aggregate(source_seed,['operation','domain','split','source'],cols))
 # Exact contributions to the macro recall difference; every physical positive counted once per seed/op.
 contribution=[]
 for sp in ['train','val','test']:
  for cl in sorted({x['role_class'] for x in records if x['domain']=='trans' and x['split']==sp}):
   for seed in [42,1,2]:
    aa=[x for x in records if x['seed']==seed and x['domain']=='trans' and x['split']==sp and x['operation']=='val_recall80' and x['role_class']==cl]
    if aa:contribution.append(dict(seed=seed,split=sp,role_class=cl,unique_positive_nodes=len(aa),lost=sum(x['lost'] for x in aa),gained=sum(x['gained'] for x in aa),macro_recall_delta_contribution=sum(x['macro_recall_contribution'] for x in aa),mean_score_delta=avg([x['score_delta'] for x in aa])))
 for sp in ['train','val','test']:
  for seed in [42,1,2]:
   total=sum(x['macro_recall_delta_contribution'] for x in contribution if x['seed']==seed and x['split']==sp);ref=next(x for x in macro_checks if x['seed']==seed and x['key']=='trans_'+sp and x['operation']=='val_recall80');assert abs(total-(ref['C_recall']-ref['H_recall']))<1e-12
 dump('role_unique_node_contributions.csv',contribution)
 # Paired source-role diagnostics, with both threshold-reference orders retained.
 spec=rows(B/'coordinate_manifest.csv');pairrows=[]
 for x in spec:
  key=x['domain']+'_'+x['split'];ni=np.array([int(i) for i in x['normal_ids'].split('|')]);ti=np.array([int(i) for i in x['trojan_ids'].split('|')])
  for seed in [42,1,2]:
   nh=pred[(seed,'H',key)][ni];nc=pred[(seed,'C',key)][ni];th=pred[(seed,'H',key)][ti];tc=pred[(seed,'C',key)][ti]
   for op in ['historical_fpr5','val_recall80','val_recall90']:
    ht=ev[(seed,'H')]['thresholds'][op];ct=ev[(seed,'C')]['thresholds'][op];hh=avg(th>=ht);cc=avg(tc>=ct);ch=avg(tc>=ht);hc=avg(th>=ct);dn=avg(nc-nh);dt=avg(tc-th);nfH=avg(nh>=ht);nfC=avg(nc>=ct)
    pairrows.append(dict(seed=seed,operation=op,domain=x['domain'],split=x['split'],source=x['source'],trojan_source=x['trojan_source'],view=x['view'],trojan_view=x['trojan_view'],role=x['role'],role_class=x['role_class'],normal_delta=dn,trojan_delta=dt,normal_fpr_H=nfH,normal_fpr_C=nfC,normal_fpr_delta=nfC-nfH,trojan_recall_H=hh,trojan_recall_C=cc,trojan_recall_delta=cc-hh,score_component=.5*((ch-hh)+(cc-hc)),threshold_component=.5*((hc-hh)+(cc-ch)),both_scores_fall=int(dn<-1e-6 and dt<-1e-6),mean_separation_delta=dt-dn,normal_benefit_T_loss=int(nfC<nfH and cc<hh),T_loss_no_normal_benefit=int(cc<hh and nfC>=nfH),normal_Cscores_Hthreshold=avg(nc>=ht),T_Cscores_Hthreshold=ch))
 dump('paired_role_view_changes.csv',pairrows)
 cols=['normal_delta','trojan_delta','normal_fpr_H','normal_fpr_C','normal_fpr_delta','trojan_recall_H','trojan_recall_C','trojan_recall_delta','score_component','threshold_component','both_scores_fall','mean_separation_delta','normal_benefit_T_loss','T_loss_no_normal_benefit','normal_Cscores_Hthreshold','T_Cscores_Hthreshold']
 ps=aggregate(pairrows,['seed','operation','domain','split','source','trojan_source','role','role_class'],cols);pa=aggregate(ps,['operation','domain','split','source','trojan_source','role','role_class'],cols);dump('paired_source_role_seed.csv',ps);dump('paired_source_role_average.csv',pa)
 # Source/category equal weighting, matching prior role analysis; keep object identity before pooling.
 cls=aggregate(ps,['seed','operation','domain','split','source','role_class'],cols);dump('paired_source_class_seed.csv',cls);dump('paired_roleclass_average.csv',aggregate(cls,['operation','domain','split','role_class'],cols))
 for p in [B/'COMPLETE.json',B/'manifest.json',B/'coordinate_manifest.csv',B/'EVALUATION_PLAN.json',V/'input_contract.json',Path(__file__)]:inputs[str(p.relative_to(R))]=sha(p)
 (O/'AUDIT_COMPLETE.json').write_text(json.dumps(dict(training=0,model_forward=0,SAT=0,labels_modified=False,unique_positive_rows=sum(len(x) for x in positive.values()),positive_annotations=dict(collections.Counter(x['role_class'] for x in factory_rows)),positive_loss_rows=len(records),paired_role_view_rows=len(pairrows),all_stored_macro_recalls_reproduced=True,decomposition='symmetric two-order score/threshold reference decomposition; descriptive, not causal or calibration invariant',inputs=inputs),ensure_ascii=False,indent=2),encoding='utf-8');print('Completed offline positive audit')
if __name__=='__main__':main()
