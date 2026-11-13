"""Independent reverse-distance checks and explicit closed dead-component certificates."""
import audit as C
import numpy as np,collections,json,ast
from scipy.sparse import csr_matrix
O=C.O;R=C.R
def b(v):return v=='True' or v is True
def distances(pred,seed,initial=0):
 n=pred.shape[0];d=np.full(n,-1,np.int32);q=collections.deque()
 for i in set(map(int,seed)):d[i]=initial;q.append(i)
 while q:
  u=q.popleft()
  for v in pred.indices[pred.indptr[u]:pred.indptr[u+1]]:
   if d[v]<0:d[v]=d[u]+1;q.append(int(v))
 return d
def main():
 done=C.read(O/'AUDIT_COMPLETE.json');assert C.read(O/'ANALYSIS_COMPLETE.json')['passed'];rr=C.rows(O/'NODE_BOUNDARIES.csv');lm={(r['key'],r['row']):r for r in rr};fc=C.read(C.V/'input_contract.json');checks=0;seedcounts=[]
 for key in done['scope']:
  folder=R/fc['shared_inputs'][key]['folder'];x=np.load(folder/'x39.npy',mmap_mode='r');e=np.load(folder/'edge_index.npy',mmap_mode='r');roles=np.load(folder/'edge_roles.npy',mmap_mode='r');n=len(x);cols=fc['columns39'];ffcols=[i for i,s in enumerate(cols[:25]) if 'DFF' in s];ff=x[:,ffcols].sum(1)>0;comb=~ff[e[0]]&~ff[e[1]];pred=csr_matrix((np.ones(int(comb.sum()),np.int8),(e[1,comb],e[0,comb])),shape=(n,n));po=np.flatnonzero((x[:,30]==0)&~ff);pdist=distances(pred,po)
  dd={}
  for bit,label in [(1,'D'),(4,'SI')]:
   mask=(~ff[e[0]])&ff[e[1]]&((roles&bit)!=0);dd[label]=distances(pred,e[0,mask],1)
  full_mask=(~ff[e[1]])|((roles&1)!=0);fp=csr_matrix((np.ones(int(full_mask.sum()),np.int8),(e[1,full_mask],e[0,full_mask])),shape=(n,n));functional=distances(fp,np.flatnonzero(x[:,30]==0));old=np.asarray(x[:,30])>=0
  for r in [r for r in rr if r['key']==key]:
   i=int(r['row']);assert bool(ff[i])==b(r['root_is_register'])
   if not ff[i]:
    for name,d in [('D_distance',dd['D']),('SI_distance',dd['SI']),('PO_before_register_distance',pdist),('PO_Donly_structural_distance',functional)]:assert int(r[name])==int(d[i]),(key,i,name,r[name],d[i]);checks+=1
    assert b(r['PO_Donly_structural_path'])==bool(old[i])
  seedcounts.append(dict(key=key,registers=int(ff.sum()),register_columns=ffcols,nonregister_audited=sum(r['key']==key and not b(r['root_is_register']) for r in rr),Donly_PO_reach_identical_to_existing_column30_on_audited=True))
 C.table('INDEPENDENT_DISTANCE_CHECKS.csv',seedcounts)
 # Literal model interface and installed PyG direction checks, no model imported.
 loader=R/'_p0pilot/control_loader_po_20261105/supervision_loader.py';tree=ast.parse(loader.read_text(encoding='utf-8'));f=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='torch_graph');ret=next(n.value for n in ast.walk(f) if isinstance(n,ast.Return));assert isinstance(ret,ast.Call) and [k.arg for k in ret.keywords]==['x','edge','y'];model=(R/'_p0pilot/control_best200_20261104/evaluate.py').read_text(encoding='utf-8');assert 'def forward(self,x,e)' in model and 'self.post(h,e)' in model and 'edge_roles' not in model;mp=R/'ginvenv_gpu/Lib/site-packages/torch_geometric/nn/conv/message_passing.py';gin=R/'ginvenv_gpu/Lib/site-packages/torch_geometric/nn/conv/gin_conv.py';assert 'flow: str = "source_to_target"' in mp.read_text(encoding='utf-8');assert 'def message(self, x_j: Tensor) -> Tensor:' in gin.read_text(encoding='utf-8')
 # Inspect closed dead fanout components for every fixed case endpoint labeled no-boundary.
 cases=C.rows(O/'FIXED_CASES_BOUNDARY_RESULT.csv');need={}
 for c in cases:
  for field in ['positive_row','normal_row']:
   r=lm[c['key'],c[field]]
   if b(r['no_output_or_register_boundary']):need[r['key'],r['row']]=r
 lib=C.NL.load_library(C.F/'verilog_lib.v');cert=[];cache={}
 for (key,row),r in sorted(need.items()):
  path=C.F/('trans' if key.startswith('trans') else 'orig')/(r['view']+'.v');raw=cache.setdefault(str(path),C.raw_network(path,lib)) if str(path) not in cache else cache[str(path)];root=r['node_name'];seen={root};q=collections.deque([root])
  while q:
   u=q.popleft()
   for t in raw['succ'][u]:
    if t not in seen:seen.add(t);q.append(t)
  assert not (seen&raw['pocells']) and all('DFF' not in raw['cells'][u][0].upper() for u in seen);assert all(raw['succ'][u]<=seen for u in seen);assert len(seen)==int(r['comb_nodes_visited']);sinks=sorted(u for u in seen if not raw['succ'][u]);assert len(sinks)==int(r['dead_end_count']);cert.append(dict(key=key,row=int(row),source=r['source'],view=r['view'],root=root,side=r['side'],parents=r['parents'],source_sha=C.sha(path),closed_no_PO_no_register=True,cells={u:dict(type=raw['pins'][u][0],pins=raw['pins'][u][1],successors=sorted(raw['succ'][u])) for u in sorted(seen)},terminal_cells=sinks,interpretation='structural closed fanout component;not label correction or new functional SAT proof'))
 (O/'DEAD_COMPONENT_CERTIFICATES.json').write_text(json.dumps(cert,ensure_ascii=False,indent=2),encoding='utf-8')
 for p,h in done['protected_inputs'].items():assert C.sha(R/p)==h,p
 result=dict(passed=True,frozen_nodes=len(rr),independent_distance_checks=checks,independent_views=done['views'],actual_pin_role_checks=done['pin_role_checks'],closed_dead_fixed_endpoint_certificates=len(cert),model_interface_verified=['x','edge','y'],edge_roles_not_consumed=True,installed_message_direction='source_to_target',Donly_PO_reach_adds_no_binary_distinction_on_frozen_nodes=True,model_forwards=0,training=0,SAT=0,labels_changed=False,protected_local_runtime={str(p.relative_to(R)):C.sha(p) for p in [loader,mp,gin]})
 (O/'VERIFIED.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(result)
if __name__=='__main__':main()
