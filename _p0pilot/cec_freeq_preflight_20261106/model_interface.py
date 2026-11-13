"""Frozen-contract25d free-Q DAG encoder and actual scheduled batch loader.

No optimizer, training loop, solver, detector, safety-label or39d-feature loading.
"""
from pathlib import Path
import collections,hashlib,importlib.util,json,math
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
R=Path(__file__).resolve().parents[2];C=R/'_p0pilot/cec_po_contract_20261106';V=R/'_p0pilot/cec_hard_validation_20261106'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
L=load('frozen_freeQ_array_schema',R/'_p0pilot/cec_hard_boundary_20261106/local_interface.py')

class Loader:
 def __init__(self):
  assert read(C/'VERIFIED.json')['passed']
  self.contract=read(C/'FAIR_MODEL_CONTRACT.json')
  for n,h in read(C/'FROZEN_INDICES.json').items():assert sha(C/n)==h,n
  self.schedule=read(C/'SCHEDULE_SEED42.json');self.training={u['unit_id']:u for u in read(C/'TRAINING_POOL.json')}
  local=read(V/'local_graphs.json');self.graphs=dict(zip(local['cone_ids'],local['graphs']));self.contexts=dict(zip(local['cone_ids'],local['contexts']))
  self.tokens={m['context_key']:m['tokens'] for m in read(R/'_p0pilot/cec_interface_minimal_20261105/boundary_maps_audit_only.json')}
 def arrays(self,ids,tag):
  assert ids and len(ids)==len(set(ids));graphs=[self.graphs[c] for c in ids];keys=[self.contexts[c] for c in ids]
  result=L.collate(graphs,keys,self.tokens,tag)
  for i,g in enumerate(graphs):
   L.validate(g);a,b=result['graph_ptr'][i:i+2];assert b-a==len(g['op'])
   # Every local node is an ancestor of the root,including PI/Q and constants.
   inc=collections.defaultdict(list)
   for s,d,role,phase in g['edge']:inc[d].append(s)
   visited=set();todo=[g['root']]
   while todo:
    j=todo.pop()
    if j in visited:continue
    visited.add(j);todo+=inc[j]
   assert len(visited)==len(g['op']) and len(g['comb_names'])==sum(o>=4 for o in g['op'])
  return result
 def batch(self,update,device='cpu'):
  step=self.schedule[update-1];assert step['update']==update;ids=sorted({c for u in step['units'] for c in u['cone_ids']});ix={c:j for j,c in enumerate(ids)}
  arrays=self.arrays(ids,update);tensors=pack(arrays,device);anchors=[];candidates=[];real=[];perm=[];neg=[];qw=[];nw=[]
  for u in step['units']:
   assert self.training[u['unit_id']]['split']=='train'
   anchors += [ix[c] for c in u['anchors']];candidates += [[ix[c] for c in row] for row in u['candidates']]
   real+=u['real_targets'];perm+=u['permuted_targets'];neg +=[[ix[a],ix[b]] for a,b in u['common_negative_edges']]
   qw +=[u['query_weight']]*len(u['anchors']);nw +=[u['negative_weight']]*len(u['common_negative_edges'])
  losses={k:torch.tensor(v,device=device,dtype=torch.float32 if k in ['query_weight','negative_weight'] else torch.long) for k,v in dict(anchors=anchors,candidates=candidates,real=real,permuted=perm,negative_edges=neg,query_weight=qw,negative_weight=nw).items()}
  return dict(update=update,cone_ids=ids,records=step['units'],arrays=arrays,graph=tensors,loss=losses)

def pack(a,device='cpu'):
 """Only25d x and local directed topology/role/phase enter the encoder."""
 n=len(a['x']);op=a['x'][:,:9].argmax(1);assert a['x'].shape==(n,25) and np.isfinite(a['x']).all()
 assert np.all((a['x'][:,:9]==0)|(a['x'][:,:9]==1)) and np.all(a['x'][:,:9].sum(1)==1)
 src,dst=a['edge_index'];role=a['edge_role'];phase=a['edge_phase'];levels=a['level'];gi=a['graph_index']
 assert np.all(src<dst) and np.all(levels[src]<levels[dst]) and np.array_equal(gi[src],gi[dst])
 assert set(role.tolist())<=set(range(5)) and set(phase.tolist())<={0,1}
 plans=[];consumed=[]
 for lev in sorted(set(levels[op>=4].tolist())):
  nodes=np.flatnonzero((levels==lev)&(op>=4));lookup=np.full(n,-1,np.int64);lookup[nodes]=np.arange(len(nodes));ee=np.flatnonzero(levels[dst]==lev);counts=np.bincount(lookup[dst[ee]],minlength=len(nodes));assert np.all(counts>0)
  groups=[]
  for r in range(5):
   ii=ee[role[ee]==r]
   if not len(ii):continue
   groups.append(dict(role=r,src=torch.tensor(src[ii],device=device),dst=torch.tensor(lookup[dst[ii]],device=device),phase=torch.tensor(phase[ii],device=device),edges=len(ii)))
  plans.append(dict(level=int(lev),nodes=torch.tensor(nodes,device=device),denominator=torch.tensor(np.sqrt(counts),device=device,dtype=torch.float32)[:,None],groups=groups,node_count=len(nodes)))
  consumed+=ee.tolist()
 assert sorted(consumed)==list(range(len(src)))
 leaves=np.flatnonzero(op<4);comb=np.flatnonzero(op>=4)
 assert len(leaves)+sum(p['node_count'] for p in plans)==n
 return dict(x=torch.tensor(a['x'],device=device),leaf=torch.tensor(leaves,device=device),comb=torch.tensor(comb,device=device),plans=plans,root_index=torch.tensor(a['root_index'],device=device),graph_index=torch.tensor(gi,device=device),graph_count=len(a['root_index']),comb_lengths=torch.tensor(np.bincount(gi[comb],minlength=len(a['root_index'])),device=device,dtype=torch.float32),nodes=n,edges=len(src),leaf_count=len(leaves),comb_count=len(comb),max_level=int(levels.max()))

class FreeQModel(nn.Module):
 def __init__(self):
  super().__init__();self.input=nn.Linear(25,64);self.role_maps=nn.ModuleList([nn.Linear(64,64,bias=False) for _ in range(5)]);self.phase_embedding=nn.Embedding(2,64);nn.init.zeros_(self.phase_embedding.weight);self.gru=nn.GRUCell(64,64);self.norm=nn.LayerNorm(64)
 def encode(self,b,return_internal=False):
  x=b['x'];assert x.dtype==torch.float32 and x.shape[1]==25
  base=F.relu(self.input(x));h=torch.zeros_like(base).index_copy(0,b['leaf'],self.norm(base[b['leaf']]));visited=b['leaf_count'];edges=0;updates=[]
  for p in b['plans']:
   # Only states computed at earlier DAG levels are read. Duplicate pins stay duplicate.
   pieces=[];dest=[]
   for g in p['groups']:
    msg=self.role_maps[g['role']](h[g['src']]);msg=msg*(1-2*g['phase'][:,None]).to(msg.dtype)+self.phase_embedding(g['phase']);pieces.append(msg);dest.append(g['dst']);edges+=g['edges']
   aggregate=torch.zeros((p['node_count'],64),device=x.device,dtype=x.dtype).index_add(0,torch.cat(dest),torch.cat(pieces))/p['denominator']
   new=self.norm(self.gru(aggregate,base[p['nodes']]));h=h.index_copy(0,p['nodes'],new);visited+=p['node_count'];updates.append(p['node_count'])
  assert visited==b['nodes'] and edges==b['edges']
  roots=h[b['root_index']];audit=dict(consumed_nodes=visited,consumed_comb_nodes=sum(updates),consumed_pin_edges=edges,levels=len(updates),max_level=b['max_level'])
  if return_internal:return roots,h,base,audit
  return roots,audit
 def readouts(self,b):
  roots,h,base,audit=self.encode(b,True);mean=h.new_zeros(b['graph_count'],64).index_add(0,b['graph_index'][b['comb']],h[b['comb']])/b['comb_lengths'][:,None]
  return dict(root64=roots,mean64=mean,concat128=torch.cat([roots,mean],1)),audit

def objective(root,b):
 assert root.dtype==torch.float32
 anchor=root[b['anchors']][:,None,:];other=root[b['candidates']];dist=torch.sqrt((anchor-other).square().mean(-1)+1e-12);logits=-dist
 real=(b['query_weight']*F.cross_entropy(logits,b['real'],reduction='none')).sum();wrong=(b['query_weight']*F.cross_entropy(logits,b['permuted'],reduction='none')).sum()
 ne=b['negative_edges'];nd=torch.sqrt((root[ne[:,0]]-root[ne[:,1]]).square().mean(-1)+1e-12);different=(b['negative_weight']*F.relu(1-nd).square()).sum();variance=.1*F.relu(.5-torch.sqrt(root.var(0,unbiased=False)+1e-4)).mean()
 pieces=dict(CE_R=real,CE_P=wrong,different=different,variance_weighted=variance)
 # Compute both associations in every group;only their coefficients differ.
 common=different+variance;totals=dict(Z=common+0.*real+0.*wrong,R=common+real+0.*wrong,P=common+wrong+0.*real)
 return pieces,totals,dict(distances=dist,logits=logits,negative_distances=nd)

def state_digest(m):
 d=hashlib.sha256()
 for n,t in sorted(m.state_dict().items()):d.update((n+str(t.dtype)+str(tuple(t.shape))).encode());d.update(t.detach().cpu().contiguous().numpy().tobytes())
 return d.hexdigest()
def fresh(device='cpu'):
 torch.manual_seed(42)
 if torch.cuda.is_available():torch.cuda.manual_seed_all(42)
 return FreeQModel().to(device)
