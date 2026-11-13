"""Inventory all5238 proved pairs using saved128 inputs;no SAT or model forward."""
from pathlib import Path
import collections,csv,gzip,hashlib,importlib.util,json,time,traceback
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;J=R/'_p0pilot/cec_joint_expand_20261105';I=R/'_p0pilot/cec_interface_minimal_20261105';PRE=R/'_p0pilot/cec_pretrain_ready_20261105'
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
A=load('frozen_saved128_replay',R/'_p0pilot/cec_relative_contract_20261106/prepare.py')
def bucket_size(n):return (n-1).bit_length()
def main():
 assert not (O/'INVENTORY_COMPLETE.json').exists();start=time.perf_counter()
 protected=dict(read(R/'_p0pilot/cec_freeq_preflight_20261106/EXECUTION_CONTRACT.json')['protected_files'])
 for n,h in read(R/'_p0pilot/cec_freeq_preflight_20261106/OUTPUT_MANIFEST.json').items():protected[str((R/'_p0pilot/cec_freeq_preflight_20261106'/n).relative_to(R))]=h
 for p,h in read(J/'PUBLISHED.json')['files'].items():protected[p]=h
 paths=[I/'cone_pin_incidence.jsonl.gz',I/'boundary_maps_audit_only.json',PRE/'witness_contexts.json',R/'_p0pilot/cec_cert_expand_20261105/validation_witness_contexts.json',R/'_p0pilot/cec_cause_audit_20261106/panel_cone_depths.json',R/'_p0pilot/cec_hard_boundary_20261106/local_interface.py',Path(__file__)]
 for p in paths:protected[str(p.relative_to(R))]=sha(p)
 for p,h in protected.items():assert sha(R/p)==h,p
 rules=dict(universe='5238 final_pairs only,fixed train/val splits;no test pool,no new search,no training',primary_tiers=['H3:exact boundary sets per side+rootgate/size/depth/op/pin/phase/repeat profile','H2:exact boundary sets per side+rootgate/size/depth','H1:exact boundary sets per side+rootgate+fixed power2 size/depth bins'],supplement='B0:exact boundary sets per side only;wide support,not fully structure-controlled',same_boundary='all candidate functions have identical actual PI/Q sets within LEFT and within RIGHT;separately flag whether left set equals right set',PO='excluded from main matching;previous T3_PO_exact4train4val retained unchanged;additional exactPO coverage diagnostic only',functions='merge same saved128 outputsignature conservatively per full nativecontext,never claim new equality proof;different signatures supply existing-input witnesses',selection='source/viewflow/MUX coverage round robin before model/prediction reads;strongest available tier;fixedSHA tie;no safetylabel selection',exposure='function-unique core max1/context-signature;separate coverage supplement cap2/context-signature and report linked dependence;no infinite aliases',candidate_construction='fixed hash partitions into triples or real pairs,never fabricate third function;all eligible viewpairs,not one best flow/source',independence='source objects and viewflows may share host/query/functions;report both raw and unique-family counts',new_input_patterns=0,SAT=0,training=0,model_forwards=0)
 write('SELECTION_CONTRACT.json',rules)
 contexts=read(paths[2])
 for k,v in read(paths[3]).items():
  if k in contexts:assert contexts[k]==v
  contexts[k]=v
 replay=A.Replay(contexts,protected);cones={c['cone_id']:c for c in read(J/'final_cones.json')};pairs=read(J/'final_pairs.json');proofs=read(J/'proofs.json');depth=read(paths[4]);maps={m['context_key']:m['tokens'] for m in read(paths[1])};desc={};boundaries={};profiles={}
 with gzip.open(paths[0],'rt',encoding='utf-8') as f:
  for line in f:
   g=json.loads(line);cid=g['cone_id'];c=cones[cid];module=replay.model(c)[0];root_gate=module['cells'][c['output_cell']]['type'];count=collections.Counter(g['op']);pins=collections.Counter();inc=collections.defaultdict(list);leaf=set()
   for kind,src,phase,dst,role in g['edge']:
    inc[dst].append((kind,src,phase));pins['phase']+=phase
    if kind==1:
     t=maps[g['context_lookup']][src];leaf.add((t['kind'],t['audit_name'],t['bit']));pins[t['kind']]+=1
    elif kind==2:pins['C'+str(src)]+=1
   boundary=tuple(sorted(leaf));bk=ident(boundary);boundaries[bk]=boundary;base=(root_gate,len(g['op']),depth[cid]['gate_depth']);exact=base+tuple(count[k] for k in ['AND','OR','XOR','NOT','MUX'])+tuple(pins[k] for k in ['PI','Q','C0','C1','phase'])+(sum(len(v)-len(set(v)) for v in inc.values()),)
   pk={}
   for name,value in [('H3',exact),('H2',base),('H1',(root_gate,bucket_size(len(g['op'])),bucket_size(depth[cid]['gate_depth']))),('B0',())]:
    h=ident(value);profiles[h]=value;pk[name]=h
   desc[cid]=dict(boundary=bk,profiles=pk,root_gate=root_gate,members=len(g['op']),depth=depth[cid]['gate_depth'],mux=count['MUX'],root_mux=root_gate in ['MX2X1_RS','$mux'],context_lookup=g['context_lookup'])
 entries=[];groups=collections.defaultdict(list);family_signatures=collections.defaultdict(list)
 for p in pairs:
  assert p['split'] in ['train','val'] and p['functional_auxiliary_data_eligible']
  assert p['proof_ids'] or p.get('enum',{}).get('equal');assert all(k in proofs for k in p['proof_ids'])
  cc=sorted([p['left_cone'],p['right_cone']],key=lambda c:cones[c]['view']);ctx=p['context_id'];out=[replay.evaluate(cones[c],ctx) for c in cc];assert out[0]==out[1]
  # Exact common input context is required for signature-based cross-source suppression.
  keys=[desc[c]['context_lookup'] for c in cc];assert all(json.loads(k)[1]==ctx for k in keys)
  views=[cones[c]['view'] for c in cc];source=p['source_object'];flow=[v.rsplit('__',1)[-1] for v in views];boundary=[desc[c]['boundary'] for c in cc];tiers={t:ident([boundary,[desc[c]['profiles'][t] for c in cc]]) for t in ['H3','H2','H1','B0']}
  e=dict(pair_id=p['pair_id'],split=p['split'],source=source,context_id=ctx,view_direction=views,flow='|'.join(flow),cones=cc,signature=hex(out[0]),boundaries=boundary,left_right_same_boundary=boundary[0]==boundary[1],tier_keys=tiers,has_mux=any(desc[c]['mux'] for c in cc),root_mux=any(desc[c]['root_mux'] for c in cc),shallow_small=all(desc[c]['members']<=16 and desc[c]['depth']<=4 for c in cc),proof_ids=p['proof_ids'],enum=p.get('enum',{}))
  entries.append(e);groups[(p['split'],source,ctx,*views)].append(e);family_signatures[(ctx,e['signature'])].append(e['pair_id'])
  if len(entries)%1000==0:print('REUSED_PAIRS',len(entries),flush=True)
 support=[];view_support=[]
 for key,ee in sorted(groups.items()):
  row=dict(split=key[0],source=key[1],context_id=key[2],left_view=key[3],right_view=key[4],flow=ee[0]['flow'],existing_pairs=len(ee),observed_functions=len({e['signature'] for e in ee}))
  for tier in ['H3','H2','H1','B0']:
   buckets=collections.defaultdict(list)
   for e in ee:buckets[e['tier_keys'][tier]].append(e)
   sizes=[len({e['signature'] for e in es}) for es in buckets.values()];row[tier+'_triples']=sum(n//3 for n in sizes);row[tier+'_pairs']=sum(int(n%3==2) for n in sizes);row[tier+'_functions_with_competitors']=sum(n for n in sizes if n>=2)
  view_support.append(row)
 for split in ['train','val']:
  for source in sorted({e['source'] for e in entries if e['split']==split}):
   rr=[r for r in view_support if r['source']==source and r['split']==split];ee=[e for e in entries if e['source']==source and e['split']==split]
   support.append(dict(split=split,source=source,pairs=len(ee),contexts=len({e['context_id'] for e in ee}),flows=len(rr),MUX_pairs=sum(e['has_mux'] for e in ee),**{tier+'_raw_units':sum(r[tier+'_triples']+r[tier+'_pairs'] for r in rr) for tier in ['H3','H2','H1','B0']}))
 write('pair_inventory.json',entries);write('cone_descriptors.json',desc);write('boundary_sets.json',boundaries);write('structure_profiles.json',profiles);table('available_by_source.csv',support);table('available_by_flow.csv',view_support)
 for p,h in protected.items():assert sha(R/p)==h,p
 write('INVENTORY_COMPLETE.json',dict(passed=True,pairs=len(entries),cones=len(desc),saved128_scalar_root_matches=2*len(entries),contexts=len({e['context_id'] for e in entries}),observed_context_function_classes=len(family_signatures),source_objects=len(support),new_SAT=0,new_patterns=0,training=0,model_forwards=0,seconds=time.perf_counter()-start,protected_files=protected))
 print('INVENTORY_COMPLETE',len(entries),len(desc),len(family_signatures),flush=True)
if __name__=='__main__':
 try:main()
 except Exception:
  O.mkdir(exist_ok=True);(O/f'failure_inventory_{time.strftime("%H%M%S")}.log').write_text(traceback.format_exc(),encoding='utf-8');raise
