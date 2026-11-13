"""Read-only train/val manufacturing lineage and feature/structure alignment."""
import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import csv,json,hashlib,collections,re,importlib.util,sys
import numpy as np
from scipy.sparse import csr_matrix
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;F=R/'generate_trans/folds/hosts_bt31';V=R/'_p0pilot/control_boundary_v3_20261104';P=R/'_p0pilot/control_overall_contract_20261105';B=R/'_p0pilot/control_budget_bounded_20261105';KEYS=['orig_train','orig_val','trans_train','trans_val']
s=importlib.util.spec_from_file_location('retained_parser',R/'_p0pilot/control_retention_20261104/audit.py');A=importlib.util.module_from_spec(s);s.loader.exec_module(A)
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(p):return list(csv.DictReader(p.open(encoding='utf-8-sig',newline='')))
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def table(n,rr):
 if rr:
  with (O/n).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def role(s):
 if re.fullmatch(r'T(?:N|I|M|X|Y)?\d+',s):return 'trigger'
 if re.fullmatch(r'P\d+',s):return 'payload'
 if re.fullmatch(r'S\d+',s):return 'payload_select'
 if s=='HJ':return 'output_hijack'
 return 'unresolved'
def main():
 c=read(V/'input_contract.json');norm=dict(np.load(V/'normalization.npz'));views=[v for v in rows(R/'_p0pilot/control_loader_po_20261105/view_dictionary.csv') if v['key'] in KEYS];vm={(v['key'],v['view']):v for v in views};protected={};data={};chosen={};exposure={};poolmeta={}
 def bind(p):protected[str(p.relative_to(R))]=sha(p)
 for p in [Path(__file__),V/'input_contract.json',V/'normalization.npz',R/'_p0pilot/control_retention_20261104/audit.py',R/'_p0pilot/control_risk_20261104/source_node_pairs.csv',R/'_p0pilot/control_loader_po_20261105/view_dictionary.csv']:bind(p)
 for key in KEYS:
  d=R/c['shared_inputs'][key]['folder'];data[key]={n:np.load(d/(n+'.npy'),mmap_mode='r') for n in ['x39','edge_index','y','trusted','physical']}
  for n in data[key]:p=d/(n+'.npy');assert sha(p)==c['files'][str(p.relative_to(R))];bind(p)
  q=P/f'normal_{key}.npz';z=dict(np.load(q));bind(q);mi=z['rows'][z['category']==1];a=data[key];pos=np.flatnonzero(a['trusted']&a['physical']&(a['y']==1));assert not np.intersect1d(mi,pos).size;chosen[key]={int(i):'positive' for i in pos};chosen[key].update({int(i):'M' for i in mi});exposure[key]=collections.Counter();poolmeta[key]={}
  if key.endswith('train'):
   q=B/f'pools_{key}.npz';pool=dict(np.load(q));bind(q);q=B/f'main_fanout05_{key}_pairs.npy';seq=np.load(q);bind(q);uses=np.bincount(seq.ravel(),minlength=len(pool['N']))
   for j in np.flatnonzero(pool['category']==1):poolmeta[key][int(pool['N'][j])]=dict(pair_id=int(j),eligible=bool(pool['main_eligible'][j]),uses=int(uses[j]));exposure[key][int(pool['N'][j])]+=int(uses[j])
 names={};loc={};wanted={'orig':{},'trans':{}}
 for v in views:
  key=v['key'];lo,hi=int(v['start']),int(v['physical_stop'])
  for i in chosen[key]:
   if lo<=i<hi:gid=int(v['old_start'])+i-lo;wanted[key.split('_')[0]][gid]=(key,i);loc[key,i]=v
 for dm,p in [('orig',R/'_p0pilot/round32_20261029/orig_names/node_names_orig.txt'),('trans',F/'data/processed/node_names_trans.txt')]:
  bind(p);need=wanted[dm]
  with p.open(encoding='utf-8') as f:
   for gid,line in enumerate(f):
    if gid in need:names[need[gid]]=A.norm(line)
  assert all(k in names for k in need.values())
 prov=collections.defaultdict(list)
 sources={v['source'] for v in views if any(loc[k]['source']==v['source'] for k in names)}
 for p in (R/'generate_trans').glob('hosts*/*/provenance.json'):
  try:
   z=read(p)
   if isinstance(z,list):
    for x in z:
     if x.get('view') in sources:prov[x['view']].append((p,x))
  except (ValueError,OSError):pass
 scache={};source_roles={};sr=[];discrep=[]
 for src in sorted(sources):
  p=F/'orig'/(src+'.v');sc,st=A.cells(p);bind(p);scache[src]=(sc,st);candidates=prov[src];assert candidates,src;prefixes={x['prefix'] for p,x in candidates if 'prefix' in x};assert len(prefixes)==1,(src,prefixes);prefix=next(iter(prefixes));pp,pd=candidates[0];bind(pp);new=set(A.norm(g) for g in pd.get('new_gates',[]));rmap={}
  # The provenance prefix anchors manufacturing names; every gate must exist in current source.
  for name,(typ,con) in sc.items():
   suffix=name[len(prefix):] if name.startswith(prefix) else '';cl=role(suffix)
   if pd.get('ctl_type')=='deep_xor' and re.fullmatch(r'X\d+',suffix) and ('XOR' in typ.upper() or 'XNOR' in typ.upper()):cl='payload'
   if pd.get('ctl_type')=='deep_xor' and suffix=='Buf':cl='buffer_aux'
   if suffix=='PD' and name in new and ('INV' in typ.upper() or 'BUF' in typ.upper()):cl='payload_sink'
   if cl!='unresolved':rmap[name]=cl;sr.append(dict(source=src,gate=name,type=typ,role=cl,listed_new=name in new,provenance=str(pp.relative_to(R)),prefix=prefix,connections=json.dumps(con,sort_keys=True),interpretation='manufacturing role,not per-node functional necessity'))
  source_roles[src]=rmap;missing=sorted(new-set(sc));extra=sorted(set(rmap)-new)
  if missing or extra:discrep.append(dict(source=src,listed_absent='|'.join(missing),role_gates_unlisted='|'.join(extra),action='record_only_current_fold_source_and_exact_maps_used'))
 out=[];portrows=[];mapcache={};ambiguous=[]
 for v in views:
  key,view,src=v['key'],v['view'],v['source'];ids=[i for i in chosen[key] if loc[key,i]['view']==view]
  if not ids:continue
  sc,st=scache[src];rmap=source_roles[src]
  if key.startswith('trans'):
   p=F/'mappings'/(view+'.json');mp=read(p);bind(p);assert mp['src_view']==src and mp['rw_view']==view;rev=collections.defaultdict(set)
   for parent,children in mp['node_alignment'].items():
    for child in children:rev[A.norm(child)].add(A.norm(parent))
   p=F/'trans'/(view+'.v');tc,tt=A.cells(p);bind(p)
  else:tc,tt=sc,st;rev=None
  # Decode explicit scalar aliases and source-instance.pin aliases, without Boolean inference.
  uf={}
  def find(a):
   uf.setdefault(a,a)
   while uf[a]!=a:uf[a]=uf[uf[a]];a=uf[a]
   return a
  for a,b in re.findall(r'\bassign\s+([^=;]+)\s*=\s*([^;]+);',tt):
   a,b=A.norm(a),A.norm(b)
   if re.fullmatch(r'[\w.$\[\]/]+',a) and re.fullmatch(r'[\w.$\[\]/]+',b):uf[find(a)]=find(b)
  nets={n for _,con in sc.values() for n in con.values()};classes=collections.defaultdict(set)
  for wire in set(uf)|{n for _,con in tc.values() for n in con.values()}:
   if wire in nets:classes[find(wire)].add(wire)
   if '.' in wire:
    inst,pin=wire.rsplit('.',1)
    if inst in sc and pin in sc[inst][1]:classes[find(wire)].add(sc[inst][1][pin])
  for i in ids:
   name=names[key,i];parents=sorted(rev[name]) if rev is not None else [name];pr=[rmap.get(p,'host_or_other') for p in parents];typ,con=tc.get(name,('NOT_PARSED',{}));host=any(p not in rmap for p in parents);seq='DFF' in typ.upper();role_set=set(pr);cl='unresolved' if not parents else 'mixed_source' if host or len(role_set)>1 else next(iter(role_set));nature='sequential_descendant' if seq else 'multi_parent_descendant' if len(parents)>1 else 'combinational_descendant';bound=False
   if len(parents)==1 and parents[0] in sc and not seq:
    styp,scon=sc[parents[0]];pinmap={p:p for p in scon} if set(scon)<=set(con) else {'A':'IN1','B':'IN2','S0':'S','Y':'Q'} if cl=='output_hijack' and {'A','B','S0','Y'}<=set(con) and {'IN1','IN2','S','Q'}<=set(scon) else {}
    if pinmap:
     matches={p:scon[q] in classes[find(con[p])] for p,q in pinmap.items()};bound=all(matches.values());portrows.append(dict(key=key,view=view,row=i,parent=parents[0],all_ports_bound=bound,pinmap=json.dumps(pinmap,sort_keys=True),matches=json.dumps(matches,sort_keys=True)))
     if bound:nature='direct_role_port_bound'
   a=data[key];pm=poolmeta[key].get(i,{});out.append(dict(key=key,view=view,source=src,host=v['host'],recipe=v['recipe'],row=i,old_global_row=int(v['old_start'])+i-int(v['start']),side=chosen[key][i],node_name=name,target_type=typ,parents='|'.join(parents),parent_count=len(parents),role=cl,role_set='|'.join(sorted(role_set)),host_or_other_parent=host,nature=nature,all_ports_bound=bound,old_y=int(a['y'][i]),old_trusted=bool(a['trusted'][i]),M_pair_id=pm.get('pair_id',-1),M_main_eligible=pm.get('eligible',False),M_exposure_200=exposure[key][i],mapping_source='source_instance' if rev is None else 'exact_node_alignment',coordinate_verified=False))
  print('LINEAGE',key,view,len(ids),flush=True)
 # Independently check map ownership against the training alignment coordinate transport.
 orig_all=(R/'_p0pilot/round32_20261029/orig_names/node_names_orig.txt').read_text(encoding='utf-8').splitlines();ov={v['source']:v for v in views if v['key'].startswith('orig')};need={r['old_global_row']:r for r in out if r['key'].startswith('trans')};transport=collections.defaultdict(set);p=F/'data/for_train/alignment.json';bind(p)
 for oi,ti in read(p):
  if ti in need:transport[ti].add(oi)
 for r in out:
  if r['key'].startswith('orig'):r['coordinate_verified']=True;continue
  v=ov[r['source']];raw=transport[r['old_global_row']];inside=all(int(v['old_start'])<=j<int(v['old_stop']) for j in raw);pn={A.norm(orig_all[j]) for j in raw};ok=bool(raw) and inside and pn==set(r['parents'].split('|'));r['coordinate_verified']=ok
  if not ok:ambiguous.append(dict(key=r['key'],row=r['row'],view=r['view'],map_parents=r['parents'],transport_parents='|'.join(sorted(pn)),inside_source=inside))
 table('SOURCE_GATE_ROLES.csv',sr);table('PROVENANCE_DISCREPANCIES.csv',discrep);table('NODE_LINEAGE.csv',out);table('DIRECT_PORT_CHECKS.csv',portrows);table('COORDINATE_DISCREPANCIES.csv',ambiguous)
 # Explicit consumed graph: duplicate edges retained as multiplicities; incoming GIN receptive field.
 descriptors=[];links=[];sourcepairs=rows(R/'_p0pilot/control_risk_20261104/source_node_pairs.csv');sp={(r['control_source'],r['control_instance'],r['trojan_source'],r['trojan_instance']) for r in sourcepairs if r['role_pair']=='True'}
 for key in KEYS:
  a=data[key];x=np.array(a['x39'],dtype=np.float32);x[:,25:]=np.clip((x[:,25:]-norm['mean'][25:])/norm['std'][25:],-10,10);e=a['edge_index'];n=len(x);adj=csr_matrix((np.ones(e.shape[1],np.int32),(e[0],e[1])),shape=(n,n));pred=adj.T.tocsr();adj.sort_indices();pred.sort_indices();memo={};gmemo={};roots=[r for r in out if r['key']==key]
  def h(i,d,gateonly=False):
   cache=gmemo if gateonly else memo;k=(i,d)
   if k in cache:return cache[k]
   root=str(int(np.argmax(x[i,:25]))).encode() if gateonly else x[i].tobytes()
   if d:
    lo,hi=pred.indptr[i:i+2];tokens=sorted((h(int(j),d-1,gateonly),int(m)) for j,m in zip(pred.indices[lo:hi],pred.data[lo:hi]));root+=b'['+b';'.join(t.encode()+b'*'+str(m).encode() for t,m in tokens)+b']'
   value=hashlib.sha256(root).hexdigest();cache[k]=value;return value
  for r in roots:
   i=r['row'];desc=dict(key=key,row=i,gate=c['columns39'][int(np.argmax(x[i,:25]))],fanin=int(pred.indptr[i+1]-pred.indptr[i]),fanout=int(adj.indptr[i+1]-adj.indptr[i]),physical=bool(a['physical'][i]),feature_hash=h(i,0),incoming_gate_2=h(i,2,True),incoming_feature_1=h(i,1),incoming_feature_2=h(i,2),incoming_feature_3=h(i,3),PO_distance=float(a['x39'][i,30]),exact2_fanout=float(np.expm1(a['x39'][i,32])));descriptors.append(desc)
  dl={r['row']:r for r in descriptors if r['key']==key};ms=[r for r in roots if r['side']=='M' and r['coordinate_verified'] and r['role'] not in ['mixed_source','unresolved'] and r['nature']!='sequential_descendant'];targets=[r for r in roots if r['side']=='positive' and r['role'] in ['payload','output_hijack'] and r['coordinate_verified'] and r['nature']!='sequential_descendant']
  for r in targets:
   i=r['row'];valid=[m for m in ms if m['host']==r['host'] and m['recipe']==r['recipe'] and dl[m['row']]['gate']==dl[i]['gate']]
   for route in ['all_M','exposed_M_only','manufacturing_counterpart']:
    cand=[m for m in valid if (route!='exposed_M_only' or m['M_exposure_200']>0) and (route!='manufacturing_counterpart' or any((m['source'],mp,r['source'],tp) in sp for mp in m['parents'].split('|') for tp in r['parents'].split('|')))]
    if not cand:links.append(dict(key=key,positive_row=i,normal_row=-1,route=route,matched=False,candidates=0,ties=0,rms_z14=None,max_z14=None,feature_equal=False,gate_context2_equal=False,incoming_feature3_equal=False));continue
    ids=np.array([m['row'] for m in cand]);dist=np.sqrt(np.mean((x[ids,25:]-x[i,25:])**2,axis=1));ix=np.lexsort((ids,dist))[0];j=int(ids[ix]);dd=np.abs(x[j,25:]-x[i,25:]);links.append(dict(key=key,positive_row=i,normal_row=j,route=route,matched=True,candidates=len(cand),ties=int(np.sum(dist==dist[ix])),rms_z14=float(dist[ix]),max_z14=float(dd.max()),feature_equal=np.array_equal(x[i],x[j]),gate_context2_equal=dl[i]['incoming_gate_2']==dl[j]['incoming_gate_2'],incoming_feature3_equal=dl[i]['incoming_feature_3']==dl[j]['incoming_feature_3']))
  # Save only audited roots: 39 raw + the actual normalized 39 columns.
  ids=np.array(sorted(r['row'] for r in roots));np.savez_compressed(O/(key+'_features.npz'),rows=ids,raw=a['x39'][ids],normalized=x[ids]);print('STRUCTURE',key,len(roots),len(memo),flush=True)
 table('LOCAL_DESCRIPTORS.csv',descriptors);table('FEATURE_NEAREST_LINKS.csv',links)
 cov=[]
 for key in KEYS:
  for side in ['positive','M']:
   rr=[r for r in out if r['key']==key and r['side']==side];cov.append(dict(key=key,side=side,nodes=len(rr),sources=len({r['source'] for r in rr}),mapped=sum(bool(r['parents']) for r in rr),coordinate_verified=sum(r['coordinate_verified'] for r in rr),pure_role=sum(r['role'] not in ['mixed_source','unresolved'] for r in rr),mixed=sum(r['role']=='mixed_source' for r in rr),unresolved=sum(r['role']=='unresolved' for r in rr),sequential=sum(r['nature']=='sequential_descendant' for r in rr),direct_ports_bound=sum(r['all_ports_bound'] for r in rr),actually_exposed_M=sum(r['M_exposure_200']>0 for r in rr)))
 table('COVERAGE.csv',cov)
 for p,h0 in protected.items():assert sha(R/p)==h0,p
 result=dict(passed=True,scope=KEYS,model_forwards=0,training=0,SAT=0,labels_changed=False,roles='sidecar manufacturing lineage;no securityrole/CEC transfer',normal_matching='same split/domain/host/recipe/gate;features only,never predictions;all candidate and actually-exposed pools separate',structure='incoming 3hop feature-colored multiset unfolding on exact saved directed edges;not induced-isomorphism proof;edge pinroles not model inputs',coordinate_discrepancies=len(ambiguous),protected_inputs=protected)
 (O/'BUILD_COMPLETE.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print('BUILD_COMPLETE',len(out),len(links),len(ambiguous),flush=True)
if __name__=='__main__':main()
