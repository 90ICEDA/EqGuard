"""One explicit loader/loss interface for the frozen five-arm contract; never trains."""
from pathlib import Path
import collections,hashlib,json
import numpy as np
import torch
import torch.nn.functional as F
R=Path(__file__).resolve().parents[2];C=R/'_p0pilot/cec_relative_contract_20261106'
ARMS=['Z','A_R','A_P','S_R','S_P']
ASSOC=['A_R','A_P','S_R','S_P']
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
class Interface:
 def __init__(self):
  self.contract=read(C/'RELATIVE_OBJECTIVE_CONTRACT.json');self.triples={t['triple_id']:t for t in read(C/'triple_pool.json')};self.schedule=read(C/'schedule_seed42.json');self.cones={c['cone_id']:c for c in read(R/'_p0pilot/cec_joint_expand_20261105/final_cones.json')}
  self.batches={u:self.batch(u) for u in range(1,51)}
 def batch(self,u):
  rows=[r for r in self.schedule if r['update']==u];ids=sorted({c for r in rows for c in self.triples[r['triple_id']]['cones']});ix={c:i for i,c in enumerate(ids)}
  anchors=[];candidates=[];real=[];perm=[];qweights=[];neg=[];nweights=[];targets=[]
  for r in rows:
   t=self.triples[r['triple_id']];a,b,c,d,e,f=[ix[c] for c in t['cones']];targets.append(dict(triple_id=t['triple_id'],cone_ids=t['cones'],indices=[a,b,c,d,e,f]))
   for anchor,cc,ir,ip in [(a,[b,d,f],0,1),(c,[b,d,f],1,0),(b,[a,c,e],0,1),(d,[a,c,e],1,0)]:
    anchors.append(anchor);candidates.append(cc);real.append(ir);perm.append(ip);qweights.append(r['source_block_weight']/4)
   neg +=[(a,c),(b,d),(a,f),(c,f),(b,e),(d,e)];nweights += [r['source_block_weight']/6]*6
  return dict(update=u,rows=rows,cone_ids=ids,anchors=anchors,candidates=candidates,real=real,permuted=perm,query_weights=qweights,negative_edges=neg,negative_weights=nweights,loaded_triples=targets)
 def tensors(self,b,device):
  return {k:torch.tensor(b[k],device=device,dtype=torch.float32 if k in ['query_weights','negative_weights'] else torch.long) for k in ['anchors','candidates','real','permuted','query_weights','negative_edges','negative_weights']}
def terms(z,b):
 # z.float() keeps all distance/CE arithmetic FP32 inside the BF16 encoder run.
 zz=z.float();a=zz[b['anchors']][:,None,:];v=zz[b['candidates']];mse=(a-v).square().mean(-1);dist=torch.sqrt(mse+1e-12);logits=-dist
 qi=torch.arange(len(dist),device=z.device);w=b['query_weights'];nw=b['negative_weights'];ne=b['negative_edges']
 parts={
  'A_R':(w*mse[qi,b['real']]).sum(),
  'A_P':(w*mse[qi,b['permuted']]).sum(),
  'S_R':(w*F.cross_entropy(logits,b['real'],reduction='none')).sum(),
  'S_P':(w*F.cross_entropy(logits,b['permuted'],reduction='none')).sum(),
  'different':(nw*F.relu(1-torch.sqrt((zz[ne[:,0]]-zz[ne[:,1]]).square().mean(-1)+1e-12)).square()).sum(),
  'variance_weighted':.1*F.relu(.5-torch.sqrt(zz.var(0,unbiased=False)+1e-4)).mean()
 }
 total={arm:parts['different']+parts['variance_weighted']+sum((1. if arm==k else 0.)*parts[k] for k in ASSOC) for arm in ARMS}
 return parts,total,dict(distances=dist,mse=mse,logits=logits)
def audit_loaded(i):
 src=collections.Counter();tr=collections.Counter();nc=collections.Counter();detail=[];globalpos={k:set() for k in ['R','P']};globalneg=set();parent={k:{} for k in ['R','P']}
 def addr(cid):
  c=i.cones[cid];return (c['split'],c['view'],c['root_row'])
 def edge(a,b):return tuple(sorted([a,b]))
 def find(mode,x):
  p=parent[mode];p.setdefault(x,x)
  if p[x]!=x:p[x]=find(mode,p[x])
  return p[x]
 for u,b in i.batches.items():
  ids=b['cone_ids'];r=collections.Counter();p=collections.Counter();an=collections.Counter()
  for j,(a,cand) in enumerate(zip(b['anchors'],b['candidates'])):
   aa=addr(ids[a]);ar=addr(ids[cand[b['real'][j]]]);ap=addr(ids[cand[b['permuted'][j]]]);cc=addr(ids[cand[2]])
   assert ar!=ap and ar!=cc and ap!=cc
   for mode,target in [('R',ar),('P',ap)]:globalpos[mode].add(edge(aa,target));parent[mode][find(mode,aa)]=find(mode,target)
   w=b['query_weights'][j];r[ar]+=w;p[ap]+=w;an[aa]+=w
  assert r==p==an
  for a,c in b['negative_edges']:globalneg.add(edge(addr(ids[a]),addr(ids[c])))
  for row in b['rows']:
   t=i.triples[row['triple_id']];assert t['split']=='train';src[row['source']]+=1;tr[row['triple_id']]+=1
   for c in t['cones']:
    z=i.cones[c];nc.update((z['view'],v) for v in z['graph_rows'])
  assert abs(sum(b['query_weights'])-1)<1e-12 and abs(sum(b['negative_weights'])-1)<1e-12
  detail.append(dict(update=u,sources=len(b['rows']),unique_readouts=len(ids),positive_pairs=len(b['anchors'])//2,queries=len(b['anchors']),distances=3*len(b['anchors']),common_negatives=len(b['negative_edges']),weighted_target_mass_identical=True))
 for mode in ['R','P']:
  assert not globalpos[mode]&globalneg
  assert not any(find(mode,a)==find(mode,b) for a,b in globalneg)
 assert len(src)==8 and set(src.values())=={25} and max(tr.values())==2 and max(nc.values())==27
 assert sum(x['positive_pairs'] for x in detail)==400 and sum(x['queries'] for x in detail)==800 and sum(x['distances'] for x in detail)==2400 and sum(x['common_negatives'] for x in detail)==1200
 return detail,dict(sources=dict(src),unique_triples=len(tr),max_function_exposure=max(tr.values()),max_node_pooling=max(nc.values()),global_conflicts=0)
