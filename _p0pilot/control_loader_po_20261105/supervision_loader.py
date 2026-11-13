"""Explicit, fail-closed consumer of frozen five-arm supervision. No model imports."""
from pathlib import Path
from dataclasses import dataclass
import hashlib,json
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def archive(p):
 with np.load(p,allow_pickle=False) as z:return {k:z[k] for k in z.files}
@dataclass(frozen=True)
class SupervisionStep:
 domain:str
 arm:str
 step:int
 variant:str
 indices:np.ndarray
 positive:np.ndarray
 common_negative:np.ndarray
 replacement_negative:np.ndarray
 pair_ids:np.ndarray
 def torch_indices(self,device='cpu'):
  import torch
  return torch.tensor(self.indices,dtype=torch.long,device=device)
class FiveGroupLoader:
 def __init__(self,root=ROOT,verify_hashes=True):
  self.root=Path(root);self.folder=self.root/'_p0pilot/control_budget_bounded_20261105';self.contract=read(self.folder/'EXPERIMENT_CONTRACT.json');self.feature_contract=read(self.root/'_p0pilot/control_boundary_v3_20261104/input_contract.json');self.normalization=archive(self.root/'_p0pilot/control_boundary_v3_20261104/normalization.npz');self.pools={};self.common={};self.sequences={};self.graphs={}
  if self.contract['status']!='OFFLINE_FAIRNESS_VERIFIED_NOT_AUTHORIZED_TO_TRAIN':raise ValueError('Unexpected supervision contract status')
  if verify_hashes:self.verify_bindings()
  for dm in ['orig','trans']:
   key=dm+'_train';self.pools[dm]=archive(self.folder/('pools_'+key+'.npz'));self.common[dm]=np.load(self.folder/('common_'+key+'.npy'),mmap_mode='r',allow_pickle=False)
   for variant in self.contract['variants']:self.sequences[dm,variant]=np.load(self.folder/(variant+'_'+key+'_pairs.npy'),mmap_mode='r',allow_pickle=False)
 def verify_bindings(self):
  manifests=[read(self.folder/'COMPLETE.json')['files'],self.contract['inputs'],read(self.root/'_p0pilot/control_overall_contract_20261105/FIVE_GROUP_CONTRACT.json')['inputs']]
  checked={}
  for manifest in manifests:
   for name,expected in manifest.items():
    if name in checked:
     if checked[name]!=expected:raise ValueError('Conflicting bindings: '+name)
     continue
    if sha(self.root/name)!=expected:raise ValueError('Input hash mismatch: '+name)
    checked[name]=expected
  self.checked_files=checked
 def arrays(self,domain,split='train'):
  if domain not in ['orig','trans'] or split not in ['train','val','test']:raise ValueError('Unknown domain/split')
  key=domain+'_'+split
  if key not in self.graphs:
   d=self.root/self.feature_contract['shared_inputs'][key]['folder'];self.graphs[key]={n:np.load(d/(n+'.npy'),mmap_mode='r',allow_pickle=False) for n in ['x39','edge_index','edge_roles','y','trusted','physical']}
  return self.graphs[key]
 def normalized_x(self,domain,split='train'):
  raw=self.arrays(domain,split)['x39'];result=np.array(raw,dtype=np.float32,copy=True);result[:,25:]=np.clip((result[:,25:]-self.normalization['mean'][25:])/self.normalization['std'][25:],-10,10)
  return result
 def torch_graph(self,domain,split='train',device='cpu'):
  import torch
  a=self.arrays(domain,split)
  # No default training mask: consumers must use step().torch_indices().
  return dict(x=torch.tensor(self.normalized_x(domain,split),dtype=torch.float32,device=device),edge=torch.tensor(np.asarray(a['edge_index']),dtype=torch.long,device=device),y=torch.tensor(np.asarray(a['y']),dtype=torch.long,device=device))
 def step(self,domain,arm,step,variant='main_fanout05',seed=42):
  if domain not in self.pools:raise ValueError('Unknown domain')
  if arm not in self.contract['arms']:raise ValueError('Unknown arm')
  if variant not in self.contract['variants']:raise ValueError('Unknown variant')
  if type(step) is not int or not 0<=step<200:raise ValueError('step is zero-based integer0..199')
  if type(seed) is not int or seed not in self.contract['frozen']['seeds']:raise ValueError('Unknown seed')
  pool=self.pools[domain];pairs=np.asarray(self.sequences[domain,variant][step],np.int64);modes=np.array([m=='N' for m in self.contract['arms'][arm]],bool);extras=np.where(modes[pool['category'][pairs]],pool['N'][pairs],pool['H'][pairs]);positive=np.array(pool['positive'],np.int64,copy=True);common=np.array(self.common[domain][step],np.int64,copy=True);ids=np.concatenate([positive,common,extras]).astype(np.int64,copy=False)
  for v in [ids,positive,common,extras,pairs]:v.flags.writeable=False
  return SupervisionStep(domain,arm,step,variant,ids,positive,common,extras,pairs)
