"""Five-arm loading and no-update gradient preflight. No optimizer is instantiated."""
import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import collections,contextlib,csv,gc,hashlib,importlib.util,json,sys,time,traceback
import numpy as np
from interface import Interface,read,sha,terms,audit_loaded,ARMS,ASSOC
O=Path(__file__).resolve().parent;R=O.parents[1];C=R/'_p0pilot/cec_relative_contract_20261106'
spec=importlib.util.spec_from_file_location('frozen_role_interface',R/'_p0pilot/cec_pinrole_effective_20261106/run.py');A=importlib.util.module_from_spec(spec);spec.loader.exec_module(A)
D=A.D;B=A.B;E=A.E;torch=A.torch
def write(n,x):E.write(O/n,x)
def table(n,rr):
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def group(n):
 if n.startswith('projection.'):return 'projection'
 if n.startswith('boundary_adapter.'):return 'shared_boundary'
 if n.startswith('pin_boundary_adapter.'):return 'pin_boundary'
 if n.startswith('pin_scales.'):return 'pin_internal'
 return 'backbone'
def cosine(a,b):
 den=np.linalg.norm(a)*np.linalg.norm(b);return float(np.dot(a,b)/den) if den else None
def snapshot(m):return {k:v.detach().clone() for k,v in m.state_dict().items()}
def same(s,m):return all(torch.equal(v,m.state_dict()[k]) for k,v in s.items())
@contextlib.contextmanager
def mode_context(m,head,mode):
 flags=[(v,v.training) for module in [m,head] for v in module.modules()];saved=[]
 for module in m.modules():
  if isinstance(module,torch.nn.modules.batchnorm._BatchNorm):
   for n in ['running_mean','running_var','num_batches_tracked']:
    val=getattr(module,n);saved.append((module,n,val));setattr(module,n,val.clone() if val is not None else None)
 m.train(mode=='contract_train');head.train(mode=='contract_train')
 try:yield
 finally:
  for module,n,val in saved:setattr(module,n,val)
  for module,flag in flags:module.training=flag
def leaf_reference(z,b,parts,totals,aux):
 # Independent NumPy reconstruction from actual GPU-produced projection values.
 zz=z.detach().float().cpu().numpy().astype(np.float64);aa=zz[np.array(b['anchors'])][:,None,:];vv=zz[np.array(b['candidates'])];mse=np.mean((aa-vv)**2,-1);dist=np.sqrt(mse+1e-12);logit=-dist;mx=logit.max(1);lse=mx+np.log(np.exp(logit-mx[:,None]).sum(1));q=np.arange(len(dist));w=np.array(b['query_weights']);ne=np.array(b['negative_edges']);nw=np.array(b['negative_weights'])
 ref={k:float(np.sum(w*mse[q,np.array(b['real' if k=='A_R' else 'permuted'])])) for k in ['A_R','A_P']}
 ref.update({k:float(np.sum(w*(lse-logit[q,np.array(b['real' if k=='S_R' else 'permuted'])]))) for k in ['S_R','S_P']})
 ref['different']=float(np.sum(nw*np.maximum(0,1-np.sqrt(np.mean((zz[ne[:,0]]-zz[ne[:,1]])**2,1)+1e-12))**2));ref['variance_weighted']=float(.1*np.maximum(0,.5-np.sqrt(zz.var(0)+1e-4)).mean())
 err=max(abs(float(parts[k].detach())-v) for k,v in ref.items());assert err<2e-5,err
 for arm in ARMS:
  expect=ref['different']+ref['variance_weighted']+(ref[arm] if arm in ASSOC else 0);assert abs(float(totals[arm].detach())-expect)<3e-5
 # Actual differentiable distance -> CE Jacobian must include the nonselected candidate.
 logits=aux['logits'].detach().clone().requires_grad_(True);lossr=torch.nn.functional.cross_entropy(logits,torch.tensor(b['real'],device=z.device),reduction='none');lossp=torch.nn.functional.cross_entropy(logits,torch.tensor(b['permuted'],device=z.device),reduction='none');ww=torch.tensor(b['query_weights'],device=z.device)
 gr=torch.autograd.grad((ww*lossr).sum(),logits,retain_graph=True)[0];gp=torch.autograd.grad((ww*lossp).sum(),logits)[0]
 expect=torch.zeros_like(gr);qi=torch.arange(len(gr),device=z.device);expect[qi,torch.tensor(b['real'],device=z.device)]-=ww;expect[qi,torch.tensor(b['permuted'],device=z.device)]+=ww
 assert torch.allclose(gr-gp,expect,atol=2e-7,rtol=1e-5)
 nonselected=float(torch.minimum(gr[:,2].abs(),gp[:,2].abs()).min());assert nonselected>0
 return dict(max_loss_abs_error=err,logit_true_permuted_gradient_difference_exact=True,third_candidate_min_abs_derivative=nonselected)
def flatten(gs,pp):return np.concatenate([(g.detach().float().cpu().numpy().reshape(-1) if g is not None else np.zeros(p.numel(),np.float32)) for g,p in zip(gs,pp)])
def main():
 assert 'ginvenv_gpu' in sys.executable and torch.cuda.is_available();assert not (O/'COMPLETE.json').exists()
 i=Interface();v=read(C/'VERIFIED.json');pv=read(C/'PROVENANCE_VERIFIED.json')
 protected=dict(i.contract['protected_files']);protected.update(pv['query_files_sha'])
 for n,h in v['indices_sha'].items():assert sha(C/n)==h;protected[str((C/n).relative_to(R))]=h
 for p in [Path(__file__),O/'interface.py',R/'_p0pilot/cec_pinrole_effective_20261106/run.py',R/'_p0pilot/cec_pinrole_seed42_20261106/run.py',R/'_p0pilot/cec_boundary_seed42_20261106/run.py',R/'models/gin_net.py',E.H/'init_s42.pt']:
  protected[str(p.relative_to(R))]=sha(p)
 for p,h in protected.items():assert sha(R/p)==h,p
 write('EXECUTION_CONTRACT.json',dict(frozen_files=protected,initialization='all5 arms same original seed42 zero semantic adapters;head819',gradient_batches=[1,2,25,50],modes=['contract_train','frozen_eval'],contract_train='BF16/dropout.2/BN train with temporary cloned buffers;discard clones,original buffers unchanged',frozen_eval='BF16/dropoutoff/BNfrozen secondary diagnosis',all_five_losses_share_same_forward=True,first_batch_each_arm_forward_replay=True,optimizer_steps=0,SAT=0,test_reads=0))
 details,loaded=audit_loaded(i);table('loaded_budget_per_step.csv',details);write('LOADING_BUDGET_VERIFIED.json',loaded);write('loaded_batches.json',list(i.batches.values()))
 E.set_inputs();scratch=O/'pin_loader';scratch.mkdir(exist_ok=True);D.O=scratch;B.O=scratch;b=D.PinBoundary(E.T.CONTRACT,i.cones)
 # Check every supervised cone against the actual raw-to-global-row loader.
 attachment=[]
 for t in i.triples.values():
  if t['split']!='train':continue
  for c in t['cones']:
   co=i.cones[c];rm=b.rowmaps[co['view']];assert rm[co['output_cell']]==co['root_row'];assert sorted(rm[n] for n in co['members'])==sorted(co['graph_rows'])
 attachment.append(dict(triples_checked=sum(t['split']=='train' for t in i.triples.values()),all_root_and_member_global_rows_exact=True))
 write('ATTACHMENT_VERIFIED.json',attachment)
 x,e=B.graph('trans_train');m,head=D.initial();ms=snapshot(m);hs=snapshot(head);named=[(n,p) for n,p in m.named_parameters() if p.requires_grad]+[('projection.'+n,p) for n,p in head.named_parameters() if p.requires_grad];pp=[p for _,p in named]
 offsets={};start=0
 for n,p in named:offsets[n]=(start,start+p.numel());start+=p.numel()
 group_ix={g:np.concatenate([np.arange(*offsets[n]) for n,p in named if group(n)==g]) for g in ['backbone','shared_boundary','pin_boundary','pin_internal','projection']};group_ix['all']=np.arange(start)
 write('PARAMETER_LAYOUT.json',dict(names={n:dict(start=offsets[n][0],stop=offsets[n][1],shape=list(p.shape),group=group(n)) for n,p in named},total_dimensions=start,main_parameters=sum(p.numel() for p in m.parameters()),projection_parameters=sum(p.numel() for p in head.parameters())))
 norms=[];angles=[];values=[];checks=[];replays=[];forward_count=0;parameter_vjp=0;leaf_vjp=0
 for mode in ['contract_train','frozen_eval']:
  for u in [1,2,25,50]:
   batch=i.batches[u];bt=i.tensors(batch,'cuda');side=b.features('trans_train','shared',u);E.seed_all(100042+u)
   with mode_context(m,head,mode):
    with torch.autocast('cuda',dtype=torch.bfloat16):
     pooled=B.pool(m.encode(x,e,side),batch['cone_ids'],i.cones);z=head(pooled);parts,totals,aux=terms(z,bt)
    forward_count+=1;check=leaf_reference(z,batch,parts,totals,aux);leaf_vjp+=2;checks.append(dict(mode=mode,batch=u,**check))
    vectors={};ordered=list(parts.items())+[(k+'_total',totals[k]) for k in ARMS]
    for j,(term,loss) in enumerate(ordered):
     gg=torch.autograd.grad(loss,pp,retain_graph=j<len(ordered)-1,allow_unused=True);parameter_vjp+=1;vec=flatten(gg,pp);assert np.isfinite(vec).all();vectors[term]=vec
     for g,ii in group_ix.items():
      vv=vec[ii].astype(np.float64);norms.append(dict(mode=mode,batch=u,term=term,group=g,loss=float(loss.detach()),grad_norm=float(np.linalg.norm(vv)),grad_rms=float(np.sqrt(np.mean(vv**2))),dimensions=len(vv),nonzero_dimensions=int(np.count_nonzero(vv))))
     del gg
    for g,ii in group_ix.items():
     for left,right in [('A_R','A_P'),('S_R','S_P'),('A_R_total','A_P_total'),('S_R_total','S_P_total'),('A_R','different'),('S_R','different'),('A_R_total','S_R_total')]:
      va=vectors[left][ii].astype(np.float64);vb=vectors[right][ii].astype(np.float64);angles.append(dict(mode=mode,batch=u,group=g,left=left,right=right,cosine=cosine(va,vb),left_norm=float(np.linalg.norm(va)),right_norm=float(np.linalg.norm(vb)),relative_difference=float(np.linalg.norm(va-vb)/(np.linalg.norm(va)+1e-30))))
    for k,loss in parts.items():values.append(dict(mode=mode,batch=u,term=k,loss=float(loss.detach()),representation_std=float(z.detach().float().std(0,unbiased=False).mean())))
    np.savez_compressed(O/f'vectors_{mode}_u{u}.npz',**vectors)
    np.savez_compressed(O/f'forward_{mode}_u{u}.npz',cone_ids=np.array(batch['cone_ids']),projection32=z.detach().float().cpu().numpy(),pool128=pooled.detach().float().cpu().numpy())
    reference=z.detach().clone() if u==1 else None
   assert same(ms,m) and same(hs,head);assert all(p.grad is None for p in pp)
   # Actually replay the five arm forwards with identical init/RNG; shared-forward
   # gradients above remove scatter noise from within-state R/P comparison.
   if u==1:
    for arm in ARMS:
     E.seed_all(100042+u)
     with mode_context(m,head,mode):
      with torch.no_grad(),torch.autocast('cuda',dtype=torch.bfloat16):
       zz=head(B.pool(m.encode(x,e,side),batch['cone_ids'],i.cones));pa,to,au=terms(zz,bt)
      forward_count+=1;delta=float((zz-reference).float().abs().max());relative=float((zz-reference).float().square().mean().sqrt()/(reference.float().std()+1e-12));assert relative<.02,(mode,arm,relative)
      replays.append(dict(mode=mode,arm=arm,max_projection_abs_delta=delta,relative_projection_RMS=relative,loss=float(to[arm]),same_initial_state=True,same_rng=True,parameters_and_original_BN_unchanged=True))
     assert same(ms,m) and same(hs,head)
     del zz,pa,to,au
    del reference
   del z,pooled,parts,totals,aux,ordered,vectors,side,bt;gc.collect();torch.cuda.empty_cache();print('PREFLIGHT',mode,u,'state_unchanged',True,flush=True)
 table('gradient_norms.csv',norms);table('gradient_angles.csv',angles);table('loss_values.csv',values);table('first_batch_arm_replays.csv',replays);table('numeric_checks.csv',checks)
 assert same(ms,m) and same(hs,head) and all(p.grad is None for p in pp)
 for p,h in protected.items():assert sha(R/p)==h,p
 write('COMPLETE.json',dict(model_forwards=forward_count,parameter_vector_jacobian_products=parameter_vjp,leaf_vector_jacobian_products=leaf_vjp,optimizer_steps=0,SAT=0,test_reads=0,all_original_parameters_and_BN_buffers_unchanged=True,no_parameter_grad_accumulation=True,initialization='seed42 original init and zero semantic adapters;projection819',frozen_files_unchanged=True,peak_gpu_bytes=torch.cuda.max_memory_allocated(),all_eight_batches_finite=True,loaded_budget_matches_frozen_contract=True,first_batch_five_arm_forward_replays=10))
 print('ALL_PREFLIGHT_COMPLETE',flush=True)
if __name__=='__main__':
 try:main()
 except Exception:
  O.mkdir(exist_ok=True);(O/f'failure_{time.strftime("%H%M%S")}.log').write_text(traceback.format_exc(),encoding='utf-8');raise
