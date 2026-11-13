"""Authorized frozen five-arm seed42 pretraining; fixed50, no detector or SAT."""
import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import collections,csv,gc,hashlib,importlib.util,json,sys,time,traceback
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;PRE=R/'_p0pilot/cec_relative_preflight_20261106';C=R/'_p0pilot/cec_relative_contract_20261106'
sys.path.insert(0,str(PRE));from interface import Interface,read,sha,terms,audit_loaded,ARMS
spec=importlib.util.spec_from_file_location('frozen_pin_semantics',R/'_p0pilot/cec_pinrole_effective_20261106/run.py');A=importlib.util.module_from_spec(spec);spec.loader.exec_module(A)
B=A.B;D=A.D;E=A.E;torch=A.torch
def write(n,x):E.write(O/n,x)
def table(n,rr):
 if not rr:return
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def state_digest(m,h):
 hh=hashlib.sha256()
 for pre,mod in [('model',m),('projection',h)]:
  for n,t in sorted(mod.state_dict().items()):hh.update((pre+n+str(t.dtype)+str(tuple(t.shape))).encode());hh.update(t.detach().cpu().contiguous().numpy().tobytes())
 return hh.hexdigest()
def pool_spec(ids,cones):
 ll=torch.tensor([len(cones[c]['graph_rows']) for c in ids],device='cuda');roots=torch.tensor([cones[c]['root_row'] for c in ids],device='cuda');flat=torch.tensor([r for c in ids for r in cones[c]['graph_rows']],device='cuda');seg=torch.repeat_interleave(torch.arange(len(ids),device='cuda'),ll)
 return roots,ll,flat,seg
def pool(h,sp):
 roots,ll,flat,seg=sp;means=torch.zeros(len(ll),64,device='cuda').index_add_(0,seg,h[flat].float())/ll[:,None];return torch.cat([h[roots],means.to(h.dtype)],1)
def main():
 assert 'ginvenv_gpu' in sys.executable and torch.cuda.is_available()
 i=Interface();assert read(PRE/'VERIFIED.json')['passed'];pv=read(C/'VERIFIED.json');frozen=dict(i.contract['protected_files']);frozen.update(read(C/'PROVENANCE_VERIFIED.json')['query_files_sha'])
 for n,h in pv['indices_sha'].items():assert sha(C/n)==h;frozen[str((C/n).relative_to(R))]=h
 for p,h in read(PRE/'EXECUTION_CONTRACT.json')['frozen_files'].items():assert sha(R/p)==h;frozen[p]=h
 for p in [Path(__file__),PRE/'interface.py',PRE/'VERIFIED.json',PRE/'gradient_summary.csv',C/'evaluation_panel.json']:
  frozen[str(p.relative_to(R))]=sha(p)
 for p,h in frozen.items():assert sha(R/p)==h,p
 contract=dict(frozen_files=frozen,arms=ARMS,seed=42,updates_each=50,authorization='user explicitly requested seed42 five arms50steps; supersedes previous not-yet-authorized status without editing old contract',optimizer='Adam lr.0002 wd.001 clip1',initialization='original init_s42,all semantic parameters zero,projection819',fixed='graph39v3/correctboundary+MUX/dropout.2/BNtrain/BF16/weights/schedule',selection='fixedlast50;no validation choice;one common RNG seed100042+update across arms',evaluation='fixed existing60val triples,remap9000;primarytwo sources>=8triples;four-direction same-anchor root64 ordering',pin_check='S_R final correct vs existing all-view role derangement vs pin-disabled/shared-boundary-retained;diagnostic only,no posthoc acceptance threshold',finetune=0,SAT=0,test_reads=0,interleaving='outer update,inner fivearms;share feature preparation only;independent model/head/optimizer;resume completed steps without recomputing')
 binding=hashlib.sha256(json.dumps(contract,sort_keys=True).encode()).hexdigest()
 if (O/'EXECUTION_CONTRACT.json').exists():assert read(O/'EXECUTION_CONTRACT.json')==contract
 else:write('EXECUTION_CONTRACT.json',contract)
 details,loaded=audit_loaded(i);table('loaded_budget_per_step.csv',details);write('LOADING_VERIFIED.json',loaded)
 E.set_inputs();scratch=O/'pin_loader';scratch.mkdir(exist_ok=True);D.O=scratch;B.O=scratch;b=D.PinBoundary(E.T.CONTRACT,i.cones)
 x,e=B.graph('trans_train');models={};initial_sha=None
 for arm in ARMS:
  out=O/arm;out.mkdir(exist_ok=True);m,head=D.initial();digest=state_digest(m,head)
  if initial_sha is None:initial_sha=digest;E.save(O/'INITIAL_STATE.pt',dict(model=m.state_dict(),projection=head.state_dict(),digest=digest))
  assert digest==initial_sha;initial_model={k:v.detach().clone() for k,v in m.state_dict().items() if k.startswith(('classifier.','fn_head.'))}
  opt=torch.optim.Adam([p for p in m.parameters() if p.requires_grad]+list(head.parameters()),lr=.0002,weight_decay=.001);hist=[];completed=0
  if (out/'resume.pt').exists():
   ck=torch.load(out/'resume.pt',map_location='cuda',weights_only=False);assert ck['binding']==binding and ck['initial_sha']==initial_sha;m.load_state_dict(ck['model']);head.load_state_dict(ck['projection']);opt.load_state_dict(ck['optimizer']);hist=ck['history'];completed=ck['completed'];del ck
  models[arm]=dict(m=m,head=head,opt=opt,history=hist,completed=completed,initial_unchanged_heads=initial_model)
 write('INITIALIZATION_VERIFIED.json',dict(all_five_same_initial_digest=initial_sha,initial_state_sha=sha(O/'INITIAL_STATE.pt'),parameters=52455,projection_parameters=10336,semantic_parameters_zero=True,classifier_frozen=True))
 torch.cuda.reset_peak_memory_stats()
 for u in range(min(v['completed'] for v in models.values())+1,51):
  batch=i.batches[u];bt=i.tensors(batch,'cuda');side=b.features('trans_train','shared',u);sp=pool_spec(batch['cone_ids'],i.cones)
  for arm in ARMS:
   v=models[arm]
   if v['completed']>=u:continue
   assert v['completed']==u-1;m,head,opt=v['m'],v['head'],v['opt'];m.train();head.train();opt.zero_grad(set_to_none=True);E.seed_all(100042+u);start=time.perf_counter()
   with torch.autocast('cuda',dtype=torch.bfloat16):
    h=m.encode(x,e,side);pooled=pool(h,sp);z=head(pooled);parts,totals,aux=terms(z,bt);loss=totals[arm]
   assert torch.isfinite(loss);std=float(z.detach().float().std(0,unbiased=False).mean());loss.backward();norm=torch.nn.utils.clip_grad_norm_([p for p in m.parameters() if p.requires_grad]+list(head.parameters()),1.);assert torch.isfinite(norm)
   if u==1:assert std>.01 and torch.cuda.max_memory_allocated()/torch.cuda.get_device_properties(0).total_memory<.95
   opt.step();assert all(torch.isfinite(p).all() for p in list(m.parameters())+list(head.parameters()))
   assert all(torch.equal(t,m.state_dict()[k]) for k,t in v['initial_unchanged_heads'].items())
   row=dict(update=u,seconds=time.perf_counter()-start,loss=float(loss.detach()),grad_norm=float(norm),projection_std=std,source_count=len(batch['rows']),triple_ids=[r['triple_id'] for r in batch['rows']],queries=len(batch['anchors']),common_negatives=len(batch['negative_edges']),boundary_tag=u,rng_seed=100042+u,**{k:float(t.detach()) for k,t in parts.items()})
   v['history'].append(row);v['completed']=u
   E.save(O/arm/'resume.pt',dict(binding=binding,initial_sha=initial_sha,completed=u,model=m.state_dict(),projection=head.state_dict(),optimizer=opt.state_dict(),history=v['history']))
   E.write(O/arm/'history.json',v['history'])
   if u==1:write(arm+'/FIRST_STEP.json',dict(passed=True,peak_bytes=torch.cuda.max_memory_allocated(),std=std,loss=row['loss'],grad_norm=row['grad_norm']))
   if u==1 or u%10==0:print('UPDATE',arm,u,'loss',round(row['loss'],5),'std',round(std,5),flush=True)
   del h,pooled,z,parts,totals,aux,loss
  del bt,side,sp;gc.collect()
 for arm,v in models.items():
  assert v['completed']==50 and [r['update'] for r in v['history']]==list(range(1,51))
  steps={int(s['step']) for s in v['opt'].state.values() if 'step' in s};assert steps=={50}
  write(arm+'/COMPLETE.json',dict(updates=50,checkpoint_sha=sha(O/arm/'resume.pt'),initial_sha=initial_sha,optimizer_actual_steps=50,selected='fixedlast50',no_repeated_updates=True,classifier_and_unused_function_head_unchanged=True))
 peak=torch.cuda.max_memory_allocated();write('TRAINING_COMPLETE.json',dict(arms=ARMS,actual_optimizer_updates=250,updates_each=50,initial_sha=initial_sha,peak_gpu_bytes=peak,no_finetune=True,SAT=0,test_reads=0))
 del x,e;gc.collect();torch.cuda.empty_cache()
 # Evaluate all arms only after the full fixed training budget, never select by val.
 certs=read(C/'evaluation_panel.json');ids=sorted({c for t in certs for c in t['cones']});x,e=B.graph('trans_val');side=b.features('trans_val','shared',9000);sp=pool_spec(ids,i.cones);evaluation_forwards=0
 for arm,v in models.items():
  m,head=v['m'],v['head'];m.eval();head.eval();before=state_digest(m,head)
  with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):
   hh=m.encode(x,e,side);uu=pool(hh,sp);zz=head(uu)
  np.savez_compressed(O/f'val_{arm}_remap9000.npz',cone_ids=np.array(ids),concat128=uu.float().cpu().numpy(),projection32=zz.float().cpu().numpy());evaluation_forwards+=1
  assert state_digest(m,head)==before;del hh,uu,zz
 # Predeclared fixed S_R semantic sensitivity; no model updates or new proof.
 m,head=models['S_R']['m'],models['S_R']['head'];before=state_digest(m,head)
 for mode in ['wrong_roles','pin_disabled_boundary_retained']:
  ss=b.features('trans_val','viewshuffle' if mode=='wrong_roles' else 'shared',9000)
  if mode=='pin_disabled_boundary_retained':ss['pin_boundary']=torch.zeros_like(ss['pin_boundary']);ss['internal']=tuple(v[:0] for v in ss['internal'])
  with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):hh=m.encode(x,e,ss);uu=pool(hh,sp);zz=head(uu)
  np.savez_compressed(O/f'sensitivity_S_R_{mode}.npz',cone_ids=np.array(ids),concat128=uu.float().cpu().numpy(),projection32=zz.float().cpu().numpy());evaluation_forwards+=1;del hh,uu,zz,ss
 assert state_digest(m,head)==before
 for p,h in frozen.items():assert sha(R/p)==h,p
 write('COMPLETE.json',dict(optimizer_updates=250,training_forwards=250,evaluation_forwards=evaluation_forwards,all_five_complete=True,fixed_final_checkpoint=True,old_files_unchanged=True,evaluation_BN_and_weights_unchanged=True,finetune=0,SAT=0,test_reads=0))
 print('ALL_FIVE_COMPLETE',flush=True)
if __name__=='__main__':
 try:main()
 except Exception:
  O.mkdir(exist_ok=True);(O/f'failure_{time.strftime("%H%M%S")}.log').write_text(traceback.format_exc(),encoding='utf-8');raise
