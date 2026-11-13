"""User-authorized seed42 only. Gate real first steps before completing Z/R/P."""
from pathlib import Path
import argparse,collections,gc,hashlib,importlib.util,json,sys,time,traceback
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;PRE=R/'_p0pilot/cec_pretrain_ready_20261105'
sys.path.insert(0,str(PRE));import engine as E
torch=E.torch
class FirstStepDone(Exception):pass
def cleanup():gc.collect();torch.cuda.empty_cache();torch.cuda.reset_peak_memory_stats()
def packed_pool(model,head,x,edge,cids,cones,device,cache):
 h=model.encode(x,edge)
 for cid in cids:
  if cid not in cache:cache[cid]=torch.tensor(cones[cid]['graph_rows'],dtype=torch.long,device=device)
 lengths=torch.tensor([len(cones[c]['graph_rows']) for c in cids],device=device);flat=torch.cat([cache[c] for c in cids]);segments=torch.repeat_interleave(torch.arange(len(cids),device=device),lengths);total=torch.zeros((len(cids),h.size(1)),device=device,dtype=torch.float32).index_add(0,segments,h[flat].float());means=(total/lengths[:,None]).to(h.dtype);roots=torch.tensor([cones[c]['root_row'] for c in cids],device=device)
 return head(torch.cat([h[roots],means],1))
def pool_sanity():
 E.seed_all(42);h=torch.randn(20,64,requires_grad=True);groups=[[0,1,3],[3,5,7,9],[6,10]];roots=[0,5,10]
 old=torch.stack([torch.cat([h[root],h[ids].mean(0)]) for root,ids in zip(roots,groups)]);flat=torch.tensor([i for ids in groups for i in ids]);lens=torch.tensor(list(map(len,groups)));seg=torch.repeat_interleave(torch.arange(3),lens);mean=torch.zeros(3,64).index_add(0,seg,h[flat])/lens[:,None];new=torch.cat([h[roots],mean],1);assert torch.allclose(old,new,atol=1e-6,rtol=1e-6)
 a=torch.autograd.grad(old.square().sum(),h,retain_graph=True)[0];b=torch.autograd.grad(new.square().sum(),h)[0];assert torch.allclose(a,b,atol=1e-6,rtol=1e-6)
 return dict(forward_max_delta=float((old-new).abs().max()),gradient_max_delta=float((a-b).abs().max()),meaning='same root and exact member mean;single packed gather/index_add avoids many dense backward scatters')
def main():
 p=argparse.ArgumentParser();p.add_argument('--gate',choices=['Z','R','P']);p.add_argument('--finish',action='store_true');a=p.parse_args();assert bool(a.gate)!=bool(a.finish)
 O.mkdir(exist_ok=True);assert 'ginvenv_gpu' in sys.executable and torch.cuda.is_available()
 contract=dict(seed=42,mode='main',arms=['Z','R','P'],pretrain_updates=50,finetune_updates=200,prepared_contract_sha=E.sha(PRE/'RUN_CONTRACT.json'),controller_sha=E.sha(Path(__file__)),pooling='same means;packed gather with float32 sum then original hidden dtype',first_gate=dict(mean_raw_std_min=.01,effective_rank_min=1.5,negative_rms_min=.001,max_allocated_fraction=.95,max_reserved_fraction=1.02),no_new_SAT=True,no_test_selection=True)
 if (O/'EXECUTION_CONTRACT.json').exists():assert E.read(O/'EXECUTION_CONTRACT.json')==contract
 else:E.write(O/'EXECUTION_CONTRACT.json',contract)
 sanity=pool_sanity()
 if not (O/'POOL_SANITY.json').exists():E.write(O/'POOL_SANITY.json',sanity)
 E.make_embeddings=packed_pool
 original_binding=E.prepare_binding
 def binding(mode,seed,arm):
  z=original_binding(mode,seed,arm);z['execution_contract_sha']=E.sha(O/'EXECUTION_CONTRACT.json');z['controller_sha']=contract['controller_sha'];return z
 E.prepare_binding=binding
 original_terms=E.terms;original_save=E.save;current={};diagnostics={};loss_stats=[]
 def terms(z,rows,byid,index,arm):
  loss,parts=original_terms(z,rows,byid,index,arm)
  if current.get('stage')=='pretrain' and current.get('next_update')==1:
   matrix=z.detach().float().cpu().numpy();center=matrix-matrix.mean(0);singular=np.linalg.svd(center,compute_uv=False);energy=singular**2;prob=energy/energy.sum() if energy.sum()>0 else energy;rank=float(np.exp(-(prob[prob>0]*np.log(prob[prob>0])).sum())) if energy.sum()>0 else 0
   neg=[]
   for row in rows:
    pa,pb=byid[row['pair_a']],byid[row['pair_b']]
    for side in ['left_cone','right_cone']:neg.append(float(np.sqrt(np.mean((matrix[index[pa[side]]]-matrix[index[pb[side]]])**2))))
   d=dict(arm=arm,loss=float(loss.detach()),raw_std_mean=float(matrix.std(0).mean()),effective_rank=rank,negative_rms_mean=float(np.mean(neg)),max_abs_z=float(np.abs(matrix).max()),**{k:float(v.detach()) for k,v in parts.items()})
   assert np.isfinite(matrix).all() and np.isfinite(list(dv for k,dv in d.items() if isinstance(dv,(float,int)))).all()
   assert d['raw_std_mean']>.01 and d['effective_rank']>1.5 and d['negative_rms_mean']>.001,('first-step collapse gate failed',d)
   diagnostics[arm]=d
  return loss,parts
 E.terms=terms
 original_domain_loss=E.T.domain_loss
 def domain_loss(logits,y,ids):
  loss=original_domain_loss(logits,y,ids)
  if current.get('stage')=='finetune' and current.get('next_update')==1:
   selected=logits[ids].detach().float();loss_stats.append(dict(loss=float(loss.detach()),logit_std=float(selected.std()),logits_finite=bool(torch.isfinite(selected).all())));assert loss_stats[-1]['logits_finite'] and np.isfinite(loss_stats[-1]['loss'])
  return loss
 E.T.domain_loss=domain_loss
 def save(path,value):
  original_save(path,value)
  if Path(path).name!='resume.pt' or not isinstance(value,dict) or 'completed' not in value:return
  current['next_update']=value['completed']+1
  if value['completed']!=1:return
  torch.cuda.synchronize();total=torch.cuda.get_device_properties(0).total_memory;peak=torch.cuda.max_memory_allocated();reserved=torch.cuda.max_memory_reserved();gate=dict(stage=current['stage'],arm=current['arm'],completed=1,peak_allocated_bytes=peak,peak_reserved_bytes=reserved,total_cuda_bytes=total,allocated_fraction=peak/total,reserved_fraction=reserved/total,weights_finite=all(bool(torch.isfinite(v).all()) for v in value['model'].values() if v.is_floating_point()),history=value['history'][-1])
  assert gate['weights_finite'] and peak/total<.95 and reserved/total<1.02,('first-step memory/weights gate failed',gate)
  if current['stage']=='pretrain':gate['noncollapse']=diagnostics[current['arm']]
  else:gate['domain_losses']=list(loss_stats);assert len(loss_stats)==2
  gate['passed']=True;E.write(O/f"FIRST_{current['stage']}_{current['arm']}.json",gate);print('FIRST_STEP_GATE_PASS',json.dumps(gate),flush=True)
  if a.gate and current['stage']=='pretrain':raise FirstStepDone()
 E.save=save
 if a.gate:
  arm=a.gate;folder=PRE/'runs/main/seed42'/arm/'pretrain'
  if (O/f'FIRST_pretrain_{arm}.json').exists():assert E.read(O/f'FIRST_pretrain_{arm}.json')['passed'];print('REUSE FIRST GATE',arm);return
  current.update(stage='pretrain',arm=arm,next_update=1)
  try:E.pretrain('main',42,arm)
  except FirstStepDone:pass
  return
 for arm in ['Z','R','P']:assert E.read(O/f'FIRST_pretrain_{arm}.json')['passed']
 report=[]
 for arm in ['Z','R','P']:
  cleanup();folder=PRE/'runs/main/seed42'/arm/'pretrain';resume=E.read(O/f'FIRST_pretrain_{arm}.json')['completed'];current.update(stage='pretrain',arm=arm,next_update=resume+1);print('RESUME_PRETRAIN',arm,flush=True);result=E.pretrain('main',42,arm);cleanup()
  loss_stats.clear();current.update(stage='finetune',arm=arm,next_update=1);print('START_FINETUNE',arm,flush=True);E.finetune('main',42,arm);cleanup();report.append(dict(arm=arm,pretrain=result,finetune=E.read(PRE/'runs/main/seed42'/arm/'finetune/COMPLETE.json')));E.write(O/'progress.json',dict(completed_arms=[z['arm'] for z in report],SAT=0))
 E.write(O/'TRAINING_COMPLETE.json',dict(seed=42,arms=report,total_pretrain_updates=150,total_finetune_updates=600,new_SAT_queries=0,test_evaluated=False));print('ALL_THREE_ARMS_COMPLETE',flush=True)
if __name__=='__main__':
 try:main()
 except Exception:
  O.mkdir(exist_ok=True);stamp=time.strftime('%Y%m%d_%H%M%S');(O/f'failure_{stamp}.txt').write_text(traceback.format_exc(),encoding='utf-8');raise
