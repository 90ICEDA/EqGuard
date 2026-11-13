"""Explicit opt-in pretraining runner. Importing or preflight never trains."""
from pathlib import Path
import argparse,collections,gc,hashlib,importlib.util,json,os,random,time
import numpy as np
import torch
from torch import nn
import torch.nn.functional as F
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;J=R/'_p0pilot/cec_joint_expand_20261105';H=R/'_p0pilot/control_v3_eligible_20261104';V=R/'_p0pilot/control_boundary_v3_20261104'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def write(p,z):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(z,ensure_ascii=False,indent=2),encoding='utf-8');os.replace(tmp,p)
def save(p,z):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp');torch.save(z,tmp);os.replace(tmp,p)
spec=importlib.util.spec_from_file_location('cec_frozen_detection_model',R/'_p0pilot/control_best200_20261104/evaluate.py');legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy);T=legacy.T
class EncoderModel(legacy.Model):
 def encode(self,x,e):
  x=x+F.relu(self.mix(x));a=self._run(self.enc_s,x[:,:self.split],e);b=self._run(self.enc_f,x[:,self.split:],e);h=self.fuse(torch.cat((a,b),1));return F.dropout(F.relu(self.post(h,e)),p=.2,training=self.training)
 def forward(self,x,e):return self.classifier(self.encode(x,e))
class Projection(nn.Sequential):
 def __init__(self):super().__init__(nn.Linear(128,64),nn.ReLU(),nn.Linear(64,32))
def seed_all(seed):
 random.seed(seed);np.random.seed(seed);torch.manual_seed(seed)
 if torch.cuda.is_available():torch.cuda.manual_seed_all(seed)
def load_initial(seed,device):
 model=EncoderModel().to(device);state=torch.load(H/f'init_s{seed}.pt',map_location=device,weights_only=True);model.load_state_dict(state,strict=True);assert sum(p.numel() for p in model.parameters())==46620;return model,state
def set_inputs():
 T.CONTRACT=read(V/'input_contract.json');T.NORM=np.load(V/'normalization.npz');assert T.MASK_MODE=='old' and not T.EXTRA and T.EQ==0 and T.ENCODING=='39'
def batch_rows(mode,seed,update):return [r for r in read(O/'schedule.json') if r['mode']==mode and r['seed']==seed and r['update']==update]
def terms(z,rows,byid,index,arm):
 if arm not in ['Z','R','P']:raise ValueError('Explicit Z/R/P arm required')
 real=[];permuted=[];negative=[];weights=[]
 for row in rows:
  a,b=byid[row['pair_a']],byid[row['pair_b']];la,ra,lb,rb=[index[c] for c in [a['left_cone'],a['right_cone'],b['left_cone'],b['right_cone']]]
  real.extend([(la,ra),(lb,rb)]);permuted.extend([(la,rb),(lb,ra)]);negative.extend([(la,lb),(ra,rb)]);weights.extend([row['pair_weight']]*2)
 w=z.new_tensor(weights,dtype=torch.float32)
 def distances(edges):
  ids=torch.tensor(edges,dtype=torch.long,device=z.device);return (z[ids[:,0]].float()-z[ids[:,1]].float()).square().mean(1)
 real_mse=distances(real);perm_mse=distances(permuted);negative_mse=distances(negative)
 # Compute BOTH association terms in every arm so Z/R/P keep the same operations.
 real_loss=(w*real_mse).sum();perm_loss=(w*perm_mse).sum();positive=real_loss if arm=='R' else perm_loss if arm=='P' else real_loss*0
 different=(w*F.relu(1-torch.sqrt(negative_mse+1e-12)).square()).sum();std=torch.sqrt(z.float().var(dim=0,unbiased=False)+1e-4);variance=F.relu(.5-std).mean();total=positive+different+.1*variance
 return total,dict(eq_real=real_loss,eq_permuted=perm_loss,different=different,variance=variance,representation_std=std.mean())
def make_embeddings(model,head,x,edge,cids,cones,device,member_cache):
 h=model.encode(x,edge);pooled=[]
 for cid in cids:
  c=cones[cid]
  if cid not in member_cache:member_cache[cid]=torch.tensor(c['graph_rows'],dtype=torch.long,device=device)
  pooled.append(torch.cat([h[c['root_row']],h[member_cache[cid]].mean(0)],0))
 # h remains differentiable through pooling. No torch.no_grad or detach here.
 return head(torch.stack(pooled))
def prepare_binding(mode,seed,arm):
 c=read(O/'RUN_CONTRACT.json');assert c['training_started'] is False
 for path,h in c['frozen_files'].items():assert sha(R/path)==h,path
 return dict(mode=mode,seed=seed,arm=arm,contract_sha=sha(O/'RUN_CONTRACT.json'),engine_sha=sha(Path(__file__)),pretrain_updates=50,finetune_updates=200,init_sha=sha(H/f'init_s{seed}.pt'))
def pretrain(mode,seed,arm):
 assert 'ginvenv_gpu' in os.sys.executable and torch.cuda.is_available();binding=prepare_binding(mode,seed,arm);out=O/'runs'/mode/f'seed{seed}'/arm/'pretrain';out.mkdir(parents=True,exist_ok=True)
 if (out/'COMPLETE.json').exists():assert read(out/'binding.json')==binding;return read(out/'COMPLETE.json')
 if (out/'binding.json').exists():assert read(out/'binding.json')==binding
 else:write(out/'binding.json',binding)
 set_inputs();device='cuda';seed_all(seed);model,initial=load_initial(seed,device)
 for n,p in model.named_parameters():p.requires_grad_(not n.startswith('classifier.'))
 seed_all(seed+777);head=Projection().to(device);optimizer=torch.optim.Adam([p for p in model.parameters() if p.requires_grad]+list(head.parameters()),lr=.0002,weight_decay=.001);start=0;history=[]
 if (out/'resume.pt').exists():
  saved=torch.load(out/'resume.pt',map_location=device,weights_only=False);assert saved['binding']==binding;model.load_state_dict(saved['model']);head.load_state_dict(saved['projection']);optimizer.load_state_dict(saved['optimizer']);start=saved['completed'];history=saved['history']
 # Only the train graph is loaded here. No validation/test labels or features.
 folder=R/T.CONTRACT['shared_inputs']['trans_train']['folder'];xraw=np.load(folder/'x39.npy',mmap_mode='r');edge=np.load(folder/'edge_index.npy',mmap_mode='r')
 # Same normalization as the frozen downstream loader, with NO label/mask read.
 x=torch.tensor(np.asarray(xraw),device=device);structural=((x[:,25:]-torch.tensor(T.NORM['mean'][25:],device=device))/torch.tensor(T.NORM['std'][25:],device=device)).clamp(-10,10);x=torch.cat([x[:,:25],structural],1);del structural;edges=torch.tensor(np.asarray(edge),device=device)
 inventory=read(O/'function_inventory.json');byid={p['pair_id']:p for p in inventory};cones={c['cone_id']:c for c in read(J/'final_cones.json')};cache={}
 for update in range(start+1,51):
  begin=time.perf_counter();seed_all(seed+100000+update);model.train();head.train();optimizer.zero_grad(set_to_none=True);rr=batch_rows(mode,seed,update);cids=sorted({p[k] for row in rr for p in [byid[row['pair_a']],byid[row['pair_b']]] for k in ['left_cone','right_cone']});index={c:i for i,c in enumerate(cids)}
  with torch.autocast('cuda',dtype=torch.bfloat16):z=make_embeddings(model,head,x,edges,cids,cones,device,cache)
  loss,parts=terms(z,rr,byid,index,arm);assert torch.isfinite(loss);loss.backward();norm=torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad]+list(head.parameters()),1.0);assert torch.isfinite(norm);optimizer.step();del loss,z
  row=dict(update=update,seconds=time.perf_counter()-begin,grad_norm=float(norm),**{k:float(v.detach()) for k,v in parts.items()});del parts;history.append(row)
  save(out/'resume.pt',dict(binding=binding,completed=update,model=model.state_dict(),projection=head.state_dict(),optimizer=optimizer.state_dict(),history=history));write(out/'history.json',history);print(mode,seed,arm,update,row,flush=True)
 for name,value in model.state_dict().items():
  if name.startswith('classifier.'):assert torch.equal(value,initial[name]),name
 encoder={n:v.detach().cpu() for n,v in model.state_dict().items() if not n.startswith('classifier.')};save(out/'encoder.pt',encoder);write(out/'COMPLETE.json',dict(binding=binding,updates=50,encoder_sha=sha(out/'encoder.pt'),classifier_unchanged=True,selected='fixed_last_update50',new_SAT_queries=0,peak_cuda_bytes=torch.cuda.max_memory_allocated()))
 return read(out/'COMPLETE.json')
def predict(model,domain,split):
 d=T.load(domain,split,'A');model.eval()
 with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):p=torch.softmax(model(d['x'],d['edge']).float(),1)[:,1].cpu().numpy()
 assert np.isfinite(p).all();del d;gc.collect();torch.cuda.empty_cache();return p
def finetune(mode,seed,arm):
 assert 'ginvenv_gpu' in os.sys.executable and torch.cuda.is_available();binding=prepare_binding(mode,seed,arm);base=O/'runs'/mode/f'seed{seed}'/arm;pre=read(base/'pretrain/COMPLETE.json');assert pre['binding']==binding and pre['updates']==50 and pre['encoder_sha']==sha(base/'pretrain/encoder.pt');out=base/'finetune';out.mkdir(parents=True,exist_ok=True)
 if (out/'COMPLETE.json').exists():assert read(out/'binding.json')==binding;return
 if (out/'binding.json').exists():assert read(out/'binding.json')==binding
 else:write(out/'binding.json',binding)
 set_inputs();seed_all(seed);model,initial=load_initial(seed,'cuda');encoded=torch.load(base/'pretrain/encoder.pt',map_location='cuda',weights_only=True);state=model.state_dict();assert set(encoded)=={n for n in state if not n.startswith('classifier.')};state.update(encoded);model.load_state_dict(state)
 for n,v in model.state_dict().items():
  if n.startswith('classifier.'):assert torch.equal(v,initial[n])
 optimizer=torch.optim.Adam(model.parameters(),lr=.0002,weight_decay=.001);manifest=read(H/'manifest.json');domains={};slots={};start=0;history=[];best=dict(score=-1.,epoch=-1)
 if (out/'resume.pt').exists():
  saved=torch.load(out/'resume.pt',map_location='cuda',weights_only=False);assert saved['binding']==binding;model.load_state_dict(saved['model']);optimizer.load_state_dict(saved['optimizer']);start=saved['completed'];history=saved['history'];best=saved['best']
 for dm in ['orig','trans']:
  d=T.load(dm,'train','A');d['base_indices']=torch.tensor(np.flatnonzero(np.load(H/f'{dm}_base_mask.npy')),device='cuda');assert int((d['y'][d['base_indices']]==1).sum())==manifest['counts'][dm]['base_positive'];domains[dm]=d;slots[dm]=torch.tensor(np.load(H/f'{dm}_H_slots.npy'),device='cuda')
 for update in range(start+1,201):
  seed_all(seed+update-1);model.train();optimizer.zero_grad(set_to_none=True);losses=[]
  for dm,d in domains.items():
   ids=torch.cat([d['base_indices'],slots[dm][update-1]])
   with torch.autocast('cuda',dtype=torch.bfloat16):logits=model(d['x'],d['edge'])
   loss=T.domain_loss(logits,d['y'],ids);assert torch.isfinite(loss);loss.backward();losses.append(float(loss.detach()));del logits,loss,ids
  grad=torch.nn.utils.clip_grad_norm_(model.parameters(),1.0);assert torch.isfinite(grad);optimizer.step();row=dict(update=update,orig_loss=losses[0],trans_loss=losses[1])
  if update%5==0:
   p=predict(model,'trans','val');metric=T.metrics(p,'trans','val',.5)[0]['trusted']['ap'];row['val_ap']=metric
   if metric>best['score']:best=dict(score=metric,epoch=update);save(out/'best.pt',model.state_dict());np.save(out/'selected_val_scores.npy',p)
  history.append(row);save(out/'resume.pt',dict(binding=binding,completed=update,model=model.state_dict(),optimizer=optimizer.state_dict(),best=best,history=history));write(out/'history.json',history)
 # No test evaluation is automatically triggered by this training runner.
 write(out/'COMPLETE.json',dict(binding=binding,updates=200,best=best,checkpoint_sha=sha(out/'best.pt'),test_evaluated=False,followup='freeze validation thresholds,then evaluate detection on full val/test;test paired stability remains unavailable'))
def main():
 p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--stage',choices=['pretrain','finetune'],required=True);p.add_argument('--mode',choices=['main','strict'],default='main');p.add_argument('--seed',type=int,choices=[42,1,2],default=42);p.add_argument('--arm',choices=['Z','R','P'],required=True);a=p.parse_args()
 if not a.execute:print('No training started. --execute is required after user authorizes this prepared experiment.');return
 (pretrain if a.stage=='pretrain' else finetune)(a.mode,a.seed,a.arm)
if __name__=='__main__':main()
