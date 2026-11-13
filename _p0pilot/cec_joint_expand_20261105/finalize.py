"""Independent scalar replay, final mixed-proof pool, and bounded source schedule."""
from common import *
def main():
 assert not (O/'FINAL_COMPLETE.json').exists();sys.setrecursionlimit(10000)
 pairs={p['pair_id']:p for p in read(O/'joint_pairs.json')};cones={c['cone_id']:c for c in read(O/'joint_cones.json')};baseids={p['pair_id'] for p in read(PRE/'pool_pairs.json')}
 for p in read(O/'bounded_pairs.json'):assert p['pair_id'] not in pairs;pairs[p['pair_id']]=p
 for z in read(O/'bounded_cones.json'):cones[z['cone_id']]=z
 for path,h in read(PRE/'PUBLISHED.json')['files'].items():assert sha(R/path)==h,('Old artifact modified',path)
 inputs={}
 for name in ['JOINT_COMPLETE.json','BOUNDED_COMPLETE.json']:
  for path,h in read(O/name)['inputs'].items():assert sha(R/path)==h,path;inputs[path]=h
 models={};envs={k:{tuple(t['token']):int(t['mask_hex'],16) for t in c['input_masks']} for k,c in read(O/'witness_contexts.json').items()};scalar_cache={}
 def model(c):
  if c['view'] in models:return models[c['view']]
  m=next(iter(read(R/c['raw_path'])['modules'].values()));assert sha(R/c['raw_path'])==c['raw_sha'];leaf={};drivers={}
  for n,p in m['ports'].items():
   if p['direction']=='input':
    for j,b in enumerate(p['bits']):leaf[b]=('PI',n,j,0)
  for n,g in m['cells'].items():
   if 'DFF' in g['type'].upper():
    for pin in ['Q','QN']:
     for b in g['connections'].get(pin,[]):leaf[b]=('Q',n,0,int(pin=='QN'))
   else:assert g['type'] in SCHEMA;drivers[g['connections'][SCHEMA[g['type']][0]][0]]=g
  models[c['view']]=(m,leaf,drivers);return models[c['view']]
 def evaluator(c,env,cache):
  _,leaf,drivers=model(c)
  def ev(b):
   if not isinstance(b,int):assert b in ['0','1'];return int(b)
   if b in cache:return cache[b]
   if b in leaf:t=leaf[b];a=env[t[:3]]^t[3]
   else:
    g=drivers[b];v=[ev(g['connections'][pin][0]) for pin in SCHEMA[g['type']][1]];typ=g['type']
    if typ in ['AND2X2','$and']:a=v[0]&v[1]
    elif typ in ['OR2X1','$or']:a=v[0]|v[1]
    elif typ in ['XOR2X1','$xor']:a=v[0]^v[1]
    elif typ in ['INVX0','$not']:a=1-v[0]
    else:assert typ in ['MX2X1_RS','$mux'];a=v[1] if v[2] else v[0]
   cache[b]=a;return a
  return ev(c['root_bit'])
 witnesses=read(O/'nonconstant_witnesses.json');replay=[]
 for w in witnesses:
  p=pairs[w['pair_id']];cs=[cones[p[k]] for k in ['left_cone','right_cone']]
  for pattern,expected in [(w['pattern_for0'],0),(w['pattern_for1'],1)]:
   env={t:(mask>>pattern)&1 for t,mask in envs[w['context_id']].items()}
   outputs=[evaluator(c,env,scalar_cache.setdefault((c['view'],w['context_id'],pattern),{})) for c in cs];assert outputs==[expected,expected],(p['pair_id'],outputs)
  replay.append(dict(pair_id=p['pair_id'],method='independent_scalar_two_nonconstant_witnesses',assignments=2,nonconstant=True,equivalence_source='source_bound_existing_joint_CEC'))
  if len(replay)%1000==0:print('Scalar witness replay',len(replay),flush=True)
 # Independent scalar replay of EVERY input for the eight newly enumerated pairs.
 for cert in read(O/'bounded_certificates.json'):
  if cert['status']!='proved':continue
  p=pairs[cert['pair_id']];cs=[cones[p[k]] for k in ['left_cone','right_cone']];tokens=[tuple(t) for t in cert['semantic_inputs']];values=[]
  for pattern in range(cert['patterns']):
   env={t:(pattern>>j)&1 for j,t in enumerate(tokens)};a,b=[evaluator(c,env,{}) for c in cs];assert a==b,(p['pair_id'],pattern);values.append(a)
  packed=np.packbits(values,bitorder='little').tobytes();assert packed.hex()==cert['packed_truth_hex'] and hashlib.sha256(packed).hexdigest()==cert['truth_sha'];assert 0 in values and 1 in values
  replay.append(dict(pair_id=p['pair_id'],method='independent_scalar_complete_PI_Q_enumeration',assignments=cert['patterns'],nonconstant=True,equivalence_source='complete_two_valued_enumeration'))
 print('Independent replay complete',len(replay),flush=True)
 parent={}
 def find(x):
  parent.setdefault(x,x)
  if parent[x]!=x:parent[x]=find(parent[x])
  return parent[x]
 for p in pairs.values():
  u,v=[find((p['split'],p['source_object'],p['context_id'],p[k])) for k in ['left_cone','right_cone']];parent[max(u,v)]=min(u,v)
 groups=collections.defaultdict(list)
 for p in pairs.values():groups[find((p['split'],p['source_object'],p['context_id'],p['left_cone']))].append(p)
 sources={s:sorted({p['source_object'] for p in pairs.values() if p['split']==s}) for s in ['train','val','test']};assert not set(sources['train'])&set(sources['val'])
 weights=[];components={}
 for comp,rr in groups.items():
  split,src,ctx,cid=comp;nc=sum(k[0]==split and k[1]==src for k in groups)
  for p in rr:weights.append(dict(pair_id=p['pair_id'],split=split,source=src,context_id=ctx,component=cid,weight=1/len(sources[split])/nc/len(rr)));components[p['pair_id']]=cid
 for split in ['train','val']:
  ww=[w for w in weights if w['split']==split];assert np.isclose(sum(w['weight'] for w in ww),1)
  for src in sources[split]:assert np.isclose(sum(w['weight'] for w in ww if w['source']==src),1/len(sources[split]))
 # Independent graph attachment is rechecked for every physical cone.
 contract=read(R/'_p0pilot/control_boundary_v3_20261104/input_contract.json');vm={v['view']:(key,v) for key,q in contract['shared_inputs'].items() if key in ['trans_train','trans_val'] for v in q['views']};names=[n.strip().lstrip('\\') for n in (R/'generate_trans/folds/hosts_bt31/data/processed/node_names_trans.txt').read_text(encoding='utf-8').splitlines()];arrays={};meta={v['view']:v for v in rows(R/'generate_trans/folds/hosts_bt31/views_meta.csv')};used={p[k] for p in pairs.values() for k in ['left_cone','right_cone']};cones={k:v for k,v in cones.items() if k in used}
 for key in ['trans_train','trans_val']:
  folder=R/contract['shared_inputs'][key]['folder'];arrays[key]={n:np.load(folder/(n+'.npy'),mmap_mode='r') for n in ['y','trusted','physical','x39']}
 for cid,c in cones.items():
  key,v=vm[c['view']];ii=np.asarray(c['graph_rows']);assert c['split']==key.split('_')[1] and len(set(c['graph_rows']))==len(ii)>0
  assert ((ii>=v['start'])&(ii<v['physical_stop'])).all() and arrays[key]['physical'][ii].all() and np.isfinite(arrays[key]['x39'][ii]).all()
  assert c['root_row'] in ii and names[v['old_start']+c['root_row']-v['start']]==c['output_cell']
  m=model(c)[0];assert m['cells'][c['output_cell']]['connections'][c['output_pin']]==[c['root_bit']]
 for p in pairs.values():
  assert not p['labels_used_for_function_acceptance']
  for key,e in zip(['left_cone','right_cone'],p['root_endpoints']):
   c=cones[p[key]];ar=arrays[vm[c['view']][0]];assert meta[c['view']]['src_view']==p['source_object'];i=c['root_row'];assert e['label']==int(ar['y'][i]) and e['trusted']==bool(ar['trusted'][i]) and e['physical']==bool(ar['physical'][i])
 # Fifty label-blind source-balanced rounds. One observed edge/source/update.
 # This bounds any individual physical node's pooling exposure by fifty rounds.
 schedule=[];per_pair=collections.Counter();per_node=collections.Counter();source_counts=collections.Counter();by_source=collections.defaultdict(dict)
 for comp,rr in groups.items():
  if comp[0]=='train':by_source[comp[1]][comp]=rr
 for source,gg in sorted(by_source.items()):
  gglist=sorted(gg);edge_counters=collections.Counter()
  for step in range(50):
   cycle=step//len(gglist);order=sorted(gglist,key=lambda g:ident(['pretrain_components_v1',source,cycle,g]));comp=order[step%len(gglist)];rr=gg[comp];idx=edge_counters[comp];edge_cycle=idx//len(rr);edges=sorted(rr,key=lambda p:ident(['pretrain_edges_v1',source,comp,edge_cycle,p['pair_id']]));p=edges[idx%len(rr)];edge_counters[comp]+=1
   schedule.append(dict(update=step+1,source=source,pair_id=p['pair_id'],component=comp[3],split='train'));per_pair[p['pair_id']]+=1;source_counts[source]+=1
   for ckey in ['left_cone','right_cone']:
    c=cones[p[ckey]]
    for i in c['graph_rows']:per_node[c['view'],i]+=1
 assert set(source_counts.values())=={50} and max(per_node.values())<=50
 assert all(sum(r['update']==step for r in schedule)==len(sources['train']) for step in range(1,51))
 # Report overlapping membership separately from bounded actual schedule exposure.
 source_summary=[];positive=[];flows=[]
 for split in ['train','val']:
  for source in sources[split]:
   pp=[p for p in pairs.values() if p['split']==split and p['source_object']==source];ids={p[k] for p in pp for k in ['left_cone','right_cone']};membership=collections.Counter((cones[c]['view'],i) for c in ids for i in cones[c]['graph_rows']);pos=[p for p in pp if all(e['trusted'] and e['label']==1 for e in p['root_endpoints'])]
   source_summary.append(dict(split=split,source=source,pairs=len(pp),components=sum(k[0]==split and k[1]==source for k in groups),unique_cones=len(ids),unique_physical_members=len(membership),max_shared_cone_membership=max(membership.values()),positive_pairs=len(pos)))
  for p in pairs.values():
   if p['split']==split and all(e['trusted'] and e['label']==1 for e in p['root_endpoints']):positive.append(dict(split=split,source=p['source_object'],pair_id=p['pair_id'],flow='/'.join(sorted(meta[cones[p[k]]['view']]['op'] for k in ['left_cone','right_cone'])),proof_method='source_bound_CEC' if p['proof_ids'] else 'complete_enumeration'))
  for a,b in sorted({tuple(sorted(meta[cones[p[k]]['view']]['op'] for k in ['left_cone','right_cone'])) for p in pairs.values() if p['split']==split}):
   pp=[p for p in pairs.values() if p['split']==split and sorted(meta[cones[p[k]]['view']]['op'] for k in ['left_cone','right_cone'])==[a,b]];flows.append(dict(split=split,flow=a+'/'+b,pairs=len(pp),sources=len({p['source_object'] for p in pp}),positive_pairs=sum(all(e['trusted'] and e['label']==1 for e in p['root_endpoints']) for p in pp)))
 grade={s:dict(pairs=sum(p['split']==s for p in pairs.values()),sources=len(sources[s]),hosts=len({source.split('__')[0] for source in sources[s]}),positive_pairs=sum(p['split']==s and all(e['trusted'] and e['label']==1 for e in p['root_endpoints']) for p in pairs.values()),positive_sources=len({p['source_object'] for p in pairs.values() if p['split']==s and all(e['trusted'] and e['label']==1 for e in p['root_endpoints'])}),native_CEC=sum(p['split']==s and bool(p['proof_ids']) for p in pairs.values()),full_enum=sum(p['split']==s and not p['proof_ids'] for p in pairs.values())) for s in ['train','val','test']}
 write('final_pairs.json',list(pairs.values()));write('final_cones.json',list(cones.values()));table('weights.csv',weights);table('source_summary.csv',source_summary);table('positive_roots.csv',positive);table('flow_summary.csv',flows);table('scalar_replay.csv',replay);table('source_balanced_schedule.csv',schedule)
 write('SCHEDULE_VERIFIED.json',dict(training=0,model_forward=0,updates=50,slots_per_update=len(sources['train']),total_pair_slots=len(schedule),unique_pairs=len(per_pair),max_single_pair_exposure=max(per_pair.values()),per_source_pair_slots=dict(source_counts),maximum_physical_node_pooling_exposure=max(per_node.values()),cap50_verified=True,labels_or_predictions_used=False,coverage_warning='bounded prototype schedule;does not expose all5238pairs;negatives and permuted-arm exposure still require joint audit',full_graph_forward_warning='node cap counts cone pooling appearances,not full-graph message-passing visits'))
 write('FINAL_CONTRACT.json',dict(status='DATA_ONLY_NOT_TRAINING_READY',primary={s:[p['pair_id'] for p in pairs.values() if p['split']==s] for s in sources},weights={r['pair_id']:r['weight'] for r in weights},data_hashes={n:sha(O/n) for n in ['final_pairs.json','final_cones.json']},proof_methods=['source_bound_CEC','complete_PI_Q_enumeration'],train_data_only=True,val_evaluation_only=True,risk_consistency_allowed=False,label_transfer_allowed=False,training_started=False))
 write('FINAL_COMPLETE.json',dict(training=0,model_forward=0,new_SAT_queries=0,pairs=len(pairs),by_split=grade,components=len(groups),components_by_split=dict(collections.Counter(k[0] for k in groups)),graph_cones_checked=len(cones),independent_scalar_checks=len(replay),joint_witness_assignments=len(witnesses)*2,new_full_enum_assignments=read(O/'BOUNDED_COMPLETE.json')['actual_patterns'],reviews_recovered=18,reviews_new_independent_pairs=0,schedule=read(O/'SCHEDULE_VERIFIED.json'),old_files_unchanged=True,training_ready=False,solver_attempt='one failed raw preparation,WSL/E_ACCESSDENIED;no SAT query executed',inputs=inputs))
 print(read(O/'FINAL_COMPLETE.json')|{'inputs':'hashes saved'},flush=True)
if __name__=='__main__':main()
