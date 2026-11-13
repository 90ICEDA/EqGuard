"""Finalize main ALL-endpoint boundary panel and independent evidence/load audit."""
from pathlib import Path
import collections,csv,functools,gzip,hashlib,itertools,json,math,re
import numpy as np
from panel_loader import PanelLoader
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;J=R/'_p0pilot/cec_joint_expand_20261105';P=R/'_p0pilot/cec_po_contract_20261106'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def table(n,rr):
 if not rr:return
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def main():
 done=read(O/'PANEL_COMPLETE.json');assert done['passed'];protected=dict(done['protected_files'])
 for p,h in protected.items():assert sha(R/p)==h,p
 core=read(O/'CORE_FUNCTION_UNIQUE.json');supp=read(O/'COVERAGE_SUPPLEMENT.json');main=[u for u in core if u['left_right_same_boundary']];reduced=[u for u in core if not u['left_right_same_boundary']]
 write('MAIN_ALL_ENDPOINTS_SAME_BOUNDARY.json',main);write('BOUNDARY_REDUCTION_TRANSFER_DIAGNOSTIC.json',reduced)
 # This stronger main filter is structural only;no score/model/evaluation results are read.
 write('FINAL_EVALUATION_POLICY.json',dict(main='MAIN_ALL_ENDPOINTS_SAME_BOUNDARY:every query and candidate in both implementations has SAME actualPIQ set;H3/H2/H1 tiers always separate',per_side_extension='29 coreval units have fixed boundary per side but different left/right actual sets;keep separate boundary-reduction-transfer diagnostic,not main',supplement='4source/flow/MUX coverage units;B0 never mixed into structural-matched main',primary_aggregation='equal nativecontext families,then equal units within family;source-macro and per-source/flow alongside;2/3 candidate metrics separate',query_aggregation='equal unit mass,then equal functions/directions/wrong candidates;reciprocals not independent',weights='EVALUATION_WEIGHTS.csv;no training sampler generated',inference='future frozen encoder only;correct25d sharedcodes at9000/9001;do not feedPO,signatures,witnesses,source names;old training pool and schedule unchanged',independence='max1 context-signature in main;max2 main/per-side core+coverage extension;oldPO diagnostics overlap and never add independentn;val1context1host so no crosshost significance',status='panel/load/evidence verified only;NO model forward or training this round'))
 policy=read(O/'FINAL_EVALUATION_POLICY.json');policy.update(primary_comparison='H3 validation85units,exact structural profile and ALLendpoint boundary:family-macro pairwise win and per-source R-P/R-Z;NOT a combined top1 of2/3candidate tasks',extended_comparison='all98 main units and H2/H1 are secondary;do not replace primary by a more favorable stratum',weights='EVALUATION_WEIGHT_GROUPS.csv recomputes fixed weights per predefined subgroup;old EVALUATION_WEIGHTS.csv is ALL group only',missing_support='emptysource/flow/MUX/shallow subgroup is NA,not0;report supported reference population and never pretend allsource coverage')
 write('FINAL_EVALUATION_POLICY.json',policy)
 inv=read(O/'pair_inventory.json');pairs={e['pair_id']:e for e in inv};cones={c['cone_id']:c for c in read(J/'final_cones.json')};desc=read(O/'cone_descriptors.json');profiles=read(O/'structure_profiles.json');bounds=read(O/'boundary_sets.json');rawpairs={p['pair_id']:p for p in read(J/'final_pairs.json')}
 assert len(inv)==5238
 # Profile and boundary acceptance checked independently from actual exported graphs.
 loader=PanelLoader();graph_keys=loader.contexts
 for panel,uu in [('main',main),('per_side_core',core),('supplement',supp)]:
  seen=collections.Counter()
  for u in uu:
   assert u['functions']==len(u['pair_ids']) in [2,3] and len(set(u['function_signatures']))==u['functions']
   for pid,sig in zip(u['pair_ids'],u['function_signatures']):
    e=pairs[pid];assert e['split']==u['split'] and e['source']==u['source'] and e['context_id']==u['context_id'] and e['view_direction']==u['view_direction'] and e['signature']==sig
    seen[u['split'],u['context_id'],sig]+=1
   for side in [0,1]:
    ids=u['cones'][side::2];bb=[{tuple(t[:3]) for t in cones[c]['leaves']} for c in ids];assert all(x==bb[0] for x in bb)
    if panel=='main':assert bb[0]=={tuple(t[:3]) for t in cones[u['cones'][1-side]]['leaves']}
    if u['tier']!='B0':
     pp=[profiles[desc[c]['profiles'][u['tier']]] for c in ids];assert all(x==pp[0] for x in pp)
   if u['tier']=='B0':assert panel=='supplement'
  if panel in ['main','per_side_core']:assert max(seen.values())==1
 # Independently verify actual native proof log hashes and root projections;no solver execution.
 proof_registry=read(J/'proofs.json');selectedp={p for u in core+supp for p in u['pair_ids']};proofids={p for pid in selectedp for p in rawpairs[pid]['proof_ids']};proof_rows=[]
 for pid in sorted(proofids):
  p=proof_registry[pid];folder=R/p['folder'];model=folder/'model.v';script=folder/'run.ys';log=folder/'run.log'
  # Historical registry hashes normalized script TEXT and full run.log,not query.log.
  script_text=script.read_text(encoding='utf-8');text=log.read_text(encoding='utf-8');assert sha(model)==p['model_sha'] and hashlib.sha256(script_text.encode()).hexdigest()==p['script_sha'] and sha(log)==p['log_sha']
  query=int(p['query_id']);command=[s for s in script_text.splitlines() if s.startswith('sat ')][query];assert re.fullmatch(r'sat '+re.escape(p['args'])+r' -timeout \d+ -show-inputs -show-outputs -dump_json "[^"]+"',command)
  block=re.split(r'^(?:Q|QUERY)\d{4}\s*$',text,flags=re.M)[query+1];assert 'no model found: SUCCESS' in block and 'TIMEOUT' not in block and 'ERROR:' not in text
  proof_rows.append(dict(proof_id=pid,model_sha_verified=True,normalized_script_text_sha_verified=True,full_run_log_sha_verified=True,exact_query_command_and_block_success=True))
 with (J/'proof_projection.csv').open(encoding='utf-8-sig',newline='') as f:projection=list(csv.DictReader(f))
 for pid in selectedp:
  e=pairs[pid];p=rawpairs[pid];matches=[r for r in projection if r['pair_id']==pid and r['proof_id'] in p['proof_ids']]
  valid=False
  for r in matches:
   address={(r['view_a'],int(r['root_a'])),(r['view_b'],int(r['root_b']))};expected={(cones[c]['view'],cones[c]['root_bit']) for c in e['cones']}
   if address==expected:valid=True;break
  assert valid or p.get('enum',{}).get('equal'),pid
 table('PROOF_REUSE_AUDIT.csv',proof_rows)
 # Independent raw-module Boolean bitset evaluator,not the interface consumer or model.
 contexts=read(R/'_p0pilot/cec_pretrain_ready_20261105/witness_contexts.json');contexts.update(read(R/'_p0pilot/cec_cert_expand_20261105/validation_witness_contexts.json'));MASK=(1<<128)-1;models={};raw_outputs={}
 schema={'AND2X2':('Q','AND',['IN1','IN2']),'OR2X1':('Q','OR',['IN1','IN2']),'XOR2X1':('Q','XOR',['IN1','IN2']),'INVX0':('QN','NOT',['IN']),'MX2X1_RS':('Y','MUX',['A','B','S0']),'$and':('Y','AND',['A','B']),'$or':('Y','OR',['A','B']),'$xor':('Y','XOR',['A','B']),'$not':('Y','NOT',['A']),'$mux':('Y','MUX',['A','B','S'])}
 for view in {cones[c]['view'] for c in loader.graphs}:
  ids=[c for c in loader.graphs if cones[c]['view']==view];c0=cones[ids[0]];path=R/c0['raw_path'];assert sha(path)==c0['raw_sha'];m=next(iter(read(path)['modules'].values()));ctx=json.loads(graph_keys[ids[0]])[1];env={tuple(z['token']):int(z['mask_hex'],16) for z in contexts[ctx]['input_masks']};leaves={};drivers={}
  for name,p in m['ports'].items():
   if p['direction']=='input':
    for j,bit in enumerate(p['bits']):leaves[bit]=env['PI',name,j]
  for name,g in m['cells'].items():
   if 'DFF' in g['type'].upper():
    for pin in ['Q','QN']:
     for j,bit in enumerate(g['connections'].get(pin,[])):leaves[bit]=env['Q',name,j]^(MASK if pin=='QN' else 0)
   else:drivers[g['connections'][schema[g['type']][0]][0]]=g
  @functools.lru_cache(None)
  def evaluate(bit):
   if isinstance(bit,str):assert bit in ['0','1'];return MASK if bit=='1' else 0
   if bit in leaves:return leaves[bit]
   g=drivers[bit];_,op,pins=schema[g['type']];v=[evaluate(g['connections'][p][0]) for p in pins]
   if op=='AND':return v[0]&v[1]
   if op=='OR':return v[0]|v[1]
   if op=='XOR':return v[0]^v[1]
   if op=='NOT':return MASK^v[0]
   return (v[2]&v[1])|((MASK^v[2])&v[0])
  for cid in ids:raw_outputs[cid]=evaluate(cones[cid]['root_bit']);assert set(loader.graphs[cid]['comb_names'])==set(cones[cid]['members'])
 for pid in selectedp:
  e=pairs[pid];assert all(raw_outputs[c]==int(e['signature'],16) for c in e['cones'])
 certs=read(O/'DIFFERENT_FUNCTION_CERTIFICATES.json')
 for c in certs:
  aa=[(raw_outputs[cid]>>c['pattern'])&1 for p in c['pair_ids'] for cid in pairs[p]['cones']];assert aa==c['outputs'] and aa[0]!=aa[2]
 # Every exported numeric shard must reload exactly;per-unit contexts cannot depend on batching.
 shard_records=read(O/'LOADER_SHARDS.json');locations={};total_nodes=total_edges=0
 for record in shard_records:
  p=O/record['file'];assert sha(p)==record['sha'];a=loader.arrays(record['cone_ids'],9000)
  with np.load(p) as z:assert all(np.array_equal(a[k],z[k]) for k in a)
  for j,cid in enumerate(record['cone_ids']):locations[cid]=(record['file'],j)
  total_nodes+=record['nodes'];total_edges+=record['edges']
 assert len(locations)==len(loader.graphs)==done['exported_cones']
 checks=[]
 for u in main+supp:
  a,q=loader.unit(u,9000);assert len(q)==2*u['functions'] and all(len(v['candidates'])==u['functions'] for v in q);assert np.isfinite(a['x']).all()
  # All nodes reachable backwards from root; no artificial padding or unconsumed gates.
  for j,cid in enumerate(u['cones']):
   g=loader.graphs[cid];incoming=collections.defaultdict(list)
   for s,d,role,phase in g['edge']:incoming[d].append(s)
   seen=set();stack=[g['root']]
   while stack:
    k=stack.pop()
    if k in seen:continue
    seen.add(k);stack+=incoming[k]
   assert len(seen)==len(g['op']);single=loader.arrays([cid],9000);lo,hi=a['graph_ptr'][j:j+2];assert np.array_equal(single['x'],a['x'][lo:hi])
  checks.append(dict(unit_id=u['unit_id'],split=u['split'],functions=u['functions'],graphs=2*u['functions'],query_count=len(q),nodes=len(a['x']),edges=len(a['edge_role']),all_nodes_ancestors=True,standalone_batch_consistent=True))
 table('ACTUAL_UNIT_LOADING.csv',checks);write('CONE_SHARD_LOCATIONS.json',locations)
 # Evaluation weights avoid recipe aliases and two/three-candidate count inflation.
 weight_rows=[];summary=[]
 planned=read(P/'TRAINING_POOL.json');planned_classes={(u['context_id'],s) for u in planned for s in u['function_signatures']}
 for split in ['train','val']:
  ss=[u for u in main if u['split']==split];family=collections.Counter(u['context_id'] for u in ss);source=collections.Counter(u['source'] for u in ss)
  for u in ss:
   fw=1/(len(family)*family[u['context_id']]);sw=1/(len(source)*source[u['source']]);n=u['functions'];weight_rows.append(dict(unit_id=u['unit_id'],split=split,source=u['source'],context_id=u['context_id'],tier=u['tier'],functions=n,family_macro_unit_weight=fw,source_macro_unit_weight=sw,family_macro_pairwise_query_weight=fw/(2*n*(n-1)),family_macro_top1_query_weight=fw/(2*n),planned_training_function_overlap=sum((u['context_id'],s) in planned_classes for s in u['function_signatures'])))
  summary.append(dict(split=split,main_units=len(ss),triples=sum(u['functions']==3 for u in ss),pairs_only=sum(u['functions']==2 for u in ss),source_objects=len(source),context_families=len(family),hosts=len({re.match(r'^(rs232|s\d+)',u['source']).group() for u in ss}),flows=len({u['flow'] for u in ss}),unique_context_functions=sum(u['functions'] for u in ss),MUX_units=sum(u['has_mux'] for u in ss),root_MUX_units=sum(u['root_mux'] for u in ss),**{t+'_units':sum(u['tier']==t for u in ss) for t in ['H3','H2','H1']}))
 table('EVALUATION_WEIGHTS.csv',weight_rows);table('MAIN_SUMMARY.csv',summary)
 grouped_weights=[]
 for split in ['train','val']:
  ss=[u for u in main if u['split']==split]
  for group in ['ALL','H3','H2','H1','two_functions','three_functions','H3_two_functions','H3_three_functions','MUX','H3_MUX']:
   uu=[u for u in ss if group=='ALL' or group in ['H3','H2','H1'] and u['tier']==group or group=='two_functions' and u['functions']==2 or group=='three_functions' and u['functions']==3 or group=='H3_two_functions' and u['tier']=='H3' and u['functions']==2 or group=='H3_three_functions' and u['tier']=='H3' and u['functions']==3 or group=='MUX' and u['has_mux'] or group=='H3_MUX' and u['tier']=='H3' and u['has_mux']]
   if not uu:continue
   families=collections.Counter(u['context_id'] for u in uu);sources=collections.Counter(u['source'] for u in uu)
   for u in uu:
    fw=1/(len(families)*families[u['context_id']]);sw=1/(len(sources)*sources[u['source']]);n=u['functions'];grouped_weights.append(dict(group=group,split=split,unit_id=u['unit_id'],source=u['source'],context_id=u['context_id'],functions=n,family_unit_weight=fw,source_unit_weight=sw,pairwise_query_weight=fw/(2*n*(n-1)),top1_query_weight=fw/(2*n),chance_top1=1/n))
 table('EVALUATION_WEIGHT_GROUPS.csv',grouped_weights)
 # Fixed scalar baselines characterize residual cues;no model/prediction loaded.
 po=read(O/'ROOT_PO_AUDIT_ONLY.json');baseline=[]
 for split in ['train','val']:
  ss=[u for u in main if u['split']==split]
  for tier in ['ALL','H3','H2','H1']:
   uu=ss if tier=='ALL' else [u for u in ss if u['tier']==tier]
   if not uu:continue
   for control in ['PO_distance','member_count','depth','root_gate','unsigned_boundary_set']:
    scores=[]
    for u in uu:
     n=u['functions'];vals=[]
     for f in range(n):
      for side in [0,1]:
       a=u['cones'][2*f+side];t=u['cones'][2*f+1-side]
       for w in range(n):
        if w==f:continue
        b=u['cones'][2*w+1-side]
        def distance(x,y):
         if control=='PO_distance':return abs(po[x]-po[y])
         if control in ['member_count','depth']:return abs(desc[x]['members' if control=='member_count' else 'depth']-desc[y]['members' if control=='member_count' else 'depth'])
         if control=='root_gate':return float(desc[x]['root_gate']!=desc[y]['root_gate'])
         return float(desc[x]['boundary']!=desc[y]['boundary'])
        dt,dw=distance(a,t),distance(a,b);vals.append(float(dt<dw)+.5*float(dt==dw))
     scores.append((u['context_id'],u['source'],float(np.mean(vals))))
    fm=np.mean([np.mean([z[2] for z in scores if z[0]==key]) for key in {z[0] for z in scores}]);sm=np.mean([np.mean([z[2] for z in scores if z[1]==key]) for key in {z[1] for z in scores}]);baseline.append(dict(split=split,tier=tier,control=control,units=len(uu),family_macro_win=float(fm),source_macro_win=float(sm)))
 table('FIXED_STRUCTURE_BASELINES.csv',baseline)
 assert sha(O/'STRICT_PO_REFERENCE_UNCHANGED.json')==sha(P/'T3_PO_exact_units.json')
 for split in ['train','val']:
  ww=[r for r in weight_rows if r['split']==split];assert abs(sum(r['family_macro_unit_weight'] for r in ww)-1)<1e-12 and abs(sum(r['source_macro_unit_weight'] for r in ww)-1)<1e-12
 for p,h in protected.items():assert sha(R/p)==h,p
 manifest={str(p.relative_to(O)):sha(p) for p in O.rglob('*') if p.is_file() and p.suffix in ['.py','.json','.csv','.npz','.gz'] and '__pycache__' not in p.parts and p.name not in ['VERIFIED.json','OUTPUT_MANIFEST.json','PUBLISHED.json']};write('OUTPUT_MANIFEST.json',manifest)
 write('VERIFIED.json',dict(passed=True,all_input_pairs=5238,main_summary=summary,per_side_boundary_reduction_diagnostic=len(reduced),coverage_supplement=len(supp),existing_native_proof_queries_verified=len(proof_rows),selected_pair_roots_bound_to_projection_or_enum=len(selectedp),selected_local_cones=len(loader.graphs),sharded_numeric_nodes=total_nodes,sharded_numeric_pin_edges=total_edges,loaded_main_and_supplement_units=len(checks),witness_records=len(certs),independent_raw_boolean_replay_passed=True,function_unique_main=True,combined_extension_function_cap=2,strict_oldPO_file_unchanged=True,old_training_pool_and_schedule_unchanged=True,training=0,SAT=0,new_real_input_patterns=0,model_forwards=0,test_reads=0,old_files_unchanged=True,main_vs_training_pool='evaluationtrain21units is NOT oldtraining21units;planned overlap tagged,do not replace sampler',manifest_sha=sha(O/'OUTPUT_MANIFEST.json')))
 print('EXPANDED_SAME_BOUNDARY_PANEL_VERIFIED',json.dumps(summary,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
