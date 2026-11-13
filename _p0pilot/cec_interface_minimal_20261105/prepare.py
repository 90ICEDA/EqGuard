"""Prepare semantic interfaces and counterexample checks; no torch/SAT/model execution."""
from pathlib import Path
import collections,csv,gzip,hashlib,json,itertools,math
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;J=R/'_p0pilot/cec_joint_expand_20261105';F=R/'_p0pilot/cec_fair_audit_20261105'
SCHEMA={'AND2X2':('Q','AND',['IN1','IN2']),'OR2X1':('Q','OR',['IN1','IN2']),'XOR2X1':('Q','XOR',['IN1','IN2']),'INVX0':('QN','NOT',['IN']),'MX2X1_RS':('Y','MUX',['A','B','S0']),'$and':('Y','AND',['A','B']),'$or':('Y','OR',['A','B']),'$xor':('Y','XOR',['A','B']),'$not':('Y','NOT',['A']),'$mux':('Y','MUX',['A','B','S'])}
inputs={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):inputs[str(Path(p).relative_to(R))]=sha(p);return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(name,x): (O/name).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def table(name,rows):
 with (O/name).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def compact(x):return json.dumps(x,ensure_ascii=True,separators=(',',':'))
def code(kind,slot):
 h=hashlib.sha256(compact(['boundary_vector_v1',kind,slot]).encode()).digest();v=np.frombuffer(h,dtype='<u2').astype(float)-32767.5;return v/np.linalg.norm(v)

def export():
 pairs=read(J/'final_pairs.json');cones={c['cone_id']:c for c in read(J/'final_cones.json')};assignment={};contexts=collections.defaultdict(set)
 for p in pairs:
  key=compact([p['source_object'],p['context_id']])
  for k in ['left_cone','right_cone']:
   cid=p[k];assert cid not in assignment or assignment[cid]==key;assignment[cid]=key;contexts[key].add(cones[cid]['raw_path'])
 raws={};layouts={};lookups={}
 for path in sorted({c['raw_path'] for c in cones.values()}):
  data=read(R/path);m=next(iter(data['modules'].values()));raws[path]=m;leaf={};tokens=set()
  for name,p in m['ports'].items():
   if p['direction']=='input':
    for j,b in enumerate(p['bits']):leaf[b]=('PI',name,j,0);tokens.add(('PI',name,j))
  for name,g in m['cells'].items():
   if 'DFF' in g['type'].upper():
    for pin in ['Q','QN']:
     for j,b in enumerate(g['connections'].get(pin,[])):leaf[b]=('Q',name,j,int(pin=='QN'));tokens.add(('Q',name,j))
  layouts[path]=tokens;lookups[path]=leaf
 maps={};auditmaps=[]
 for key,paths in sorted(contexts.items()):
  assert len({tuple(sorted(layouts[p])) for p in paths})==1,'Context PI/physicalQ layout mismatch'
  tokens=sorted(layouts[next(iter(paths))]);maps[key]={t:i for i,t in enumerate(tokens)}
  vectors=np.stack([code(t[0],i) for i,t in enumerate(tokens)]);assert len(np.unique(vectors,axis=0))==len(tokens)
  auditmaps.append(dict(context_key=key,views=len(paths),tokens=[dict(slot=i,kind=t[0],audit_name=t[1],bit=t[2]) for i,t in enumerate(tokens)],training_feature_excludes=['audit_name','context_key','source_object','pair_id','labels','proof_result','witness_outputs']))
 write('boundary_maps_audit_only.json',auditmaps)
 stats=[];edgecount=0
 with gzip.open(O/'cone_pin_incidence.jsonl.gz','wt',encoding='utf-8') as out:
  for cid,c in sorted(cones.items()):
   path=c['raw_path'];assert inputs[path]==c['raw_sha'];m=raws[path];leaf=lookups[path];key=assignment[cid];slots=maps[key];names=list(c['members']);index={n:i for i,n in enumerate(names)};drivers={};ops=[]
   for n in names:
    g=m['cells'][n];pin,op,ins=SCHEMA[g['type']];ops.append(op)
    for b in g['connections'][pin]:drivers[b]=index[n]
   edges=[];seen_leaves=set()
   for n in names:
    g=m['cells'][n];pin,op,ins=SCHEMA[g['type']]
    for port,b in [(p,b) for p in ins for b in g['connections'][p]]:
     role=0 if op in ['AND','OR','XOR'] else 1 if op=='NOT' else [2,3,4][ins.index(port)]
     if b in drivers:kind,src,phase=0,drivers[b],0
     elif b in leaf:
      t=leaf[b];kind,src,phase=1,slots[t[:3]],t[3];seen_leaves.add(t)
     elif b in ['0','1']:kind,src,phase=2,int(b),0
     else:raise AssertionError((cid,'nonclosed boundary',b))
     edges.append([kind,src,phase,index[n],role])
   assert seen_leaves=={tuple(t) for t in c['leaves']},'Exported boundary differs from existing proof'
   # No raw bit IDs, source names, labels or function outputs in numeric incidence payload.
   payload=dict(cone_id=cid,context_lookup=key,root=index[c['output_cell']],graph_rows=c['graph_rows'],op=ops,edge=edges)
   out.write(compact(payload)+'\n');edgecount+=len(edges)
   stats.append(dict(cone_id=cid,split=c['split'],nodes=len(names),incidences=len(edges),boundary_inputs=len(seen_leaves),has_mux='MUX' in ops,closed=True))
 table('interface_coverage.csv',stats)
 write('SCHEMA.json',dict(version='pin_boundary_incidence_v1',scope='existing proved cones only;combinational free physicalQ context,not sequential behavior',edge_columns=['src_kind','src_index','physicalQ_complement','dst_gate_index','dst_role'],src_kind={'0':'internal gate local index','1':'boundary slot in context','2':'constant value0/1'},dst_role={'0':'commutative input (multiplicity retained)','1':'NOT input','2':'MUX data0','3':'MUX data1','4':'MUX select'},source_polarity='Q/QN share physicalQ slot;QN phase1;INV output called QN is NOT gate output and gets no extra phase',duplicate_edges='one incidence per connected input pin,do not merge',constants='literal0/1 distinct,no learned variable ID',variable_alignment='one map per source/context covering all views and all four endpoints;never build separate rank maps for each cone/pair',metadata_not_features=['cone_id','context_lookup','graph_rows'],failure_policy='unsupported cell/output,missing map,context mismatch or open boundary abort;do not mark covered',P0='roles collapsed to DATA within each gate,op retained',P1='semantic destination roles above',B0='boundary kind+phase only;no variable identity',B1='shared neutral slot/code within context;no raw signal names or host as features'))
 write('EXPORT_COMPLETE.json',dict(cones=len(stats),pairs=len(pairs),contexts=len(contexts),views=len(raws),incidences=edgecount,all_context_layouts_match=True,all_proof_leaves_match=True,training_updates=0,model_forward=0,SAT=0))
 return pairs,cones,maps

# Structural signatures are information-retention checks, NOT Boolean equivalence proofs.
def canonical(g,pin,identity,rename=None):
 def neg(x):return x[1] if x[0]=='NOT' else ('NOT',x)
 def ev(n):
  op,aa=g['nodes'][n]
  if op=='LEAF':
   kind,slot,phase=aa;slot=rename.get(slot,slot) if rename else slot;x=('BOUNDARY',kind,slot if identity else '*');return neg(x) if phase else x
  vv=[ev(a) for a in aa]
  if op=='BUF':return vv[0]
  if op=='NOT':return neg(vv[0])
  if op in ['AND','OR','XOR'] or not pin:return (op,tuple(sorted(vv,key=repr)))
  return (op,tuple(zip(['DATA0','DATA1','SELECT'],vv)))
 return ev(g['root'])
def evaluate(g,env):
 def ev(n):
  op,aa=g['nodes'][n]
  if op=='LEAF':kind,slot,phase=aa;return env[slot]^phase
  vv=[ev(a) for a in aa]
  if op=='BUF':return vv[0]
  if op=='NOT':return 1-vv[0]
  if op=='MUX':return vv[1] if vv[2] else vv[0]
  if op=='AND':return vv[0]&vv[1]
  if op=='OR':return vv[0]|vv[1]
  return vv[0]^vv[1]
 return ev(g['root'])
def fixture_checks():
 old=read(F/'INPUT_INFORMATION_AUDIT.json');base={'a':('LEAF',('PI',0,0)),'b':('LEAF',('PI',1,0)),'s':('LEAF',('PI',2,0)),'ua':('BUF',['a']),'ub':('BUF',['b']),'us':('BUF',['s'])}
 mux1=dict(nodes=dict(base,m=('MUX',['ua','ub','us'])),root='m');mux2=dict(nodes=dict(base,m=('MUX',['us','ub','ua'])),root='m')
 not1=dict(nodes=dict(base,m=('NOT',['a'])),root='m');not2=dict(nodes=dict(base,m=('NOT',['b'])),root='m')
 cases=[('mux_select_data_pin_swap',mux1,mux2,2),('boundary_PI_identity_swap',not1,not2,4)];rows=[]
 for name,a,b,n in cases:
  assert any(f['case']==name and f['different_patterns']==n for f in old['fixtures'])
  files=[F/f'fixtures/{name}_{s}.v' for s in ['left','right']]
  for f in files:inputs[str(f.relative_to(R))]=sha(f)
  truth=sum(evaluate(a,env)!=evaluate(b,env) for vals in itertools.product([0,1],repeat=3) for env in [dict(enumerate(vals))]);assert truth==n
  for p in [0,1]:
   for aligned in [0,1]:
    separate=canonical(a,p,aligned)!=canonical(b,p,aligned);expected=bool(aligned and (p or 'identity' in name));assert separate==expected
    rows.append(dict(case=name,P=p,B=aligned,distinct_structural_signature=separate,truth_different=truth,total_patterns=8))
 # Legal input-port permutations on commutative gates must not create a semantic distinction.
 ca=dict(nodes=dict(base,m=('AND',['a','b'])),root='m');cb=dict(nodes=dict(base,m=('AND',['b','a'])),root='m');assert canonical(ca,1,1)==canonical(cb,1,1)
 # Jointly rename physical inputs AND transport the mapping: same graph semantics after alignment.
 renamed=dict(nodes={'x':('LEAF',('PI',9,0)),'m':('NOT',['x'])},root='m');assert canonical(not1,1,1)==canonical(renamed,1,1,{9:0})
 qn=dict(nodes={'q':('LEAF',('Q',0,1))},root='q');nq=dict(nodes={'q':('LEAF',('Q',0,0)),'m':('NOT',['q'])},root='m');assert canonical(qn,1,1)==canonical(nq,1,1)
 assert canonical(qn,1,1)!=canonical(dict(nodes={'q':('LEAF',('Q',0,0))},root='q'),1,1)
 # B-only 20d adapter input prototype for direct boundary incidences:counts PI,Q,C0,C1 +16 code sum.
 def adapter_input(slot,identity):
  x=np.zeros(20);x[0]=math.log1p(1);x[4:]=code('PI',slot if identity else 'TYPE');return x
 assert np.array_equal(adapter_input(0,False),adapter_input(1,False));assert not np.array_equal(adapter_input(0,True),adapter_input(1,True))
 table('fixture_matrix.csv',rows);write('FIXTURE_CHECKS.json',dict(rows=rows,checks=dict(original_fixture_truth_counts_pass=True,commutative_pin_swap_invariant=True,joint_renaming_with_transported_map_invariant=True,Q_vs_QN_distinct=True,QN_equals_NOT_Q=True,boundary_only_adapter_separates_NOT_a_NOT_b=True),interpretation='Distinct structural signature means input information retained;not a trained model score,not proof of equivalence across different gate decompositions;P1B1 passes both old counterexamples,P1-only fails unaligned variables,B1-only fails MUX pin swap'))

def contract():
 original=R/'_p0pilot/cec_pretrain_ready_20261105';schedule=read(original/'schedule.json');rr=[r for r in schedule if r['mode']=='main' and r['seed']==42];assert len(rr)==250
 plan=dict(status='DESIGNED_NOT_EXECUTED;NO_TRAINING_QUEUE',question='At fixed P0,does shared boundary variable identity improve root64 function discrimination beyond boundary type/polarity alone?',factor='B0 collapsed boundary kind codes vs B1 context-aligned variable codes ONLY',why_B_first='Existing NOT(a)/NOT(b) counterexample tests B alone;original symmetric MUX example needs both P and B and cannot isolate pin role alone',conditions=['B0Z','B0R','B0P','B1Z','B1R','B1P'],seed=42,new_seeds=0,new_SAT=0,pretrain_updates_per_condition=50,total_planned_pretrain_updates=300,finetune_updates=0,features='original39v3/graph/normalization unchanged;common boundary20->39 linear residual adapter preceding existing encoder input;all six have same adapter parameters',adapter=dict(input20='log1p direct boundary pin counts PI,Q,C0,C1 +16 signed unit-code sum/sqrt(max(1,n_boundary_pins))',B0='PI/Q use one type code each,constants fixed',B1='per-variable code shared across all views in source/context;phase sign and constant handling same as B0',parameter_initialization='20->39 linear,no bias,weights all zero;original model46620 init_s42 identical;common new780 parameters;projection same initial state',limitation='sum is compressed and not generally lossless;semantic incidence stays authoritative;collisions beyond fixtures not ruled out'),input_codes=dict(no_raw_names_or_host_features=True,no_labels_or_truth_outputs=True,map_scope='entire source/context before any R/P permutation;not pair-specific',training_remap='deterministic shared slot permutation from seed42/update/context-local token count;same permutation for all four endpoints,allarms;mapping indices only,context name not vector hash',evaluation='fixed eval mapping plus predetermined second joint slot permutation as robustness diagnostic;neither selected by results'),fixed=dict(model='original improved dual 2+2+post1 hidden64,split29/10',pooling='same root64+mean64 ->128/64/32',P='P0:no consumer pin role added to message passing or adapter;all input-pin contributions unordered',loss='original MSE+certified-different hinge+.1variance;Z keeps common different term',dropout=.2,BatchNorm='original train behavior',optimizer='original Adam lr.0002 weight_decay.001 clip1',sampling='exact frozen main seed42 382 unique pairs/500slots,10sources50slots each',selection='fixed final pretrain50,no AP/checkpoint selection',no_changes=['labels','graph edges','pair pool','loss weights','region weights','pin-aware message passing','fine-tuning retention']),bindings={n:sha(original/n) for n in ['engine.py','schedule.json','function_inventory.json','negative_certificates.json','RUN_CONTRACT.json']},initial_sha=sha(R/'_p0pilot/control_v3_eligible_20261104/init_s42.pt'),evaluation=dict(primary='root64 same-anchor real-vs-certified-wrong cross-implementation comparisons;per-source/recipe/size;macro and pooled AUC',secondary=['concat128','projection32 fixed head','same-view different-function discrimination','variance/effective rank','joint-variable-remapping robustness'],contrast='D_R=metric(B1R)-metric(B0R),similarlyD_P,D_Z;report D_R-D_P and D_R-D_Z;do not call general input benefit equivalence-supervision benefit',success='B1 must retain NOT fixture;check finite gradients and unchanged first zero-adapter output during future preflight;seek nontrivial root64 gain beyondP/Z and no obvious source-level reversal;single seed not statistical significance',limits=['5 val sources/1host,2/1/1 small blocks','same endpoints but no exact joint gate/size matching','not evaluated detector gain;no test use']),next_stage='Only if functional signal survives at root64 discuss separate detection transfer contract;adapter transport must be specified,never silently discarded while claiming gain')
 # Shared-vs-shuffled identity is a cleaner causal contrast than type-only-vs-unique:
 # both conditions retain variable distinctness and the same code vocabulary per view.
 plan.update(question='At fixed P0,does correct cross-view boundary-variable alignment improve root64 function discrimination over deliberately misaligned but equally distinct variable codes?',factor='B_shared vs B_viewshuffle:ONLY cross-view correspondence of within-kind boundary codes changes',conditions=[f'{b}{a}' for b in ['B_shared','B_viewshuffle'] for a in ['Z','R','P']],why_B_first='NOT(a)/NOT(b) proves variable identity is needed;shared-vs-viewshuffle isolates alignment without mixing identity granularity and code distribution;pin roles stayP0')
 plan['adapter'].update(B0='Not a training condition;type-only B0 is an offline information-loss check',B1='Both training conditions use distinct variable codes;shared applies same map to all views,viewshuffle applies a per-view within-kind derangement,with one anchor view unchanged')
 plan['input_codes'].update(training_remap='Seed42/update shared within-kind slot permutation;B_viewshuffle additionally applies fixed view-rank cyclic derangement within PI/Q separately,whole context and all arms,never per-pair;singletons explicitly unchanged',evaluation='Fixed eval code map plus predetermined second joint slot permutation;each condition applies its own shared/viewshuffle rule;no selection',matched='same dimensions,variable counts,code vocabulary and unit norm per variable,type/polarity/constants and within-view alias reuse;not claiming exact per-cell vector covariance equality')
 plan['evaluation']['contrast']='D_R=metric(B_sharedR)-metric(B_viewshuffleR),similarlyD_P,D_Z;report D_R-D_P and D_R-D_Z;do not call general input benefit equivalence-supervision benefit'
 plan['evaluation']['success']='Both conditions retain within-view NOT(a)/NOT(b) distinction;shared transports the same variable across implementations,viewshuffle deliberately breaks alignment without collapsing identities;future preflight must verify finite gradients and zero-adapter initial-output identity;seek root64 improvement beyond P/Z;single seed not significance'
 plan['fixed']['no_changes'].append('no detection finetuning this stage')
 plan['implementation_prerequisites']=['Current files are schema/prototype only,not training runner','Build direct boundary consumer rows for all32 covered views against frozen graph names;fail on missing mappings;DFF cells get zero adapter input because their Q is free boundary,not a temporal equation','Common adapter and code-generation hooks must be identical across6 conditions;old checkpoints are context only,not a replacement for new shared-interface controls','Verify common initial encoder/head and zero-adapter outputs before optimization','No true/differ certificates,labels,truth table,proof status or test information in input vectors','Compressed20d summaries are not a lossless serialization of the full pin-boundary incidence']
 write('NEXT_SINGLE_FACTOR_CONTRACT.json',plan)

def main():
 O.mkdir(exist_ok=True);assert not (O/'COMPLETE.json').exists(),'Reuse prepared interface outputs'
 pairs,cones,maps=export();fixture_checks();contract();assert all(sha(R/p)==h for p,h in inputs.items())
 write('COMPLETE.json',dict(training_updates=0,model_forwards=0,optimizer_steps=0,SAT=0,Yosys=0,proofs_reused_only=True,old_inputs_unchanged=True,input_sha256=inputs,scope='interface export+structural counterexamples+designed contract;no model implementation or queue'))
 print('INTERFACE_PREPARED',flush=True)
if __name__=='__main__':main()
