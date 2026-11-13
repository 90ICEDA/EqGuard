"""Build exact-structure-matched function panels from existing equalities/witnesses."""
from pathlib import Path
import collections,csv,gzip,hashlib,importlib.util,json,sys,time,traceback
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;J=R/'_p0pilot/cec_joint_expand_20261105';I=R/'_p0pilot/cec_interface_minimal_20261105';PRE=R/'_p0pilot/cec_pretrain_ready_20261105';C=R/'_p0pilot/cec_relative_contract_20261106'
s=importlib.util.spec_from_file_location('old_saved_input_replay',C/'prepare.py');A=importlib.util.module_from_spec(s);s.loader.exec_module(A)
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def ident(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def write(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def table(n,rr):
 if not rr:return
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def main():
 O.mkdir(exist_ok=True);assert not (O/'PANEL_COMPLETE.json').exists()
 frozen={}
 for p,h in read(J/'PUBLISHED.json')['files'].items():assert sha(R/p)==h;frozen[p]=h
 for p,h in read(R/'_p0pilot/cec_relative_diagnosis_20261106/ANALYSIS_CONTRACT.json')['frozen_files'].items():assert sha(R/p)==h;frozen[p]=h
 paths=[I/'cone_pin_incidence.jsonl.gz',I/'boundary_maps_audit_only.json',PRE/'witness_contexts.json',R/'_p0pilot/cec_cert_expand_20261105/validation_witness_contexts.json',R/'_p0pilot/cec_cause_audit_20261106/panel_cone_depths.json',Path(__file__),O/'local_interface.py',C/'prepare.py']
 for p in paths:frozen[str(p.relative_to(R))]=sha(p)
 write('SELECTION_CONTRACT.json',dict(phase='posthoc diagnostic panel,not fresh confirmatory validation',selection='source/context/view-pair matched;exact structural keys;fixed hash,never predictions or safety labels',tiers=['T3_same_boundary','T2_extended_profile','T1_exact_profile'],base_key='root gate type,exact member count,exact maximum gate depth,exact physical-input count in BOTH views',extended_key='base+5op histogram,PI/Q pin counts,constant0/1 pin counts,phase1 count,repeated-pin count',T3='extended+same aligned physical boundary token sets in both views',per_source_total_cap=16,functions='different existing128-pattern outputs required;equal signatures merged conservatively,not equivalence proofs;no new patterns for real netlists',shape='six endpoints if3functions available,otherwise4endpoint eval-only block;disjoint signatures per source/context',canonical_views='lexicographically maximize T3/T2/T1 unit support then hash;support-based only',training=0,SAT=0,test_reads=0))
 contexts=read(paths[2])
 for k,v in read(paths[3]).items():
  if k in contexts:assert contexts[k]==v
  contexts[k]=v
 replay=A.Replay(contexts,frozen);pairs=read(J/'final_pairs.json');byid={p['pair_id']:p for p in pairs};cones={c['cone_id']:c for c in read(J/'final_cones.json')};depth=read(paths[4]);maps={m['context_key']:m['tokens'] for m in read(paths[1])};desc={};masks={};canonical={};groups=collections.defaultdict(list)
 with gzip.open(paths[0],'rt',encoding='utf-8') as f:
  for line in f:
   g=json.loads(line);cid=g['cone_id'];c=cones[cid];module=replay.model(c)[0];gate=module['cells'][c['output_cell']]['type'];ph=collections.Counter(g['op']);pins=collections.Counter();inc=collections.defaultdict(list);leaf=set()
   for kind,src,phase,dst,role in g['edge']:
    inc[dst].append((kind,src,phase));pins['phase1']+=phase
    if kind==1:
     token=maps[g['context_lookup']][src];pins[token['kind']]+=1;leaf.add((token['kind'],token['audit_name'],token['bit']))
    if kind==2:pins['C'+str(src)]+=1
   repeats=sum(len(v)-len(set(v)) for v in inc.values());base=(gate,len(g['op']),depth[cid]['gate_depth'],len(leaf));ext=base+tuple(ph[k] for k in ['AND','OR','XOR','NOT','MUX'])+tuple(pins[k] for k in ['PI','Q','C0','C1','phase1'])+(repeats,);strict=ext+(tuple(sorted(leaf)),)
   desc[cid]=dict(base=base,extended=ext,strict=strict,context_lookup=g['context_lookup'],mux=ph['MUX'])
 for p in pairs:
  assert p['split'] in ['train','val'] and p['functional_auxiliary_data_eligible'] and (p['proof_ids'] or p.get('enum',{}).get('equal'))
  cc=sorted([p['left_cone'],p['right_cone']],key=lambda c:cones[c]['view']);av,bv=[replay.evaluate(cones[c],p['context_id']) for c in cc];assert av==bv
  masks[p['pair_id']]=av;canonical[p['pair_id']]=cc;groups[(p['split'],p['source_object'],p['context_id'],cones[cc[0]]['view'],cones[cc[1]]['view'])].append(p['pair_id'])
 bysource=collections.defaultdict(list);viewrows=[]
 tiers=[('T3_same_boundary','strict'),('T2_extended_profile','extended'),('T1_exact_profile','base')]
 def buckets(ids,key):
  d=collections.defaultdict(list)
  for pid in ids:d[tuple(desc[c][key] for c in canonical[pid])].append(pid)
  return d
 def count_units(ids,key):
  ns=[len({masks[p] for p in pp}) for pp in buckets(ids,key).values()];return sum(n//3+int(n%3==2) for n in ns)
 for group,ids in groups.items():bysource[group[:3]].append((group,ids,tuple(count_units(ids,k) for _,k in tiers)))
 oldtrain=read(C/'triple_pool.json');oldused={r['triple_id'] for r in read(C/'schedule_seed42.json')};seenp={t[k] for t in oldtrain if t['triple_id'] in oldused for k in ['pair_A','pair_B','pair_C']};seenmask={(t['source'],t['context_id'],sig) for t in oldtrain if t['triple_id'] in oldused for sig in t['function_signatures']}
 # Direct certificate reuse is counted separately from replays of saved input bits.
 oldedges={}
 for path in [PRE/'negative_certificates.json',R/'_p0pilot/cec_cert_expand_20261105/validation_negative_certificates.json',R/'_p0pilot/cec_cause_audit_20261106/panel_certificates.json']:
  frozen[str(path.relative_to(R))]=sha(path)
  for c in read(path):oldedges.setdefault(tuple(sorted([c['pair_a'],c['pair_b']])),dict(reference=str(path.relative_to(R)),certificate_id=c.get('certificate_id',c.get('block_id')),pattern=c['pattern']))
 units=[];support=[]
 for base,choices in sorted(bysource.items()):
  group,ids,score=min(choices,key=lambda item:(tuple(-v for v in item[2]),ident(item[0])))
  for gg,ii,sc in choices:viewrows.append(dict(split=gg[0],source=gg[1],left_view=gg[3],right_view=gg[4],existing_pairs=len(ii),T3_units=sc[0],T2_units=sc[1],T1_units=sc[2],selected=gg==group))
  used=set();selected=[]
  for tier,key in tiers:
   bb=buckets(ids,key)
   for profile,pp in sorted(bb.items(),key=lambda kv:(-len({masks[p] for p in kv[1]}),ident(kv[0]))):
    reps={}
    for pid in sorted(pp,key=lambda p:ident(['representative',p])):
     if masks[pid] not in used:reps.setdefault(masks[pid],pid)
    values=sorted(reps.values(),key=lambda p:ident(['function_order',base,hex(masks[p])]))
    while len(values)>=2 and len(selected)<16:
     n=3 if len(values)>=3 else 2;chosen=values[:n];values=values[n:];used.update(masks[p] for p in chosen);cc=[c for p in chosen for c in canonical[p]];witness=[]
     for j,a in enumerate(chosen):
      for b in chosen[j+1:]:
       old=oldedges.get(tuple(sorted([a,b])));diff=masks[a]^masks[b];assert diff;bit=old['pattern'] if old else (diff&-diff).bit_length()-1;assert (diff>>bit)&1
       witness.append(dict(pair_a=a,pair_b=b,pattern=bit,outputs=[(masks[a]>>bit)&1]*2+[(masks[b]>>bit)&1]*2,origin='existing_certificate' if old else 'saved_input_replay',reference=old if old else dict(context_id=base[2],input_file=str((PRE/'witness_contexts.json' if base[0]=='train' else paths[3]).relative_to(R)))))
     for side in [0,1]:assert len({tuple(desc[canonical[p][side]]['base']) for p in chosen})==1
     u=dict(unit_id=ident(['exact_structure_hard_v1',group,tier,chosen]),split=base[0],source=base[1],context_id=base[2],view_direction=[group[3],group[4]],tier=tier,pair_ids=chosen,cones=cc,functions=n,third_function_available=n==3,training_use='candidate only;no optimizer;four-endpoint blocks eval-only',function_signatures=[hex(masks[p]) for p in chosen],witnesses=witness,prior_supervised_pair_count=sum(p in seenp for p in chosen),prior_observed_signature_count=sum((base[1],base[2],hex(masks[p])) in seenmask for p in chosen),has_mux=any(desc[c]['mux'] for c in cc),shallow_small=all(desc[c]['base'][1]<=16 and desc[c]['base'][2]<=4 for c in cc))
     selected.append(u)
   support.append(dict(split=base[0],source=base[1],tier=tier,potential_units_before_function_dedup=count_units(ids,key),selected_units=sum(u['tier']==tier for u in selected),selected_triples=sum(u['tier']==tier and u['functions']==3 for u in selected),selected_pairs_only=sum(u['tier']==tier and u['functions']==2 for u in selected),selected_mux=sum(u['tier']==tier and u['has_mux'] for u in selected)))
  units+=selected
 write('hard_panel.json',units);table('panel_support.csv',support);table('view_support.csv',viewrows)
 # Independent raw scalar replay uses original modules and exactly old input positions.
 replays=[]
 for u in units:
  for w in u['witnesses']:
   out=[replay.evaluate(cones[c],u['context_id'],w['pattern']) for pid in [w['pair_a'],w['pair_b']] for c in canonical[pid]];assert out==w['outputs'] and out[0]!=out[2];replays.append(dict(unit_id=u['unit_id'],pattern=w['pattern'],origin=w['origin'],outputs=''.join(map(str,out)),passed=True))
 table('witness_replay.csv',replays)
 # Basic structure baselines must tie by exact matching, not approximately match bins.
 for u in units:
  for side in [0,1]:assert all(desc[u['cones'][side]]['base']==desc[u['cones'][j]]['base'] for j in range(side,len(u['cones']),2))
 for p,h in frozen.items():assert sha(R/p)==h,p
 write('PANEL_COMPLETE.json',dict(units=len(units),selected_cones=len({c for u in units for c in u['cones']}),selected_existing_equal_pairs=len({p for u in units for p in u['pair_ids']}),witnesses=len(replays),direct_existing_witnesses=sum(r['origin']=='existing_certificate' for r in replays),saved_input_witness_replays=sum(r['origin']=='saved_input_replay' for r in replays),structure_baseline_same_anchor_win=.5,structure_baseline_function_AUC=.5,triplet_structure_threeway_accuracy=1/3,raw_signature_matching='conservative observed128 output merge,not equality proof',old_files_unchanged=True,training=0,SAT=0,new_real_netlist_input_patterns=0,test_features_labels_predictions_reads=0,frozen_files=frozen))
 print(json.dumps(dict(units=len(units),witnesses=len(replays),tiers=collections.Counter(u['tier'] for u in units),splits=collections.Counter(u['split'] for u in units)),ensure_ascii=False),flush=True)
if __name__=='__main__':
 try:main()
 except Exception:
  O.mkdir(exist_ok=True);(O/f'panel_failure_{time.strftime("%H%M%S")}.log').write_text(traceback.format_exc(),encoding='utf-8');raise
