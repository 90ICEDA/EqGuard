"""No model execution: certify budgets, global sign consistency and ranking algebra."""
from pathlib import Path
import collections,csv,hashlib,json
import numpy as np
O=Path(__file__).resolve().parent;R=O.parents[1];J=R/'_p0pilot/cec_joint_expand_20261105'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def table(n,rr):
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def associations(t,mode):
 a,b,c,d,e,f=t['cones'];pos=[(a,b),(c,d)] if mode=='R' else [(a,d),(c,b)]
 return pos,[(a,c),(b,d),(a,f),(c,f),(b,e),(d,e)]
def directed(t):
 a,b,c,d,e,f=t['cones']
 return [(a,[b,d,f],0,1),(c,[b,d,f],1,0),(b,[a,c,e],0,1),(d,[a,c,e],1,0)]
def edge(a,b):return tuple(sorted([a,b]))
def main():
 prep=read(O/'PREPARED.json');assert not prep['training_started']
 for p,h in prep['protected_files'].items():assert sha(R/p)==h,p
 tt=read(O/'triple_pool.json');byid={t['triple_id']:t for t in tt};schedule=read(O/'schedule_seed42.json');evaluation=read(O/'evaluation_panel.json');cones={c['cone_id']:c for c in read(J/'final_cones.json')};pairs={p['pair_id']:p for p in read(J/'final_pairs.json')}
 addr=lambda cid:(cones[cid]['split'],cones[cid]['view'],cones[cid]['root_row'])
 # Function roles are permanent across the entire source/context, not per batch.
 roles={}
 for t in tt:
  for sig,role in zip(t['function_signatures'],['candidate','candidate','third_negative']):
   k=(t['split'],t['source'],t['context_id'],sig)
   if k in roles:assert roles[k]==role
   roles[k]=role
 sourcecounts=collections.Counter(r['source'] for r in schedule);assert set(sourcecounts.values())=={25}
 tc=collections.Counter(r['triple_id'] for r in schedule);assert max(tc.values())<=17
 nc=collections.Counter()
 for row in schedule:
  t=byid[row['triple_id']];assert t['split']=='train'
  for c in t['cones']:nc.update((cones[c]['view'],r) for r in cones[c]['graph_rows'])
 assert max(nc.values())<=50
 budgets=[];conflict=[]
 arms={'Z':('off','none'),'A_R':('MSE','R'),'A_P':('MSE','P'),'S_R':('three_way_CE','R'),'S_P':('three_way_CE','P')}
 for arm,(objective,mode) in arms.items():
  parent={};positive=set();negative=set();soft_negative=set();targetmass=collections.Counter();sourcemass=collections.Counter();endpointcounts=collections.Counter()
  def find(x):
   parent.setdefault(x,x)
   if parent[x]!=x:parent[x]=find(parent[x])
   return parent[x]
  for row in schedule:
   t=byid[row['triple_id']];pmode=mode if mode!='none' else 'R';pos,neg=associations(t,pmode)
   for a,b in pos:
    aa,bb=addr(a),addr(b);positive.add(edge(aa,bb));parent[find(aa)]=find(bb)
   negative.update(edge(addr(a),addr(b)) for a,b in neg)
   for a,cc,real,perm in directed(t):
    target=cc[real if pmode=='R' else perm];targetmass[addr(target)]+=row['source_block_weight']/4
    if objective=='three_way_CE':soft_negative.update(edge(addr(a),addr(c)) for c in cc if c!=target)
   sourcemass[row['source']]+=row['source_block_weight']
   endpointcounts.update(addr(c) for c in t['cones'])
  literal=positive&negative;transitive=[e for e in negative if find(e[0])==find(e[1])];own_soft=positive&soft_negative
  assert not literal and not transitive and not own_soft,(arm,literal,transitive,own_soft)
  conflict.append(dict(arm=arm,positive_common_negative_overlap=0,positive_association_non_target_overlap=0,negative_within_positive_component=0,global_check=True,physical_row_addresses=True))
  budgets.append(dict(arm=arm,objective=objective,planned_steps=50,full_graph_forwards=50,source_count=len(sourcecounts),triple_slots=len(schedule),positive_pair_slots=2*len(schedule),anchor_query_slots=4*len(schedule),candidate_distance_slots=12*len(schedule),common_negative_terms=6*len(schedule),readout_endpoint_slots=6*len(schedule),unique_training_triples=len(tc),max_triple_or_function_exposure=max(tc.values()),max_node_cone_pooling_exposure=max(nc.values()),source_total_weight=dict(sourcemass)))
 # Target endpoint weighted mass must match R/P exactly within each step.
 fair=[]
 for step in range(1,51):
  rr=[r for r in schedule if r['update']==step];mr=collections.Counter();mp=collections.Counter();anchors=collections.Counter()
  for row in rr:
   t=byid[row['triple_id']]
   for a,cc,ir,ip in directed(t):
    mr[addr(cc[ir])]+=row['source_block_weight']/4;mp[addr(cc[ip])]+=row['source_block_weight']/4;anchors[addr(a)]+=row['source_block_weight']/4
  assert mr==mp==anchors
  fair.append(dict(step=step,active_sources=len(rr),anchor_queries=4*len(rr),candidate_distances=12*len(rr),R_P_target_mass_equal=True,all_five_groups_same_readout=True))
 table('budget_per_arm.csv',budgets);table('global_conflicts.csv',conflict);table('fairness_per_step.csv',fair)
 # Scalar, synthetic objective fixtures (no model or learned representation).
 tau=1.;margin=.2
 def ce(d,target):
  s=-np.array(d)/tau;s-=s.max();p=np.exp(s)/np.exp(s).sum();return float(-np.log(p[target])),p
 d=[0.,2.,100.];r,pr=ce(d,0);p,pp=ce(d,1)
 assert max(0,margin+d[0]-d[2])==max(0,margin+d[1]-d[2])==0
 assert p>r and abs((p-r)-2)<1e-12
 gr=(pr-np.eye(3)[0])/-tau;gp=(pp-np.eye(3)[1])/-tau
 assert np.allclose(gr-gp,[1,-1,0])
 # Both R and P admit embeddings satisfying identical shared negatives.
 def fixture(swapped):
  vals=np.array([-1.,1.,4.,1. if swapped else -1.,-1. if swapped else 1.,4.])
  # convert [A_L,B_L,C_L,A_R,B_R,C_R] to t.cones order
  z=vals[[0,3,1,4,2,5]];t={'cones':list(range(6))};rs=[];ps=[]
  for a,cc,ir,ip in directed(t):
   ds=[abs(z[a]-z[c]) for c in cc];rs.append(ce(ds,ir)[0]);ps.append(ce(ds,ip)[0])
  common=associations(t,'R')[1];loss=sum(max(0,1-abs(z[a]-z[b]))**2 for a,b in common)/6
  return dict(real=float(np.mean(rs)),permuted=float(np.mean(ps)),common_negative=loss)
 fr,fp=fixture(False),fixture(True);assert fr['real']<fr['permuted'] and fp['permuted']<fp['real'] and fr['common_negative']==fp['common_negative']==0
 # Detect the prohibited design explicitly: AB cross edges cannot be common negatives.
 toy={'cones':['al','ar','bl','br','cl','cr']};ppos,_=associations(toy,'P');bad={edge('al','br'),edge('bl','ar')};assert {edge(a,b) for a,b in ppos}&bad
 write('OBJECTIVE_FIXTURES.json',dict(passed=True,far_third_triplet_cannot_distinguish_true_and_swapped=True,three_way_CE_true=r,three_way_CE_permuted=p,distance_gradient_difference=(gr-gp).tolist(),truth_aligned_fixture=fr,permutation_aligned_fixture=fp,both_controls_can_satisfy_identical_common_negatives=True,bad_common_AB_negative_detected=True,model_forwards=0,backwards=0,SAT=0))
 # Index construction is independent from labels and scores; report provenance only.
 usage=[]
 for source in sorted(sourcecounts):
  rr=[r for r in schedule if r['source']==source];ts={r['triple_id']:byid[r['triple_id']] for r in rr};sn=collections.Counter()
  for row in rr:
   for c in byid[row['triple_id']]['cones']:sn.update((cones[c]['view'],r) for r in cones[c]['graph_rows'])
  usage.append(dict(source=source,slots=len(rr),unique_triples=len(ts),unique_positive_pairs=2*len(ts),third_pairs=len(ts),existing_literal_triangles=sum(t['origin']=='existing_three_edge_certificate_triangle' for t in ts.values()),shallow_small_unique_triples=sum(t['shallow_small'] for t in ts.values()),max_node_pooling=max(sn.values()),max_triple_exposure=max(collections.Counter(r['triple_id'] for r in rr).values()),historical_label_assisted_pairs=sum(any('label_assisted' in s for s in pairs[t[k]].get('origins',[])) for t in ts.values() for k in ['pair_A','pair_B','pair_C'])))
 table('training_usage.csv',usage)
 es=[]
 for source in sorted({t['source'] for t in evaluation}):
  for shallow in [True,False]:
   tt2=[t for t in evaluation if t['source']==source and t['shallow_small']==shallow]
   es.append(dict(source=source,shallow_small=shallow,triples=len(tt2),mux=sum(t['has_mux'] for t in tt2),primary_source=sum(t['source']==source for t in evaluation)>=8))
 table('evaluation_support.csv',es)
 assert set(t['source'] for t in evaluation).isdisjoint(sourcecounts)
 for p,h in prep['protected_files'].items():assert sha(R/p)==h,p
 contract=dict(status='OFFLINE_CONTRACT_VERIFIED_NOT_TRAINED',training_authorized=False,arms=list(arms),seed=42,planned_updates_per_arm=50,detector_finetune=0,SAT=0,inputs='same39v3 graph/labels/supervision untouched;correct shared boundary+MUX roles',initialization='same original init_s42,semantic adapters zero,projection seed819;do not initialize from different R/P checkpoints',architecture='fixed dual2+2+post1 hidden64;root64+mean64,projection128->64->32',optimizer_plan='Adam lr0.0002 wd0.001 clip1;all arms same dropout.2/BN training/BF16',distance='sqrt(mean((z_anchor-z_candidate)^2)+1e-12)',relative_loss='mean4 CE(logits=-distance/1.0, target=real for S_R or swapped for S_P);all three opposite-view candidates compete',absolute_loss='mean4 MSE selected real for A_R or swapped for A_P',common_negative='mean6 relu(1-RMS)^2;AB same-view two edges + AC/BC cross-view four edges;never AB cross-view',variance='0.1*mean relu(0.5-sqrt(var_dim(z,unbiased=False)+1e-4)),same six endpoints per triple',total='source-balanced association+source-balanced common-negative+variance;Z association0',compute_fairness='compute both real/permuted MSE and CE in every group;inactive terms multiplied by0 in same autograd graph;one fullgraph forward/update',loss_scale_caveat='CE versus MSE inherently changes gradient scale;not claimed pure normalized-gradient comparison',permutation_negative_semantics='S_P association non-target true-equivalent A is intentional wrong-supervision control,not a certified-different claim;only third C and AB within-view are shared certified negatives',source_count=len(sourcecounts),sources=list(sourcecounts),reference_budget='400positive pair slots,286 unique positive pairs,not historical500/382;historical checkpoints cannot substitute matched A controls',evaluation='root64 primary:source-macro same-anchor real-v-swapped win and cross AUC;main two val sources>=8triples;shallow/deep,MUX,recipes separately;third-only success insufficient;one-triple source descriptive only',acceptance='exploratory: S_R must improve real-v-swapped macro win over S_P and Z by>=0.02,with nonnegative change on both main sources;AUC agrees,noncollapse and no pin semantic loss;compare(S_R-S_P)-(A_R-A_P);no significance or detectionAP claim',next_step_gate='loader/gradient-only preflight of this frozen contract before any training;start training only after explicit subsequent request',protected_files=prep['protected_files'])
 write('RELATIVE_OBJECTIVE_CONTRACT.json',contract)
 write('VERIFIED.json',dict(passed=True,model_forwards=0,backwards=0,optimizer_steps=0,SAT=0,test_reads=0,budget_groups=5,global_literal_and_transitive_conflicts=0,within_step_target_mass_identical=True,synthetic_objective_checks=True,function_role_rotation_disabled=True,old_files_unchanged=True,indices_sha={n:sha(O/n) for n in ['triple_pool.json','schedule_seed42.json','evaluation_panel.json','RELATIVE_OBJECTIVE_CONTRACT.json','budget_per_arm.csv','training_usage.csv','OBJECTIVE_FIXTURES.json']}))
 print(json.dumps(dict(verified=True,sources=len(sourcecounts),unique_training_triples=len(tc),max_triple_exposure=max(tc.values()),max_node_pooling=max(nc.values()),evaluation=es,synthetic_fixtures=[fr,fp]),ensure_ascii=False),flush=True)
if __name__=='__main__':main()
