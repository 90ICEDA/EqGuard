"""Authorized seed42 Z/R/P32 exploration,unchanged freeQ training contract.
New H3 evaluation binding is explicit;no detector or SAT calls.
"""
import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import collections,csv,gc,hashlib,json,math,shutil,sys,time,traceback
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;PRE=R/'_p0pilot/cec_freeq_preflight_20261106';C=R/'_p0pilot/cec_po_contract_20261106';P=R/'_p0pilot/cec_boundary_panel_expand_20261107'
sys.path.insert(0,str(PRE));import model_interface as M
sys.path.insert(0,str(P));from panel_loader import PanelLoader
torch=M.torch;ARMS=['Z','R','P']
def read(p):return M.read(p)
def sha(p):return M.sha(p)
def write(n,v):
 p=O/n;p.parent.mkdir(exist_ok=True,parents=True);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8');os.replace(tmp,p)
def save(p,v):
 p=Path(p);p.parent.mkdir(exist_ok=True,parents=True);tmp=p.with_suffix(p.suffix+'.tmp');torch.save(v,tmp);os.replace(tmp,p)
def table(n,rr):
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def arrsha(a):return hashlib.sha256(str(a.dtype).encode()+str(a.shape).encode()+a.tobytes()).hexdigest()
def freeze():
 assert read(PRE/'VERIFIED.json')['passed'] and read(P/'VERIFIED.json')['passed']
 protected=dict(read(P/'PANEL_COMPLETE.json')['protected_files'])
 for directory in [PRE,P]:
  for n,h in read(directory/'OUTPUT_MANIFEST.json').items():assert sha(directory/n)==h,n;protected[str((directory/n).relative_to(R))]=h
 for p in [PRE/'VERIFIED.json',PRE/'INITIAL_STATE.pt',P/'VERIFIED.json',P/'PUBLISHED.json',P/'FINAL_EVALUATION_POLICY.json',C/'FAIR_MODEL_CONTRACT.json',C/'FROZEN_INDICES.json',Path(__file__)]:protected[str(p.relative_to(R))]=sha(p)
 for p,h in protected.items():assert sha(R/p)==h,p
 contract=dict(authorization='user explicitly authorized seed42 Z/R/P each32 steps,bind new85H3 primary;supersedes old notraining flags without editing historical files',parent_training_contract=str((C/'FAIR_MODEL_CONTRACT.json').relative_to(R)),parent_sha=sha(C/'FAIR_MODEL_CONTRACT.json'),evaluation_policy=str((P/'FINAL_EVALUATION_POLICY.json').relative_to(R)),evaluation_sha=sha(P/'FINAL_EVALUATION_POLICY.json'),primary='validation H3 ALLendpoint sameboundary85units;root64,familymacro pairwise win;source macro andsource directions alongside;9000 main,9001 sensitivity',diagnostic_PO='old4val/4train unchanged AND newmain exactPO7val/2train separate,never pool into primary',hypothesis='report R-P andR-Z on primary at9000;alsoINIT difference,tag9001 andtwo sources;no predeclared minimum effect or significance gate;any positive result exploratory only',fixed='original21training triples/63contextfunctions/3families/126endpoints;shared savedINIT47360params;25d fullfreeQ DAG/roles/phase/LN/noBN/noDropout/noProjection;FP32 noAMP noTF32;Adam .0002 wd.001 clip1;same loss and schedule',arms=ARMS,seed=42,updates_each=32,initialization_sha=sha(PRE/'INITIAL_STATE.pt'),checkpoint_selection='fixedlast32 only;evaluate INIT andfinal after alltraining,never choose byval',evaluation_tags=[9000,9001],inference_shard_graphs=48,resume='atomic latestcheckpoint eacharm perupdate;skip completed updates;do not recompute successful training steps',finetune=0,SAT=0,test_reads=0,protected_files=protected)
 binding=hashlib.sha256(json.dumps(contract,sort_keys=True).encode()).hexdigest()
 if (O/'EXECUTION_CONTRACT.json').exists():assert read(O/'EXECUTION_CONTRACT.json')==contract
 else:write('EXECUTION_CONTRACT.json',contract)
 return contract,binding
def panels(loader):
 main=read(P/'MAIN_ALL_ENDPOINTS_SAME_BOUNDARY.json');oldpo=read(P/'STRICT_PO_REFERENCE_UNCHANGED.json');newpo=read(P/'CORE_EXACT_PO_DIAGNOSTIC.json');mainids={u['unit_id'] for u in main}
 result={'train_frozen_pool':list(loader.training.values()),'train_boundary_all':[u for u in main if u['split']=='train'],'val_boundary_all':[u for u in main if u['split']=='val'],'train_old_PO':[u for u in oldpo if u['split']=='train'],'val_old_PO':[u for u in oldpo if u['split']=='val'],'train_new_PO':[u for u in newpo if u['split']=='train' and u['parent_unit'] in mainids],'val_new_PO':[u for u in newpo if u['split']=='val' and u['parent_unit'] in mainids],'val_boundary_reduction':read(P/'BOUNDARY_REDUCTION_TRANSFER_DIAGNOSTIC.json'),'train_coverage_supplement':[u for u in read(P/'COVERAGE_SUPPLEMENT.json') if u['split']=='train'],'val_coverage_supplement':[u for u in read(P/'COVERAGE_SUPPLEMENT.json') if u['split']=='val']}
 assert len([u for u in result['val_boundary_all'] if u['tier']=='H3'])==85 and len(result['val_old_PO'])==4
 write('EVALUATION_PANELS.json',result);return result
def train(loader,contract,binding):
 initial=torch.load(PRE/'INITIAL_STATE.pt',map_location='cpu',weights_only=False);models={};initial_digest=initial['digest']
 if not (O/'INITIAL_STATE.pt').exists():shutil.copy2(PRE/'INITIAL_STATE.pt',O/'INITIAL_STATE.pt')
 assert sha(O/'INITIAL_STATE.pt')==contract['initialization_sha']
 for arm in ARMS:
  m=M.fresh('cuda');m.load_state_dict(initial['model']);assert M.state_digest(m)==initial_digest;assert sum(p.numel() for p in m.parameters())==47360
  opt=torch.optim.Adam(m.parameters(),lr=.0002,weight_decay=.001);state=dict(model=m,opt=opt,completed=0,history=[],gradient_present=collections.Counter())
  if (O/arm/'resume.pt').exists():
   ck=torch.load(O/arm/'resume.pt',map_location='cuda',weights_only=False);assert ck['binding']==binding and ck['initial_digest']==initial_digest;m.load_state_dict(ck['model']);opt.load_state_dict(ck['optimizer']);state.update(completed=ck['completed'],history=ck['history'],gradient_present=collections.Counter(ck['gradient_present']));del ck
  models[arm]=state
 torch.cuda.reset_peak_memory_stats();budget=[]
 with (PRE/'initial_loss_preview.csv').open(encoding='utf-8-sig') as f:reference=next(csv.DictReader(f))
 for update in range(1,33):
  if all(s['completed']>=update for s in models.values()):continue
  batch=loader.batch(update,'cuda');feature_sha=arrsha(batch['arrays']['x']);loss_input=batch['loss'];assert loss_input['candidates'].shape==(18,3) and loss_input['negative_edges'].shape==(18,2)
  for arm in ARMS:
   s=models[arm]
   if s['completed']>=update:continue
   assert s['completed']==update-1;m=s['model'];opt=s['opt'];m.train();opt.zero_grad(set_to_none=True);start=time.perf_counter();root,audit=m.encode(batch['graph']);pieces,totals,aux=M.objective(root,loss_input);loss=totals[arm];assert torch.isfinite(loss);std=float(root.detach().std(0,unbiased=False).mean());assert std>1e-5
   if update==1:assert abs(float(loss.detach())-float(reference['loss_'+arm]))<2e-5
   loss.backward();grad_present={n:p.grad is not None for n,p in m.named_parameters()};s['gradient_present'].update(n for n,has in grad_present.items() if has)
   assert all(p.grad is None or torch.isfinite(p.grad).all() for p in m.parameters());norm=torch.nn.utils.clip_grad_norm_(m.parameters(),1.);assert torch.isfinite(norm)
   opt.step();assert all(torch.isfinite(p).all() for p in m.parameters())
   row=dict(update=update,loss=float(loss.detach()),gradient_norm_before_clip=float(norm),root_mean_std=std,feature_sha=feature_sha,context_families=3,unit_slots=3,queries=18,candidate_distances=54,common_negative_terms=18,boundary_tag=update,seconds=time.perf_counter()-start,gradient_present=grad_present,consumed_nodes=audit['consumed_nodes'],consumed_edges=audit['consumed_pin_edges'],**{k:float(v.detach()) for k,v in pieces.items()});s['history'].append(row);s['completed']=update
   save(O/arm/'resume.pt',dict(binding=binding,initial_digest=initial_digest,completed=update,model=m.state_dict(),optimizer=opt.state_dict(),history=s['history'],gradient_present=dict(s['gradient_present'])));write(arm+'/history.json',s['history'])
   if update==1:write(arm+'/FIRST_STEP.json',dict(passed=True,loss=row['loss'],root_mean_std=std,gradient_norm_before_clip=float(norm),peak_gpu_bytes=torch.cuda.max_memory_allocated(),preflight_initial_loss_matches=True))
   if update==1 or update%8==0:print('UPDATE',arm,update,'loss',round(row['loss'],5),'std',round(std,5),flush=True)
   del root,pieces,totals,aux,loss
  budget.append(dict(update=update,feature_sha=feature_sha,unit_slots=3,query_slots=18,candidate_distances=54,common_negative_terms=18))
  del batch;gc.collect();torch.cuda.empty_cache()
 audits=[]
 for arm,s in models.items():
  assert s['completed']==32 and [r['update'] for r in s['history']]==list(range(1,33));m=s['model'];opt=s['opt'];steps={n:int(opt.state[p]['step']) if p in opt.state else 0 for n,p in m.named_parameters()};assert steps==dict(s['gradient_present'])
  write(arm+'/COMPLETE.json',dict(updates=32,optimizer_step_calls=32,per_parameter_actual_steps=steps,per_parameter_gradient_presence=dict(s['gradient_present']),checkpoint_sha=sha(O/arm/'resume.pt'),initial_digest=initial_digest,final_digest=M.state_digest(m),selection='fixedlast32',no_missing_or_repeated_updates=True))
  audits.append(dict(arm=arm,updates=32,checkpoint_sha=sha(O/arm/'resume.pt'),model_digest=M.state_digest(m)))
 for u in range(32):
  hh=[s['history'][u] for s in models.values()];assert len({r['feature_sha'] for r in hh})==1 and all(r['gradient_present']==hh[0]['gradient_present'] for r in hh)
 write('TRAINING_COMPLETE.json',dict(arms=ARMS,actual_optimizer_updates=96,updates_each=32,per_arm_budget=read(C/'SUPERVISION_BUDGET.json'),same_features_targets_and_parameter_usage=True,peak_gpu_bytes=torch.cuda.max_memory_allocated(),finetune=0,SAT=0,test_reads=0));table('checkpoint_audit.csv',audits)
 print('ALL_THREE32_TRAINING_COMPLETE',flush=True)
 del models;gc.collect();torch.cuda.empty_cache()
def evaluate(loader,pp,contract):
 expanded=PanelLoader()
 # Reuse original126 train endpoints absent from the evaluation-only expanded panel.
 for u in pp['train_frozen_pool']:
  for c in u['cones']:
   if c in expanded.graphs:
    for key in ['op','slot','level','edge','root']:assert expanded.graphs[c][key]==loader.graphs[c][key]
   else:expanded.graphs[c]=loader.graphs[c];expanded.contexts[c]=loader.contexts[c]
 states=['INIT',*ARMS];forwards=0;records=[];cache=[]
 for domain in ['train','val']:
  uu=[u for name,rows in pp.items() if name.startswith(domain+'_') for u in rows];ids=sorted({c for u in uu for c in u['cones']})
  for tag in [9000,9001]:
   needed=[arm for arm in states if not (O/f'{domain}_{arm}_tag{tag}.npz').exists()]
   if not needed:continue
   ms={};buffers={arm:{'root64':[],'mean64':[],'concat128':[]} for arm in needed};before={}
   for arm in needed:
    m=M.fresh('cuda');ck=torch.load(O/'INITIAL_STATE.pt' if arm=='INIT' else O/arm/'resume.pt',map_location='cuda',weights_only=False)
    if arm!='INIT':assert ck['completed']==32
    m.load_state_dict(ck['model']);m.eval();ms[arm]=m;before[arm]=M.state_digest(m);del ck
   for start in range(0,len(ids),48):
    batchids=ids[start:start+48];arrays=expanded.arrays(batchids,tag);b=M.pack(arrays,'cuda')
    for arm,m in ms.items():
     with torch.inference_mode():out,audit=m.readouts(b)
     assert audit['consumed_nodes']==b['nodes'] and audit['consumed_pin_edges']==b['edges'];assert all(torch.isfinite(v).all() for v in out.values())
     for key,v in out.items():buffers[arm][key].append(v.cpu().numpy())
     forwards+=1;records.append(dict(domain=domain,tag=tag,arm=arm,shard=start//48,graphs=len(batchids),nodes=b['nodes'],depth=b['max_level'],weights_unchanged=M.state_digest(m)==before[arm]))
     del out
    del b,arrays;gc.collect();torch.cuda.empty_cache()
   for arm,m in ms.items():
    assert M.state_digest(m)==before[arm];z={k:np.concatenate(v,0) for k,v in buffers[arm].items()};np.savez_compressed(O/f'{domain}_{arm}_tag{tag}.npz',cone_ids=np.array(ids),**z);cache.append(dict(domain=domain,tag=tag,arm=arm,cones=len(ids),file=f'{domain}_{arm}_tag{tag}.npz'))
   print('EVALUATED',domain,'tag',tag,'states',needed,'cones',len(ids),flush=True);del ms,buffers;gc.collect();torch.cuda.empty_cache()
 table('evaluation_forward_audit.csv',records);write('EVALUATION_COMPLETE.json',dict(new_forwards_this_execution=forwards,cache_files=cache,weights_and_buffers_unchanged=True,selection='INIT andfixedlast32 only;no valchoice',finetune=0,SAT=0,test_reads=0))
def main():
 assert 'ginvenv_gpu' in sys.executable and torch.cuda.is_available();torch.set_num_threads(1);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False;start=time.perf_counter()
 contract,binding=freeze();loader=M.Loader();pp=panels(loader)
 if not (O/'TRAINING_COMPLETE.json').exists():train(loader,contract,binding)
 else:
  for arm in ARMS:assert read(O/arm/'COMPLETE.json')['checkpoint_sha']==sha(O/arm/'resume.pt')
 evaluate(loader,pp,contract)
 for p,h in contract['protected_files'].items():assert sha(R/p)==h,p
 write('COMPLETE.json',dict(actual_optimizer_updates=96,updates_each=32,arms=ARMS,old_files_unchanged=True,evaluation_completed=True,finetune=0,SAT=0,test_reads=0,seconds_this_execution=time.perf_counter()-start))
 print('TRAINING_AND_EVALUATION_COMPLETE',flush=True)
if __name__=='__main__':
 try:main()
 except Exception:
  O.mkdir(exist_ok=True);(O/f'failure_{time.strftime("%H%M%S")}.log').write_text(traceback.format_exc(),encoding='utf-8');raise
