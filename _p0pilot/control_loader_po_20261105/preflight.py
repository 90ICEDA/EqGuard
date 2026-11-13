"""Exercise the actual public loader and CPU/CUDA tensors; no model/loss/backward."""
from pathlib import Path
import json,csv,collections
import numpy as np
import torch
from supervision_loader import FiveGroupLoader,sha,read
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent
def main():
 assert not (O/'LOADING_VERIFIED.json').exists();torch.set_num_threads(2);loader=FiveGroupLoader();contract=loader.contract;records=[];digests={};source_total=collections.defaultdict(collections.Counter);views=list(csv.DictReader((R/'_p0pilot/control_overall_contract_20261105/view_dictionary.csv').open(encoding='utf-8-sig')));cuda_steps=0
 assert 'ginvenv_gpu' in str(Path(__import__('sys').executable))
 for dm in ['orig','trans']:
  raw=loader.arrays(dm);graph=loader.torch_graph(dm);assert set(graph)=={'x','edge','y'} and graph['x'].dtype==torch.float32 and graph['edge'].dtype==torch.int64 and graph['y'].dtype==torch.int64;assert torch.isfinite(graph['x']).all();assert graph['x'].shape==(len(raw['y']),39);assert np.array_equal(graph['x'][:,:25].numpy(),raw['x39'][:,:25]);assert np.array_equal(graph['edge'].numpy(),raw['edge_index']);assert np.array_equal(graph['y'].numpy(),raw['y'])
  # Match legacy loader arithmetic, without importing its model/training module.
  ref=torch.from_numpy(np.array(raw['x39'][:,25:],copy=True));ref=((ref-torch.tensor(loader.normalization['mean'][25:]))/torch.tensor(loader.normalization['std'][25:])).clamp(-10,10);assert torch.allclose(graph['x'][:,25:],ref,rtol=0,atol=0);del ref
  vmap={int(v['view_id']):v for v in views if v['key']==dm+'_train'};sources=read(loader.folder/('sources_'+dm+'_train.json'));row_source=np.full(len(raw['y']),-1,np.int16);iscontrol=np.zeros(len(raw['y']),bool)
  for v in vmap.values():row_source[int(v['start']):int(v['physical_stop'])]=sources.index(v['source']);iscontrol[int(v['start']):int(v['physical_stop'])]=v['kind']=='control'
  if torch.cuda.is_available():
   gpu=loader.torch_graph(dm,device='cuda');assert torch.equal(gpu['edge'].cpu(),graph['edge']);assert torch.equal(gpu['y'].cpu(),graph['y']);assert torch.equal(gpu['x'].cpu(),graph['x']);gpu_y=gpu['y']
  for variant in contract['variants']:
   snapshots=[]
   for arm in contract['arms']:
    nodecount=np.zeros(len(raw['y']),np.int64);sourcecount=np.zeros(len(sources),np.int64);ledger=__import__('hashlib').sha256()
    for step in range(200):
     b=loader.step(dm,arm,step,variant);i=b.torch_indices();assert i.dtype==torch.int64 and i.ndim==1;assert int(i.min())>=0 and int(i.max())<len(raw['y']);yy=graph['y'].index_select(0,i);expected=contract['domains'][dm];assert int((yy==1).sum())==expected['positive'] and int((yy==0).sum())==expected['negative_per_update'];assert len(np.unique(b.indices))==len(b.indices);assert (raw['trusted'][b.indices]&raw['physical'][b.indices]).all();assert np.array_equal(b.positive,loader.pools[dm]['positive']);assert np.array_equal(b.common_negative,loader.common[dm][step]);assert np.array_equal(b.pair_ids,loader.sequences[dm,variant][step]);assert not iscontrol[b.positive].any() and not iscontrol[b.common_negative].any();ncontrols=int(iscontrol[b.indices].sum());assert arm!='G0' or ncontrols==0
     # Independent reconstruction from raw files, not the loader's endpoint logic.
     p=loader.pools[dm];reconstructed=[];cursor=0
     for j,(cat,n) in enumerate(expected['block_entries'].items()):
      pairs=b.pair_ids[cursor:cursor+n];cursor+=n;assert (p['category'][pairs]==j).all();endpoint=p['N'] if contract['arms'][arm][j]=='N' else p['H'];reconstructed.extend(endpoint[pairs].tolist())
     assert np.array_equal(b.replacement_negative,np.array(reconstructed,np.int64));assert (raw['y'][b.replacement_negative]==0).all()
     for seed in [1,2]:assert np.array_equal(loader.step(dm,arm,step,variant,seed).indices,b.indices)
     if step in [0,99,199] and torch.cuda.is_available():
      ci=b.torch_indices('cuda');assert torch.equal(gpu_y.index_select(0,ci).cpu(),yy);cuda_steps+=1
     nodecount[b.indices[len(b.positive):]]+=1;sourcecount+=np.bincount(row_source[b.indices[len(b.positive):]],minlength=len(sources));ledger.update(b.indices.tobytes());records.append(dict(domain=dm,variant=variant,arm=arm,update=step+1,indices=len(b.indices),positive=expected['positive'],negative=expected['negative_per_update'],normal_control_entries=ncontrols,index_dtype=str(i.dtype),index_sha=__import__('hashlib').sha256(b.indices.tobytes()).hexdigest()))
    assert nodecount.max()<=128 and sourcecount.max()<=163200;snapshots.append(np.sort(nodecount[nodecount>0]));digests[dm,variant,arm]=ledger.hexdigest()
    for j in np.flatnonzero(sourcecount):source_total[variant,arm][sources[j]]+=int(sourcecount[j])
   assert all(np.array_equal(snapshots[0],h) for h in snapshots[1:])
  del graph
  if torch.cuda.is_available():del gpu,gpu_y;torch.cuda.empty_cache()
 for counts in source_total.values():assert max(counts.values())<=326400
 # Fail-closed guards; no disk mutation or mock training.
 for args in [('orig','bad',0),('bad','G0',0),('orig','G0',-1),('orig','G0',200),('orig','G0',True),('orig','G0',1.5)]:
  try:loader.step(*args)
  except ValueError:pass
  else:raise AssertionError(args)
 for kwargs in [dict(seed=0),dict(variant='old_mask')]:
  try:loader.step('orig','G0',0,**kwargs)
  except ValueError:pass
  else:raise AssertionError(kwargs)
 with (O/'loaded_indices_ledger.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
 report=dict(status='ACTUAL_LOADER_VERIFIED_NO_TRAINING',training=0,model_forward=0,loss_calls=0,backward=0,SAT=0,records=len(records),model_seeds_checked=[42,1,2],matched_old_budget_ledger=True,index_order='all fixed positives,common8192,B,M,U',hash_bound_files=len(loader.checked_files),feature_normalization_exact_CPU_match=True,full_train_graph_CPU_CUDA_copy_checked=torch.cuda.is_available(),CUDA_index_label_checks=cuda_steps,torch_version=torch.__version__,cuda_device=torch.cuda.get_device_name() if torch.cuda.is_available() else None,unknown_arm_step_seed_variant_rejected=True,old_default_training_masks_not_exposed=True,negative_source_node_caps_verified=True,contract_sha=sha(loader.folder/'EXPERIMENT_CONTRACT.json'),loader_sha=sha(O/'supervision_loader.py'),ordered_indices_digest={','.join(k):v for k,v in digests.items()})
 # Verify exact budgets against the separately frozen budget-check ledger.
 expected=list(csv.DictReader((loader.folder/'step_fairness.csv').open(encoding='utf-8-sig')));assert len(expected)==len(records)
 lookup={(r['domain'],r['variant'],r['arm'],int(r['update'])):r for r in expected}
 for r in records:
  e=lookup[r['domain'],r['variant'],r['arm'],r['update']];assert all(int(e[k])==r[k] for k in ['positive','negative','normal_control_entries'])
 (O/'LOADING_VERIFIED.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({k:report[k] for k in ['records','hash_bound_files','CUDA_index_label_checks','training','model_forward','SAT']},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
