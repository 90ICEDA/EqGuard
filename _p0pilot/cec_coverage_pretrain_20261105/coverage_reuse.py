"""Inventory gaps and recover exact native proof projections. Zero SAT/training."""
from pathlib import Path
import collections, csv, hashlib, json, re, sys
import numpy as np
R=Path(__file__).resolve().parents[2]; O=Path(__file__).resolve().parent
P=R/'_p0pilot/cec_cone_expand_20261105';T=R/'10.15/06_统一评测协议/N4_三向泛化/tables'
sys.path.insert(0,str(R/'_p0pilot/cec_cone_audit_20261105'))
from audit import read,rows,sha,ident,cone,module,SCHEMA
sys.path.insert(0,str(R/'_p0pilot/round10_20261025'));import native as N
def forbidden(*a,**k):raise RuntimeError('No solver/subprocess permitted')
N.P0.run_yosys=forbidden
def write(n,z):
 p=O/n;assert not p.exists(),n;p.write_text(json.dumps(z,ensure_ascii=False,indent=2),encoding='utf-8')
def table(n,z):
 if not z:return
 p=O/n;assert not p.exists(),n
 with p.open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(z[0]));w.writeheader();w.writerows(z)
def main():
 assert not (O/'REUSE_COMPLETE.json').exists()
 for path,h in read(P/'FINAL_COMPLETE.json')['files'].items():assert sha(R/path)==h
 base=[p for p in read(P/'final_pairs.json') if p['proof_ids']];pairmap={p['pair_id']:p for p in base};oldids=set(pairmap)
 cones={c['cone_id']:c for c in read(P/'final_cones.json')};proofs=read(P/'reused_proofs.json')
 contractpath=R/'_p0pilot/control_boundary_v3_20261104/input_contract.json';c=read(contractpath)
 vm={v['view']:(key,v) for key,q in c['shared_inputs'].items() if key.startswith('trans_') for v in q['views']}
 metadata=rows(R/'generate_trans/folds/hosts_bt31/views_meta.csv');meta={x['view']:x for x in metadata}
 names=[x.strip().lstrip('\\') for x in (R/'generate_trans/folds/hosts_bt31/data/processed/node_names_trans.txt').read_text(encoding='utf-8').splitlines()]
 arrays={};raws={};bindings={};maps={};layouts={};generated={};cells={};input_hashes={str(contractpath.relative_to(R)):sha(contractpath)}
 for split in ['train','val']:
  key='trans_'+split;folder=R/c['shared_inputs'][key]['folder'];arrays[key]={}
  for n in ['y','trusted','physical','x39']:
   path=folder/(n+'.npy');hh=sha(path);assert hh==c['files'][str(path.relative_to(R))];input_hashes[str(path.relative_to(R))]=hh;arrays[key][n]=np.load(path,mmap_mode='r')
 def raw(view):
  if view in raws:return raws[view]
  assert view in vm and vm[view][0] in ['trans_train','trans_val']
  options=[T/d/'structures'/view/'raw.json' for d in ['sat_pair_round10','sat_pair_round11','sat_pair_round12']]
  options += [T/'sat_cases_round8'/view/'raw.json']
  path=next(p for p in options if p.exists());hh=sha(path);source=R/'generate_trans/folds/hosts_bt31/trans'/(view+'.v');ss=sha(source)
  if (path.parent/'source.json').exists():
   s=read(path.parent/'source.json');assert s['raw_sha']==hh and s['source_sha']==ss
  else:
   s=next(x for x in rows(T/'sat_cases_round8/sources.csv') if x['view']==view);assert s['raw_sha']==hh and s['source_sha']==ss
  input_hashes[str(path.relative_to(R))]=hh;input_hashes[str(source.relative_to(R))]=ss
  m=next(iter(read(path)['modules'].values()));raws[view]=m;bindings[view]=dict(raw_path=str(path.relative_to(R)),raw_sha=hh,source_sha=ss)
  _,v=vm[view];maps[view]={n:v['start']+j for j,n in enumerate(names[v['old_start']:v['old_stop']])};layouts[view]=N.layout(m)
  dm=collections.defaultdict(list)
  for name,g in m['cells'].items():
   if g['type'] in SCHEMA:
    pin=SCHEMA[g['type']][0]
    for b in g['connections'][pin]:dm[b].append((name,pin))
  cells[view]=dm
  return m
 ledger=[];queries=[];candidates=[];newcert=[];rejections=[];cached_cones={}
 def makecone(view,bit):
  if (view,bit) in cached_cones:return cached_cones[view,bit]
  m=raw(view)
  if len(cells[view].get(bit,[]))!=1:cached_cones[view,bit]=None;return None
  cell,pin=cells[view][bit][0];z=cone(m,bit,maps[view],bindings[view]['raw_sha'])
  if z['errors'] or z['unmapped_members'] or not z['nontrivial']:cached_cones[view,bit]=None;return None
  z.update(cone_id=ident([bindings[view]['source_sha'],cell,pin]),view=view,split=vm[view][0].split('_')[1],output_cell=cell,output_pin=pin,root_row=maps[view][cell],**bindings[view])
  ar=arrays[vm[view][0]];ii=np.asarray(z['graph_rows']);_,v=vm[view]
  assert ((ii>=v['start'])&(ii<v['physical_stop'])).all() and ar['physical'][ii].all() and np.isfinite(ar['x39'][ii]).all()
  cached_cones[view,bit]=z;return z
 def consider(va,vb,ba,bb,pid,index,origin,positive_only):
  if positive_only:
   possible=False
   for view,bit in [(va,ba),(vb,bb)]:
    raw(view)
    for cell,pin in cells[view].get(bit,[]):
     if cell in maps[view]:
      ar=arrays[vm[view][0]];i=maps[view][cell]
      possible |= bool(ar['physical'][i] and ar['trusted'][i] and ar['y'][i]==1)
   if not possible:return
  aa,bb=makecone(va,ba),makecone(vb,bb)
  if aa is None or bb is None:
   rejections.append(dict(view_a=va,view_b=vb,proof_id=pid,index=index,reason='PI_Q_or_constant_anchor_or_unmapped_nontrivial_cone'));return
  ends=[]
  for z in [aa,bb]:
   ar=arrays[vm[z['view']][0]];i=z['root_row'];ends.append(dict(view=z['view'],row=i,cell=z['output_cell'],pin=z['output_pin'],label=int(ar['y'][i]),trusted=bool(ar['trusted'][i]),physical=bool(ar['physical'][i])))
  positive_sides=sum(x['trusted'] and x['label']==1 for x in ends)
  if positive_only and not positive_sides:return
  assert layouts[va]==layouts[vb];ctx=ident(dict(PI=layouts[va][0],physicalQ=layouts[va][1],free=True));source=meta[va]['src_view'];assert source==meta[vb]['src_view']
  key=ident([source,ctx,sorted([aa['cone_id'],bb['cone_id']])]);split=aa['split'];assert split==bb['split']
  isnew=key not in pairmap
  if isnew:
   p=dict(pair_id=key,source_object=source,split=split,context_id=ctx,left_cone=aa['cone_id'],right_cone=bb['cone_id'],origins=[origin],proof_ids=[pid],observations=[f'proof_index:{index}'],enum=dict(method='existing_exact_proof_projection_no_new_enumeration',inputs=len({tuple(l[:3]) for z in [aa,bb] for l in z['leaves']}),equal=None),root_endpoints=ends,labels_used_for_selection=positive_only,labels_used_for_function_acceptance=False,functional_auxiliary_data_eligible=True,current_detection_training_allowed=False,detection_stability_diagnostic_eligible=all(x['trusted'] and x['physical'] for x in ends) and ends[0]['label']==ends[1]['label'])
   pairmap[key]=p
   for z in [aa,bb]:cones[z['cone_id']]=z
  newcert.append(dict(pair_id=key,proof_id=pid,observation_index=index,root_a=aa['root_bit'],root_b=bb['root_bit'],view_a=va,view_b=vb,new_pair=isnew,origin=origin))
  candidates.append(dict(pair_id=key,split=split,source=source,proof_id=pid,index=index,new_pair=isnew,positive_sides=positive_sides,label_a=ends[0]['label'],label_b=ends[1]['label'],origin=origin))
 # All known whole-proof observations, without old first64 or first4 positive caps.
 for g in rows(P/'whole_proof_observation_sources.csv'):
  va,vb=g['view_a'],g['view_b'];pid=g['proof_id'];q=proofs[pid];code=(R/q['folder']/'model.v').read_text(encoding='utf-8')
  for v in [va,vb]:raw(v)
  ns=['left_design','right_design'] if q['args']=='-prove observation_diff 0' else ['design_ys_id','design_ys_abc'];terms=[]
  for mn in ns:terms.append([x.strip() for x in re.search(r'assign obs\s*=\s*\{(.*?)\};',module(code,mn)).group(1).split(',')][::-1])
  assert len(terms[0])==len(terms[1])==int(g['observations_proved'])
  for j,(a,b) in enumerate(zip(*terms)):
   if re.fullmatch(r'b\d+',a) and re.fullmatch(r'b\d+',b):consider(va,vb,int(a[1:]),int(b[1:]),pid,j,'label_assisted_exhaustive_existing_PO_D',True)
  ledger.append(dict(kind='whole_existing',source=g['source'],view_a=va,view_b=vb,proof_id=pid,observations_scanned=len(terms[0])))
 # Audit every exact, unconditional proved native query in current cumulative tables.
 seen=set()
 for dirname,filename in [('sat_pair_round10','queries_with_repairs.csv'),('sat_pair_round11','queries_batch3.csv'),('sat_pair_round12','queries.csv')]:
  file=T/dirname/filename;input_hashes[str(file.relative_to(R))]=sha(file)
  for q in rows(file):
   if q['status']!='proved' or not re.fullmatch(r'-prove (?:delta\[\d+\]|mismatch|observation_diff) 0',q['args']):continue
   unique=(q['folder'],int(q['query_id']))
   if unique in seen:continue
   seen.add(unique)
   phase=3 if 'pairs_batch3' in q['folder'] else 2 if 'pairs_batch2' in q['folder'] else 1
   planpath=T/dirname/('plan.json' if phase==1 else f'plan_batch{phase}.json');plan=read(planpath);input_hashes[str(planpath.relative_to(R))]=sha(planpath)
   item=plan['selected'][int(q['pair_index'])];va,vb=item['source_view'],item['partner']
   if va not in vm or vb not in vm or vm[va][0] not in ['trans_train','trans_val'] or vm[vb][0]!=vm[va][0]:
    queries.append(dict(folder=q['folder'],query_id=q['query_id'],status='excluded_non_train_val_or_split'));continue
   for view in [va,vb]:raw(view)
   assert meta[va]['src_view']==meta[vb]['src_view'] and layouts[va]==layouts[vb]
   folder=R/q['folder'];code=(folder/'model.v').read_text(encoding='utf-8');script=(folder/'run.ys').read_text(encoding='utf-8');log=(folder/'run.log').read_text(encoding='utf-8')
   assert sha(folder/'model.v')==q['model_sha'] and sha(folder/'run.log')==q['log_sha'] and hashlib.sha256(script.encode()).hexdigest()==q['script_sha']
   cmds=[s for s in script.splitlines() if s.startswith('sat ')];cmd=cmds[int(q['query_id'])];assert re.fullmatch(r'sat '+re.escape(q['args'])+r' -timeout \d+ -show-inputs -show-outputs -dump_json "[^"]+"',cmd)
   blocks=re.split(r'^Q\d{4}\s*$',log,flags=re.M);block=blocks[int(q['query_id'])+1];assert 'no model found: SUCCESS' in block and 'TIMEOUT' not in block and 'ERROR:' not in log
   for name in ['model.v','run.ys','run.log']:input_hashes[str((folder/name).relative_to(R))]=sha(folder/name)
   check=module(code,'check');assert 'left_design l(env,a,oa)' in check and 'right_design r(env,b,ob)' in check
   assert not re.search(r'\bassume\b|assign\s+env\s*=',check)
   terms=[];bound=True
   for view,mn in [(va,'left_design'),(vb,'right_design')]:
    body=module(code,mn);m=raw(view);net=next(n for n,z in m['netnames'].items() if len(z['bits'])==1)
    if (view,mn) not in generated:generated[view,mn]=N.emit(m,mn,[net]*5)[0]
    strip=lambda s:re.sub(r'assign sigs=\{.*?\};','assign sigs=BOUND;',s)
    if strip(generated[view,mn])!=strip(body):
     queries.append(dict(folder=q['folder'],query_id=q['query_id'],status='excluded_model_not_equal_to_current_planned_raw'))
     bound=False;break
    field='obs' if q['args']=='-prove observation_diff 0' else 'sigs';terms.append([x.strip() for x in re.search(r'assign '+field+r'\s*=\s*\{(.*?)\};',body).group(1).split(',')][::-1])
   if not bound:continue
   assert len(terms[0])==len(terms[1]);pid=ident([q['model_sha'],q['args']]);proofs[pid]={k:q[k] for k in ['folder','query_id','args','model_sha','script_sha','log_sha']}
   if q['args']=='-prove observation_diff 0':assert 'assign observation_diff=|(oa^ob);' in check;indices=range(len(terms[0]));posonly=True;origin='label_assisted_exhaustive_existing_PO_D'
   else:
    if q['args']=='-prove mismatch 0':j=int(re.search(r'assign mismatch=a\[(\d+)\]\^b\[\1\];',check).group(1))
    else:assert 'assign delta=a^b;' in check;j=int(re.search(r'delta\[(\d+)\]',q['args']).group(1))
    indices=[j];posonly=False;origin='existing_unconditional_point_proof_census'
   for j in indices:
    a,b=terms[0][j],terms[1][j]
    if re.fullmatch(r'b\d+',a) and re.fullmatch(r'b\d+',b):consider(va,vb,int(a[1:]),int(b[1:]),pid,j,origin,posonly)
   queries.append(dict(folder=q['folder'],query_id=q['query_id'],status='bound_model_query_verified'))
 # New candidates must also have explicit nonconstancy evidence. Evaluate only two
 # deterministic witnesses here; unresolved constants will be excluded downstream.
 new=[p for p in pairmap.values() if p['pair_id'] not in oldids]
 write('candidate_pairs.json',list(pairmap.values()));write('candidate_cones.json',list(cones.values()));write('reused_proofs.json',proofs)
 table('whole_scan.csv',ledger);table('query_audit.csv',queries);table('candidate_projections.csv',newcert);table('candidate_selection.csv',candidates);table('excluded_anchors.csv',rejections)
 # Coverage denominators are all CURRENT transformed views/sources, not old pair rows.
 def coverage(pool,tag):
  output=[]
  for split in ['train','val','test']:
   available=[v for view,(key,v) in vm.items() if key=='trans_'+split]
   for host in sorted({meta[v['view']]['host'] for v in available}):
    vv=[v for v in available if meta[v['view']]['host']==host];pp=[p for p in pool if p['split']==split and p['source_object'].split('__')[0]==host]
    pos=[p for p in pp if all(e['trusted'] and e['label']==1 for e in p['root_endpoints'])]
    output.append(dict(stage=tag,split=split,host=host,total_views=len(vv),total_sources=len({meta[v['view']]['src_view'] for v in vv}),paired_sources=len({p['source_object'] for p in pp}),pairs=len(pp),positive_pairs=len(pos),positive_sources=len({p['source_object'] for p in pos})))
  return output
 table('coverage_before.csv',coverage(base,'before'));table('coverage_candidate.csv',coverage(list(pairmap.values()),'candidate_before_nonconstancy'))
 flow=[]
 for split in ['train','val','test']:
  views=[v['view'] for view,(key,v) in vm.items() if key=='trans_'+split]
  ops=sorted({meta[v]['op'] for v in views})
  for i,a in enumerate(ops):
   for b in ops[i+1:]:
    potential={meta[v]['src_view'] for v in views if meta[v]['op']==a}&{meta[v]['src_view'] for v in views if meta[v]['op']==b}
    pp=[p for p in base if p['split']==split and sorted(meta[cones[p[k]]['view']]['op'] for k in ['left_cone','right_cone'])==[a,b]]
    pos=[p for p in pp if all(e['trusted'] and e['label']==1 for e in p['root_endpoints'])]
    flow.append(dict(split=split,op_a=a,op_b=b,available_shared_sources=len(potential),paired_sources=len({p['source_object'] for p in pp}),pairs=len(pp),positive_pairs=len(pos),positive_sources=len({p['source_object'] for p in pos})))
 table('flow_gaps_before.csv',flow)
 write('REUSE_COMPLETE.json',dict(training=0,model_forward=0,new_SAT_queries=0,base_pairs=len(base),candidate_pairs=len(pairmap),new_candidates=len(new),candidate_splits=dict(collections.Counter(p['split'] for p in new)),whole_observation_positions=sum(x['observations_scanned'] for x in ledger),exact_query_census=len(queries),new_candidate_positive=sum(all(e['trusted'] and e['label']==1 for e in p['root_endpoints']) for p in new),test_labels_loaded=False,inputs=input_hashes))
 print(read(O/'REUSE_COMPLETE.json')|{'inputs':'hashes saved'},flush=True)
if __name__=='__main__':main()
