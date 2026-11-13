"""Authorized frozen six-arm two-code training; no detector or SAT."""
import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import collections,csv,gc,hashlib,json,shutil,sys,time,traceback
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;PRE=R/'_p0pilot/cec_dualcode_preflight_20261107';BASE=R/'_p0pilot/cec_freeq_preflight_20261106';C=R/'_p0pilot/cec_repaired_contract_20261107'
sys.path.insert(0,str(PRE));import dual_interface as D
M=D.M;torch=M.torch
def read(p):return M.read(p)
def sha(p):return M.sha(p)
def write(n,v):
 p=O/n;p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8');os.replace(tmp,p)
def save(p,v):
 p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp');torch.save(v,tmp);os.replace(tmp,p)
def arrsha(a):return hashlib.sha256(str(a.dtype).encode()+str(a.shape).encode()+a.tobytes()).hexdigest()
def table(n,rr):
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def freeze():
 assert read(PRE/'VERIFIED.json')['passed'];parent=read(PRE/'FROZEN_TRAINING_CONTRACT.json');protected=dict(read(PRE/'PREFLIGHT_CONTRACT.json')['protected_files'])
 for n,h in read(PRE/'OUTPUT_MANIFEST.json').items():assert sha(PRE/n)==h,n;protected[str((PRE/n).relative_to(R))]=h
 for p in [PRE/'PUBLISHED.json',Path(__file__)]:protected[str(p.relative_to(R))]=sha(p)
 contract=dict(authorization='user explicitly authorized sixarms seed42 each32 training;supersedes historical prepared flags only in this execution record',parent=parent,parent_sha=sha(PRE/'FROZEN_TRAINING_CONTRACT.json'),coefficient=parent['coefficient'],evaluation_tags=list(range(9000,9012)),inference_shard_graphs=128,protected_files=protected,finetune=0,SAT=0,test_reads=0,resume='atomic latest perarm perupdate;skip committed updates')
 if (O/'EXECUTION_CONTRACT.json').exists():assert read(O/'EXECUTION_CONTRACT.json')==contract
 else:write('EXECUTION_CONTRACT.json',contract)
 for p,h in protected.items():assert sha(R/p)==h,p
 return contract,hashlib.sha256(json.dumps(contract,sort_keys=True).encode()).hexdigest()
def train(loader,contract,binding):
 initial=torch.load(BASE/'INITIAL_STATE.pt',map_location='cpu',weights_only=False)
 if not (O/'INITIAL_STATE.pt').exists():shutil.copy2(BASE/'INITIAL_STATE.pt',O/'INITIAL_STATE.pt')
 assert sha(O/'INITIAL_STATE.pt')==contract['parent']['initial_sha'];states={}
 for arm in D.ARMS:
  m=M.fresh('cuda');m.load_state_dict(initial['model']);assert M.state_digest(m)==initial['digest'];opt=torch.optim.Adam(m.parameters(),lr=.0002,weight_decay=.001);state=dict(model=m,opt=opt,completed=0,history=[],gradient_presence=collections.Counter())
  if (O/arm/'resume.pt').exists():
   ck=torch.load(O/arm/'resume.pt',map_location='cuda',weights_only=False);assert ck['binding']==binding and ck['initial_digest']==initial['digest'];m.load_state_dict(ck['model']);opt.load_state_dict(ck['optimizer']);state.update(completed=ck['completed'],history=ck['history'],gradient_presence=collections.Counter(ck['gradient_presence']))
  states[arm]=state
 reference={r['arm']:float(r['loss']) for r in csv.DictReader((PRE/'six_actual_clone_checks.csv').open(encoding='utf-8-sig'))};torch.cuda.reset_peak_memory_stats()
 for step in range(1,33):
  if all(s['completed']>=step for s in states.values()):continue
  a,b=D.dualbatch(loader,step);hasha=arrsha(a['arrays']['x']);hashb=arrsha(b['arrays']['x'])
  for arm,s in states.items():
   if s['completed']>=step:continue
   assert s['completed']==step-1;m=s['model'];opt=s['opt'];m.train();opt.zero_grad(set_to_none=True);start=time.perf_counter();za,aa=m.encode(a['graph']);zb,ab=m.encode(b['graph']);parts,base,j,totals,_,_=D.objective(za,zb,a['loss'],contract['coefficient']);loss=totals[arm]
   assert torch.isfinite(loss) and float(j.detach())>=-1e-7;std=min(float(za.detach().std(0,unbiased=False).mean()),float(zb.detach().std(0,unbiased=False).mean()));assert std>1e-5
   if step==1:assert abs(float(loss.detach())-reference[arm])<2e-5
   loss.backward();present={n:p.grad is not None for n,p in m.named_parameters()};assert all(p.grad is None or torch.isfinite(p.grad).all() for p in m.parameters());s['gradient_presence'].update(n for n,v in present.items() if v);norm=torch.nn.utils.clip_grad_norm_(m.parameters(),1.);assert torch.isfinite(norm);opt.step();assert all(torch.isfinite(p).all() for p in m.parameters())
   row=dict(step=step,loss=float(loss.detach()),JS=float(j.detach()),base_loss=float(base[arm[0]].detach()),gradient_norm=float(norm),min_root_std=std,feature_a_sha=hasha,feature_b_sha=hashb,gradient_presence=present,logical_units=2,logical_queries=12,encoded_units=4,encoded_queries=24,candidate_distances=72,common_negatives=24,JS_queries=12,seconds=time.perf_counter()-start,**{k:float(v.detach()) for k,v in parts.items()});s['history'].append(row);s['completed']=step
   save(O/arm/'resume.pt',dict(binding=binding,initial_digest=initial['digest'],completed=step,model=m.state_dict(),optimizer=opt.state_dict(),history=s['history'],gradient_presence=dict(s['gradient_presence'])));write(arm+'/history.json',s['history'])
   if step==1:write(arm+'/FIRST_STEP.json',dict(passed=True,loss=row['loss'],std=std,preflight_matched=True,peak_allocated_gpu_bytes=torch.cuda.max_memory_allocated()))
   if step==1 or step%8==0:print('UPDATE',arm,step,'loss',round(row['loss'],5),'JS',round(row['JS'],6),flush=True)
   del za,zb,parts,base,j,totals,loss
  del a,b;gc.collect();torch.cuda.empty_cache()
 for arm,s in states.items():
  assert s['completed']==32 and [r['step'] for r in s['history']]==list(range(1,33));m=s['model'];opt=s['opt'];actual={n:int(opt.state[p]['step']) for n,p in m.named_parameters()};assert actual==dict(s['gradient_presence'])
  write(arm+'/COMPLETE.json',dict(updates=32,checkpoint_sha=sha(O/arm/'resume.pt'),per_parameter_steps=actual,initial_digest=initial['digest'],final_digest=M.state_digest(m),no_repeated_or_missing_updates=True))
 for i in range(32):
  hh=[s['history'][i] for s in states.values()];assert len({r['feature_a_sha'] for r in hh})==len({r['feature_b_sha'] for r in hh})==1 and all(r['gradient_presence']==hh[0]['gradient_presence'] for r in hh)
 write('TRAINING_COMPLETE.json',dict(actual_updates=192,updates_each=32,arms=D.ARMS,peak_allocated_gpu_bytes=torch.cuda.max_memory_allocated(),finetune=0,SAT=0,test_reads=0));print('SIX_ARM_TRAINING_COMPLETE',flush=True);del states;gc.collect();torch.cuda.empty_cache()
def evaluate(loader,contract):
 sys.path.insert(0,str(R/'_p0pilot/cec_boundary_panel_expand_20261107'));from panel_loader import PanelLoader
 panel=R/'_p0pilot/cec_boundary_panel_expand_20261107';pp={'train_frozen_pool':read(C/'TRAIN_TRIPLES.json'),'val_H3_primary':read(C/'VAL_H3_NONFORCED.json'),'val_old_PO':[u for u in read(panel/'STRICT_PO_REFERENCE_UNCHANGED.json') if u['split']=='val'],'val_new_PO':[u for u in read(panel/'CORE_EXACT_PO_DIAGNOSTIC.json') if u['split']=='val']};write('EVALUATION_PANELS.json',pp);pl=PanelLoader();models={};digests={};audit=[]
 for arm in ['INIT',*D.ARMS]:
  m=M.fresh('cuda');ck=torch.load(O/('INITIAL_STATE.pt' if arm=='INIT' else arm+'/resume.pt'),map_location='cuda',weights_only=False);m.load_state_dict(ck['model']);m.eval();models[arm]=m;digests[arm]=M.state_digest(m)
 for tag in contract['evaluation_tags']:
  for domain in ['train','val']:
   uu=[u for group,units in pp.items() if group.startswith(domain+'_') for u in units];ids=sorted({c for u in uu for c in u['cones']});needed=[arm for arm in models if not (O/f'{domain}_{arm}_tag{tag}.npz').exists()]
   if not needed:continue
   buffers={arm:[] for arm in needed}
   for off in range(0,len(ids),128):
    g=M.pack(pl.arrays(ids[off:off+128],tag),'cuda')
    for arm in needed:
     with torch.inference_mode():z,au=models[arm].encode(g)
     assert torch.isfinite(z).all() and au['consumed_nodes']==g['nodes'] and au['consumed_pin_edges']==g['edges'];buffers[arm].append(z.cpu().numpy());audit.append(dict(tag=tag,domain=domain,arm=arm,shard=off//128,graphs=min(128,len(ids)-off),nodes=g['nodes'],weights_unchanged=M.state_digest(models[arm])==digests[arm]))
    del g;gc.collect();torch.cuda.empty_cache()
   for arm in needed:
    tmp=O/f'{domain}_{arm}_tag{tag}.tmp.npz';np.savez_compressed(tmp,cone_ids=np.array(ids),root64=np.concatenate(buffers[arm]));os.replace(tmp,O/f'{domain}_{arm}_tag{tag}.npz')
  print('EVALUATED_TAG',tag,flush=True)
 assert all(M.state_digest(m)==digests[arm] for arm,m in models.items());table('evaluation_forward_audit.csv',audit);write('EVALUATION_COMPLETE.json',dict(new_forwards_this_execution=len(audit),states_unchanged=True,finetune=0,SAT=0,test_reads=0))
def main():
 assert 'ginvenv_gpu' in sys.executable and torch.cuda.is_available();torch.set_num_threads(1);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False;start=time.perf_counter();contract,binding=freeze();loader=D.pf.Loader()
 if not (O/'TRAINING_COMPLETE.json').exists():train(loader,contract,binding)
 else:
  for arm in D.ARMS:assert read(O/arm/'COMPLETE.json')['checkpoint_sha']==sha(O/arm/'resume.pt')
 evaluate(loader,contract)
 for p,h in contract['protected_files'].items():assert sha(R/p)==h,p
 write('COMPLETE.json',dict(actual_optimizer_updates=192,updates_each=32,seconds_this_execution=time.perf_counter()-start,old_files_unchanged=True,finetune=0,SAT=0,test_reads=0));print('SIX_ARM_TRAIN_EVAL_COMPLETE',flush=True)
if __name__=='__main__':
 try:main()
 except Exception:(O/f'failure_{time.strftime("%H%M%S")}.log').write_text(traceback.format_exc(),encoding='utf-8');raise
