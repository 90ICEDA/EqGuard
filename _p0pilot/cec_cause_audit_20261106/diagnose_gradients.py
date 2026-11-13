"""Fixed checkpoint/batch autograd and panel inference. Never creates an optimizer."""
import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import csv,gc,importlib.util,json,time,traceback
import numpy as np
O=Path(__file__).resolve().parent;R=O.parents[1];OLD=R/'_p0pilot/cec_pinrole_effective_20261106'
s=importlib.util.spec_from_file_location('frozen_effective_roles',OLD/'run.py');A=importlib.util.module_from_spec(s);s.loader.exec_module(A)
B=A.B;D=A.D;E=A.E;torch=A.torch
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(n,x):E.write(O/n,x)
def table(n,rr):
 if not rr:return
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def group(n):
 if n.startswith('projection.'):return 'projection'
 if n.startswith('boundary_adapter.'):return 'shared_boundary'
 if n.startswith('pin_boundary_adapter.'):return 'pin_boundary'
 if n.startswith('pin_scales.'):return 'pin_internal'
 return 'backbone'
def load(arm):
 m,head=D.initial();ck=torch.load(OLD/f'shared_{arm}/resume.pt',map_location='cuda',weights_only=False)
 assert ck['completed']==50;m.load_state_dict(ck['model']);head.load_state_dict(ck['projection']);del ck
 m.eval();head.eval();return m,head
def flat(gs,pp,indices):
 return torch.cat([(gs[j].detach().float().flatten() if gs[j] is not None else torch.zeros(pp[j].numel(),device='cuda')) for j in indices]).cpu().numpy().astype(np.float64)
def cosine(a,b):
 d=np.linalg.norm(a)*np.linalg.norm(b);return float(np.dot(a,b)/d) if d>0 else None
def main():
 assert 'ginvenv_gpu' in __import__('sys').executable and torch.cuda.is_available()
 assert not (O/'GRADIENT_COMPLETE.json').exists()
 panel=read(O/'panel_certificates.json');pc=read(O/'PANEL_COMPLETE.json')
 frozen=dict(pc['frozen_files'])
 for arm in ['Z','R','P']:frozen[str((OLD/f'shared_{arm}/resume.pt').relative_to(R))]=E.sha(OLD/f'shared_{arm}/resume.pt')
 for n in ['panel_certificates.json','build_panel.py']:frozen[str((O/n).relative_to(R))]=E.sha(O/n)
 write('DIAGNOSTIC_CONTRACT.json',dict(checkpoints='fixed shared_Z/R/P step50',batches=[1,2,25,50],boundary_tags='original update id for gradient;9000 for new panel',main_mode='eval:BN frozen,dropout off;BF16 original precision',extra_dropout_probe='R checkpoint update1/2,dropout on but BN frozen and seeded',loss_terms=['real association','permuted association','different','weighted variance0.1'],optimizer_steps=0,SAT=0,test_reads=0,selection='batch IDs fixed before gradient/result inspection;panel frozen before checkpoint inference',frozen_files=frozen))
 E.set_inputs();cones={c['cone_id']:c for c in read(E.J/'final_cones.json')}
 scratch=O/'pin_loader';scratch.mkdir(exist_ok=True);D.O=scratch;B.O=scratch
 b=D.PinBoundary(E.T.CONTRACT,cones)
 byid={p['pair_id']:p for p in read(B.PRE/'function_inventory.json')};schedule=read(B.PRE/'schedule.json')
 grads=[];angles=[];blocks=[];summaries=[];forwards=0;vjp=0;states=[]
 for domain in ['trans_val','trans_train']:
  split=domain.split('_')[1];cc=[c for c in panel if c['split']==split];ids=sorted({k for c in cc for k in c['cones']})
  x,e=B.graph(domain)
  for arm in ['Z','R','P']:
   m,head=load(arm);before={k:v.detach().clone() for k,v in m.state_dict().items()};hb={k:v.detach().clone() for k,v in head.state_dict().items()}
   side=b.features(domain,'shared',9000)
   with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):
    h=m.encode(x,e,side);u=B.pool(h,ids,cones);z=head(u)
    uu=u.float().cpu().numpy().astype(np.float64);zz=z.float().cpu().numpy().astype(np.float64)
   forwards+=1;del h,u,z,side
   np.savez_compressed(O/f'panel_{split}_{arm}.npz',cone_ids=np.array(ids),concat128=uu,projection32=zz)
   for tier in sorted({c['tier'] for c in cc}):
    ss=[c for c in cc if c['tier']==tier]
    for space,xx in [('root64',uu[:,:64]),('mean64',uu[:,64:]),('concat128',uu),('projection32',zz)]:
     rr,s,st=B.metrics('correct_roles',arm,9000,space,xx,ids,cones,ss)
     for r in rr:r.update(split=split,tier=tier)
     s.update(split=split,tier=tier,sources=len({c['source'] for c in ss}));blocks+=rr;summaries.append(s)
   if split=='train':
    named=[(n,p) for n,p in m.named_parameters() if p.requires_grad]+[('projection.'+n,p) for n,p in head.named_parameters() if p.requires_grad]
    pp=[p for _,p in named];groups={k:[i for i,(n,p) in enumerate(named) if group(n)==k] for k in ['backbone','shared_boundary','pin_boundary','pin_internal','projection']};groups['all']=list(range(len(pp)))
    for batch in [1,2,25,50]:
     for dropout in ([False,True] if arm=='R' and batch in [1,2] else [False]):
      m.eval();head.eval()
      if dropout:m.training=True # functional dropout reads this flag; BN children remain eval.
      assert all(not mod.training for mod in m.modules() if isinstance(mod,torch.nn.modules.batchnorm._BatchNorm))
      E.seed_all(100042+batch);rr=[r for r in schedule if r['mode']=='main' and r['seed']==42 and r['update']==batch]
      cids=sorted({p[k] for r in rr for p in [byid[r['pair_a']],byid[r['pair_b']]] for k in ['left_cone','right_cone']});ix={k:i for i,k in enumerate(cids)}
      side=b.features(domain,'shared',batch)
      with torch.autocast('cuda',dtype=torch.bfloat16):
       z=head(B.pool(m.encode(x,e,side),cids,cones));_,parts=E.terms(z,rr,byid,ix,'R')
      forwards+=1
      terms={'real':parts['eq_real'],'permuted':parts['eq_permuted'],'different':parts['different'],'variance_weighted':.1*parts['variance']};vectors={}
      for j,(term,loss) in enumerate(terms.items()):
       gg=torch.autograd.grad(loss,pp,retain_graph=j<3,allow_unused=True);vjp+=1;vectors[term]={}
       for g,ii in groups.items():
        vec=flat(gg,pp,ii);assert np.isfinite(vec).all();vectors[term][g]=vec
        grads.append(dict(checkpoint=arm,batch=batch,dropout=dropout,BN='frozen',term=term,group=g,loss=float(loss.detach()),grad_norm=float(np.linalg.norm(vec)),grad_rms=float(np.sqrt(np.mean(vec**2))),dimensions=len(vec),sources=len({r['source'] for r in rr}),mux_cones=sum(any(b.ops.get((domain,int(row)))=='MUX' for row in cones[c]['graph_rows']) for c in cids)))
       del gg
      for g in groups:
       vs={k:v[g] for k,v in vectors.items()};common=vs['different']+vs['variance_weighted'];rg=vs['real']+common;pg=vs['permuted']+common
       for a,z,va,vz in [('real','permuted',vs['real'],vs['permuted']),('real','different',vs['real'],vs['different']),('real','common',vs['real'],common),('R_total','P_total',rg,pg)]:
        angles.append(dict(checkpoint=arm,batch=batch,dropout=dropout,group=g,left=a,right=z,cosine=cosine(va,vz),left_norm=float(np.linalg.norm(va)),right_norm=float(np.linalg.norm(vz)),relative_difference=float(np.linalg.norm(va-vz)/(np.linalg.norm(va)+1e-30))))
      print('GRADIENT',arm,batch,'dropout',dropout,flush=True)
      del vectors,z,parts,terms,side;gc.collect()
   assert all(torch.equal(before[k],v) for k,v in m.state_dict().items())
   assert all(torch.equal(hb[k],v) for k,v in head.state_dict().items())
   states.append(dict(domain=domain,arm=arm,all_parameters_and_buffers_unchanged=True))
   del m,head,before,hb;gc.collect();torch.cuda.empty_cache()
  del x,e;gc.collect();torch.cuda.empty_cache()
 table('panel_evaluation_blocks.csv',blocks);table('panel_evaluation_summary.csv',summaries);table('gradient_norms.csv',grads);table('gradient_angles.csv',angles)
 for p,h in frozen.items():assert E.sha(R/p)==h,p
 write('GRADIENT_COMPLETE.json',dict(model_forwards=forwards,loss_vector_jacobian_products=vjp,optimizer_steps=0,SAT=0,test_reads=0,states=states,old_files_unchanged=True,peak_gpu_bytes=torch.cuda.max_memory_allocated(),interpretation='local fixed-checkpoint gradients in eval BN mode,not optimizer updates or causal proof;dropout probe keeps BN frozen;zero-norm cosines undefined',completed=True))
 print('DIAGNOSTIC_COMPLETE',flush=True)
if __name__=='__main__':
 try:main()
 except Exception:
  (O/f'gradient_failure_{time.strftime("%H%M%S")}.log').write_text(traceback.format_exc(),encoding='utf-8');raise
