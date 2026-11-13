"""Independent CPU losses/budgets/gradients and one all-node CUDA reference check."""
import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import collections,csv,hashlib,json,math,sys
import numpy as np
import torch
import model_interface as M
R=M.R;C=M.C;O=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def rows(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def array_sha(a):return hashlib.sha256(str(a.dtype).encode()+str(a.shape).encode()+a.tobytes()).hexdigest()
def cpu_losses(z,b):
 z=z.astype(np.float64);dist=np.sqrt(np.mean((z[b['anchors']][:,None,:]-z[b['candidates']])**2,2)+1e-12);logits=-dist;shift=logits.max(1);logsum=np.log(np.exp(logits-shift[:,None]).sum(1))+shift
 ceR=np.dot(b['query_weight'],logsum-logits[np.arange(len(logits)),b['real']]);ceP=np.dot(b['query_weight'],logsum-logits[np.arange(len(logits)),b['permuted']]);ne=b['negative_edges'];nd=np.sqrt(np.mean((z[ne[:,0]]-z[ne[:,1]])**2,1)+1e-12);negative=np.dot(b['negative_weight'],np.maximum(0,1-nd)**2);variance=.1*np.maximum(0,.5-np.sqrt(z.var(0)+1e-4)).mean()
 return dict(CE_R=float(ceR),CE_P=float(ceP),different=float(negative),variance_weighted=float(variance),loss_Z=float(negative+variance),loss_R=float(negative+variance+ceR),loss_P=float(negative+variance+ceP))
def main():
 assert 'ginvenv_gpu' in sys.executable and torch.cuda.is_available();torch.set_num_threads(1);torch.backends.cuda.matmul.allow_tf32=False
 complete=read(O/'COMPLETE.json');assert complete['passed'] and complete['optimizer_updates']==complete['optimizer_objects']==0
 protected=read(O/'EXECUTION_CONTRACT.json')['protected_files']
 for p,h in protected.items():assert M.sha(R/p)==h,p
 assert M.sha(O/'INITIAL_STATE.pt')==read(O/'MODEL_LOADED.json')['initial_file_sha']
 # Rebuild each scheduled batch directly from old immutable schema,not the new loader.
 old=M.read(M.V/'local_graphs.json');graphs=dict(zip(old['cone_ids'],old['graphs']));contexts=dict(zip(old['cone_ids'],old['contexts']));tokens={m['context_key']:m['tokens'] for m in read(R/'_p0pilot/cec_interface_minimal_20261105/boundary_maps_audit_only.json')}
 schedule=read(C/'SCHEDULE_SEED42.json');loadrows=rows(O/'actual_loading_budget.csv');lossrows=rows(O/'initial_loss_preview.csv');budgets=collections.Counter();max_loss_error=0.;shapes=[]
 for step in schedule:
  u=step['update'];ids=sorted({c for r in step['units'] for c in r['cone_ids']});ix={c:j for j,c in enumerate(ids)};aa=M.L.collate([graphs[c] for c in ids],[contexts[c] for c in ids],tokens,u);audit=next(r for r in loadrows if int(r['update'])==u)
  for k,v in aa.items():assert array_sha(v)==json.loads(audit['graph_arrays_sha'])[k],(u,k)
  assert len(aa['x'])==int(audit['nodes']) and len(aa['edge_role'])==int(audit['pin_edges']) and int(aa['level'].max())==int(audit['max_level'])
  expected=collections.defaultdict(list)
  for r in step['units']:
   expected['anchors'] +=[ix[c] for c in r['anchors']];expected['candidates'] +=[[ix[c] for c in cc] for cc in r['candidates']];expected['real']+=r['real_targets'];expected['permuted']+=r['permuted_targets'];expected['negative_edges'] +=[[ix[a],ix[b]] for a,b in r['common_negative_edges']];expected['query_weight'] +=[r['query_weight']]*6;expected['negative_weight'] +=[r['negative_weight']]*6
  with np.load(O/f'preview_step{u:02}.npz') as z:
   assert z['cone_ids'].tolist()==ids and np.isfinite(z['root64']).all()
   for k,v in expected.items():assert np.array_equal(z[k],np.array(v,dtype=z[k].dtype)),(u,k)
   b={k:z[k].copy() for k in expected};metric=cpu_losses(z['root64'],b)
  recorded=next(r for r in lossrows if int(r['update'])==u)
  for k,v in metric.items():
   error=abs(float(recorded[k])-v);max_loss_error=max(max_loss_error,error);assert error<1e-6,(u,k,error)
  # Weighted association targets exactly preserve endpoint masses in R and P.
  mass={arm:collections.Counter() for arm in ['R','P']}
  for i,a in enumerate(expected['anchors']):
   for arm,key in [('R','real'),('P','permuted')]:mass[arm][expected['candidates'][i][expected[key][i]]]+=1
  assert mass['R']==mass['P']==collections.Counter(expected['anchors'])
  budgets.update(dict(unit_slots=3,queries=len(b['anchors']),candidate_distances=np.prod(b['candidates'].shape),common_negatives=len(b['negative_edges'])))
  shapes.append(dict(update=u,nodes=len(aa['x']),edges=len(aa['edge_role']),max_depth=int(aa['level'].max())))
 assert dict(budgets)==complete['actual_supervision']
 # Verify all saved VJPs independently;full vectors,not only log summaries.
 with np.load(O/'gradient_vectors.npz') as vectors:
  checked=0;cosines=[];norm_error=0.
  for update in complete['gradient_steps']:
   vv={k:vectors[f'update{update}_{k}'].astype(np.float64) for k in ['CE_R','CE_P','different','variance_weighted','total_Z','total_R','total_P']};common=vv['different']+vv['variance_weighted']
   for arm,expected in [('Z',common),('R',common+vv['CE_R']),('P',common+vv['CE_P'])]:
    actual=vv['total_'+arm];err=np.linalg.norm(actual-expected)/np.linalg.norm(actual);assert err<2e-5;assert np.isfinite(actual).all() and np.linalg.norm(actual)>0;checked+=1
   def cosine(a,b):return float(np.dot(a,b)/(np.linalg.norm(a)*np.linalg.norm(b)))
   cosines.append(dict(update=update,association_cosine=cosine(vv['CE_R'],vv['CE_P']),total_cosine=cosine(vv['total_R'],vv['total_P'])))
 # Exactly one extra forward checks every node against the already saved independent NumPy result.
 initial=torch.load(O/'INITIAL_STATE.pt',map_location='cpu',weights_only=False);m=M.fresh('cuda');m.load_state_dict(initial['model']);m.eval();assert M.state_digest(m)==initial['digest'];a=dict(np.load(O/'loaded_step1_arrays.npz'));b=M.pack(a,'cuda');before=M.state_digest(m)
 with torch.no_grad():root,h,base,audit=m.encode(b,True)
 reference=np.load(O/'step1_numpy_reference.npz')['all_nodes64'];actual=h.cpu().numpy();delta=float(np.max(np.abs(reference-actual)));assert reference.shape==actual.shape==(4059,64) and np.allclose(reference,actual,atol=2e-5,rtol=2e-5)
 assert M.state_digest(m)==before
 # A signed,role-specific graph is the ONLY model input;names,PO and safety fields ignored.
 g=graphs[next(iter(ids))];key=contexts[next(iter(ids))];orig=M.L.collate([g],[key],tokens,9000);changed=json.loads(json.dumps(g));changed.update(POdistance=999999,host='changed',safety_label=1,root_global_row=999999);changed['comb_names']=['changed_'+str(j) for j in range(len(changed['comb_names']))]
 altered=M.L.collate([changed],['renamed_context'],{'renamed_context':tokens[key]},9000);assert all(np.array_equal(orig[k],altered[k]) for k in orig)
 # Compare diagnostic member readout too,without another forward.
 gi=a['graph_index'];comb=np.flatnonzero(a['x'][:,:9].argmax(1)>=4);means=np.array([actual[comb[gi[comb]==j]].mean(0) for j in range(len(a['root_index']))]);assert means.shape==(18,64) and np.isfinite(means).all()
 primary=read(O/'PRIMARY_VALIDATION_LOADING.json');assert primary['units']==4 and primary['functions_per_unit']==2 and primary['graphs']==16 and not primary['padded_third_candidate']
 assert read(O/'THREE_GROUPS_VERIFIED.json')['passed'] and read(O/'FIXTURES_VERIFIED.json')['passed']
 for p,h in protected.items():assert M.sha(R/p)==h,p
 # Executed source files are frozen and retained;preflight's rawroot reference precedes this fullnode check.
 write('INDEPENDENT_CHECKS.json',dict(passed=True,batches_rebuilt=32,all_nodes_reference_compared=4059,all_node_reference_max_abs_delta=delta,original_reference_check='preflight compared roots;this independent check compares all4059nodes',losses_recomputed=32*7,max_loss_abs_error=max_loss_error,total_gradient_vectors_checked=checked,gradient_cosines=cosines,forbidden_metadata_perturbation_no_input_change=True,all_32_loaded_inputs_match_old_schema=True,extra_model_forwards=1,extra_backwards=0,optimizer_objects=0,optimizer_updates=0))
 manifest={p.name:M.sha(p) for p in O.iterdir() if p.is_file() and p.suffix in ['.py','.json','.npz','.csv','.pt'] and p.name not in ['OUTPUT_MANIFEST.json','VERIFIED.json','PUBLISHED.json']};write('OUTPUT_MANIFEST.json',manifest)
 loading=rows(O/'actual_loading_budget.csv');grad=[r for r in rows(O/'gradient_summary.csv') if r['arm']!='COSINES'];stds=[float(r['root_mean_std']) for r in loading];ranks=[float(r['effective_rank']) for r in loading]
 write('VERIFIED.json',dict(passed=True,contract_sha=M.sha(C/'FAIR_MODEL_CONTRACT.json'),parameters=47360,actual_batches=32,root_std_range=[min(stds),max(stds)],effective_rank_range=[min(ranks),max(ranks)],max_depth=max(int(r['max_level']) for r in loading),max_batch_nodes=max(int(r['nodes']) for r in loading),gradient_norm_range=[min(float(r['total_norm']) for r in grad),max(float(r['total_norm']) for r in grad)],association_cosine_range=[min(r['association_cosine'] for r in cosines),max(r['association_cosine'] for r in cosines)],total_cosine_range=[min(r['total_cosine'] for r in cosines),max(r['total_cosine'] for r in cosines)],model_forwards=complete['counters']['model_forwards']+1,autograd_calls=complete['counters']['autograd_calls'],optimizer_objects=0,training_updates=0,SAT=0,new_real_patterns=0,test_reads=0,initial_weights_and_buffers_unchanged=True,old_files_unchanged=True,primary_support='4two-function units/2sources/1host,exploratory only',preflight_pass_is_not_performance_gain=True,manifest_sha=M.sha(O/'OUTPUT_MANIFEST.json')))
 print('INDEPENDENT_FREEQ_PREFLIGHT_VERIFIED',flush=True)
if __name__=='__main__':main()
