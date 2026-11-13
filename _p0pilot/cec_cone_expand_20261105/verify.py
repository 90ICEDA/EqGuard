"""Audit proof projection, raw totality, dedup and source weighting; no SAT/models."""
from pathlib import Path
import sys,json,csv,collections
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;OLD=R/'_p0pilot/cec_cone_audit_20261105'
sys.path.insert(0,str(OLD));from audit import read,sha,SCHEMA,ident
def dump(n,rr):
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def main():
 assert not (O/'VERIFIED.json').exists();summary=read(O/'EXPANDED.json');pairs=read(O/'pairs.json');cones={c['cone_id']:c for c in read(O/'cones.json')};meta={v['view']:v for v in csv.DictReader((R/'generate_trans/folds/hosts_bt31/views_meta.csv').open(encoding='utf-8-sig'))};views={c['view']:c for c in cones.values()};totality=[]
 for view,c in views.items():
  m=next(iter(read(R/c['raw_path'])['modules'].values()));drivers={};errors=[];statebits=set();comb={}
  def drv(b,name):
   if not isinstance(b,int):errors.append('constant_driven');return
   if b in drivers and drivers[b]!=name:errors.append('multiple_driver:'+str(b))
   drivers[b]=name
  for n,p in m['ports'].items():
   if p['direction']=='input':
    for j,b in enumerate(p['bits']):drv(b,'PI:'+n+':'+str(j))
  for n,g in m['cells'].items():
   if 'DFF' in g['type'].upper():
    for pin in ['Q','QN']:
     for b in g['connections'].get(pin,[]):drv(b,'Q:'+n+':'+pin);statebits.add(b)
   else:
    assert g['type'] in SCHEMA;out,ins=SCHEMA[g['type']];assert len(g['connections'][out])==1;drv(g['connections'][out][0],n);comb[n]=[b for pin in ins for b in g['connections'][pin]]
  successors=collections.defaultdict(set);degree={n:0 for n in comb}
  for n,bs in comb.items():
   for b in bs:
    if not isinstance(b,int):
     if b not in ['0','1']:errors.append('X_or_Z_constant')
     continue
    if b not in drivers:errors.append('undriven:'+str(b));continue
    parent=drivers[b]
    if parent in comb and n not in successors[parent]:successors[parent].add(n);degree[n]+=1
  queue=collections.deque(n for n,d in degree.items() if d==0);count=0
  while queue:
   n=queue.popleft();count+=1
   for t in successors[n]:
    degree[t]-=1
    if degree[t]==0:queue.append(t)
  if count!=len(comb):errors.append('combinational_cycle')
  assert not errors,(view,errors[:6]);totality.append(dict(view=view,comb_cells=len(comb),topologically_evaluated=count,free_PI_Q_total_function=True,unresolved=0,cycles=0,multiple_drivers=0))
 # Components per source count logical objects without Cartesian expansion.
 parent={}
 def find(x):
  parent.setdefault(x,x)
  if parent[x]!=x:parent[x]=find(parent[x])
  return parent[x]
 for p in pairs:
  a,b=find(p['left_cone']),find(p['right_cone']);parent[max(a,b)]=min(a,b)
 components=collections.defaultdict(list)
 for p in pairs:components[p['source_object'],p['split'],find(p['left_cone'])].append(p)
 bysource=collections.defaultdict(list)
 for k,pp in components.items():bysource[k[0],k[1]].append((k[2],pp))
 stats=[];weights=[];split_members=collections.defaultdict(set)
 for (source,split),groups in sorted(bysource.items()):
  refs=[p for _,pp in groups for p in pp];stats.append(dict(source_object=source,split=split,host=source.split('__')[0],unique_pairs=len(refs),logical_components=len(groups),positive_root_pairs=sum(p['root_endpoints'][0]['label']==1 for p in refs),negative_root_pairs=sum(p['root_endpoints'][0]['label']==0 for p in refs),label_assisted_pairs=sum(any('label_assisted' in t for t in p['origins']) for p in refs)))
  nsource=sum(sp==split for _,sp in bysource)
  for comp,pp in groups:
   for p in pp:
    weight=1/nsource/len(groups)/len(pp);weights.append(dict(pair_id=p['pair_id'],source_object=source,split=split,component=comp,weight=weight))
    for cid in [p['left_cone'],p['right_cone']]:
     cc=cones[cid];assert cc['split']==split and meta[cc['view']]['src_view']==source;split_members[split].update((cc['view'],i) for i in cc['graph_rows'])
 for split in ['train','val']:
  ww=[w for w in weights if w['split']==split];assert np.isclose(sum(w['weight'] for w in ww),1)
  for source,sp in bysource:
   if sp==split:assert np.isclose(sum(w['weight'] for w in ww if w['source_object']==source),1/sum(s==split for _,s in bysource))
 assert not split_members['train']&split_members['val'];assert all(p['split'] in ['train','val'] for p in pairs)
 # Grade uses; functional evidence is independent of diagnostic class labels.
 usage=[]
 for p in pairs:
  assert p['proof_ids'] or p['enum']['equal'] is True
  assert p['enum']['equal'] is not False
  if p['enum']['method']=='not_enumerated_width_cap':assert p['proof_ids']
  assert p['labels_used_for_function_acceptance']==False;assert p['current_detection_training_allowed']==False
  usage.append(dict(pair_id=p['pair_id'],split=p['split'],source=p['source_object'],origins='|'.join(p['origins']),functional_stability_eval=True,node_score_drift_diagnostic=p['detection_stability_diagnostic_eligible'],functional_auxiliary_training_data=p['split']=='train',risk_consistency_training=False,whole_cone_label_transfer=False,regional_security_role_equivalence=False))
 dump('raw_model_totality.csv',totality);dump('source_summary.csv',stats);dump('source_component_weights.csv',weights);dump('usage_grades.csv',usage)
 # Recheck new and previous frozen artifacts; old flags/data stay intact.
 for name,hh in summary['inputs'].items():assert sha(R/name)==hh,name
 for name,hh in read(OLD/'COMPLETE.json')['files'].items():assert sha(R/name)==hh,name
 report=dict(training=0,model_forward=0,SAT=0,pairs=len(pairs),splits=dict(collections.Counter(p['split'] for p in pairs)),logical_components=len(components),components_by_split=dict(collections.Counter(k[1] for k in components)),source_objects=len(bysource),sources_by_split={s:sum(sp==s for _,sp in bysource) for s in ['train','val']},hosts_by_split={s:len({src.split('__')[0] for src,sp in bysource if sp==s}) for s in ['train','val']},physical_members_by_split={s:len(split_members[s]) for s in ['train','val']},raw_totality_views=len(totality),global_proof_projection_valid=True,local_enum_pairs=sum(p['enum']['equal'] is True for p in pairs),global_only_over12_input_pairs=sum(p['enum']['method']=='not_enumerated_width_cap' for p in pairs),unconditional_native_proof_pairs=sum(bool(p['proof_ids']) for p in pairs),enum_only_pairs=sum(not p['proof_ids'] for p in pairs),positive_root_pairs_by_split={s:sum(p['split']==s and p['root_endpoints'][0]['label']==1 for p in pairs) for s in ['train','val']},negative_root_pairs_by_split={s:sum(p['split']==s and p['root_endpoints'][0]['label']==0 for p in pairs) for s in ['train','val']},source_component_weights_sum1=True,train_val_disjoint=True,test_pairs=0,old_artifacts_unchanged=True)
 (O/'VERIFIED.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');(O/'PAIR_USAGE_CONTRACT.json').write_text(json.dumps(dict(status='DATA_AND_EVIDENCE_ONLY_NO_TRAINING_AUTHORIZATION',proof_scope=summary['proof_scope'],selection='blind root, preselected-view and label-assisted origins explicitly retained; no strict-label-free gate',training_pair_ids=[p['pair_id'] for p in pairs if p['split']=='train'],validation_pair_ids=[p['pair_id'] for p in pairs if p['split']=='val'],test_pair_ids=[],sampling_weights='source_component_weights.csv; equal source then equal component then observed edge; do not train val; no all-pairs expansion',functional_auxiliary_data_ready=True,detector_probability_consistency_allowed=False,whole_hidden_embedding_alignment_allowed=False,security_labels_transferred=False,current_model_functional_head_implemented=False,anti_collapse_training_protocol_implemented=False),ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
