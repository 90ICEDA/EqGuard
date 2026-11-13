"""CPU synthetic gradient/transfer checks plus actual frozen-index loading. No updates."""
from pathlib import Path
import json,hashlib,collections,csv,importlib.util
import numpy as np
import torch
import engine as E
R=E.R;O=E.O;J=E.J
def main():
 assert not (O/'PREFLIGHT_COMPLETE.json').exists();E.set_inputs();contract=E.T.CONTRACT
 controls=E.read(O/'CONTROLS_COMPLETE.json');assert controls['main_budget_and_endpoints_pass'] and controls['strict_structural_matching_pass']
 rows=E.read(O/'schedule.json');records=E.read(O/'function_inventory.json');byid={p['pair_id']:p for p in records};cones={c['cone_id']:c for c in E.read(J/'final_cones.json')};rawpairs={p['pair_id']:p for p in E.read(J/'final_pairs.json')};domain=contract['shared_inputs']['trans_train'];folder=R/domain['folder'];physical=np.load(folder/'physical.npy',mmap_mode='r');x=np.load(folder/'x39.npy',mmap_mode='r');edge=np.load(folder/'edge_index.npy',mmap_mode='r');norm=E.T.NORM
 assert x.shape[1]==39 and edge.shape[0]==2 and int(edge.max())<len(x) and int(edge.min())>=0
 referenced={p[k] for row in rows for p in [byid[row['pair_a']],byid[row['pair_b']]] for k in ['left_cone','right_cone']}
 for cid in referenced:
  c=cones[cid];assert c['split']=='train';ii=np.asarray(c['graph_rows']);assert physical[ii].all() and np.isfinite(x[ii]).all() and c['root_row'] in ii
 assert all(rawpairs[row[k]]['split']=='train' for row in rows for k in ['pair_a','pair_b'])
 # Check exact encoder extraction against frozen detector on synthetic data only.
 E.seed_all(42);new,initial=E.load_initial(42,'cpu');old=E.legacy.Model();old.load_state_dict(initial);new.eval();old.eval();E.seed_all(180);xx=torch.randn(16,39);ee=torch.tensor([[i for i in range(16)]+[i for i in range(15)],[((i+1)%16) for i in range(16)]+[i for i in range(1,16)]])
 with torch.inference_mode():a=new(xx,ee);b=old(xx,ee)
 assert torch.equal(a,b),'Encoder extraction changes frozen logits'
 # Mathematical control sanity: true pairs coincide, different functions differ.
 rr=E.batch_rows('main',42,1);cids=sorted({p[k] for row in rr for p in [byid[row['pair_a']],byid[row['pair_b']]] for k in ['left_cone','right_cone']});index={cid:i for i,cid in enumerate(cids)};z=torch.zeros(len(cids),32)
 for row in rr:
  p=byid[row['pair_b']];z[index[p['left_cone']]]=1;z[index[p['right_cone']]]=1
 lz,_=E.terms(z,rr,byid,index,'Z');lr,pr=E.terms(z,rr,byid,index,'R');lp,pp=E.terms(z,rr,byid,index,'P');assert abs(float(lr))<1e-6 and abs(float(lz))<1e-6 and float(lp)>.99
 collapsed,_=E.terms(torch.zeros_like(z),rr,byid,index,'R');assert float(collapsed)>.9
 # Classifier never receives functional gradients; encoder and projection must.
 gradients=[];initialization_checks=[]
 for arm in ['Z','R','P']:
  E.seed_all(42);model,_=E.load_initial(42,'cpu');model.train()
  for n,p in model.named_parameters():p.requires_grad_(not n.startswith('classifier.'))
  E.seed_all(819);head=E.Projection();fake={cid:dict(root_row=(i*3)%16,graph_rows=sorted({(i*3)%16,(i*3+1)%16,(i*3+5)%16})) for i,cid in enumerate(cids)}
  cache={};zz=E.make_embeddings(model,head,xx,ee,cids,fake,'cpu',cache);loss,parts=E.terms(zz,rr,byid,index,arm);assert torch.isfinite(loss);loss.backward()
  enc_grad=sum(float(p.grad.abs().sum()) for n,p in model.named_parameters() if not n.startswith('classifier.') and p.grad is not None);head_grad=sum(float(p.grad.abs().sum()) for p in head.parameters() if p.grad is not None);assert enc_grad>0 and head_grad>0;assert all(p.grad is None for n,p in model.named_parameters() if n.startswith('classifier.'))
  assert all(torch.isfinite(p.grad).all() for p in list(model.parameters())+list(head.parameters()) if p.grad is not None)
  gradients.append(dict(arm=arm,loss=float(loss.detach()),encoder_grad_abs_sum=enc_grad,projection_grad_abs_sum=head_grad,classifier_grad_none=True))
 # Reset / transfer preserves classifier and uses only known encoder keys.
 transfer,_=E.load_initial(42,'cpu');encoded={n:v.clone() for n,v in new.state_dict().items() if not n.startswith('classifier.')};state=transfer.state_dict();state.update(encoded);transfer.load_state_dict(state,strict=True);assert all(torch.equal(v,initial[n]) for n,v in transfer.state_dict().items() if n.startswith('classifier.'))
 for seed in [42,1,2]:
  fingerprints=[]
  for arm in ['Z','R','P']:
   E.seed_all(seed);m,st=E.load_initial(seed,'cpu');E.seed_all(seed+777);h=E.Projection();digest=hashlib.sha256()
   for n,v in sorted(h.state_dict().items()):digest.update(n.encode());digest.update(v.numpy().tobytes())
   fingerprints.append(digest.hexdigest())
  assert len(set(fingerprints))==1;initialization_checks.append(dict(seed=seed,detector_init_sha=E.sha(E.H/f'init_s{seed}.pt'),projection_fingerprint=fingerprints[0],arms_identical=True))
 # Preserve the exact original H supervised slots. This preflight reads, never edits.
 supervised=[]
 for dm in ['orig','trans']:
  mask=np.load(E.H/f'{dm}_base_mask.npy',mmap_mode='r');slots=np.load(E.H/f'{dm}_H_slots.npy',mmap_mode='r');assert slots.shape==(200,320) and not mask[slots].any();supervised.append(dict(domain=dm,updates=200,extra_slots_per_update=320,base_mask_sha=E.sha(E.H/f'{dm}_base_mask.npy'),slots_sha=E.sha(E.H/f'{dm}_H_slots.npy')))
 bound={}
 for path,h in E.read(J/'PUBLISHED.json')['files'].items():assert E.sha(R/path)==h,path
 for name in ['engine.py','function_inventory.json','witness_contexts.json','negative_certificates.json','schedule.json','CONTROLS_COMPLETE.json']:
  bound[str((O/name).relative_to(R))]=E.sha(O/name)
 for path,h in contract['files'].items():assert E.sha(R/path)==h,path;bound[path]=h
 for path in [E.V/'input_contract.json',E.V/'normalization.npz',E.H/'manifest.json',R/'_p0pilot/control_best200_20261104/evaluate.py',R/'_p0pilot/p2b_main_20261031/train_ab.py',R/'train_test2.2.py']:
  bound[str(path.relative_to(R))]=E.sha(path)
 for seed in [42,1,2]:bound[str((E.H/f'init_s{seed}.pt').relative_to(R))]=E.sha(E.H/f'init_s{seed}.pt')
 for dm in ['orig','trans']:
  for n in [f'{dm}_base_mask.npy',f'{dm}_H_slots.npy']:bound[str((E.H/n).relative_to(R))]=E.sha(E.H/n)
 run=dict(status='READY_FOR_EXPLORATORY_SEED42_NOT_EXECUTED',training_started=False,arms=['Z','R','P'],main_mode='main',secondary_mode='strict',main_scope='endpoint/source/context/view-budget fair;pair joint structure not controlled',strict_scope='exact boundary/gate/cut/size-bin support;151 background pairs;not positive coverage',pretrain_updates=50,finetune_updates=200,seeds=[42,1,2],start_with_seed=42,features='39v3;noSATinput',model='unchanged improved dual_mix_post_cat 2+2+post1 hidden64',projection='concat(root64,meanCone64),128->64ReLU->32',loss='weighted per-dimension MSE equivalence + weighted hinge(1-RMS)^2 certified-different +0.1 relu(0.5-std)',pretrain_selection='fixed update50;no validation/test selection',fine_tuning='discard projection,transfer only encoder incl BN;original classifier init;new Adam;fixed H200 masks and slots',classification_loss='unchanged ASL+1.4soft-miss squared',optimizer='Adam lr0.0002 weight_decay0.001 clip1',test_policy='no test data during pretrain;test detection remains evaluable later;test pair MAE/flip unavailable',frozen_files=bound,preflight='CPU synthetic only;real-index loading;no real graph forward;no optimizer steps;full GPU memory run not tested',execute_gate='engine.py requires explicit --execute;no queue created')
 E.write(O/'RUN_CONTRACT.json',run)
 result=dict(training_updates=0,optimizer_steps=0,real_model_forward=0,synthetic_forward_and_backward_only=True,synthetic_backward_calls=3,encoder_logits_match_old=True,loaded_schedule_rows=len(rows),referenced_train_cones=len(referenced),gradient_checks=gradients,initialization_checks=initialization_checks,supervised_slots=supervised,cuda_available=torch.cuda.is_available(),python=__import__('sys').executable,torch=torch.__version__,new_SAT_queries=0,ready_for_seed42_exploration=True,full_graph_cuda_memory_unverified=True)
 E.write(O/'PREFLIGHT_COMPLETE.json',result);print(json.dumps(result,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
