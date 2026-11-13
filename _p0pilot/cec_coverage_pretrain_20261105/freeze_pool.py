"""Independent scalar certificates, coverage, weights and permutation feasibility."""
from pathlib import Path
import collections,csv,hashlib,json,sys
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;P=R/'_p0pilot/cec_cone_expand_20261105'
sys.path.insert(0,str(R/'_p0pilot/cec_cone_audit_20261105'));from audit import read,rows,sha,ident,SCHEMA,cone
def write(n,z):
 path=O/n;assert not path.exists(),n;path.write_text(json.dumps(z,ensure_ascii=False,indent=2),encoding='utf-8')
def table(n,rr):
 if not rr:return
 path=O/n;assert not path.exists(),n
 with path.open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def main():
 assert not (O/'POOL_COMPLETE.json').exists()
 old={p['pair_id']:p for p in read(P/'final_pairs.json')};pp={p['pair_id']:p for p in read(O/'candidate_pairs.json')};cc={c['cone_id']:c for c in read(O/'candidate_cones.json')}
 for p in read(O/'bounded_positive_pairs.json'):pp[p['pair_id']]=p
 for c in read(O/'bounded_positive_cones.json'):cc[c['cone_id']]=c
 # Include and reverify original enum-only supplement rather than losing it.
 for pid,p in old.items():
  if not p['proof_ids']:pp.setdefault(pid,p)
 raw={};models={};replay=[];certificates=[];excluded=[]
 def getmodel(c):
  if c['view'] in models:return models[c['view']]
  assert sha(R/c['raw_path'])==c['raw_sha'];m=next(iter(read(R/c['raw_path'])['modules'].values()));raw[c['view']]=m
  drivers={};leaf={};degree={};outmap={}
  def add(b,v):
   assert isinstance(b,int) and b not in outmap,(c['view'],b);outmap[b]=v
  for n,p in m['ports'].items():
   if p['direction']=='input':
    for j,b in enumerate(p['bits']):add(b,('PI',n,j,0));leaf[b]=('PI',n,j,0)
  for n,g in m['cells'].items():
   if 'DFF' in g['type'].upper():
    for pin in ['Q','QN']:
     for b in g['connections'].get(pin,[]):add(b,('Q',n,0,int(pin=='QN')));leaf[b]=('Q',n,0,int(pin=='QN'))
   else:
    assert g['type'] in SCHEMA;pin,ins=SCHEMA[g['type']];assert len(g['connections'][pin])==1
    b=g['connections'][pin][0];add(b,n);drivers[b]=g;degree[n]=0
  successors=collections.defaultdict(set)
  for b,g in drivers.items():
   n=outmap[b]
   for pin in SCHEMA[g['type']][1]:
    assert len(g['connections'][pin])==1
    a=g['connections'][pin][0]
    if not isinstance(a,int):assert a in ['0','1'];continue
    assert a in outmap,('undriven',c['view'],a)
    parent=outmap[a]
    if isinstance(parent,str) and n not in successors[parent]:successors[parent].add(n);degree[n]+=1
  todo=collections.deque(n for n,d in degree.items() if not d);visited=0
  while todo:
   n=todo.popleft();visited+=1
   for nxt in successors[n]:
    degree[nxt]-=1
    if not degree[nxt]:todo.append(nxt)
  assert visited==len(degree),'cycle'
  def evaluate(root,env):
   cache={}
   def ev(b):
    if not isinstance(b,int):assert b in ['0','1'];return int(b)
    if b in cache:return cache[b]
    if b in leaf:
     token=leaf[b];v=env[token[:3]] ^ token[3]
    else:
     g=drivers[b];vls=[ev(g['connections'][pin][0]) for pin in SCHEMA[g['type']][1]];t=g['type']
     if t in ['AND2X2','$and']:v=vls[0]&vls[1]
     elif t in ['OR2X1','$or']:v=vls[0]|vls[1]
     elif t in ['XOR2X1','$xor']:v=vls[0]^vls[1]
     elif t in ['INVX0','$not']:v=1-vls[0]
     else:assert t in ['MX2X1_RS','$mux'];v=vls[1] if vls[2] else vls[0]
    cache[b]=v;return v
   return ev(root)
  models[c['view']]=(m,evaluate);return models[c['view']]
 for p in pp.values():
  if p['pair_id'] in old and p['proof_ids']:continue
  cs=[cc[p[k]] for k in ['left_cone','right_cone']];tokens=sorted({tuple(l[:3]) for z in cs for l in z['leaves']});w=len(tokens)
  patterns=range(1<<w) if w<=13 else [0,(1<<w)-1]+[1<<j for j in range(w)]+[((1<<w)-1)^(1<<j) for j in range(w)]
  outputs=[];witness={}
  for pat in patterns:
   env={t:(pat>>j)&1 for j,t in enumerate(tokens)};vv=[getmodel(z)[1](z['root_bit'],env) for z in cs];assert vv[0]==vv[1],('scalar mismatch',p['pair_id'],pat)
   outputs.append(vv[0]);witness.setdefault(vv[0],dict(values=[env[t] for t in tokens],both_outputs=vv[0]))
  if set(witness)!={0,1}:
   excluded.append(dict(pair_id=p['pair_id'],reason='constant_function' if w<=13 else 'nonconstancy_not_demonstrated',inputs=w,patterns=len(outputs)));continue
  if not p['proof_ids']:
   assert w<=12 and p['enum']['equal'] and p['enum']['nonconstant']
   truthsha=hashlib.sha256(np.packbits(outputs,bitorder='little').tobytes()).hexdigest();assert truthsha==p['enum']['truth_sha']
   certificates.append(dict(pair_id=p['pair_id'],method='independent_scalar_complete_PI_Q_enumeration',semantic_inputs=[list(t) for t in tokens],patterns=len(outputs),truth_sha=truthsha,packed_truth_hex=np.packbits(outputs,bitorder='little').tobytes().hex(),raw_shas=[z['raw_sha'] for z in cs],root_bits=[z['root_bit'] for z in cs],witnesses=witness))
  replay.append(dict(pair_id=p['pair_id'],split=p['split'],inputs=w,patterns=len(outputs),full_enumeration=w<=13,nonconstant=True,old_source_bound_proof=bool(p['proof_ids']),new_pair=p['pair_id'] not in old))
 for z in excluded:pp.pop(z['pair_id'])
 # Rebuild all newly admitted members and check current physical coordinate/labels.
 contract=read(R/'_p0pilot/control_boundary_v3_20261104/input_contract.json');vm={v['view']:(key,v) for key,q in contract['shared_inputs'].items() if key in ['trans_train','trans_val'] for v in q['views']};meta={v['view']:v for v in rows(R/'generate_trans/folds/hosts_bt31/views_meta.csv')};names=[x.strip().lstrip('\\') for x in (R/'generate_trans/folds/hosts_bt31/data/processed/node_names_trans.txt').read_text(encoding='utf-8').splitlines()];arrays={}
 used={p[k] for p in pp.values() for k in ['left_cone','right_cone']};cc={k:c for k,c in cc.items() if k in used}
 for p in pp.values():
  assert p['split'] in ['train','val']
  for key,end in zip(['left_cone','right_cone'],p['root_endpoints']):
   z=cc[p[key]];domain,v=vm[z['view']];assert domain=='trans_'+p['split'] and meta[z['view']]['src_view']==p['source_object']
   if domain not in arrays:
    folder=R/contract['shared_inputs'][domain]['folder'];arrays[domain]={n:np.load(folder/(n+'.npy'),mmap_mode='r') for n in ['y','trusted','physical']}
   ar=arrays[domain];i=z['root_row'];assert end['label']==int(ar['y'][i]) and end['trusted']==bool(ar['trusted'][i]) and ar['physical'][i]
   assert v['start']<=i<v['physical_stop'] and names[v['old_start']+i-v['start']]==z['output_cell']
   if p['pair_id'] not in old:
    m=getmodel(z)[0];maps={n:v['start']+j for j,n in enumerate(names[v['old_start']:v['old_stop']])};rebuild=cone(m,z['root_bit'],maps,z['raw_sha'])
    for name in ['members','graph_rows','leaves','errors','unmapped_members']:assert z[name]==rebuild[name]
    assert m['cells'][z['output_cell']]['connections'][z['output_pin']]==[z['root_bit']]
 parent={}
 def find(x):
  parent.setdefault(x,x)
  if parent[x]!=x:parent[x]=find(parent[x])
  return parent[x]
 for p in pp.values():
  u,v=[find((p['split'],p['source_object'],p['context_id'],p[k])) for k in ['left_cone','right_cone']];parent[max(u,v)]=min(u,v)
 groups=collections.defaultdict(list)
 for p in pp.values():groups[find((p['split'],p['source_object'],p['context_id'],p['left_cone']))].append(p)
 weights=[];sources={s:sorted({p['source_object'] for p in pp.values() if p['split']==s}) for s in ['train','val','test']};assert not set(sources['train'])&set(sources['val'])
 compmap={}
 for comp,rr in groups.items():
  sp,src,ctx,cid=comp;nc=sum(g[0]==sp and g[1]==src for g in groups)
  for p in rr:weights.append(dict(pair_id=p['pair_id'],split=sp,source=src,component=cid,weight=1/len(sources[sp])/nc/len(rr)));compmap[p['pair_id']]=cid
 for sp in ['train','val']:assert np.isclose(sum(z['weight'] for z in weights if z['split']==sp),1)
 coverage=[]
 allc=read(R/'_p0pilot/control_boundary_v3_20261104/input_contract.json')
 for sp in ['train','val','test']:
  views=allc['shared_inputs']['trans_'+sp]['views']
  for host in sorted({meta[v['view']]['host'] for v in views}):
   vv=[v['view'] for v in views if meta[v['view']]['host']==host];pool=[p for p in pp.values() if p['split']==sp and p['source_object'].split('__')[0]==host];pos=[p for p in pool if all(e['trusted'] and e['label']==1 for e in p['root_endpoints'])]
   coverage.append(dict(split=sp,host=host,total_sources=len({meta[v]['src_view'] for v in vv}),paired_sources=len({p['source_object'] for p in pool}),pairs=len(pool),positive_pairs=len(pos),positive_sources=len({p['source_object'] for p in pos})))
 # Full endpoint-preserving permutation within source/context/view direction.
 # Reject known equivalence components; unknown function collisions remain to audit.
 buckets=collections.defaultdict(list)
 for p in pp.values():
  if p['split']=='train':buckets[p['source_object'],p['context_id'],cc[p['left_cone']]['view'],cc[p['right_cone']]['view']].append(p)
 perm=[];unmatched=[]
 for group,rr in sorted(buckets.items()):
  # Maximum matching can be partial. Retain only cycles, so both endpoint multisets match.
  byid={p['pair_id']:p for p in rr};ids=sorted(byid);edges={a:sorted([b for b in ids if compmap[a]!=compmap[b]],key=lambda b:ident(['perm_v1',a,b])) for a in ids};match={}
  def augment(a,seen):
   for b in edges[a]:
    if b in seen:continue
    seen.add(b)
    if b not in match or augment(match[b],seen):match[b]=a;return True
   return False
  for a in ids:augment(a,set())
  mapping={a:b for b,a in match.items()};cycles=set()
  for a in ids:
   path=[];x=a
   while x in mapping and x not in path:path.append(x);x=mapping[x]
   if x in path:cycles.update(path[path.index(x):])
  for a in ids:
   if a in cycles:
    b=mapping[a];perm.append(dict(true_pair_id=a,partner_from_pair_id=b,source=group[0],left_cone=byid[a]['left_cone'],true_right_cone=byid[a]['right_cone'],permuted_right_cone=byid[b]['right_cone'],known_equivalent_component=False))
   else:unmatched.append(dict(pair_id=a,reason='no_closed_endpoint_preserving_derangement_cycle'))
 # Endpoint multiplicities, not just number of rows, are the required invariant.
 assert collections.Counter(p['true_right_cone'] for p in perm)==collections.Counter(p['permuted_right_cone'] for p in perm)
 write('pool_pairs.json',list(pp.values()));write('pool_cones.json',list(cc.values()));write('ENUM_CERTIFICATES.json',certificates);table('scalar_replay.csv',replay);table('excluded_constants.csv',excluded);table('pool_weights.csv',weights);table('coverage_after.csv',coverage);table('permutation_draft.csv',perm);table('permutation_unmatched.csv',unmatched)
 grades={sp:dict(pairs=sum(p['split']==sp for p in pp.values()),native_CEC=sum(p['split']==sp and bool(p['proof_ids']) for p in pp.values()),complete_enum_only=sum(p['split']==sp and not p['proof_ids'] for p in pp.values()),positive_pairs=sum(p['split']==sp and all(e['trusted'] and e['label']==1 for e in p['root_endpoints']) for p in pp.values()),positive_sources=len({p['source_object'] for p in pp.values() if p['split']==sp and all(e['trusted'] and e['label']==1 for e in p['root_endpoints'])}),sources=len(sources[sp])) for sp in ['train','val','test']}
 write('POOL_CONTRACT.json',dict(status='FUNCTIONAL_DATA_ONLY_NOT_TRAINING_AUTHORIZATION',primary={s:[p['pair_id'] for p in pp.values() if p['split']==s] for s in sources},weights={x['pair_id']:x['weight'] for x in weights},data_hashes={n:sha(O/n) for n in ['pool_pairs.json','pool_cones.json']},proof_methods=['source_bound_native_CEC','complete_two_valued_PI_Q_enumeration'],risk_consistency_allowed=False,whole_embedding_alignment_allowed=False,label_transfer_allowed=False,pretraining_not_implemented=True))
 write('POOL_COMPLETE.json',dict(training=0,model_forward=0,new_SAT_queries=0,by_split=grades,pairs=len(pp),new_vs_previous_all_candidates=len(set(pp)-set(old)),components=len(groups),components_by_split=dict(collections.Counter(k[0] for k in groups)),independent_scalar_verified_pairs=len(replay),full_enum_certificates=len(certificates),full_enum_patterns=sum(x['patterns'] for x in certificates),new_raw_totality_views=len(models),excluded_new_constant_pairs=len(excluded),permutation_rows=len(perm),permutation_unmatched=len(unmatched),permutation_fully_qualified=False,permutation_remaining='exclude actual equal functions not connected by known proofs; match gate/cut difficulty; renormalize common pool weights',test_labels_loaded=False))
 print(read(O/'POOL_COMPLETE.json'),flush=True)
if __name__=='__main__':main()
