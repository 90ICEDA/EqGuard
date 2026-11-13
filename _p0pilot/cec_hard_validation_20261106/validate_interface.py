"""Frozen-evidence free-PI/Q interface validation. No solver or model training."""
from pathlib import Path
import collections,copy,gzip,hashlib,importlib.util,json,time,traceback
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent
H=R/'_p0pilot/cec_hard_boundary_20261106';J=R/'_p0pilot/cec_joint_expand_20261105';I=R/'_p0pilot/cec_interface_minimal_20261105'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def load(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
L=load('frozen_local_interface',H/'local_interface.py')
A=load('frozen_saved_input_replay',R/'_p0pilot/cec_relative_contract_20261106/prepare.py')
def vocabulary(tokens,tag=9000):
 v={}
 for ki,kind in enumerate(['PI','Q']):
  slots=[t['slot'] for t in tokens if t['kind']==kind]
  rng=np.random.default_rng([420000,int(tag),ki,len(slots)]);perm=rng.permutation(len(slots))
  for j,s in enumerate(slots):v[int(s)]=L.code(kind,slots[int(perm[j])])
 return v
def check_batch(b):
 n=len(b['x']);ptr=b['graph_ptr'];gi=b['graph_index'];s,d=b['edge_index']
 assert b['x'].shape==(n,25) and np.isfinite(b['x']).all()
 assert ptr[0]==0 and ptr[-1]==n and np.all(np.diff(ptr)>0)
 assert np.array_equal(gi,np.repeat(np.arange(len(ptr)-1),np.diff(ptr)))
 assert len(s)==len(d)==len(b['edge_role'])==len(b['edge_phase'])
 assert np.all((s>=0)&(s<n)&(d>=0)&(d<n)) and np.array_equal(gi[s],gi[d])
 assert np.all(s<d) and np.all(b['level'][s]<b['level'][d])
 assert set(b['edge_role'].tolist())<=set(range(5)) and set(b['edge_phase'].tolist())<={0,1}
 op=b['x'][:,:9];assert np.all((op==0)|(op==1)) and np.all(op.sum(1)==1)
 assert np.all((b['root_index']>=ptr[:-1])&(b['root_index']<ptr[1:]))
 incoming=collections.defaultdict(list)
 for k,(ss,dd) in enumerate(zip(s,d)):incoming[int(dd)].append(k)
 for j in range(n):
  name=L.OPS[int(op[j].argmax())];ii=incoming[j];roles=sorted(int(b['edge_role'][k]) for k in ii)
  if name in ['PI','Q','CONST0','CONST1']:assert not ii and b['level'][j]==0
  else:assert roles==([1] if name=='NOT' else [2,3,4] if name=='MUX' else [0,0])
  if name not in ['PI','Q']:assert np.count_nonzero(b['x'][j,9:])==0
 return incoming
def consume_batch(b,keys,tables,envs,mask=(1<<128)-1):
 """Boolean QA only. Decode the actual 25d arrays, roles and phases after load.
 Witness outputs/env bits are audit targets, NEVER added to neural features.
 """
 inc=check_batch(b);values=[];voc={key:vocabulary(tables[key]) for key in set(keys)}
 for j,x in enumerate(b['x']):
  op=L.OPS[int(x[:9].argmax())];key=keys[int(b['graph_index'][j])]
  if op in ['PI','Q']:
   matches=[s for s,v in voc[key].items() if np.array_equal(v,x[9:]) and next(t['kind'] for t in tables[key] if t['slot']==s)==op]
   assert len(matches)==1,'ambiguous feature boundary identity';v=envs[key][matches[0]]
  elif op.startswith('CONST'):v=mask if op=='CONST1' else 0
  else:
   aa=[(int(b['edge_role'][k]),values[int(b['edge_index'][0,k])]^(mask if b['edge_phase'][k] else 0)) for k in inc[j]];vv=[v for _,v in aa]
   if op=='AND':v=vv[0]&vv[1]
   elif op=='OR':v=vv[0]|vv[1]
   elif op=='XOR':v=vv[0]^vv[1]
   elif op=='NOT':v=mask^vv[0]
   else:dd=dict(aa);v=(dd[4]&dd[3])|((mask^dd[4])&dd[2])
  values.append(v)
 return [values[int(j)] for j in b['root_index']]

def fixtures():
 tokens=[dict(kind='PI',audit_name='a',bit=0,slot=0),dict(kind='PI',audit_name='b',bit=0,slot=1),dict(kind='PI',audit_name='s',bit=0,slot=2),dict(kind='Q',audit_name='ff',bit=0,slot=3)]
 def module(op,inputs,out=20):
  pin=L.SCHEMA[op];conn={pin[0]:[out],**{p:[v] for p,v in zip(pin[2],inputs)}}
  return dict(ports={n:dict(direction='input',bits=[b]) for n,b in [('a',2),('b',3),('s',4)]},cells={'ff':dict(type='DFF',connections={'D':[2],'Q':[5],'QN':[6]}),'root':dict(type=op,connections=conn)})
 def graph(m):return L.ModuleIndex(m,tokens).cone(20)
 env={s:sum(((p>>s)&1)<<p for p in range(16)) for s in range(4)};mask=(1<<16)-1;rows=[]
 def outputs(gg):return [L.replay(g,env,mask) for g in gg]
 def record(name,cond):assert cond,name;rows.append(dict(check=name,passed=True))
 # Existing counterexample families, independently exhaustively exercised only on tiny synthetic fixtures.
 m=module('MX2X1_RS',[2,3,4]);g=graph(m)
 swapped=graph(module('MX2X1_RS',[4,3,2]));record('MUX_DATA0_SELECT_swap_distinct',outputs([g])[0]!=outputs([swapped])[0])
 ab=graph(module('MX2X1_RS',[3,2,4]));record('MUX_DATA0_DATA1_swap_distinct',outputs([g])[0]!=outputs([ab])[0])
 ga,gb=map(graph,[module('INVX0',[2]),module('INVX0',[3])]);record('PI_identity_NOT_a_vs_NOT_b',outputs([ga])[0]!=outputs([gb])[0])
 q,qn=map(graph,[module('INVX0',[5]),module('INVX0',[6])]);record('Q_QN_phase_complement',outputs([q])[0]^outputs([qn])[0]==mask)
 mc=module('INVX0',[5]);ma=copy.deepcopy(mc);ma['cells']['ff']['connections']['D']=[3]
 record('Q_upstream_D_change_does_not_enter_cone',graph(mc)==graph(ma));record('no_DFF_operation_in_loaded_cone',all(L.OPS[o]!='DFF' for o in graph(mc)['op']))
 repeated=graph(module('XOR2X1',[2,2]));distinct=graph(module('XOR2X1',[2,3]));record('repeated_pin_multiplicity_XOR',outputs([repeated])[0]==0 and outputs([distinct])[0]!=0 and len(repeated['edge'])==2)
 zero,one=map(graph,[module('AND2X2',[5,'0']),module('OR2X1',[5,'1'])]);record('constant_zero_one_consumed',outputs([zero,one])==[0,mask])
 c1,c2=map(graph,[module('AND2X2',[2,3]),module('AND2X2',[3,2])]);record('commutative_swap_function_invariant',outputs([c1])==outputs([c2]))
 deep=module('INVX0',[5]);deep['cells']['root']['connections']['IN']=[14]
 for j in range(5):deep['cells']['n'+str(j)]=dict(type='INVX0',connections={'IN':[5 if j==0 else 10+j-1],'QN':[10+j]})
 gd=graph(deep);record('all_six_logic_levels_consumed',max(gd['level'])==6 and outputs([gd])==[env[3]])
 gg=[g,swapped,ab,ga,gb,q,qn,repeated,distinct,zero,one,c1,c2,gd];bb=L.collate(gg,['fixture']*len(gg),{'fixture':tokens})
 record('actual_collated_arrays_match_scalar_truth',consume_batch(bb,['fixture']*len(gg),{'fixture':tokens},{'fixture':env},mask)==outputs(gg))
 # Deliberate malformed inputs must fail closed.
 def rejects(name,fn):
  try:fn()
  except (AssertionError,ValueError,KeyError,IndexError):record(name,True)
  else:raise AssertionError('failed to reject '+name)
 rejects('undriven_bit_rejected',lambda:graph(module('INVX0',[999])))
 cyc=module('INVX0',[20]);rejects('comb_cycle_rejected',lambda:graph(cyc))
 rejects('unknown_constant_rejected',lambda:graph(module('INVX0',['x'])))
 for name,field in [('wrong_MUX_role_rejected','edge_role'),('invalid_phase_rejected','edge_phase')]:
  bad={k:v.copy() for k,v in bb.items()};bad[field][0]=99;rejects(name,lambda:check_batch(bad))
 bad={k:v.copy() for k,v in bb.items()};bad['edge_index'][0,0]=bb['graph_ptr'][1];rejects('cross_graph_edge_rejected',lambda:check_batch(bad))
 bad={k:v.copy() for k,v in bb.items()};bad['x'][0,0]=np.nan;rejects('nonfinite_feature_rejected',lambda:check_batch(bad))
 return rows

def main():
 start=time.perf_counter();assert not (O/'INTERFACE_VERIFIED.json').exists()
 protected=dict(read(H/'PANEL_COMPLETE.json')['frozen_files'])
 for p in [H/'PANEL_COMPLETE.json',H/'hard_panel.json',H/'local_interface.py',Path(__file__)]:protected[str(p.relative_to(R))]=sha(p)
 old=R/'_p0pilot/cec_relative_seed42_20261106'
 for p in [old/'INITIAL_STATE.pt',*[old/a/'resume.pt' for a in ['Z','A_R','A_P','S_R','S_P']]]:protected[str(p.relative_to(R))]=sha(p)
 for p,h in protected.items():assert sha(R/p)==h,p
 write('READ_ONLY_CONTRACT.json',dict(purpose='105-unit posthoc difficult-panel diagnostic; no retraining, solver, new real input patterns, or test read',models=['INIT','Z','A_R','A_P','S_R','S_P'],readouts=['root64','mean64','concat128','projection32'],main_comparison='fixed full-graph existing model;pairwise wrong candidates equally within each anchor,unit then source equal;all functions and both directions;triples separate from pair-only',local_interface='25d independent semantic schema not compatible with historical39 input; validate arrays only,do not invent an untrained conversion or claim its model performance',frozen_files=protected))
 units=read(H/'hard_panel.json');assert len(units)==105;cones={c['cone_id']:c for c in read(J/'final_cones.json')};pairs={p['pair_id']:p for p in read(J/'final_pairs.json')}
 ids=sorted({c for u in units for c in u['cones']});assert len(ids)==620
 context_of={}
 with gzip.open(I/'cone_pin_incidence.jsonl.gz','rt',encoding='utf-8') as f:
  for line in f:
   z=json.loads(line)
   if z['cone_id'] in ids:context_of[z['cone_id']]=z['context_lookup']
 tables={m['context_key']:m['tokens'] for m in read(I/'boundary_maps_audit_only.json')}
 contexts=read(R/'_p0pilot/cec_pretrain_ready_20261105/witness_contexts.json');contexts.update(read(R/'_p0pilot/cec_cert_expand_20261105/validation_witness_contexts.json'))
 replay=A.Replay(contexts,protected);indices={};graphs=[];rows=[];envs={};raw_out={}
 for cid in ids:
  c=cones[cid];key=context_of[cid];ctx=json.loads(key)[1];model=replay.model(c)[0]
  if c['view'] not in indices:indices[c['view']]=L.ModuleIndex(model,tables[key])
  g=indices[c['view']].cone(c['root_bit']);L.validate(g)
  assert set(g['comb_names'])==set(c['members']) and g['comb_names'][g['root']-sum(x<4 for x in g['op'])]==c['output_cell']
  physical={tuple(t[:3]) for t in c['leaves']};exported={(t['kind'],t['audit_name'],t['bit']) for t in tables[key] if t['slot'] in set(g['slot'])};assert physical==exported
  for name in g['comb_names']:assert 'DFF' not in model['cells'][name]['type'].upper()
  envs[key]={int(t['slot']):replay.env[ctx][(t['kind'],t['audit_name'],t['bit'])] for t in tables[key]}
  raw=replay.evaluate(c,ctx);got=L.replay(g,envs[key],(1<<128)-1);assert raw==got
  raw_out[cid]=raw;graphs.append(g)
  rows.append(dict(cone_id=cid,split=c['split'],view=c['view'],context=key,comb_nodes=len(g['comb_names']),boundary_nodes=sum(L.OPS[o] in ['PI','Q'] for o in g['op']),q_nodes=sum(L.OPS[o]=='Q' for o in g['op']),phase1_pins=sum(e[3] for e in g['edge']),constant_nodes=sum(L.OPS[o].startswith('CONST') for o in g['op']),pin_edges=len(g['edge']),depth=max(g['level']),matches_raw_saved128=True))
  if len(graphs)%100==0:print('LOADED',len(graphs),flush=True)
 keys=[context_of[c] for c in ids];batch=L.collate(graphs,keys,tables);np.savez_compressed(O/'local_arrays.npz',**batch)
 with np.load(O/'local_arrays.npz') as z:actual={k:z[k].copy() for k in z.files}
 for k in batch:assert np.array_equal(batch[k],actual[k])
 assert consume_batch(actual,keys,tables,envs)==[raw_out[c] for c in ids]
 # The neutral vocabulary is independent of batch order/context names and cone sizes.
 for i,g in enumerate(graphs):
  single=L.collate([g],[keys[i]],tables);a,b=actual['graph_ptr'][i:i+2]
  assert np.array_equal(single['x'],actual['x'][a:b]);e=(actual['graph_index'][actual['edge_index'][1]]==i)
  assert np.array_equal(single['edge_index'],actual['edge_index'][:,e]-a) and np.array_equal(single['edge_role'],actual['edge_role'][e]) and np.array_equal(single['edge_phase'],actual['edge_phase'][e])
  renamed=L.collate([g],['renamed'],{'renamed':tables[keys[i]]});assert all(np.array_equal(single[k],renamed[k]) for k in single)
 # Replay all stored negatives and all existing equalities without changing proof status.
 count=0;roots=0
 for u in units:
  for pid in u['pair_ids']:
   p=pairs[pid];assert p['functional_auxiliary_data_eligible'] and (p['proof_ids'] or p.get('enum',{}).get('equal'))
   assert raw_out[p['left_cone']]==raw_out[p['right_cone']]
  for w in u['witnesses']:
   out=[(raw_out[c]>>w['pattern'])&1 for pid in [w['pair_a'],w['pair_b']] for c in u['cones'] if c in [pairs[pid]['left_cone'],pairs[pid]['right_cone']]]
   assert out==w['outputs'] and out[0]!=out[2];count+=1;roots+=len(out)
 checks=fixtures();write('fixture_checks.json',checks);write('cone_loading_audit.json',rows);write('local_graphs.json',dict(cone_ids=ids,contexts=keys,graphs=graphs))
 for p,h in protected.items():assert sha(R/p)==h,p
 write('INTERFACE_VERIFIED.json',dict(passed=True,units=105,cones=len(ids),existing_equal_pairs=310,saved_patterns_per_cone=128,raw_scalar_and_collated_root_comparisons=len(ids)*128,existing_negative_certificates_replayed=count,witness_root_outputs=roots,synthetic_checks=len(checks),views=len(indices),loaded_nodes=len(batch['x']),loaded_pin_edges=len(batch['edge_role']),q_cones=sum(r['q_nodes']>0 for r in rows),phase1_pins=sum(r['phase1_pins'] for r in rows),constant_nodes=sum(r['constant_nodes'] for r in rows),roundtrip_exact=True,standalone_batch_and_context_rename_exact=True,neural_compatibility='25d semantic interface validated;NOT connected to historical39d model',model_forwards=0,training=0,backward=0,SAT=0,new_real_input_patterns=0,test_reads=0,old_files_unchanged=True,seconds=time.perf_counter()-start,protected_files=protected))
 print('INTERFACE_VERIFIED',len(ids),count,len(checks),flush=True)
if __name__=='__main__':
 try:main()
 except Exception:
  O.mkdir(exist_ok=True);(O/f'validation_failure_{time.strftime("%H%M%S")}.log').write_text(traceback.format_exc(),encoding='utf-8');raise
