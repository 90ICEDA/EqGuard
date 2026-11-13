"""Certified function negatives and paired-swap controls with exact endpoint budgets."""
from pathlib import Path
import collections,csv,hashlib,json,sys
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;J=R/'_p0pilot/cec_joint_expand_20261105'
sys.path.insert(0,str(J));from common import read,sha,ident,SCHEMA
def write(n,z):
 p=O/n;assert not p.exists(),n;p.write_text(json.dumps(z,ensure_ascii=False,indent=2),encoding='utf-8')
def table(n,rr):
 if not rr:return
 p=O/n;assert not p.exists(),n
 with p.open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def main():
 assert not (O/'CONTROLS_COMPLETE.json').exists()
 data=read(O/'function_inventory.json');byid={p['pair_id']:p for p in data};rawpairs={p['pair_id']:p for p in read(J/'final_pairs.json')};cones={c['cone_id']:c for c in read(J/'final_cones.json')};contexts=read(O/'witness_contexts.json');groups=collections.defaultdict(list)
 for p in data:
  base=[p['source'],p['context_id'],cones[p['left_cone']]['view'],cones[p['right_cone']]['view']]
  groups['main',ident(base)].append(p);groups['strict',p['strict_group']].append(p)
 blockmaps={};support=[];exceptions=[]
 for mode in ['main','strict']:
  blocks={};eligible=set()
  for (m,gid),rr in groups.items():
   if m!=mode or len({p['mask_hex'] for p in rr})<2:continue
   rr=sorted(rr,key=lambda p:ident(['block_candidates_v1',p['pair_id']]))
   for i,p in enumerate(rr):
    # Sparse cyclic neighbors keep construction linear rather than all-pairs.
    picked=0
    for delta in range(1,min(len(rr),33)):
     q=rr[(i+delta)%len(rr)]
     if p['mask_hex']==q['mask_hex'] or p['component']==q['component']:continue
     a,b=sorted([p['pair_id'],q['pair_id']]);bid=ident(['negative_and_swap_block_v1',a,b]);blocks[bid]=dict(block_id=bid,source=p['source'],context_id=p['context_id'],pair_a=a,pair_b=b)
     eligible.update([a,b]);picked+=1
     if picked==4:break
  blockmaps[mode]=blocks
  for src in sorted({p['source'] for p in data}):
   rr=[x for x in eligible if byid[x]['source']==src];support.append(dict(mode=mode,source=src,eligible_pairs=len(rr),blocks=sum(b['source']==src for b in blocks.values()),positive_pairs=sum(all(e['trusted'] and e['label']==1 for e in rawpairs[x]['root_endpoints']) for x in rr)))
   if len(rr)<3:exceptions.append(dict(mode=mode,source=src,reason='insufficient_common_support_for50slots_and_paircap17',eligible_pairs=len(rr)))
 certificates={};schedule=[];usage=[];fairness=[];structural=[]
 for mode in ['main','strict']:
  blocks=blockmaps[mode];eligible_sources=sorted({b['source'] for b in blocks.values() if sum(p['source']==b['source'] and p['mode']==mode and p['eligible_pairs']>=3 for p in support)>0})
  nsource=len(eligible_sources);assert nsource>0
  for seed in [42,1,2]:
   paircount=collections.Counter();nodecount=collections.Counter();sourcecount=collections.Counter();componentcount=collections.Counter();rows=[]
   for rank,source in enumerate(eligible_sources):
    candidates=[b for b in blocks.values() if b['source']==source];tie={b['block_id']:ident(['schedule_tie_v1',seed,b['block_id']]) for b in candidates}
    for step in range(rank%2+1,51,2):
     feasible=[b for b in candidates if paircount[b['pair_a']]<17 and paircount[b['pair_b']]<17]
     assert feasible,(mode,seed,source,'paircap budget infeasible')
     def cost(b):
      a,q=byid[b['pair_a']],byid[b['pair_b']]
      return (max(componentcount[a['component']],componentcount[q['component']]),componentcount[a['component']]+componentcount[q['component']],max(paircount[a['pair_id']],paircount[q['pair_id']]),paircount[a['pair_id']]+paircount[q['pair_id']],tie[b['block_id']])
     b=min(feasible,key=cost);a,q=byid[b['pair_a']],byid[b['pair_b']];row=dict(mode=mode,seed=seed,update=step,source=source,block_id=b['block_id'],pair_a=a['pair_id'],pair_b=q['pair_id'],pair_weight=1/nsource);rows.append(row);sourcecount[source]+=2
     for p in [a,q]:
      paircount[p['pair_id']]+=1;componentcount[p['component']]+=1
      for key in ['left_cone','right_cone']:
       c=cones[p[key]]
       for i in c['graph_rows']:nodecount[c['view'],i]+=1
     if b['block_id'] not in certificates:
      mask=int(a['mask_hex'],16)^int(q['mask_hex'],16);assert mask;pattern=(mask&-mask).bit_length()-1;va=(int(a['mask_hex'],16)>>pattern)&1;vb=(int(q['mask_hex'],16)>>pattern)&1;assert va!=vb
      certificates[b['block_id']]=dict(block_id=b['block_id'],source=source,context_id=b['context_id'],pair_a=a['pair_id'],pair_b=q['pair_id'],pattern=pattern,output_a=va,output_b=vb,cones=[a['left_cone'],a['right_cone'],q['left_cone'],q['right_cone']],expected_outputs=[va,va,vb,vb],certified_negatives=[[a['left_cone'],q['left_cone']],[a['right_cone'],q['right_cone']]],certified_false_permuted_positives=[[a['left_cone'],q['right_cone']],[q['left_cone'],a['right_cone']]],proof='one explicit shared PI_Q input with unequal scalar outputs;independent replay required')
   assert set(sourcecount.values())=={50} and max(paircount.values())<=17 and max(nodecount.values())<=50
   # Exactly preserve all endpoints and weights WITHIN EACH UPDATE, not just totals.
   source_mass=collections.Counter()
   for step in range(1,51):
    rr=[r for r in rows if r['update']==step];r_edges=[];p_edges=[];neg_edges=[];step_struct=[]
    for row in rr:
     a,b=byid[row['pair_a']],byid[row['pair_b']];w=row['pair_weight'];r_edges +=[(a['left_cone'],a['right_cone'],w),(b['left_cone'],b['right_cone'],w)];p_edges +=[(a['left_cone'],b['right_cone'],w),(b['left_cone'],a['right_cone'],w)];neg_edges +=[(a['left_cone'],b['left_cone'],w),(a['right_cone'],b['right_cone'],w)];source_mass[row['source']]+=2*w
     step_struct.append(dict(left_gate_preserved=a['left_gate']==b['left_gate'],right_gate_preserved=a['right_gate']==b['right_gate'],left_cut_count_preserved=len(a['left_tokens'])==len(b['left_tokens']),right_cut_count_preserved=len(a['right_tokens'])==len(b['right_tokens']),left_boundary_set_preserved=a['left_tokens']==b['left_tokens'],right_boundary_set_preserved=a['right_tokens']==b['right_tokens'],size_bins_preserved=(a['left_size_bin'],a['right_size_bin'])==(b['left_size_bin'],b['right_size_bin'])))
    def endpointmass(edges):
     counter=collections.Counter()
     for a,b,w in edges:counter[a]+=w;counter[b]+=w
     return counter
    rm,pm=endpointmass(r_edges),endpointmass(p_edges);assert rm==pm
    real_counts=collections.Counter(c for a,b,w in r_edges for c in [a,b]);perm_counts=collections.Counter(c for a,b,w in p_edges for c in [a,b]);assert real_counts==perm_counts
    # Negative examples are disjoint from both positive edge sets as literal pairs.
    key=lambda a,b:tuple(sorted([a,b]));assert not {key(a,b) for a,b,w in neg_edges}&({key(a,b) for a,b,w in r_edges}|{key(a,b) for a,b,w in p_edges})
    fairness.append(dict(mode=mode,seed=seed,update=step,active_sources=len(rr),positive_terms=len(r_edges),negative_terms=len(neg_edges),cone_pool_rows=len(rm),endpoint_counts_equal=True,weighted_endpoint_mass_max_delta=0.0,same_negative_edges=True,same_full_graph_forward_count=1,no_literal_positive_negative_edge_conflict=True))
    for name in ['left_gate_preserved','right_gate_preserved','left_cut_count_preserved','right_cut_count_preserved','left_boundary_set_preserved','right_boundary_set_preserved','size_bins_preserved']:
     structural.append(dict(mode=mode,seed=seed,update=step,field=name,passed=sum(z[name] for z in step_struct),total=len(step_struct)))
    if mode=='strict':assert all(all(z.values()) for z in step_struct)
   assert len(set(round(x,12) for x in source_mass.values()))==1
   schedule+=rows;usage.append(dict(mode=mode,seed=seed,sources=nsource,positive_pair_slots=len(rows)*2,negative_pair_slots=len(rows)*2,unique_positive_pairs=len(paircount),max_pair_exposure=max(paircount.values()),max_physical_node_pooling_exposure=max(nodecount.values()),source_pair_slots=dict(sourcecount),source_cumulative_loss_weight=dict(source_mass)))
 # Independent scalar evaluation, structurally separate from 128-way bit evaluation.
 rawmodels={};cached_values={};envs={ctx:{tuple(t['token']):int(t['mask_hex'],16) for t in info['input_masks']} for ctx,info in contexts.items()};verified=[]
 def getmodel(c):
  if c['view'] in rawmodels:return rawmodels[c['view']]
  assert sha(R/c['raw_path'])==c['raw_sha'];m=next(iter(read(R/c['raw_path'])['modules'].values()));leaf={};drivers={}
  for name,p in m['ports'].items():
   if p['direction']=='input':
    for j,b in enumerate(p['bits']):leaf[b]=('PI',name,j,0)
  for name,g in m['cells'].items():
   if 'DFF' in g['type'].upper():
    for pin in ['Q','QN']:
     for b in g['connections'].get(pin,[]):leaf[b]=('Q',name,0,int(pin=='QN'))
   else:drivers[g['connections'][SCHEMA[g['type']][0]][0]]=g
  rawmodels[c['view']]=(leaf,drivers);return leaf,drivers
 sys.setrecursionlimit(10000)
 for cert in certificates.values():
  env={t:(mask>>cert['pattern'])&1 for t,mask in envs[cert['context_id']].items()};outputs=[]
  for cid in cert['cones']:
   c=cones[cid];leaf,drivers=getmodel(c);cache=cached_values.setdefault((c['view'],cert['context_id'],cert['pattern']),{})
   def ev(b):
    if not isinstance(b,int):assert b in ['0','1'];return int(b)
    if b in cache:return cache[b]
    if b in leaf:t=leaf[b];out=env[t[:3]]^t[3]
    else:
     g=drivers[b];v=[ev(g['connections'][p][0]) for p in SCHEMA[g['type']][1]];typ=g['type']
     if typ in ['AND2X2','$and']:out=v[0]&v[1]
     elif typ in ['OR2X1','$or']:out=v[0]|v[1]
     elif typ in ['XOR2X1','$xor']:out=v[0]^v[1]
     elif typ in ['INVX0','$not']:out=1-v[0]
     else:assert typ in ['MX2X1_RS','$mux'];out=v[1] if v[2] else v[0]
    cache[b]=out;return out
   outputs.append(ev(c['root_bit']))
  assert outputs==cert['expected_outputs'] and outputs[0]!=outputs[2],cert['block_id'];cert['independent_scalar_verified']=True
  verified.append(dict(block_id=cert['block_id'],source=cert['source'],shared_pattern=cert['pattern'],outputs=''.join(map(str,outputs)),different_function_proved=True))
 table('support.csv',support);table('excluded_support.csv',exceptions);table('schedule.csv',schedule);table('usage.csv',[{**r,'source_pair_slots':json.dumps(r['source_pair_slots']),'source_cumulative_loss_weight':json.dumps(r['source_cumulative_loss_weight'])} for r in usage]);table('fairness_per_update.csv',fairness);table('structure_matching.csv',structural);table('scalar_negative_replay.csv',verified)
 write('negative_certificates.json',list(certificates.values()));write('schedule.json',schedule)
 write('CONTROLS_COMPLETE.json',dict(training=0,model_forward=0,new_SAT_queries=0,negative_certificates=len(certificates),independent_scalar_replays=len(verified),support=support,usage=usage,per_update_fairness_checks=len(fairness),main_budget_and_endpoints_pass=True,main_pair_structural_matching_pass=False,strict_structural_matching_pass=True,main_conclusion_scope='real versus arbitrary source/context/view-matched certified-different links;pair joint structure is not held fixed',strict_conclusion_scope='exact boundary/gate/cut/size-bin support only;151 background pairs,not whole pool or Trojan positive coverage',test_pairs=0,ready_for_model_preflight=True))
 print(json.dumps(dict(certificates=len(certificates),usage=usage),ensure_ascii=False),flush=True)
if __name__=='__main__':main()
