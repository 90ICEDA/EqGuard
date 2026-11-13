"""Repair known candidate/control defects using alreadyexported evidence only."""
from pathlib import Path
import collections,csv,gzip,hashlib,itertools,json,shutil
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;P=R/'_p0pilot/cec_boundary_panel_expand_20261107';A=R/'_p0pilot/cec_freeq_encoding_audit_20261107';OLD=R/'_p0pilot/cec_freeq_zrp_seed42_20261107';PRE=R/'_p0pilot/cec_freeq_preflight_20261106'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def ident(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def write(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
 assert not (O/'VERIFIED.json').exists();assert read(A/'VERIFIED.json')['passed'];protected=dict(read(A/'FROZEN_EXECUTION.json')['protected_files'])
 for n,h in read(A/'OUTPUT_MANIFEST.json').items():assert sha(A/n)==h;protected[str((A/n).relative_to(R))]=h
 for p in [P/'MAIN_ALL_ENDPOINTS_SAME_BOUNDARY.json',P/'DIFFERENT_FUNCTION_CERTIFICATES.json',P/'local_graphs.json.gz',PRE/'INITIAL_STATE.pt',Path(__file__)]:protected[str(p.relative_to(R))]=sha(p)
 for p,h in protected.items():assert sha(R/p)==h,p
 with gzip.open(P/'local_graphs.json.gz','rt',encoding='utf-8') as f:z=json.load(f)
 gg=dict(zip(z['cone_ids'],z['graphs']));ctx=dict(zip(z['cone_ids'],z['contexts']));classes={};intern={}
 for cid,g in gg.items():
  inc=collections.defaultdict(list)
  for s,d,role,phase in g['edge']:inc[d].append((s,role,phase))
  state=[]
  for j,op in enumerate(g['op']):
   k=('leaf',op,ctx[cid],g['slot'][j]) if op<2 else ('constant',op) if op<4 else ('op',op,tuple(sorted((r,p,state[s]) for s,r,p in inc[j])))
   if k not in intern:intern[k]=len(intern)
   state.append(intern[k])
  classes[cid]=state[g['root']]
 main=read(P/'MAIN_ALL_ENDPOINTS_SAME_BOUNDARY.json');eligible=[];excluded=[]
 for u in main:
  ix=[j for j in range(u['functions']) if classes[u['cones'][2*j]]!=classes[u['cones'][2*j+1]]]
  if len(ix)<2:excluded.append(dict(unit_id=u['unit_id'],split=u['split'],reason='fewer_than_two_nonforced_function_pairs',remaining=len(ix)));continue
  v=dict(u);v.update(unit_id=ident(['repaired_control_v1',u['unit_id'],ix]),parent_unit=u['unit_id'],functions=len(ix),pair_ids=[u['pair_ids'][j] for j in ix],cones=[c for j in ix for c in u['cones'][2*j:2*j+2]],function_signatures=[u['function_signatures'][j] for j in ix],known_encoder_forced_ties=0)
  assert v['left_right_same_boundary'];eligible.append(v)
 write('ELIGIBLE_ALL.json',eligible);write('EXCLUDED.json',excluded)
 train=[u for u in eligible if u['split']=='train' and u['functions']==3];pairdiag=[u for u in eligible if u['split']=='train' and u['functions']==2];validation=[u for u in eligible if u['split']=='val' and u['tier']=='H3'];write('TRAIN_TRIPLES.json',train);write('TRAIN_PAIRS_DIAGNOSTIC.json',pairdiag);write('VAL_H3_NONFORCED.json',validation)
 # Every new negative relation is a subset of an ALREADY verified unit's certificate.
 certificates=read(P/'DIFFERENT_FUNCTION_CERTIFICATES.json');byedge={tuple(sorted(c['pair_ids'])):c for c in certificates};reused=[]
 for u in eligible:
  for a,b in itertools.combinations(u['pair_ids'],2):
   c=byedge[tuple(sorted([a,b]))];assert c['outputs'][0]==c['outputs'][1] and c['outputs'][2]==c['outputs'][3] and c['outputs'][0]!=c['outputs'][2];reused.append(dict(unit_id=u['unit_id'],certificate_id=c['certificate_id'],pair_ids=c['pair_ids']))
 write('REUSED_CERTIFICATES.json',reused)
 families=collections.defaultdict(list)
 for u in train:families[u['context_id']].append(u)
 assert families and all(len(us)>=2 for us in families.values());schedule=[];exposure=collections.Counter();function_exposure=collections.Counter();negative=set();pos={a:set() for a in ['R','P']}
 for step in range(1,33):
  records=[]
  for key,uu in sorted(families.items()):
   uu=sorted(uu,key=lambda u:ident(['schedule',u['unit_id']]));u=uu[(step-1)%len(uu)];exposure[u['unit_id']]+=1;function_exposure.update((key,s) for s in u['function_signatures']);shift=1+int(ident(['Pshift',u['unit_id']]),16)%2;anchors=[];candidates=[];real=[];wrong=[]
   for f in range(3):
    for side in [0,1]:anchors.append(u['cones'][2*f+side]);candidates.append([u['cones'][2*j+1-side] for j in range(3)]);real.append(f);wrong.append((f+shift if side==0 else f-shift)%3)
   ne=[(u['cones'][2*a+s],u['cones'][2*b+s]) for s in [0,1] for a,b in itertools.combinations(range(3),2)]
   for a,cc,t,w in zip(anchors,candidates,real,wrong):
    assert classes[a]!=classes[cc[t]] and classes[a]!=classes[cc[w]];pos['R'].add(tuple(sorted([a,cc[t]])));pos['P'].add(tuple(sorted([a,cc[w]])))
   negative.update(tuple(sorted(e)) for e in ne);records.append(dict(unit_id=u['unit_id'],source=u['source'],context_id=key,cone_ids=u['cones'],anchors=anchors,candidates=candidates,real_targets=real,permuted_targets=wrong,negative_edges=ne,query_weight=1/(6*len(families)),negative_weight=1/(6*len(families)),boundary_tag=step))
  schedule.append(dict(update=step,units=records))
 for arm,edges in pos.items():
  parent={}
  def find(x):
   parent.setdefault(x,x)
   if parent[x]!=x:parent[x]=find(parent[x])
   return parent[x]
  for a,b in edges:parent[find(classes[a])]=find(classes[b])
  assert not any(find(classes[a])==find(classes[b]) for a,b in negative)
 assert max(function_exposure.values())<=16;write('SCHEDULE_SEED42.json',schedule)
 budget=dict(updates_each=32,families=len(families),unique_triples=len(train),unique_context_functions=3*len(train),unit_slots=32*len(families),queries=32*len(families)*6,candidate_distances=32*len(families)*18,common_negatives=32*len(families)*6,max_function_exposure=max(function_exposure.values()),scope='NEW support andbudget,not old3family/576query budget;identical within all3groups')
 write('BUDGET.json',budget)
 counts={}
 for split in ['train','val']:
  ss=[u for u in eligible if u['split']==split];counts[split]=dict(units=len(ss),triples=sum(u['functions']==3 for u in ss),pairs=sum(u['functions']==2 for u in ss),H3=sum(u['tier']=='H3' for u in ss),sources=len({u['source'] for u in ss}),families=len({u['context_id'] for u in ss}),MUX=sum(u['has_mux'] for u in ss))
 contract=dict(status='prepared_only_not_training_authorized',eligibility='same actualboundary for ALL endpoints;differentfunction certificates reused;everytruepair nonidentical under current rootencoder computation;encoderaugmented positive/negative graph conflictfree',training_pool='TRAIN_TRIPLES.json only;pair-only candidates diagnostic,no fake3rdcandidate',validation='VAL_H3_NONFORCED.json primary diagnostically;old85H3 andoldPO retained separately,not overwritten',groups='Z/R/P same repaired pool,sharedoldINIT47360,parametrization/objective/Adam/FP32 unchanged',budget=budget,selection='fixedlast32,seed42;no execution this round',encoding='unchanged oldshared recoding tag=update;9000 main9001 predefined sensitivity;9002-5 posthoc diagnostics',single_factor_scope='new protocol conditional on common supported families;DO NOT compare to old3family run as a onefactor effect;to compare trainingdifficulty,build original/repaired pools on SAME supported families first',code_stability='leave for next SINGLE factor;do not add consistency loss while changing eligibility. Futuresharedremapping shouldregularize relational scores/ranks,not force pointwiseembeddings invariant',limits='passing necessary feasibility checks is NOT proof that P canbe fitted;actual loader and no-update gradient preflight pending;few independent contexts',training_authorized=False,training=0,SAT=0,model_forwards=0)
 write('REPAIRED_CONTRACT.json',contract)
 for p,h in protected.items():assert sha(R/p)==h,p
 write('VERIFIED.json',dict(passed=True,counts=counts,budget=budget,reused_witness_records=len(reused),known_forced_truepairs_removed=True,implicit_encoder_conflicts_R=0,implicit_encoder_conflicts_P=0,all_shared_boundary_inputset_distance_ties=True,actual_model_loading_pending=True,sufficient_fitting_feasibility_not_proven=True,training=0,SAT=0,model_forwards=0,old_assets_unchanged=True,protected_files=protected))
 print(json.dumps(dict(counts=counts,budget=budget),ensure_ascii=False),flush=True)
if __name__=='__main__':main()
