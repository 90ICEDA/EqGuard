"""Frozen code remaps,final-component VJPs,MUX identity stress tests and ablations.
No optimizer construction or parameter updates;no solver/real-input generation.
"""
import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import collections,csv,gc,hashlib,json,sys,time,traceback
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;OLD=R/'_p0pilot/cec_freeq_zrp_seed42_20261107';PRE=R/'_p0pilot/cec_freeq_preflight_20261106';P=R/'_p0pilot/cec_boundary_panel_expand_20261107'
sys.path.insert(0,str(PRE));import model_interface as M
sys.path.insert(0,str(P));from panel_loader import PanelLoader
from cache_analysis import read,sha,write,table,query_records
torch=M.torch;COUNTERS=collections.Counter()
def model(arm):
 m=M.fresh('cuda');ck=torch.load(OLD/'INITIAL_STATE.pt' if arm=='INIT' else OLD/arm/'resume.pt',map_location='cuda',weights_only=False)
 if arm!='INIT':assert ck['completed']==32
 m.load_state_dict(ck['model']);m.eval();return m
def forward(m,b,kind):
 COUNTERS['model_forwards']+=1;COUNTERS['forward_'+kind]+=1;return m.encode(b)
def infer(m,loader,ids,tag,kind,change=None):
 out=[]
 for j in range(0,len(ids),48):
  a=loader.arrays(ids[j:j+48],tag)
  if change=='identity_zero':a['x'][:,9:]=0
  if change=='MUX_cycle':
   e=a['edge_role'];a['edge_role']=np.where(e>=2,2+(e-2+1)%3,e)
  b=M.pack(a,'cuda')
  with torch.inference_mode():z,audit=forward(m,b,kind)
  assert audit['consumed_nodes']==b['nodes'] and audit['consumed_pin_edges']==b['edges'] and torch.isfinite(z).all();out.append(z.cpu().numpy());del b,z;gc.collect();torch.cuda.empty_cache()
 return np.concatenate(out)
def cos(a,b):
 a=a.astype(float);b=b.astype(float);d=np.linalg.norm(a)*np.linalg.norm(b);return float(a@b/d) if d else None
def gradient(m,loss):
 pp=list(m.parameters());vv=torch.autograd.grad(loss,pp,retain_graph=True,allow_unused=True);COUNTERS['autograd_calls']+=1
 return torch.cat([(v if v is not None else torch.zeros_like(p)).reshape(-1) for p,v in zip(pp,vv)]).detach().cpu().numpy()
def gradient_row(checkpoint,u,v):
 cr=v['CE_R'].astype(float);cp=v['CE_P'].astype(float);d=v['different'].astype(float);var=v['variance_weighted'].astype(float);common=d+var;n=np.linalg.norm(common);norm=lambda a:float(np.linalg.norm(a));orth=cr-common*(cr@common)/max(1e-30,n*n)
 return dict(checkpoint=checkpoint,batch=u,real_norm=norm(cr),wrong_norm=norm(cp),negative_norm=norm(d),variance_norm=norm(var),common_norm=norm(common),common_over_real=norm(common)/norm(cr),common_over_wrong=norm(common)/norm(cp),real_common_cos=cos(cr,common),wrong_common_cos=cos(cp,common),real_wrong_cos=cos(cr,cp),Rtotal_Ptotal_cos=cos(v['total_R'],v['total_P']),Rtotal_Ztotal_cos=cos(v['total_R'],v['total_Z']),real_CE_directional_slope_under_common_descent=float(-cr@common/max(n,1e-30)),wrong_CE_directional_slope_under_common_descent=float(-cp@common/max(n,1e-30)),real_orthogonal_to_common_fraction=norm(orth)/norm(cr))
def toy_graphs():
 """Old synthetic16 input positions;known MUX=OR(AND,AND) identity,not netlist search."""
 result={}
 for kind in ['PI','Q']:
  names=['a','b','s'];tokens=[dict(kind=kind,audit_name=n,bit=0,slot=j) for j,n in enumerate(names)]
  def base():
   return dict(ports={n:dict(direction='input',bits=[j+2]) for j,n in enumerate(names)} if kind=='PI' else {},cells={} if kind=='PI' else {n:dict(type='DFF',connections={'D':['0'],'Q':[j+2]}) for j,n in enumerate(names)})
  def native(a,b,s):
   m=base();m['cells']['root']=dict(type='$mux',connections={'A':[a],'B':[b],'S':[s],'Y':[50]});return m
  def expanded(a,b,s):
   m=base();m['cells'].update(inv=dict(type='$not',connections={'A':[s],'Y':[40]}),a0=dict(type='$and',connections={'A':[a],'B':[40],'Y':[41]}),a1=dict(type='$and',connections={'A':[b],'B':[s],'Y':[42]}),root=dict(type='$or',connections={'A':[41],'B':[42],'Y':[50]}));return m
  graphs=[M.L.ModuleIndex(m,tokens).cone(50) for abc in [(2,3,4),(3,2,4),(4,3,2)] for m in [native(*abc),expanded(*abc)]]
  env={j:sum(((p>>j)&1)<<p for p in range(16)) for j in range(3)};outputs=[M.L.replay(g,env,(1<<16)-1) for g in graphs];assert all(outputs[2*j]==outputs[2*j+1] for j in range(3)) and len(set(outputs))==3
  result[kind]=dict(tokens=tokens,graphs=graphs,outputs=outputs,unit=dict(unit_id='toy_'+kind,source='toy_'+kind,context_id='toy_'+kind,functions=3,cones=[kind+str(j) for j in range(6)],has_mux=True))
 return result
def main():
 assert 'ginvenv_gpu' in sys.executable and torch.cuda.is_available();assert read(O/'CACHE_COMPLETE.json')['passed'] and not (O/'FROZEN_COMPLETE.json').exists();torch.set_num_threads(1);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False;start=time.perf_counter()
 protected=dict(read(O/'ANALYSIS_CONTRACT.json')['protected_files']);protected[str(Path(__file__).relative_to(R))]=sha(Path(__file__))
 for p,h in protected.items():assert sha(R/p)==h,p
 write('FROZEN_EXECUTION.json',dict(training=0,optimizer_objects=0,SAT=0,extra_tags=[9002,9003,9004,9005],gradient_batches=[1,2,16,32],synthetic='MUX andsameboundary4gate expansion,PI/Q versions;old16toy patterns;no realinput patterns',ablations='MUXrolecycle onctl34;identityzero on85;bothdistribution-shift diagnostics,not revised validinputs/performance',protected_files=protected))
 loader=PanelLoader();pp=read(OLD/'EVALUATION_PANELS.json');val=[u for u in pp['val_boundary_all'] if u['tier']=='H3'];ids=sorted({c for u in val for c in u['cones']});controller=[u for u in val if '__ctlmatchb_' in u['source']];cid=sorted({c for u in controller for c in u['cones']})
 # Explicitly check only identity-code channels change and mapping is a within-kind bijection.
 structural=None;input_audit=[];grams={}
 for tag in range(9000,9006):
  a=loader.arrays(ids,tag);payload={k:hashlib.sha256(v.tobytes()).hexdigest() for k,v in a.items() if k!='x'};payload['operation_bits']=hashlib.sha256(a['x'][:,:9].tobytes()).hexdigest()
  if structural is None:structural=payload
  assert payload==structural
  v=a['x'][:,9:];leaf=a['x'][:,:2].sum(1)>0;assert np.allclose(np.linalg.norm(v[leaf],axis=1),1) and np.all(v[~leaf]==0)
  bycontext={}
  for context in sorted({loader.contexts[c] for c in ids}):
   g=next(loader.graphs[c] for c in ids if loader.contexts[c]==context);tokens=loader.tokens[context];used=sorted({s for c in ids if loader.contexts[c]==context for s in loader.graphs[c]['slot'] if s>=0});vectors={}
   for ki,kind in enumerate(['PI','Q']):
    slots=[t['slot'] for t in tokens if t['kind']==kind];rng=np.random.default_rng([420000,tag,ki,len(slots)]);perm=rng.permutation(len(slots));assert len(set(perm.tolist()))==len(slots)
    for j,s in enumerate(slots):vectors[s]=M.L.code(kind,slots[int(perm[j])])
   x=np.array([vectors[s] for s in used]);assert len({v.tobytes() for v in x})==len(used);grams[context,tag]=x.astype(float)@x.astype(float).T;bycontext[context]=dict(used_variables=len(used),unit_norm=True,unique_codes=True)
  input_audit.append(dict(tag=tag,only_leaf_identity_channels_changed=True,topology_operations_roles_phases_and_roots_identical=True,contexts=bycontext))
 gramrows=[]
 for context in sorted({k[0] for k in grams}):
  a,b=grams[context,9000],grams[context,9001];mask=~np.eye(len(a),dtype=bool);gramrows.append(dict(context=context,used_variables=len(a),code_dimensions=16,offdiagonal_Gram_change_RMS=float(np.sqrt(np.mean((a[mask]-b[mask])**2))),max_abs_offdiagonal_cos9000=float(np.abs(a[mask]).max()),mean_abs_offdiagonal_cos9000=float(np.abs(a[mask]).mean())))
 write('INPUT_CODE_AUDIT.json',input_audit);table('input_code_geometry.csv',gramrows)
 # Four extra fixed maps;the original two cache files are never overwritten.
 for tag in [9002,9003,9004,9005]:
  for arm in ['INIT','Z','R','P']:
   path=O/f'val_{arm}_tag{tag}.npz'
   if path.exists():continue
   m=model(arm);before=M.state_digest(m);root=infer(m,loader,ids,tag,'extra_code');assert M.state_digest(m)==before;np.savez_compressed(path,cone_ids=np.array(ids),root64=root);del m;gc.collect();torch.cuda.empty_cache()
  print('FROZEN_CODE',tag,'all4states',flush=True)
 # Same original shard/input repeated to bound GPU numerical jitter.
 z=np.load(OLD/'val_R_tag9000.npz');oldids=z['cone_ids'].tolist()[:48];a=loader.arrays(oldids,9000);b=M.pack(a,'cuda');m=model('R');before=M.state_digest(m)
 with torch.inference_mode():r1,_=forward(m,b,'repeat_control');r2,_=forward(m,b,'repeat_control')
 write('REPEAT_CONTROL.json',dict(root_max_abs_repeat=float((r1-r2).abs().max()),root_max_abs_vs_oldcache=float(np.abs(r1.cpu().numpy()-z['root64'][:48]).max()),graphs=48,checkpoint_and_input_identical=True));assert M.state_digest(m)==before;del m,b,r1,r2;gc.collect();torch.cuda.empty_cache()
 # Component gradients on ORIGINAL training batches;INIT vectors already exist and are reused.
 vectors={};gradient_rows=[]
 with np.load(PRE/'gradient_vectors.npz') as z:
  for u in [1,2,16,32]:
   v={k:z[f'update{u}_{k}'].copy() for k in ['CE_R','CE_P','different','variance_weighted','total_Z','total_R','total_P']};gradient_rows.append(gradient_row('INIT',u,v))
 batchloader=M.Loader()
 for arm in ['Z','R','P']:
  m=model(arm);before=M.state_digest(m)
  for u in [1,2,16,32]:
   batch=batchloader.batch(u,'cuda');root,_=forward(m,batch['graph'],'component_gradient');parts,totals,_=M.objective(root,batch['loss']);v={k:gradient(m,loss) for k,loss in {**parts,**{'total_'+k:v for k,v in totals.items()}}.items()}
   assert all(np.isfinite(x).all() for x in v.values());common=v['different']+v['variance_weighted']
   for group,expected in [('Z',common),('R',common+v['CE_R']),('P',common+v['CE_P'])]:assert np.linalg.norm(v['total_'+group]-expected)/np.linalg.norm(v['total_'+group])<2e-5
   for k,x in v.items():vectors[f'{arm}_batch{u}_{k}']=x
   gradient_rows.append(gradient_row(arm,u,v));assert M.state_digest(m)==before and all(p.grad is None for p in m.parameters());del root,parts,totals,batch;gc.collect();torch.cuda.empty_cache()
  print('FROZEN_GRADIENTS',arm,flush=True);del m;gc.collect();torch.cuda.empty_cache()
 np.savez_compressed(O/'final_component_vectors.npz',**vectors);table('component_gradient_summary.csv',gradient_rows)
 # Actual parameter displacements since common init,not a causal decomposition of Adam.
 init=torch.load(OLD/'INITIAL_STATE.pt',map_location='cpu',weights_only=False)['model'];delta={};paramrows=[]
 for arm in ['Z','R','P']:
  state=torch.load(OLD/arm/'resume.pt',map_location='cpu',weights_only=False)['model'];delta[arm]=np.concatenate([(state[k]-init[k]).numpy().ravel() for k in init])
 for arm in ['R','P']:paramrows.append(dict(arm=arm,delta_from_INIT_norm=float(np.linalg.norm(delta[arm])),Z_delta_norm=float(np.linalg.norm(delta['Z'])),delta_cos_with_Z=cos(delta[arm],delta['Z']),relative_distance_to_Z=float(np.linalg.norm(delta[arm]-delta['Z'])/np.linalg.norm(delta['Z']))))
 table('parameter_displacements.csv',paramrows)
 # Tiny Boolean identities use old synthetic input pattern convention,never realSAT inputs.
 toys=toy_graphs();toyrows=[]
 for kind,t in toys.items():
  for tag in [9000,9001]:
   arrays=M.L.collate(t['graphs'],['toy_'+kind]*6,{'toy_'+kind:t['tokens']},tag);b=M.pack(arrays,'cuda')
   for arm in ['INIT','Z','R','P']:
    m=model(arm);before=M.state_digest(m)
    with torch.inference_mode():root,_=forward(m,b,'MUX_identity_toy')
    q=query_records([t['unit']],t['unit']['cones'],root.cpu().numpy());toyrows.append(dict(kind=kind,tag=tag,arm=arm,functions=3,pairwise_win=float(np.mean([r['win'] for r in q])),native_F_queries_win=float(np.mean([r['win'] for r in q if r['anchor_function']==0 and r['anchor_side']==0])),margin=float(np.mean([r['margin'] for r in q])),truth_identity_verified_16patterns=True));assert M.state_digest(m)==before;del m;gc.collect();torch.cuda.empty_cache()
   del b
 table('MUX_boolean_identity_stress.csv',toyrows);write('MUX_TOY_TRUTH.json',{kind:t['outputs'] for kind,t in toys.items()})
 # Fixed-input interventions:rolecycle for same-source34,identityzero for all85.
 ablations=[]
 for tag in [9000,9001]:
  for arm in ['INIT','Z','R','P']:
   m=model(arm);before=M.state_digest(m)
   for change,scope,subset in [('MUX_cycle','ctlmatchb34',controller),('identity_zero','H3all85',val)]:
    subids=sorted({c for u in subset for c in u['cones']});root=infer(m,loader,subids,tag,'ablation',change);q=query_records(subset,subids,root)
    for group,uu in [('all',subset),('MUX',[u for u in subset if u['has_mux']]),('nonMUX',[u for u in subset if not u['has_mux']])]:
     if not uu:continue
     uid={u['unit_id'] for u in uu};rr=[r for r in q if r['unit_id'] in uid];per=[np.mean([r['win'] for r in rr if r['unit_id']==u['unit_id']]) for u in uu];ablations.append(dict(tag=tag,arm=arm,change=change,scope=scope,group=group,units=len(uu),unit_macro_win=float(np.mean(per)),note='corrupted-input posthoc sensitivity,not alternative valid performance'))
    np.savez_compressed(O/f'ablation_{arm}_{tag}_{change}.npz',cone_ids=np.array(subids),root64=root)
   assert M.state_digest(m)==before;del m;gc.collect();torch.cuda.empty_cache()
 table('frozen_input_ablations.csv',ablations)
 for p,h in protected.items():assert sha(R/p)==h,p
 write('FROZEN_COMPLETE.json',dict(passed=True,counters=dict(COUNTERS),extra_codes=[9002,9003,9004,9005],initial_gradients_reused=True,weights_buffers_and_grad_fields_unchanged=True,optimizer_objects=0,optimizer_updates=0,training=0,SAT=0,new_real_boolean_patterns=0,synthetic_patterns='old16positions on constructed identity only',test_reads=0,old_files_unchanged=True,seconds=time.perf_counter()-start))
 print('ALL_FROZEN_DIAGNOSTICS_COMPLETE',dict(COUNTERS),flush=True)
if __name__=='__main__':
 try:main()
 except Exception:
  O.mkdir(exist_ok=True);(O/f'failure_{time.strftime("%H%M%S")}.log').write_text(traceback.format_exc(),encoding='utf-8');raise
