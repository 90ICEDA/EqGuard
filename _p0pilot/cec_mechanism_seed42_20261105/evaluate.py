"""Checkpoint-only representation/head/BN/dropout probes. No optimizer/backward."""
from pathlib import Path
import collections,csv,gc,hashlib,importlib.util,json,sys
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;PRE=R/'_p0pilot/cec_pretrain_ready_20261105';J=R/'_p0pilot/cec_joint_expand_20261105'
sys.path.insert(0,str(PRE));import engine as E
torch=E.torch
def state_hash(state):
 h=hashlib.sha256()
 for n,t in sorted(state.items()):h.update(n.encode());h.update(t.detach().cpu().contiguous().numpy().tobytes())
 return h.hexdigest()
def main():
 if (O/'EMBEDDINGS_COMPLETE.json').exists():print('Reuse completed diagnostic embeddings');return
 plan=E.read(O/'PREPARED.json')
 for p,h in plan['frozen'].items():assert E.sha(R/p)==h,p
 E.set_inputs();assert 'ginvenv_gpu' in sys.executable and torch.cuda.is_available();cones={c['cone_id']:c for c in E.read(J/'final_cones.json')};graphs={};forward_count=0;checks=[];stages={};heads={};initial=torch.load(E.H/'init_s42.pt',map_location='cpu',weights_only=True);E.seed_all(819);inithead=E.Projection();heads['initial']=inithead.state_dict();stages['initial']=initial
 def isbn(k):return k.endswith(('running_mean','running_var','num_batches_tracked'))
 weightrows=[];cpu_model=E.EncoderModel();parameter_keys=set(dict(cpu_model.named_parameters()))
 def delta(a,b,keys):
  num=sum(float((a[k].double()-b[k].double()).square().sum()) for k in keys);den=sum(float(b[k].double().square().sum()) for k in keys);return dict(abs_L2=float(np.sqrt(num)),relative_L2=float(np.sqrt(num/max(den,1e-24))))
 for arm in ['Z','R','P']:
  run=PRE/'runs/main/seed42'/arm;pre=torch.load(run/'pretrain/resume.pt',map_location='cpu',weights_only=False);last=torch.load(run/'finetune/resume.pt',map_location='cpu',weights_only=False);best=torch.load(run/'finetune/best.pt',map_location='cpu',weights_only=True);assert pre['completed']==50 and last['completed']==200;heads[arm]=pre['projection'];stages[arm+'_pre']=pre['model'];stages[arm+'_best']=best;stages[arm+'_last']=last['model'];stages[arm+'_preW_fineBN']={k:(best[k] if isbn(k) else v) for k,v in pre['model'].items()};stages[arm+'_fineW_preBN']={k:(pre['model'][k] if isbn(k) else v) for k,v in best.items()}
  for label,aa,bb in [('pre_vs_init',pre['model'],initial),('best_vs_pre',best,pre['model']),('last_vs_pre',last['model'],pre['model'])]:
   for prefix in ['mix.','enc_s.','enc_f.','fuse.','post.','classifier.']:
    keys=[k for k in parameter_keys if k.startswith(prefix)];z=delta(aa,bb,keys);weightrows.append(dict(arm=arm,comparison=label,module=prefix,**z))
  for module in ['0.','2.']:
   z=delta(heads[arm],heads['initial'],[k for k in heads['initial'] if k.startswith(module)]);weightrows.append(dict(arm=arm,comparison='projection_pre_vs_initial',module=module,**z))
  del pre,last
 (O/'weight_deltas.json').write_text(json.dumps(weightrows,ensure_ascii=False,indent=2),encoding='utf-8')
 def graph(split):
  if split not in graphs:
   folder=R/E.T.CONTRACT['shared_inputs']['trans_'+split]['folder'];raw=np.load(folder/'x39.npy',mmap_mode='r');edge=np.load(folder/'edge_index.npy',mmap_mode='r');x=torch.tensor(np.asarray(raw),device='cuda');structural=((x[:,25:]-torch.tensor(E.T.NORM['mean'][25:],device='cuda'))/torch.tensor(E.T.NORM['std'][25:],device='cuda')).clamp(-10,10);graphs[split]=(torch.cat([x[:,:25],structural],1),torch.tensor(np.asarray(edge),device='cuda'))
  return graphs[split]
 def encode(stage,split,mode='eval_running',seed=101):
  nonlocal forward_count
  out=O/'embeddings'/stage;out.mkdir(parents=True,exist_ok=True);path=out/f'{split}_{mode}.npy';stamp=path.with_suffix('.json');state=stages[stage];binding=dict(stage=stage,split=split,mode=mode,state_sha=state_hash(state),seed=seed,prepared_sha=E.sha(O/'PREPARED.json'))
  if path.exists():b=E.read(stamp);assert b['binding']==binding and b['sha']==E.sha(path);return
  model=E.EncoderModel().cuda();model.load_state_dict(state);model.eval();drop='dropout' in mode;batch='batch' in mode
  if drop:model.train()
  for layer in model.modules():
   if isinstance(layer,torch.nn.BatchNorm1d):layer.track_running_stats=not batch;layer.train(batch)
  before=state_hash(model.state_dict());E.seed_all(seed);x,edge=graph(split);cids=plan['train_cones'] if split=='train' else plan['val_cones'];chunks=[]
  with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):
   h=model.encode(x,edge);forward_count+=1
   for start in range(0,len(cids),64):
    ids=cids[start:start+64];lengths=torch.tensor([len(cones[c]['graph_rows']) for c in ids],device='cuda');flat=torch.tensor([r for c in ids for r in cones[c]['graph_rows']],device='cuda');seg=torch.repeat_interleave(torch.arange(len(ids),device='cuda'),lengths);summed=torch.zeros((len(ids),64),device='cuda').index_add(0,seg,h[flat].float());means=(summed/lengths[:,None]).to(h.dtype);root=torch.tensor([cones[c]['root_row'] for c in ids],device='cuda');chunks.append(torch.cat([h[root],means],1).float().cpu().numpy())
  result=np.concatenate(chunks);assert result.shape==(len(cids),128) and np.isfinite(result).all();assert state_hash(model.state_dict())==before,'BN buffer or parameter mutation during read-only diagnostic';np.save(path,result);E.write(stamp,dict(binding=binding,sha=E.sha(path),shape=result.shape,model_state_unchanged=True));checks.append(dict(stage=stage,split=split,mode=mode,state_unchanged=True));del model,h;gc.collect();torch.cuda.empty_cache();print('ENCODED',stage,split,mode,flush=True)
 # Encode each graph/checkpoint once; every projection swap reuses this output.
 for stage in stages:
  for split in ['train','val']:encode(stage,split)
 for arm in ['Z','R','P']:
  for mode,seed in [('dropout_running101',101),('dropout_running202',202),('clean_batchBN',101),('dropout_batchBN101',101),('dropout_batchBN202',202)]:encode(arm+'_pre','train',mode,seed)
 head_hashes={}
 for label,state in heads.items():
  np.savez(O/f'head_{label}.npz',**{k:v.numpy() for k,v in state.items()});head_hashes[label]=state_hash(state)
 E.write(O/'EMBEDDINGS_COMPLETE.json',dict(training_updates=0,optimizer_steps=0,backward_calls=0,new_SAT_queries=0,no_test_forward=True,new_model_forwards=forward_count,model_state_checks=checks,head_hashes=head_hashes,stages=list(stages),data_domains=['train','val']))
 print('EMBEDDINGS_COMPLETE',forward_count,flush=True)
if __name__=='__main__':main()
