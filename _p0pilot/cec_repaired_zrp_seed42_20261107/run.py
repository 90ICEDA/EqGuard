import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import collections,csv,gc,hashlib,json,shutil,sys,time,traceback
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent
PRE=R/'_p0pilot/cec_freeq_preflight_20261106';C=R/'_p0pilot/cec_repaired_contract_20261107';PREF=R/'_p0pilot/cec_repaired_preflight_20261107'
sys.path.insert(0,str(R/'_p0pilot/cec_freeq_zrp_seed42_20261107'))
import run as original
sys.path.insert(0,str(PREF));import run as unused
# Load preflight module explicitly to avoid its generic name colliding with old runner.
import importlib.util
spec=importlib.util.spec_from_file_location('repaired_preflight',PREF/'run.py');pf=importlib.util.module_from_spec(spec);spec.loader.exec_module(pf)
M=pf.M;torch=M.torch;ARMS=['Z','R','P']
read=original.read;sha=original.sha;arrsha=original.arrsha
original.O=O
write=original.write;save=original.save;table=original.table
def freeze():
 assert read(PREF/'VERIFIED.json')['passed']
 protected=dict(read(PREF/'EXECUTION_CONTRACT.json')['protected_files'])
 for folder in [PREF,C,R/'_p0pilot/cec_freeq_zrp_seed42_20261107']:
  for p in folder.iterdir():
   if p.is_file() and p.suffix in ['.json','.py','.csv','.pt','.npz']:protected[str(p.relative_to(R))]=sha(p)
 protected[str(Path(__file__).relative_to(R))]=sha(Path(__file__))
 contract=dict(authorization='user authorized repaired seed42 Z/R/P each32 steps;supersedes historical prepared-only flags without editing them',initialization_sha=sha(PRE/'INITIAL_STATE.pt'),arms=ARMS,seed=42,updates_each=32,primary='73 repaired H3 validation units,root64 familymacro pairwise win;9000 primary,9001 predefined sensitivity',checkpoint='fixedlast32 only,no validation selection',fixed='7 triples/21classes/4sources/2families;47360params,old init,25d fullfreeQ DAG roles/phase;Adam lr.0002 wd.001 clip1;FP32/noTF32/noAMP;same objectives and schedule',budget=read(C/'BUDGET.json'),evaluation_tags=[9000,9001],finetune=0,SAT=0,test_reads=0,protected_files=protected)
 if (O/'EXECUTION_CONTRACT.json').exists():assert read(O/'EXECUTION_CONTRACT.json')==contract
 else:write('EXECUTION_CONTRACT.json',contract)
 for p,h in protected.items():assert sha(R/p)==h,p
 return contract,hashlib.sha256(json.dumps(contract,sort_keys=True).encode()).hexdigest()
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
 with (PREF/'loaded_batches.csv').open(encoding='utf-8-sig') as f:reference=next(csv.DictReader(f))
 for update in range(1,33):
  if all(s['completed']>=update for s in models.values()):continue
  batch=loader.batch(update,'cuda');feature_sha=arrsha(batch['arrays']['x']);loss_input=batch['loss'];assert loss_input['candidates'].shape==(12,3) and loss_input['negative_edges'].shape==(12,2)
  for arm in ARMS:
   s=models[arm]
   if s['completed']>=update:continue
   assert s['completed']==update-1;m=s['model'];opt=s['opt'];m.train();opt.zero_grad(set_to_none=True);start=time.perf_counter();root,audit=m.encode(batch['graph']);pieces,totals,aux=M.objective(root,loss_input);loss=totals[arm];assert torch.isfinite(loss);std=float(root.detach().std(0,unbiased=False).mean());assert std>1e-5
   if update==1:assert abs(float(loss.detach())-float(reference['loss_'+arm]))<2e-5
   loss.backward();grad_present={n:p.grad is not None for n,p in m.named_parameters()};s['gradient_present'].update(n for n,has in grad_present.items() if has)
   assert all(p.grad is None or torch.isfinite(p.grad).all() for p in m.parameters());norm=torch.nn.utils.clip_grad_norm_(m.parameters(),1.);assert torch.isfinite(norm)
   opt.step();assert all(torch.isfinite(p).all() for p in m.parameters())
   row=dict(update=update,loss=float(loss.detach()),gradient_norm_before_clip=float(norm),root_mean_std=std,feature_sha=feature_sha,context_families=2,unit_slots=2,queries=12,candidate_distances=36,common_negative_terms=12,boundary_tag=update,seconds=time.perf_counter()-start,gradient_present=grad_present,consumed_nodes=audit['consumed_nodes'],consumed_edges=audit['consumed_pin_edges'],**{k:float(v.detach()) for k,v in pieces.items()});s['history'].append(row);s['completed']=update
   save(O/arm/'resume.pt',dict(binding=binding,initial_digest=initial_digest,completed=update,model=m.state_dict(),optimizer=opt.state_dict(),history=s['history'],gradient_present=dict(s['gradient_present'])));write(arm+'/history.json',s['history'])
   if update==1:write(arm+'/FIRST_STEP.json',dict(passed=True,loss=row['loss'],root_mean_std=std,gradient_norm_before_clip=float(norm),peak_gpu_bytes=torch.cuda.max_memory_allocated(),preflight_initial_loss_matches=True))
   if update==1 or update%8==0:print('UPDATE',arm,update,'loss',round(row['loss'],5),'std',round(std,5),flush=True)
   del root,pieces,totals,aux,loss
  budget.append(dict(update=update,feature_sha=feature_sha,unit_slots=2,query_slots=12,candidate_distances=36,common_negative_terms=12))
  del batch;gc.collect();torch.cuda.empty_cache()
 audits=[]
 for arm,s in models.items():
  assert s['completed']==32 and [r['update'] for r in s['history']]==list(range(1,33));m=s['model'];opt=s['opt'];steps={n:int(opt.state[p]['step']) if p in opt.state else 0 for n,p in m.named_parameters()};assert steps==dict(s['gradient_present'])
  write(arm+'/COMPLETE.json',dict(updates=32,optimizer_step_calls=32,per_parameter_actual_steps=steps,per_parameter_gradient_presence=dict(s['gradient_present']),checkpoint_sha=sha(O/arm/'resume.pt'),initial_digest=initial_digest,final_digest=M.state_digest(m),selection='fixedlast32',no_missing_or_repeated_updates=True))
  audits.append(dict(arm=arm,updates=32,checkpoint_sha=sha(O/arm/'resume.pt'),model_digest=M.state_digest(m)))
 for u in range(32):
  hh=[s['history'][u] for s in models.values()];assert len({r['feature_sha'] for r in hh})==1 and all(r['gradient_present']==hh[0]['gradient_present'] for r in hh)
 write('TRAINING_COMPLETE.json',dict(arms=ARMS,actual_optimizer_updates=96,updates_each=32,per_arm_budget=read(C/'BUDGET.json'),same_features_targets_and_parameter_usage=True,peak_gpu_bytes=torch.cuda.max_memory_allocated(),finetune=0,SAT=0,test_reads=0));table('checkpoint_audit.csv',audits)
 print('ALL_THREE32_TRAINING_COMPLETE',flush=True)
 del models;gc.collect();torch.cuda.empty_cache()

def main():
 assert 'ginvenv_gpu' in sys.executable and torch.cuda.is_available()
 torch.set_num_threads(1);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
 start=time.perf_counter();contract,binding=freeze();loader=pf.Loader()
 # Diagnostic PO units are unchanged. Main eligibility is the repaired73 only.
 panel=R/'_p0pilot/cec_boundary_panel_expand_20261107'
 pp={'train_frozen_pool':list(loader.training.values()),'val_boundary_all':read(C/'VAL_H3_NONFORCED.json'),'val_old_PO':[u for u in read(panel/'STRICT_PO_REFERENCE_UNCHANGED.json') if u['split']=='val'],'val_new_PO':[u for u in read(panel/'CORE_EXACT_PO_DIAGNOSTIC.json') if u['split']=='val']}
 assert len(pp['val_boundary_all'])==73
 write('EVALUATION_PANELS.json',pp)
 if not (O/'TRAINING_COMPLETE.json').exists():train(loader,contract,binding)
 else:
  for arm in ARMS:assert read(O/arm/'COMPLETE.json')['checkpoint_sha']==sha(O/arm/'resume.pt')
 original.evaluate(loader,pp,contract)
 for p,h in contract['protected_files'].items():assert sha(R/p)==h,p
 write('COMPLETE.json',dict(actual_optimizer_updates=96,updates_each=32,arms=ARMS,old_files_unchanged=True,evaluation_completed=True,finetune=0,SAT=0,test_reads=0,seconds_this_execution=time.perf_counter()-start))
 print('REPAIRED_TRAINING_AND_EVALUATION_COMPLETE',flush=True)
if __name__=='__main__':
 try:main()
 except Exception:
  (O/f'failure_{time.strftime("%H%M%S")}.log').write_text(traceback.format_exc(),encoding='utf-8');raise
