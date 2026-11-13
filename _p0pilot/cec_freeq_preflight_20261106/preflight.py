"""Authorized loading and NO-UPDATE gradient preflight;never constructs an optimizer."""
import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import collections,copy,csv,gc,json,math,sys,time,traceback
import numpy as np
import torch
import model_interface as M
R=M.R;O=Path(__file__).resolve().parent;C=M.C;V=M.V
COUNTERS=collections.Counter()
def write(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def table(n,rr):
 if not rr:return
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def array_sha(a):return M.ident(a) if False else __import__('hashlib').sha256(str(a.dtype).encode()+str(a.shape).encode()+a.tobytes()).hexdigest()
def call(model,b,kind,internal=False):
 COUNTERS['model_forwards']+=1;COUNTERS['forward_'+kind]+=1;return model.encode(b,internal)
def numpy_reference(state,a):
 """Independent scalar-node float64 GRU equations;no torch module execution."""
 w={k:v.detach().cpu().numpy().astype(np.float64) for k,v in state.items()};x=a['x'].astype(np.float64);base=np.maximum(0,x@w['input.weight'].T+w['input.bias']);h=np.zeros((len(x),64));inc=collections.defaultdict(list)
 for i,(s,d) in enumerate(a['edge_index'].T):inc[int(d)].append((int(s),int(a['edge_role'][i]),int(a['edge_phase'][i])))
 def norm(v):return (v-v.mean())/np.sqrt(v.var()+1e-5)*w['norm.weight']+w['norm.bias']
 def sigmoid(v):return 1/(1+np.exp(-v))
 for j in range(len(x)):
  if a['x'][j,:9].argmax()<4:h[j]=norm(base[j]);continue
  terms=[(1-2*phase)*(h[s]@w[f'role_maps.{role}.weight'].T)+w['phase_embedding.weight'][phase] for s,role,phase in inc[j]];agg=np.sum(terms,0)/np.sqrt(len(terms));ii=w['gru.weight_ih']@agg+w['gru.bias_ih'];hh=w['gru.weight_hh']@base[j]+w['gru.bias_hh'];rr=sigmoid(ii[:64]+hh[:64]);zz=sigmoid(ii[64:128]+hh[64:128]);nn=np.tanh(ii[128:]+rr*hh[128:]);h[j]=norm((1-zz)*nn+zz*base[j])
 return h
def parameter_breakdown(model):
 out=dict(input_linear=sum(p.numel() for p in model.input.parameters()),role_maps=sum(p.numel() for p in model.role_maps.parameters()),phase_embedding=sum(p.numel() for p in model.phase_embedding.parameters()),GRUCell=sum(p.numel() for p in model.gru.parameters()),LayerNorm=sum(p.numel() for p in model.norm.parameters()))
 assert out==M.read(C/'FAIR_MODEL_CONTRACT.json')['model']['expected_parameter_breakdown'];assert sum(out.values())==47360;assert not any(isinstance(m,(torch.nn.modules.batchnorm._BatchNorm,torch.nn.Dropout)) for m in model.modules());return out
def fixtures(model):
 L=M.L;tokens=[dict(kind='PI',audit_name='a',bit=0,slot=0),dict(kind='PI',audit_name='b',bit=0,slot=1),dict(kind='PI',audit_name='s',bit=0,slot=2),dict(kind='Q',audit_name='ff',bit=0,slot=3)]
 def module(op,inputs):
  output,_,pins=L.SCHEMA[op];return dict(ports={n:dict(direction='input',bits=[b]) for n,b in [('a',2),('b',3),('s',4)]},cells={'ff':dict(type='DFF',connections={'D':[2],'Q':[5],'QN':[6]}),'root':dict(type=op,connections={output:[20],**{p:[v] for p,v in zip(pins,inputs)}})})
 def graph(m):return L.ModuleIndex(m,tokens).cone(20)
 definitions=[('mux',module('MX2X1_RS',[2,3,4])),('mux_swap_select',module('MX2X1_RS',[4,3,2])),('mux_swap_data',module('MX2X1_RS',[3,2,4])),('not_a',module('INVX0',[2])),('not_b',module('INVX0',[3])),('not_q',module('INVX0',[5])),('not_qn',module('INVX0',[6])),('xor_repeat',module('XOR2X1',[2,2])),('xor_distinct',module('XOR2X1',[2,3])),('and_zero',module('AND2X2',[5,'0'])),('and_one',module('AND2X2',[5,'1'])),('and_ab',module('AND2X2',[2,3])),('and_ba',module('AND2X2',[3,2]))]
 changed=module('INVX0',[5]);changed['cells']['ff']['connections']['D']=[3];definitions.append(('not_q_changed_D',changed))
 deep=module('INVX0',[5]);deep['cells']['root']['connections']['IN']=[14]
 for j in range(5):deep['cells']['n'+str(j)]=dict(type='INVX0',connections={'IN':[5 if j==0 else 10+j-1],'QN':[10+j]})
 definitions.append(('deep6',deep));graphs=[graph(m) for n,m in definitions];names=[n for n,m in definitions];a=L.collate(graphs,['fixture']*len(graphs),{'fixture':tokens},9000);b=M.pack(a,'cuda');before=M.state_digest(model)
 with torch.no_grad():root,h,base,consumed=call(model,b,'synthetic',True)
 z=root.cpu().numpy();ix={n:j for j,n in enumerate(names)};checks=[]
 def record(name,passed,delta=None):assert passed,name;checks.append(dict(check=name,passed=True,max_delta=delta))
 for a1,a2 in [('mux','mux_swap_select'),('mux','mux_swap_data'),('not_a','not_b'),('not_q','not_qn'),('xor_repeat','xor_distinct'),('and_zero','and_one')]:
  delta=float(np.max(np.abs(z[ix[a1]]-z[ix[a2]])));record(a1+'_vs_'+a2,delta>1e-5,delta)
 delta=float(np.max(np.abs(z[ix['and_ab']]-z[ix['and_ba']])));record('commutative_input_exchange_invariant',delta<2e-5,delta)
 delta=float(np.max(np.abs(z[ix['not_q']]-z[ix['not_q_changed_D']])));record('Q_upstream_D_change_invariant',delta==0.,delta)
 # Batch composition cannot change LayerNorm local-cone results.
 single=M.pack(L.collate([graphs[0]],['fixture'],{'fixture':tokens},9000),'cuda')
 with torch.no_grad():alone,_=call(model,single,'synthetic_single')
 delta=float((alone[0]-root[0]).abs().max());record('standalone_vs_batch_same_representation',delta<2e-5,delta)
 # Actual autograd through six operation levels,well beyond the old root3hop radius.
 da=L.collate([graphs[-1]],['fixture'],{'fixture':tokens},9000);db=M.pack(da,'cuda');db['x'].requires_grad_(True);dr,dh,_,audit=call(model,db,'synthetic_deep_gradient',True);probe=(dr[0]*torch.linspace(-1,1,64,device='cuda')).sum();grad=torch.autograd.grad(probe,db['x'])[0];COUNTERS['autograd_calls']+=1
 qrow=int(np.flatnonzero(da['x'][:,1]==1)[0]);gn=float(grad[qrow,9:].norm());record('six_level_Q_identity_gradient_reaches_root',gn>1e-10,gn);record('six_comb_nodes_and_all_edges_consumed',audit['consumed_comb_nodes']==6 and audit['consumed_pin_edges']==6)
 assert M.state_digest(model)==before
 np.savez_compressed(O/'synthetic_roots.npz',names=np.array(names),root64=z,deep_input_gradient=grad.cpu().numpy());write('FIXTURES_VERIFIED.json',dict(passed=True,checks=checks,parameter_probe='frozen random seed42 initialization;not learned Boolean correctness or transfer performance',weights_unchanged=True,deep_gradient_norm=gn))
 return checks
def grad_vector(loss,model,retain=True):
 pp=list(model.parameters());gg=torch.autograd.grad(loss,pp,retain_graph=retain,allow_unused=True);COUNTERS['autograd_calls']+=1
 return torch.cat([(g if g is not None else torch.zeros_like(p)).reshape(-1) for g,p in zip(gg,pp)]).detach().cpu().numpy()
def cosine(a,b):
 den=np.linalg.norm(a.astype(float))*np.linalg.norm(b.astype(float));return float(np.dot(a.astype(float),b.astype(float))/den) if den else None
def geometry(z):
 x=z.astype(np.float64);x-=x.mean(0);s=np.linalg.svd(x,compute_uv=False);e=s*s;prob=e/e.sum() if e.sum() else e;rank=float(np.exp(-sum(p*np.log(p) for p in prob if p>0))) if e.sum() else 0
 return dict(root_mean_std=float(z.std(0).mean()),effective_rank=rank,PC1_energy=float(prob[0]) if len(prob) else None,distinct_root_vectors=int(len(np.unique(z,axis=0))))
def main():
 start=time.perf_counter();assert 'ginvenv_gpu' in sys.executable and torch.cuda.is_available();assert not (O/'COMPLETE.json').exists()
 torch.set_num_threads(1);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
 assert M.read(C/'VERIFIED.json')['passed'];protected=dict(M.read(C/'AUDIT_COMPLETE.json')['protected_files'])
 for n,h in M.read(C/'OUTPUT_MANIFEST.json').items():assert M.sha(C/n)==h,n;protected[str((C/n).relative_to(R))]=h
 for p in [C/'VERIFIED.json',C/'PUBLISHED.json',Path(__file__),O/'model_interface.py',V/'local_graphs.json',V/'local_arrays.npz',R/'_p0pilot/cec_interface_minimal_20261105/boundary_maps_audit_only.json']:protected[str(p.relative_to(R))]=M.sha(p)
 for p,h in protected.items():assert M.sha(R/p)==h,p
 write('EXECUTION_CONTRACT.json',dict(authorization='user requested model hookup/load/no-update gradient preflight only',training_authorized=False,training_updates=0,optimizer_objects=0,SAT=0,test_reads=0,precision='FP32 CUDA no autocast noTF32',gradient_batches='1,2,16,32 plus earliest real MUX-bearing scheduled step if not already covered',all32_batches='exact actual loader+frozen forward+CE preview,not optimizer steps',protected_files=protected))
 loader=M.Loader();model=M.fresh('cuda');model.eval();parts=parameter_breakdown(model);assert model.phase_embedding.weight.count_nonzero()==0
 digest=M.state_digest(model);torch.save(dict(model={k:v.detach().cpu() for k,v in model.state_dict().items()},seed=42,contract_sha=M.sha(C/'FAIR_MODEL_CONTRACT.json'),model_code_sha=M.sha(O/'model_interface.py'),digest=digest,optimizer_updates=0),O/'INITIAL_STATE.pt')
 write('MODEL_LOADED.json',dict(parameters=sum(p.numel() for p in model.parameters()),breakdown=parts,initial_digest=digest,initial_file_sha=M.sha(O/'INITIAL_STATE.pt'),BN_modules=0,dropout_modules=0,projection_heads=0,old39_weights_loaded=False))
 checks=fixtures(model);audit_rows=[];preview=[];grad_steps={1,2,16,32};first_mux=None;torch.cuda.reset_peak_memory_stats()
 for update in range(1,33):
  begin=time.perf_counter();batch=loader.batch(update,'cuda');a=batch['arrays'];g=batch['graph'];loss_inputs=batch['loss'];bhash={k:array_sha(v) for k,v in a.items()}
  if first_mux is None and np.any(a['edge_role']>=2):first_mux=update
  assert len(batch['cone_ids'])==18 and len(batch['records'])==3 and loss_inputs['candidates'].shape==(18,3) and loss_inputs['negative_edges'].shape==(18,2)
  assert all(abs(float(loss_inputs[k].sum())-1)<2e-7 for k in ['query_weight','negative_weight'])
  with torch.no_grad():z,consumed=call(model,g,'actual32_loading');pieces,totals,aux=M.objective(z,loss_inputs)
  assert torch.isfinite(z).all() and all(torch.isfinite(v) for v in totals.values());info=geometry(z.cpu().numpy());assert info['root_mean_std']>1e-5 and info['distinct_root_vectors']>1
  assert consumed['consumed_nodes']==g['nodes'] and consumed['consumed_comb_nodes']==g['comb_count'] and consumed['consumed_pin_edges']==g['edges']
  rr=dict(update=update,graphs=18,units=3,families=3,nodes=g['nodes'],comb_nodes=g['comb_count'],pin_edges=g['edges'],max_level=g['max_level'],MUX_pin_edges=int(np.sum(a['edge_role']>=2)),Q_nodes=int(np.sum(a['x'][:,1])),phase1_pins=int(a['edge_phase'].sum()),queries=18,candidate_distances=54,common_negatives=18,root_queries=18,all_nodes_and_pins_consumed=True,seconds=time.perf_counter()-begin,feature_sha=bhash['x'],graph_arrays_sha=json.dumps(bhash,sort_keys=True),**info);audit_rows.append(rr)
  pr=dict(update=update,**{k:float(v) for k,v in pieces.items()},**{'loss_'+k:float(v) for k,v in totals.items()});preview.append(pr)
  np.savez_compressed(O/f'preview_step{update:02}.npz',root64=z.cpu().numpy(),cone_ids=np.array(batch['cone_ids']),**{k:v.cpu().numpy() for k,v in loss_inputs.items()})
  if update==1:
   np.savez_compressed(O/'loaded_step1_arrays.npz',**a);reference=numpy_reference(model.state_dict(),a);delta=float(np.max(np.abs(reference-z.new_tensor(reference,dtype=torch.float32).cpu().numpy()))) if False else float(np.max(np.abs(reference[a['root_index']]-z.cpu().numpy())))
   assert np.allclose(reference[a['root_index']],z.cpu().numpy(),atol=2e-5,rtol=2e-5),delta
   write('NUMPY_REFERENCE_VERIFIED.json',dict(passed=True,actual_batch=1,nodes_compared=len(a['x']),root_max_abs_delta=delta,reference='independent float64 nodeby-node GRU r/z/n and LayerNorm equations',tolerance='atol2e-5 rtol2e-5'));np.savez_compressed(O/'step1_numpy_reference.npz',all_nodes64=reference)
  assert M.state_digest(model)==digest
  if update==1 or update%8==0:print('LOADED_FROZEN',update,'nodes',g['nodes'],'depth',g['max_level'],'lossR',round(pr['loss_R'],5),flush=True)
  del batch,g,loss_inputs,z,pieces,totals,aux;gc.collect();torch.cuda.empty_cache()
 if first_mux is not None:grad_steps.add(first_mux)
 table('actual_loading_budget.csv',audit_rows);table('initial_loss_preview.csv',preview);write('GRADIENT_BATCHES.json',dict(updates=sorted(grad_steps),first_real_MUX_step=first_mux,selection='fixedsteps plus rolecoverage,not scores/gradients'))
 # Both component and actual total vector-Jacobian products at EXACT same weights and input.
 gradient_rows=[];vectors={};components=['CE_R','CE_P','different','variance_weighted'];norm_rows=[]
 for update in sorted(grad_steps):
  batch=loader.batch(update,'cuda');root,consumed=call(model,batch['graph'],'gradient_shared');pieces,totals,aux=M.objective(root,batch['loss']);vv={k:grad_vector(v,model) for k,v in {**pieces,**{'total_'+k:v for k,v in totals.items()}}.items()}
  for k,v in vv.items():assert np.isfinite(v).all();vectors[f'update{update}_{k}']=v
  shared=vv['different']+vv['variance_weighted']
  for arm,expected in [('Z',shared),('R',shared+vv['CE_R']),('P',shared+vv['CE_P'])]:
   actual=vv['total_'+arm];assert np.linalg.norm(actual)>0;relative=float(np.linalg.norm(actual.astype(float)-expected.astype(float))/max(1e-20,np.linalg.norm(actual.astype(float))));assert relative<2e-5,(update,arm,relative)
   gradient_rows.append(dict(update=update,arm=arm,total_norm=float(np.linalg.norm(actual)),association_norm=0. if arm=='Z' else float(np.linalg.norm(vv['CE_'+arm])),common_negative_norm=float(np.linalg.norm(vv['different'])),variance_norm=float(np.linalg.norm(vv['variance_weighted'])),additivity_relative_error=relative,CE_R=float(pieces['CE_R']),CE_P=float(pieces['CE_P']),loss=float(totals[arm]),root_std=float(root.detach().std(0,unbiased=False).mean())))
  gradient_rows.append(dict(update=update,arm='COSINES',total_norm=cosine(vv['total_R'],vv['total_P']),association_norm=cosine(vv['CE_R'],vv['CE_P']),common_negative_norm=None,variance_norm=None,additivity_relative_error=None,CE_R=None,CE_P=None,loss=None,root_std=None))
  offset=0
  for name,p in model.named_parameters():
   v=vv['total_R'][offset:offset+p.numel()];offset+=p.numel();norm_rows.append(dict(update=update,parameter=name,total_R_gradient_norm=float(np.linalg.norm(v)),finite=bool(np.isfinite(v).all())))
  assert offset==47360 and M.state_digest(model)==digest and all(p.grad is None for p in model.parameters())
  print('NO_UPDATE_GRADIENT',update,'association_cos',round(cosine(vv['CE_R'],vv['CE_P']),5),'total_cos',round(cosine(vv['total_R'],vv['total_P']),5),flush=True)
  del batch,root,pieces,totals,aux;gc.collect();torch.cuda.empty_cache()
 np.savez_compressed(O/'gradient_vectors.npz',**vectors);table('gradient_summary.csv',gradient_rows);table('parameter_gradients.csv',norm_rows)
 # Actual independent Z/R/P instances loaded from the SAME initial full state.
 batch=loader.batch(1,'cuda');three=[];grads={}
 for arm in ['Z','R','P']:
  m=M.fresh('cuda');m.load_state_dict(model.state_dict());m.eval();before=M.state_digest(m);z,_=call(m,batch['graph'],'independent_group');pieces,totals,aux=M.objective(z,batch['loss']);v=grad_vector(totals[arm],m,False);assert before==digest==M.state_digest(m)
  assert np.allclose(v,vectors['update1_total_'+arm],rtol=2e-4,atol=2e-6)
  three.append(z.detach().cpu().numpy());grads[arm]=v;del m,z,pieces,totals,aux;gc.collect();torch.cuda.empty_cache()
 assert all(np.allclose(three[0],z,atol=2e-5,rtol=2e-5) for z in three[1:]);write('THREE_GROUPS_VERIFIED.json',dict(passed=True,common_initial_digest=digest,identical_actual_batch=True,independent_forward_roots_match=True,total_gradients_match_shared_graph=True,optimizer_objects=0,updates=0))
 # Primary validation loads genuine TWO-candidate records;it is never padded to three.
 strict=[u for u in M.read(C/'T3_PO_exact_units.json') if u['split']=='val'];ids=sorted({c for u in strict for c in u['cones']});aa=loader.arrays(ids,9000);gg=M.pack(aa,'cuda')
 with torch.no_grad():rr,consumed=call(model,gg,'primary_two_candidate_loading')
 assert len(strict)==4 and len(ids)==16 and all(u['functions']==2 for u in strict) and torch.isfinite(rr).all();write('PRIMARY_VALIDATION_LOADING.json',dict(units=4,functions_per_unit=2,source_counts=dict(collections.Counter(u['source'] for u in strict)),graphs=len(ids),all_nodes_and_pins_consumed=True,padded_third_candidate=False,performance_not_acceptance=True))
 assert M.state_digest(model)==digest
 for p,h in protected.items():assert M.sha(R/p)==h,p
 write('COMPLETE.json',dict(passed=True,parameter_count=47360,actual_loaded_steps=32,actual_supervision=dict(unit_slots=sum(r['units'] for r in audit_rows),queries=sum(r['queries'] for r in audit_rows),candidate_distances=sum(r['candidate_distances'] for r in audit_rows),common_negatives=sum(r['common_negatives'] for r in audit_rows)),gradient_steps=sorted(grad_steps),parameter_and_buffers_unchanged=True,parameter_grad_fields_untouched=True,optimizer_objects=0,optimizer_updates=0,training_updates=0,SAT=0,new_real_input_patterns=0,test_reads=0,counters=dict(COUNTERS),peak_gpu_bytes=torch.cuda.max_memory_allocated(),GPU_total_bytes=torch.cuda.get_device_properties(0).total_memory,seconds=time.perf_counter()-start,protected_files_unchanged=True))
 print('FREEQ_NO_UPDATE_PREFLIGHT_COMPLETE',dict(COUNTERS),flush=True)
if __name__=='__main__':
 try:main()
 except Exception:
  O.mkdir(exist_ok=True);(O/f'failure_{time.strftime("%H%M%S")}.log').write_text(traceback.format_exc(),encoding='utf-8');raise
