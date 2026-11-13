"""Offline third-function evidence and collision-free, equal-budget sampling contract."""
from pathlib import Path
import collections,csv,hashlib,json,itertools,time,traceback
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent
J=R/'_p0pilot/cec_joint_expand_20261105';PRE=R/'_p0pilot/cec_pretrain_ready_20261105';OLD=R/'_p0pilot/cec_cause_audit_20261106'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def ident(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def write(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def table(n,rr):
 if not rr:return
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
SCHEMA={'AND2X2':('Q',['IN1','IN2']),'OR2X1':('Q',['IN1','IN2']),'XOR2X1':('Q',['IN1','IN2']),'INVX0':('QN',['IN']),'MX2X1_RS':('Y',['A','B','S0']),'$and':('Y',['A','B']),'$or':('Y',['A','B']),'$xor':('Y',['A','B']),'$not':('Y',['A']),'$mux':('Y',['A','B','S'])}
class Replay:
 def __init__(self,contexts,protected):
  self.env={k:{tuple(t['token']):int(t['mask_hex'],16) for t in c['input_masks']} for k,c in contexts.items()};self.models={};self.protected=protected
 def model(self,c):
  view=c['view']
  if view not in self.models:
   p=R/c['raw_path'];assert sha(p)==c['raw_sha'];self.protected[str(p.relative_to(R))]=sha(p);m=next(iter(read(p)['modules'].values()));leaf={};drv={}
   for n,p in m['ports'].items():
    if p['direction']=='input':
     for j,b in enumerate(p['bits']):leaf[b]=('PI',n,j,0)
   for n,g in m['cells'].items():
    if 'DFF' in g['type'].upper():
     for pin in ['Q','QN']:
      for b in g['connections'].get(pin,[]):leaf[b]=('Q',n,0,int(pin=='QN'))
    else:drv[g['connections'][SCHEMA[g['type']][0]][0]]=g
   self.models[view]=(m,leaf,drv,{})
  return self.models[view]
 def evaluate(self,c,ctx,pattern=None):
  _,leaf,drv,cache=self.model(c);mask=(1<<128)-1 if pattern is None else 1
  if pattern is not None:cache={}
  def ev(bit):
   if not isinstance(bit,int):assert bit in ['0','1'];return mask if bit=='1' else 0
   if bit in cache:return cache[bit]
   if bit in leaf:
    t=leaf[bit];v=self.env[ctx][t[:3]]
    if pattern is not None:v=(v>>pattern)&1
    v^=mask if t[3] else 0
   else:
    g=drv[bit];aa=[ev(g['connections'][pin][0]) for pin in SCHEMA[g['type']][1]];typ=g['type']
    if typ in ['AND2X2','$and']:v=aa[0]&aa[1]
    elif typ in ['OR2X1','$or']:v=aa[0]|aa[1]
    elif typ in ['XOR2X1','$xor']:v=aa[0]^aa[1]
    elif typ in ['INVX0','$not']:v=mask^aa[0]
    else:v=(aa[2]&aa[1])|((mask^aa[2])&aa[0])
   cache[bit]=v;return v
  return ev(c['root_bit'])
def pos_neg(t,arm):
 a,b,c,d,e,f=t['cones'] # A_L,A_R,B_L,B_R,C_L,C_R
 pos=[(a,b),(c,d)] if arm=='R' else [(a,d),(c,b)]
 return pos,[(a,c),(b,d),(a,f),(c,f),(b,e),(d,e)]
def main():
 O.mkdir(exist_ok=True);assert not (O/'PREPARED.json').exists()
 protected={}
 for p,h in read(J/'PUBLISHED.json')['files'].items():assert sha(R/p)==h;protected[p]=h
 contexts=read(PRE/'witness_contexts.json');vc=R/'_p0pilot/cec_cert_expand_20261105/validation_witness_contexts.json'
 for k,v in read(vc).items():
  if k in contexts:assert contexts[k]==v
  contexts[k]=v
 for p in [PRE/'witness_contexts.json',vc,OLD/'panel_cone_depths.json',PRE/'negative_certificates.json',R/'_p0pilot/cec_cert_expand_20261105/validation_negative_certificates.json',OLD/'panel_certificates.json',R/'_p0pilot/cec_pinrole_effective_20261106/shared_R/resume.pt',R/'_p0pilot/control_v3_eligible_20261104/init_s42.pt']:
  protected[str(p.relative_to(R))]=sha(p)
 write('SELECTION_CONTRACT.json',dict(no_predictions_or_labels_for_selection=True,existing_inputs_only=128,canonical_views='maximum distinct observed signatures,then fixed hash;one fixed view pair per source/context',partition='disjoint function triples;existing literal certificate triangles first;remaining functions fixed-hash chunks;third role permanent',training_budget='50 planned steps,25triple-slots/source,pair/function/triple cap17,physical-node cone-membership cap50;drop unsupported sources,never silently duplicate',seed=42,training_started=False,SAT=0))
 pairs=read(J/'final_pairs.json');byid={p['pair_id']:p for p in pairs};cones={c['cone_id']:c for c in read(J/'final_cones.json')};depth=read(OLD/'panel_cone_depths.json');replay=Replay(contexts,protected)
 groups=collections.defaultdict(list);masks={};pairkey={};canonical={}
 for p in pairs:
  assert p['functional_auxiliary_data_eligible'] and (p['proof_ids'] or p.get('enum',{}).get('equal'))
  cc=sorted([cones[p[k]] for k in ['left_cone','right_cone']],key=lambda x:x['view']);ctx=p['context_id'];av,bv=[replay.evaluate(c,ctx) for c in cc];assert av==bv
  pid=p['pair_id'];masks[pid]=av;key=(p['split'],p['source_object'],ctx,cc[0]['view'],cc[1]['view']);groups[key].append(pid);pairkey[pid]=key;canonical[pid]=[c['cone_id'] for c in cc]
 certs=[]
 for file in [PRE/'negative_certificates.json',R/'_p0pilot/cec_cert_expand_20261105/validation_negative_certificates.json',OLD/'panel_certificates.json']:
  for c in read(file):
   a,b=c['pair_a'],c['pair_b'];assert pairkey[a]==pairkey[b] and masks[a]!=masks[b]
   assert ((masks[a]^masks[b])>>c['pattern'])&1
   certs.append(dict(pair_a=a,pair_b=b,pattern=c['pattern'],reference=str(file.relative_to(R)),certificate=c.get('certificate_id',c.get('block_id'))))
 edge={}
 for c in sorted(certs,key=ident):edge.setdefault(tuple(sorted([c['pair_a'],c['pair_b']])),c)
 view_inventory=[];candidates=collections.defaultdict(list)
 for key,ids in groups.items():
  nf=len({masks[p] for p in ids});candidates[key[:3]].append((key,ids,nf))
 for base,gg in candidates.items():
  chosen=min(gg,key=lambda x:(-x[2],ident(x[0])))[0]
  for key,ids,nf in gg:view_inventory.append(dict(split=key[0],source=key[1],context=key[2],left_view=key[3],right_view=key[4],pairs=len(ids),observed_distinct_signatures=nf,chosen=key==chosen))
 table('view_support.csv',view_inventory)
 triple_pool=[];support=[];tri_stats=[]
 for base,gg in sorted(candidates.items()):
  key,ids,nf=min(gg,key=lambda x:(-x[2],ident(x[0])));pool=set(ids);neigh=collections.defaultdict(set)
  for a,b in edge:
   if a in pool and b in pool:neigh[a].add(b);neigh[b].add(a)
  literal=[]
  for a in sorted(neigh):
   for b in sorted(x for x in neigh[a] if x>a):
    for c in sorted(x for x in neigh[a]&neigh[b] if x>b):
     if len({masks[x] for x in [a,b,c]})==3:literal.append([a,b,c])
  reps={}
  for pid in sorted(ids,key=lambda x:ident(['representative',x])):reps.setdefault(masks[pid],pid)
  used=set();tri=[]
  def add(pp,origin):
   pp=sorted(pp,key=lambda x:ident(['triple_role',base,hex(masks[x])]))
   used.update(masks[x] for x in pp);cc=[c for pid in pp for c in canonical[pid]]
   witnesses=[]
   for a,b in itertools.combinations(pp,2):
    old=edge.get(tuple(sorted([a,b])));pattern=old['pattern'] if old else ((masks[a]^masks[b])&-(masks[a]^masks[b])).bit_length()-1
    witnesses.append(dict(pair_a=a,pair_b=b,pattern=pattern,expected_a=(masks[a]>>pattern)&1,expected_b=(masks[b]>>pattern)&1,kind='existing_literal_certificate' if old else 'saved_input_replay',reference=old if old else dict(context_file=str((PRE/'witness_contexts.json' if key[0]=='train' else vc).relative_to(R)),context_id=key[2])))
   shallow=all(len(cones[c]['members'])<=16 and depth[c]['gate_depth']<=4 for c in cc)
   t=dict(triple_id=ident(['relative_triple_v1',key,pp]),split=key[0],source=key[1],context_id=key[2],left_view=key[3],right_view=key[4],pair_A=pp[0],pair_B=pp[1],pair_C=pp[2],cones=cc,witnesses=witnesses,origin=origin,shallow_small=shallow,has_mux=any(depth[c]['mux'] for c in cc),function_signatures=[hex(masks[x]) for x in pp])
   tri.append(t)
  # Process shallow proof triangles first, then deep; no model information involved.
  for pp in sorted(literal,key=lambda pp:(not all(len(cones[c]['members'])<=16 and depth[c]['gate_depth']<=4 for pid in pp for c in canonical[pid]),ident(pp))):
   if not used.intersection(masks[x] for x in pp):add(pp,'existing_three_edge_certificate_triangle')
  rest=[pid for sig,pid in reps.items() if sig not in used]
  shallow=lambda pid:all(len(cones[c]['members'])<=16 and depth[c]['gate_depth']<=4 for c in canonical[pid])
  rem=[]
  for flag in [True,False]:
   rr=sorted([p for p in rest if shallow(p)==flag],key=lambda p:ident(['function_partition',base,hex(masks[p])]))
   if not flag:rr=rem+rr
   for j in range(0,len(rr)-2,3):add(rr[j:j+3],'replay_saved_input_assignments')
   rem=rr[3*(len(rr)//3):]
  triple_pool+=tri
  support.append(dict(split=key[0],source=key[1],context=key[2],canonical_view_direction=key[3].split('__')[-1]+'|'+key[4].split('__')[-1],existing_pairs=len(ids),distinct_observed_signatures=nf,literal_existing_triangles=len(literal),disjoint_existing_triangles=sum(t['origin']=='existing_three_edge_certificate_triangle' for t in tri),total_disjoint_triples=len(tri),saved_input_extension_triples=sum(t['origin']!='existing_three_edge_certificate_triangle' for t in tri),shallow_small_triples=sum(t['shallow_small'] for t in tri),shallow_mux_triples=sum(t['shallow_small'] and t['has_mux'] for t in tri),unused_signature_classes=len(rem)))
 write('triple_pool.json',triple_pool);table('support.csv',support)
 # One readout exposure counts each occurrence in a cone, including overlaps.
 nodes={t['triple_id']:collections.Counter((cones[c]['view'],r) for c in t['cones'] for r in cones[c]['graph_rows']) for t in triple_pool}
 feasible={};excluded=[]
 for source in sorted({p['source_object'] for p in pairs if p['split']=='train'}):
  tt=[t for t in triple_pool if t['source']==source and t['split']=='train'];nc=collections.Counter();tc=collections.Counter();picked=[]
  for slot in range(25):
   ok=[t for t in tt if tc[t['triple_id']]<17 and all(nc[n]+v<=50 for n,v in nodes[t['triple_id']].items())]
   if not ok:break
   def cost(t):
    ns=nodes[t['triple_id']];return (tc[t['triple_id']],max((nc[n]+v for n,v in ns.items()),default=0),sum(nc[n]*v for n,v in ns.items()),ident(['slot',slot,t['triple_id']]))
   t=min(ok,key=cost);picked.append(t);tc[t['triple_id']]+=1;nc.update(nodes[t['triple_id']])
  if len(picked)==25:feasible[source]=picked
  else:excluded.append(dict(source=source,triple_pool=len(tt),feasible_slots_before_cap=len(picked),required_slots=25,reason='cannot fill25 slots with triple/function cap17 and node pooling cap50;excluded in all arms'))
 schedule=[];N=len(feasible);assert N>0
 for rank,(source,tt) in enumerate(sorted(feasible.items())):
  for slot,t in enumerate(tt):schedule.append(dict(update=2*slot+1+rank%2,source=source,triple_id=t['triple_id'],source_block_weight=2/N))
 schedule=sorted(schedule,key=lambda x:(x['update'],x['source']));write('schedule_seed42.json',schedule);table('excluded_training_sources.csv',excluded)
 # Evaluation cap16/source/tier; functions disjoint globally, so no repeated endpoint.
 evaluation=[]
 for source in sorted({t['source'] for t in triple_pool if t['split']=='val'}):
  for shallow in [True,False]:evaluation += sorted([t for t in triple_pool if t['source']==source and t['split']=='val' and t['shallow_small']==shallow],key=lambda t:ident(['evaluation',t['triple_id']]))[:16]
 write('evaluation_panel.json',evaluation)
 selected={x['triple_id'] for x in schedule}|{t['triple_id'] for t in evaluation};chosen=[t for t in triple_pool if t['triple_id'] in selected]
 # Separate scalar replay for every selected three-function negative witness.
 replay_rows=[]
 for t in chosen:
  for w in t['witnesses']:
   aa=[replay.evaluate(cones[c],t['context_id'],w['pattern']) for c in canonical[w['pair_a']]];bb=[replay.evaluate(cones[c],t['context_id'],w['pattern']) for c in canonical[w['pair_b']]]
   assert aa==[w['expected_a']]*2 and bb==[w['expected_b']]*2 and aa[0]!=bb[0]
   replay_rows.append(dict(triple_id=t['triple_id'],pair_a=w['pair_a'],pair_b=w['pair_b'],pattern=w['pattern'],kind=w['kind'],outputs=''.join(map(str,aa+bb)),passed=True))
 table('selected_witness_replay.csv',replay_rows)
 for p,h in protected.items():assert sha(R/p)==h,p
 write('PREPARED.json',dict(training_started=False,model_forwards=0,backwards=0,SAT=0,new_input_patterns=0,test_reads=0,selected_sources=N,scheduled_blocks=len(schedule),positive_pair_slots=2*len(schedule),common_negative_terms=6*len(schedule),ranking_terms=4*len(schedule),readout_endpoint_slots=6*len(schedule),planned_updates=50,selected_unique_triples=len({x['triple_id'] for x in schedule}),eval_triples=len(evaluation),selected_scalar_witnesses=len(replay_rows),all_old_files_unchanged=True,protected_files=protected))
 print(json.dumps(dict(sources=N,rows=len(schedule),excluded=excluded,support=support,evaluation=len(evaluation)),ensure_ascii=False),flush=True)
if __name__=='__main__':
 try:main()
 except Exception:
  O.mkdir(exist_ok=True);(O/f'failure_{time.strftime("%H%M%S")}.log').write_text(traceback.format_exc(),encoding='utf-8');raise
