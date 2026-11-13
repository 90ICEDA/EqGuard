"""Source/flow/MUX-balanced same-boundary evaluation panels from fixed evidence."""
from pathlib import Path
import collections,csv,gzip,hashlib,importlib.util,itertools,json,math,shutil,time,traceback
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;J=R/'_p0pilot/cec_joint_expand_20261105';I=R/'_p0pilot/cec_interface_minimal_20261105';V=R/'_p0pilot/cec_hard_validation_20261106';P=R/'_p0pilot/cec_po_contract_20261106'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def ident(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def write(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def table(n,rr):
 if not rr:return
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def load(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
A=load('existing_saved128_replay',R/'_p0pilot/cec_relative_contract_20261106/prepare.py');L=load('verified_freeQ_schema',R/'_p0pilot/cec_hard_boundary_20261106/local_interface.py')
TIERS=['H3','H2','H1','B0']
def main():
 start=time.perf_counter();assert not (O/'PANEL_COMPLETE.json').exists();inv=read(O/'pair_inventory.json');desc=read(O/'cone_descriptors.json');protected=dict(read(O/'INVENTORY_COMPLETE.json')['protected_files']);protected[str(Path(__file__).relative_to(R))]=sha(Path(__file__))
 for p,h in protected.items():assert sha(R/p)==h,p
 # Hash partitions offer alternate existing function groupings;no prediction/safetylabel input.
 candidates={};rawgroups=collections.defaultdict(list)
 for e in inv:rawgroups[(e['split'],e['source'],e['context_id'],*e['view_direction'])].append(e)
 byid={e['pair_id']:e for e in inv}
 for tier in TIERS:
  for group,ee in sorted(rawgroups.items()):
   buckets=collections.defaultdict(list)
   for e in ee:buckets[e['tier_keys'][tier]].append(e)
   for profile,records in sorted(buckets.items()):
    reps={}
    for e in sorted(records,key=lambda e:(not e['has_mux'],ident(['representative',e['pair_id']]))):reps.setdefault(e['signature'],e)
    for partition in range(3):
     ordered=sorted(reps.values(),key=lambda e:ident(['partition',partition,e['context_id'],e['signature']]))
     for stride in [3,2]:
      for j in range(0,len(ordered),stride):
       zz=ordered[j:j+stride]
       if len(zz)<2:continue
       pp=[e['pair_id'] for e in zz];key=ident(['boundary_unit',group,sorted(pp)])
       if key in candidates:continue
       e=zz[0];candidates[key]=dict(unit_id=key,split=e['split'],source=e['source'],context_id=e['context_id'],view_direction=e['view_direction'],flow=e['flow'],tier=tier,functions=len(zz),pair_ids=pp,cones=[c for z in zz for c in z['cones']],function_signatures=[z['signature'] for z in zz],has_mux=any(z['has_mux'] for z in zz),root_mux=any(z['root_mux'] for z in zz),shallow_small=all(z['shallow_small'] for z in zz),left_right_same_boundary=all(z['left_right_same_boundary'] for z in zz),boundary_sets=e['boundaries'],boundary_profile=profile,tie_hash=ident(['selection',key]),function_families=[[e['split'],e['context_id'],z['signature']] for z in zz])
 pool=list(candidates.values());counts=collections.Counter();sources=collections.Counter();flows=collections.Counter();sourceflows=collections.Counter();muxsource=collections.Counter();used=set();core=[];supp=[]
 def families(u):return [tuple(k) for k in u['function_families']]
 def apply(u,target):
  used.add(u['unit_id']);target.append(u);counts.update(families(u));sources[u['split'],u['source']]+=1;flows[u['split'],u['flow']]+=1;sourceflows[u['split'],u['source'],u['flow']]+=1
  if u['has_mux']:muxsource[u['split'],u['source']]+=1
 def priority(u):return (sources[u['split'],u['source']],sourceflows[u['split'],u['source'],u['flow']],0 if u['has_mux'] and muxsource[u['split'],u['source']]==0 else 1,flows[u['split'],u['flow']],-u['functions'],u['tie_hash'])
 for tier in TIERS[:3]:
  todo=[u for u in pool if u['tier']==tier]
  while True:
   ok=[u for u in todo if not any(counts[k] for k in families(u))]
   if not ok:break
   u=min(ok,key=priority);apply(u,core);todo=[v for v in todo if v['unit_id']!=u['unit_id']]
 core_sourceflow=set(sourceflows);core_sources=set(sources);core_flows=set(flows)
 for tier in TIERS:
  while True:
   ok=[u for u in pool if u['tier']==tier and u['unit_id'] not in used and all(counts[k]<2 for k in families(u)) and ((u['split'],u['source'],u['flow']) not in sourceflows or (u['has_mux'] and not muxsource[u['split'],u['source']]))]
   if not ok:break
   u=min(ok,key=priority);apply(u,supp)
 assert max(counts.values())<=2
 for u in core+supp:u.pop('tie_hash',None)
 write('CORE_FUNCTION_UNIQUE.json',core);write('COVERAGE_SUPPLEMENT.json',supp);write('CANDIDATE_UNITS.json',pool)
 # Function uniqueness and alias records are explicit;do not count recipes/views as new functions.
 aliases=collections.defaultdict(list)
 for e in inv:aliases[e['split'],e['context_id'],e['signature']].append(e)
 selected={k for u in core+supp for k in families(u)};alias_rows=[]
 for key in sorted(selected):
  es=aliases[key];alias_rows.append(dict(split=key[0],context_id=key[1],signature=key[2],selected_unit_exposure=counts[key],available_pair_evidence=len(es),source_aliases=sorted({e['source'] for e in es}),available_flows=sorted({e['flow'] for e in es}),meaning='equal observed128 signatures merged for conservative weighting only,not new equivalence proof'))
 write('FUNCTION_ALIAS_AUDIT.json',alias_rows)
 oldpo=P/'T3_PO_exact_units.json';protected[str(oldpo.relative_to(R))]=sha(oldpo);shutil.copy2(oldpo,O/'STRICT_PO_REFERENCE_UNCHANGED.json')
 oldpo_units=read(oldpo);need={c for u in core+supp+oldpo_units for c in u['cones']};cones={c['cone_id']:c for c in read(J/'final_cones.json')};contexts=read(R/'_p0pilot/cec_pretrain_ready_20261105/witness_contexts.json')
 for k,v in read(R/'_p0pilot/cec_cert_expand_20261105/validation_witness_contexts.json').items():
  if k in contexts:assert contexts[k]==v
  contexts[k]=v
 replay=A.Replay(contexts,protected);maps={m['context_key']:m['tokens'] for m in read(I/'boundary_maps_audit_only.json')};oldgraphs=read(V/'local_graphs.json');graph_cache={c:g for c,g in zip(oldgraphs['cone_ids'],oldgraphs['graphs']) if c in need};indices={};graph_context={};rawout={}
 # Complete every selected local interface,not merely a covered marker. Compress the audit export.
 reused=len(graph_cache)
 for j,cid in enumerate(sorted(need)):
  c=cones[cid];key=desc[cid]['context_lookup'];graph_context[cid]=key
  if cid not in graph_cache:
   if c['view'] not in indices:indices[c['view']]=L.ModuleIndex(replay.model(c)[0],maps[key])
   graph_cache[cid]=indices[c['view']].cone(c['root_bit'])
  g=graph_cache[cid];L.validate(g);assert set(g['comb_names'])==set(c['members']);ctx=c['context_id'] if 'context_id' in c else json.loads(key)[1]
  values={t['slot']:replay.env[ctx][(t['kind'],t['audit_name'],t['bit'])] for t in maps[key]};out=L.replay(g,values,(1<<128)-1);assert out==replay.evaluate(c,ctx);rawout[cid]=out
  if (j+1)%500==0:print('LOCAL_GRAPH_VERIFIED',j+1,'of',len(need),flush=True)
 with gzip.open(O/'local_graphs.json.gz','wt',encoding='utf-8',compresslevel=3) as f:json.dump(dict(cone_ids=sorted(need),contexts=[graph_context[c] for c in sorted(need)],graphs=[graph_cache[c] for c in sorted(need)]),f,separators=(',',':'))
 oldwitness={}
 oldpaths=[R/'_p0pilot/cec_pretrain_ready_20261105/negative_certificates.json',R/'_p0pilot/cec_cert_expand_20261105/validation_negative_certificates.json',R/'_p0pilot/cec_cause_audit_20261106/panel_certificates.json']
 for path in oldpaths:
  for c in read(path):oldwitness.setdefault(tuple(sorted([c['pair_a'],c['pair_b']])),dict(pattern=c['pattern'],reference=str(path.relative_to(R)),certificate_id=c.get('certificate_id',c.get('block_id'))))
 certificates=[]
 for panel,uu in [('core',core),('coverage_supplement',supp)]:
  for u in uu:
   for pid in u['pair_ids']:
    e=byid[pid];assert all(rawout[c]==int(e['signature'],16) for c in e['cones'])
   for a,b in itertools.combinations(range(u['functions']),2):
    pa,pb=u['pair_ids'][a],u['pair_ids'][b];old=oldwitness.get(tuple(sorted([pa,pb])));diff=int(u['function_signatures'][a],16)^int(u['function_signatures'][b],16);assert diff;bit=old['pattern'] if old else (diff&-diff).bit_length()-1;out=[(rawout[c]>>bit)&1 for pid in [pa,pb] for c in byid[pid]['cones']];assert out[0]==out[1] and out[2]==out[3] and out[0]!=out[2]
    certificates.append(dict(certificate_id=ident(['boundary_expansion',u['unit_id'],pa,pb]),panel=panel,unit_id=u['unit_id'],split=u['split'],source=u['source'],context_id=u['context_id'],pair_ids=[pa,pb],pattern=bit,outputs=out,origin='existing_witness_record' if old else 'saved128_input_replay',reference=old if old else 'existing saved witness_contexts mask position;no new input',new_SAT=0,new_real_input_patterns=0))
 write('DIFFERENT_FUNCTION_CERTIFICATES.json',certificates)
 # Sharded actual numeric load/roundtrip,compatible with the alreadyvalidated25d model.
 shard_dir=O/'loader_shards';shard_dir.mkdir(exist_ok=True);shards=[];ordered=sorted(need)
 for start_index in range(0,len(ordered),100):
  ids=ordered[start_index:start_index+100];a=L.collate([graph_cache[c] for c in ids],[graph_context[c] for c in ids],maps,9000);p=shard_dir/f'shard{len(shards):03}.npz';np.savez_compressed(p,**a)
  with np.load(p) as z:assert all(np.array_equal(a[k],z[k]) for k in a)
  shards.append(dict(file=str(p.relative_to(O)),sha=sha(p),cone_ids=ids,graphs=len(ids),nodes=len(a['x']),edges=len(a['edge_role']),x25=True,tag=9000))
 write('LOADER_SHARDS.json',shards)
 # PO is inspected only after core/supplement indices are fixed. Keep it diagnostic.
 xcontract=read(R/'_p0pilot/control_boundary_v3_20261104/input_contract.json');po={}
 for split in ['train','val']:
  path=R/xcontract['shared_inputs']['trans_'+split]['folder']/'x39.npy';assert sha(path)==xcontract['files'][str(path.relative_to(R))];protected[str(path.relative_to(R))]=sha(path);x=np.load(path,mmap_mode='r')
  for c in need:
   if cones[c]['split']==split:po[c]=int(x[cones[c]['root_row'],30])
 diagnostics=[]
 for u in core:
  buckets=collections.defaultdict(list)
  for i,pid in enumerate(u['pair_ids']):buckets[tuple(po[c] for c in byid[pid]['cones'])].append(i)
  for coord,ix in buckets.items():
   if len(ix)<2:continue
   diagnostics.append(dict(unit_id=ident(['core_exactPO_diagnostic',u['unit_id'],ix]),parent_unit=u['unit_id'],split=u['split'],source=u['source'],context_id=u['context_id'],tier=u['tier'],functions=len(ix),pair_ids=[u['pair_ids'][j] for j in ix],cones=[c for j in ix for c in byid[u['pair_ids'][j]]['cones']],po_pair=list(coord),meaning='overlapping diagnostic only;not extra independent core evidence'))
 write('CORE_EXACT_PO_DIAGNOSTIC.json',diagnostics);write('ROOT_PO_AUDIT_ONLY.json',po)
 summary=[]
 for name,uu in [('core',core),('coverage_supplement',supp),('core_plus_supplement',core+supp)]:
  for split in ['train','val']:
   ss=[u for u in uu if u['split']==split];fs={tuple(f) for u in ss for f in u['function_families']}
   summary.append(dict(panel=name,split=split,units=len(ss),triples=sum(u['functions']==3 for u in ss),pairs_only=sum(u['functions']==2 for u in ss),source_objects=len({u['source'] for u in ss}),query_families=len({u['context_id'] for u in ss}),flows=len({u['flow'] for u in ss}),observed_function_classes=len(fs),MUX_units=sum(u['has_mux'] for u in ss),root_MUX_units=sum(u['root_mux'] for u in ss),shallow_small_units=sum(u['shallow_small'] for u in ss),left_right_same_boundary_units=sum(u['left_right_same_boundary'] for u in ss),**{t+'_units':sum(u['tier']==t for u in ss) for t in TIERS}))
 table('panel_summary.csv',summary)
 source_rows=[]
 for split,source in sorted({(e['split'],e['source']) for e in inv}):
  cc=[u for u in core if u['split']==split and u['source']==source];ss=[u for u in supp if u['split']==split and u['source']==source];available=[u for u in pool if u['split']==split and u['source']==source]
  reason='covered_in_core' if cc else 'coverage_supplement_only' if ss else 'no_same_boundary_different_function_competitor' if not available else 'function_alias_exposure_cap_or_stronger_representative'
  source_rows.append(dict(split=split,source=source,core_units=len(cc),supplement_units=len(ss),core_mux=sum(u['has_mux'] for u in cc),supplement_mux=sum(u['has_mux'] for u in ss),available_candidate_units=len(available),reason=reason))
 table('coverage_by_source.csv',source_rows);table('coverage_by_source_flow.csv',[dict(split=s,source=so,flow=f,core_units=sum(u['split']==s and u['source']==so and u['flow']==f for u in core),supplement_units=sum(u['split']==s and u['source']==so and u['flow']==f for u in supp)) for s,so,f in sorted({(e['split'],e['source'],e['flow']) for e in inv})])
 write('EXPOSURE_POLICY.json',dict(core_max_context_signature=1,core_plus_supplement_max_context_signature=2,actual_core_max=max(collections.Counter(k for u in core for k in families(u)).values()),actual_combined_max=max(counts.values()),strict_PO_reference='old file copied byte-identically;4train4val;overlapping diagnostic,never pool as new samples',evaluation='core source-macro plus queryfamily-macro and perflow;coverage supplement separate;function/recipe aliases never independent confidence replicates',training_schedule='unchanged previous21-unit/32step contract;this panel is evaluation-only',function_alias_classes=len(selected)))
 for p,h in protected.items():assert sha(R/p)==h,p
 write('PANEL_COMPLETE.json',dict(passed=True,input_pairs=5238,candidate_units=len(pool),summary=summary,exported_cones=len(need),reused_existing_local_graphs=reused,newly_materialized_from_existing_raw=len(need)-reused,local_scalar_saved128_matches=len(need)*128,witness_records=len(certificates),direct_old_witnesses=sum(c['origin']=='existing_witness_record' for c in certificates),new_real_input_patterns=0,new_SAT=0,model_forwards=0,training=0,test_reads=0,loader_shards=len(shards),old_files_unchanged=True,seconds=time.perf_counter()-start,protected_files=protected))
 print('EXPANDED_PANEL_COMPLETE',json.dumps(summary,ensure_ascii=False),flush=True)
if __name__=='__main__':
 try:main()
 except Exception:
  O.mkdir(exist_ok=True);(O/f'failure_build_{time.strftime("%H%M%S")}.log').write_text(traceback.format_exc(),encoding='utf-8');raise
