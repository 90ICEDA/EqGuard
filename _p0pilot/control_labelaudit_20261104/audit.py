"""Read-only raw netlist/label-lineage audit. No torch, model forward, solver, or writes to data."""
from pathlib import Path
import csv,json,collections,re,sys,hashlib,functools
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;F=R/'generate_trans/folds/hosts_bt31';P=R/'_p0pilot/round32_20261029';PRE=R/'_p0pilot/control_roles_20261104';B=R/'_p0pilot/control_fair200_20261104'
sys.path.insert(0,str(R));from phase2 import netlist_lib as NL
sys.path.insert(0,str(R/'phase2/ys'));import feature_encoding_v2 as V
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(n,a):
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(a[0]));w.writeheader();w.writerows(a)
def norm(s):return s.strip().lstrip('\\')
def raw_network(path,lib):
 """Independent scalar-cell/pin network with bitwise wire aliases and output-driver seeds."""
 text=re.sub(r'/\*.*?\*/|//[^\n]*|\(\*.*?\*\)','',path.read_text(encoding='utf-8'),flags=re.S);stmts=[s.strip() for s in text.split(';') if s.strip()];ranges={};outputs=[];assign=[];cells={}
 def parts(s):
  aa=[];start=0;depth=0
  for i,ch in enumerate(s):
   depth+=int(ch in '{(')-int(ch in '})')
   if ch==',' and depth==0:aa.append(s[start:i].strip());start=i+1
  aa.append(s[start:].strip());assert depth==0;return aa
 def bits(s):
  s=s.strip()
  if s.startswith('\\'):return [norm(s)]
  if s.startswith('{') and s.endswith('}'):
   body=s[1:-1];rep=re.fullmatch(r'\s*(\d+)\s*\{(.*)\}\s*',body,re.S)
   return bits('{'+rep[2]+'}')*int(rep[1]) if rep else [q for p in parts(body) for q in bits(p)]
  lit=re.fullmatch(r"(\d+)'([bBoOdDhH])([\da-fA-FxXzZ_]+)",s)
  if lit:
   w=int(lit[1]);ds=lit[3].replace('_','').lower();b=lit[2].lower()
   if b!='b':
    if any(q in ds for q in 'xz'):
     assert len(set(ds))==1;ds=ds[0]*w
    else:ds=bin(int(ds,{'o':8,'d':10,'h':16}[b]))[2:]
   return ['#'+v for v in ds.zfill(w)[-w:]]
  if s in ['0','1']:return ['#'+s]
  m=re.fullmatch(r'([\w$./]+)\[\s*(\d+)\s*:\s*(\d+)\s*\]',s)
  if m:
   hi,lo=int(m[2]),int(m[3]);return [f'{m[1]}[{i}]' for i in range(hi,lo+(1 if lo>=hi else -1),1 if lo>=hi else -1)]
  assert re.fullmatch(r'[\w$./]+(?:\[\d+\])?',s),('unsupported alias expression',path,s)
  return ranges.get(s,[s])
 for st in stmts:
  m=re.match(r'^(input|output|inout|wire|reg)\s*(?:\[\s*(\d+)\s*:\s*(\d+)\s*\])?\s*(.*)$',st,re.S)
  if m:
   kind,high,low,body=m.groups()
   for n in parts(body):
    n=norm(n)
    if high is not None:
     hi,lo=int(high),int(low);ranges[n]=[f'{n}[{i}]' for i in range(hi,lo+(1 if lo>=hi else -1),1 if lo>=hi else -1)]
    if kind in ['output','inout']:outputs.append(n)
   continue
  if st.startswith('assign '):
   m=re.fullmatch(r'assign\s+(.+?)\s*=\s*(.+)',st,re.S);assert m;assign.append((m[1],m[2]));continue
  if re.match(r'^(module|endmodule)\b',st):continue
  m=re.fullmatch(r'(\w+)\s+(\\\S+|[^\s(]+)\s*\((.*)\)',st,re.S);assert m,st[:100];typ,name,body=m.groups();assert typ in lib;con=[]
  for s in parts(body):
   mm=re.fullmatch(r'\.\s*(\w+)\s*\((.*)\)',s,re.S);assert mm
   if not mm[2].strip():continue
   nets=bits(mm[2]);assert len(nets)==1;assert mm[1] in lib[typ]['inputs']+lib[typ]['outputs'];con.append((mm[1],nets[0]))
  assert norm(name) not in cells;cells[norm(name)]=(typ,con)
 par={}
 def find(x):
  while x in par and par[x]!=x:par[x]=par.get(par[x],par[x]);x=par[x]
  return x
 for a,b in assign:
  aa,bb=bits(a),bits(b);assert len(aa)==len(bb),(a,b)
  for x,y in zip(aa,bb):
   xx,yy=find(x),find(y)
   if xx!=yy:par[max(xx,yy)]=min(xx,yy)
 po={find(n) for o in outputs for n in bits(o)};drivers=collections.defaultdict(set);cons=collections.defaultdict(set);pins={}
 for name,(typ,cc) in cells.items():
  pins[name]=(typ,[(p,find(n)) for p,n in cc])
  for p,n in cc:
   (drivers if p in lib[typ]['outputs'] else cons)[find(n)].add(name)
 succ={n:set() for n in cells};pred={n:set() for n in cells};pocells=set()
 for n,owners in drivers.items():
  if n in po:pocells.update(owners)
  for u in owners:
   for v in cons[n]:succ[u].add(v);pred[v].add(u)
 reachable=set(pocells);queue=collections.deque(pocells)
 while queue:
  v=queue.popleft()
  for u in pred[v]:
   if u not in reachable:reachable.add(u);queue.append(u)
 return dict(cells=cells,pins=pins,succ=succ,pred=pred,reachable=reachable,po=po,pocells=pocells,drivers=drivers,cons=cons,find=find,assigns=len(assign))
def cone(g,root):
 seen={root};q=collections.deque([root])
 while q:
  for n in g['succ'][q.popleft()]:
   if n not in seen:seen.add(n);q.append(n)
 return seen
def main():
 O.mkdir(exist_ok=True);contract=read(P/'input_contract.json');inv=read(O/'inventory.json');ctxrows=[x for x in rows(PRE/'role_context.csv') if x['exact_incoming3_any']=='1'];assert len(inv)==34 and len(ctxrows)==3
 coords=rows(PRE/'coordinate_manifest.csv');collspec=[next(y for y in coords if y['view']==x['view'] and y['role']==x['role']) for x in ctxrows];need={x['view'] for x in inv}|{x[k] for x in collspec for k in ['view','trojan_view']};views={};keys={}
 for key,q in contract['shared_inputs'].items():
  if key.startswith('trans_'):
   for v in q['views']:
    if v['view'] in need:views[v['view']]=v;keys[v['view']]=key
 names={};spans=sorted((v['old_start'],v['old_stop'],name) for name,v in views.items());j=0
 with (F/'data/processed/node_names_trans.txt').open(encoding='utf-8') as f:
  for gid,line in enumerate(f):
   while j<len(spans) and gid>=spans[j][1]:j+=1
   if j==len(spans):break
   lo,hi,name=spans[j]
   if gid>=lo:names.setdefault(name,[]).append(norm(line))
 lib=NL.load_library(F/'verilog_lib.v');vlib=V.load_library(F/'verilog_lib.v');cache={};sourcecache={};graphchecks=[];bindings={};meta={x['view']:x for x in rows(F/'views_meta.csv')}
 arrays={key:{n:np.load(R/q['folder']/(n+'.npy'),mmap_mode='r') for n in ['x39','edge_index','y','trusted']} for key,q in contract['shared_inputs'].items() if key in set(keys.values())}
 for view in sorted(need):
  path=F/'trans'/(view+'.v');g=raw_network(path,lib);v=views[view];key=keys[view];a=arrays[key];nn=names[view];assert set(nn)==set(g['cells']);g['names']=nn;g['index']={n:i for i,n in enumerate(nn)}
  rebuilt=V.parse(path,nn,vlib);e=a['edge_index'];mask=(e[0]>=v['start'])&(e[0]<v['stop']);stored=np.asarray(e[:,mask])-v['start'];assert np.array_equal(stored,rebuilt['edge_index']),view
  ii=g['index'];rawedges={(ii[u],ii[w]) for u,ww in g['succ'].items() for w in ww};vedges=set(map(tuple,rebuilt['edge_index'].T));assert rawedges==vedges,(view,len(rawedges),len(vedges));assert len(rebuilt['types'])==len(nn),'no continuous-expression auxiliaries expected in these selected views'
  rawreach=np.array([n in g['reachable'] for n in nn]);dist=a['x39'][v['start']:v['physical_stop'],30];assert not (rawreach&(dist<0)).any(),('stored false unreachable',view)
  extra=np.flatnonzero((dist>=0)&~rawreach)
  graphchecks.append(dict(view=view,physical_nodes=len(nn),stored_edges=stored.shape[1],independent_cell_edges=len(rawedges),v2_rebuild_edges_equal=True,independent_pin_edges_equal=True,raw_PO_reach_matches_all_nodes=not bool(len(extra)),stored_reachable_but_no_output_drive_path=len(extra),boundary_difference_examples='|'.join(nn[i] for i in extra[:12]),assigns=g['assigns']))
  mp=F/'mappings'/(view+'.json');m=read(mp);reverse=collections.defaultdict(list)
  for s,tt in m['node_alignment'].items():
   for t in tt:reverse[norm(t)].append(norm(s))
  src=m['src_view'];host=src.split('__')[0];recipe=view.rsplit('__ys_',1)[1];tag=('a4_' if meta[view]['batch'] in ['a4','a4b'] else 'bt2_')+host
  cv=R/'generate_trans/b1bind'/tag/'conv'/host/(src+'__keepbnd__ys_'+recipe+'.v');cmap=cv.with_suffix('.map.json');assert sha(cv)==sha(path),(view,cv);cm=read(cmap)
  if src not in sourcecache:sourcecache[src]=raw_network(F/'orig'/(src+'.v'),lib)
  g.update(mapping=m,reverse=reverse,source=src,converter=cm,converted_file=cv);cache[view]=g
  for p in [path,mp,cv,cmap,F/'orig'/(src+'.v')]:bindings[str(p.relative_to(R))]=sha(p)
  print('verified',view,flush=True)
 onames=(P/'orig_names/node_names_orig.txt').read_text(encoding='utf-8').splitlines();alignment=read(F/'data/for_train/alignment.json');wanted={views[x['view']]['old_start']+x['row']-views[x['view']]['start'] for x in inv};ap=collections.defaultdict(list)
 for oi,ti in alignment:
  if ti in wanted:ap[ti].append(oi)
 cm=read(F/'data/for_train/class_map_trans_transported.json');om=read(F/'data/for_train/class_map_orig.json');details=[];witness=[]
 for r in inv:
  view=r['view'];g=cache[view];n=r['name'];src=g['source'];sg=sourcecache[src];parents=g['reverse'][n];anchor=g['converter'].get('inst_prov',{}).get(n);assert len(parents)==1 and parents[0] in sg['cells'];p=parents[0];pgate=sg['cells'][p];outpins=[(pp,net) for pp,net in sg['pins'][p][1] if pp in lib[pgate[0]]['outputs']];assert anchor and sg['find'](norm(anchor)) in {net for pp,net in outpins},(n,anchor,outpins)
  globalid=views[view]['old_start']+r['row']-views[view]['start'];assert cm[str(globalid)]==1;assert ap[globalid] and all(om[str(i)]==1 for i in ap[globalid]);assert {norm(onames[i]) for i in ap[globalid]}==set(parents)
  assert n not in g['reachable'];cc=cone(g,n);term=sorted(q for q in cc if not g['succ'][q]);po=cc&g['pocells'];assert not po
  outs=[net for pin,net in g['pins'][n][1] if pin in lib[g['cells'][n][0]]['outputs']]
  relatives=g['mapping']['node_alignment'][p];live=[q for q in relatives if q in g['reachable']];dead=[q for q in relatives if q not in g['reachable']]
  details.append(dict(**r,global_trans_id=globalid,type=g['cells'][n][0],source_gate=p,inst_prov_anchor=anchor,source_gate_PO_reachable=p in sg['reachable'],lineage_and_transport_consistent=True,mixed_positive_negative_parent=False,target_output_nets='|'.join(outs),direct_consumers='|'.join(sorted(g['succ'][n])),descendant_cells=len(cc),dead_terminal_cells='|'.join(term),output_reachable=False,same_source_role_live_targets='|'.join(live),same_source_role_dead_targets='|'.join(dead),classification='retained_dead_lineage_descendant; graph and provenance consistent; no functional-role certificate'))
  witness.append(dict(view=view,node=n,source=src,source_gate=p,anchor=anchor,source_pins=sg['pins'][p],target_pins=g['pins'][n],complete_downstream_cells=[dict(name=q,type=g['cells'][q][0],pins=g['pins'][q][1],successors=sorted(g['succ'][q])) for q in sorted(cc)]))
 dump('unreachable34.csv',details);dump('graph_checks.csv',graphchecks);(O/'downstream_witnesses.json').write_text(json.dumps(witness,ensure_ascii=False,indent=2),encoding='utf-8')
 normz=np.load(P/'normalization.npz');collisions=[];trees=[]
 for r in collspec:
  ng,tg=cache[r['view']],cache[r['trojan_view']];key=keys[r['view']];a=arrays[key]
  def label(view,i):
   v=views[view];z=np.array(a['x39'][v['start']+i],copy=True);z[25:]=np.clip((z[25:]-normz['mean'][25:])/normz['std'][25:],-10,10);return z.astype('<f4').tobytes()
  @functools.lru_cache(None)
  def tree(view,name,depth):
   g=cache[view];b=label(view,g['index'][name])
   if depth:b+=tree(view,name,depth-1)+b''.join(sorted(tree(view,n,depth-1) for n in g['pred'][name]))
   return hashlib.sha256(b).digest()
  nv,tv=views[r['view']],views[r['trojan_view']];ni=[int(i)-nv['start'] for i in r['normal_ids'].split('|')];ti=[int(i)-tv['start'] for i in r['trojan_ids'].split('|')]
  for i in ni:
   for j in ti:
    nn,tn=ng['names'][i],tg['names'][j]
    if tree(r['view'],nn,3)!=tree(r['trojan_view'],tn,3):continue
    assert a['y'][nv['start']+i]==0 and a['y'][tv['start']+j]==1
    nparents=ng['reverse'][nn];tparents=tg['reverse'][tn];assert len(nparents)==len(tparents)==1
    def routes(g,node,parents):
     anch=g['converter'].get('inst_prov',{}).get(node);sg=sourcecache[g['source']];p=parents[0];outs=[net for pp,net in sg['pins'][p][1] if pp in lib[sg['cells'][p][0]]['outputs']];assert anch and sg['find'](norm(anch)) in outs;return anch
    na=routes(ng,nn,nparents);ta=routes(tg,tn,tparents);diff=[]
    for seed in [42,1,2]:
     for arm in ['H','C']:
      pred=np.load(B/f'seed{seed}'/arm/'trans_train_scores.npy',mmap_mode='r');diff.append(abs(float(pred[nv['start']+i])-float(pred[tv['start']+j])))
    assert max(diff)==0
    nncone=cone(ng,nn);tncone=cone(tg,tn)
    collisions.append(dict(source=r['source'],role=r['role'],normal_view=r['view'],trojan_view=r['trojan_view'],normal_node=nn,trojan_node=tn,normal_source_gate='|'.join(nparents),trojan_source_gate='|'.join(tparents),normal_anchor=na,trojan_anchor=ta,raw_pins_N=str(ng['pins'][nn]),raw_pins_T=str(tg['pins'][tn]),normal_reachable=nn in ng['reachable'],trojan_reachable=tn in tg['reachable'],normal_downstream_cells=len(nncone),trojan_downstream_cells=len(tncone),normal_source_reachable=nparents[0] in sourcecache[ng['source']]['reachable'],trojan_source_reachable=tparents[0] in sourcecache[tg['source']]['reachable'],graph_verified=True,lineage_verified=True,incoming_depth3_hash=tree(r['view'],nn,3).hex(),max_score_difference_six_models=max(diff),classification='identical_local_inputs; source-lineage safety labels differ; no coordinate mismatch'))
    def expand(view,node,depth):
     g=cache[view];z=dict(name=node,type=g['cells'][node][0],pins=g['pins'][node][1],feature39=list(np.frombuffer(label(view,g['index'][node]),dtype='<f4').astype(float)),incoming=sorted(g['pred'][node]),reachable=node in g['reachable'])
     if depth:z['parents']=[expand(view,p,depth-1) for p in sorted(g['pred'][node])]
     return z
    trees.append(dict(normal=expand(r['view'],nn,3),trojan=expand(r['trojan_view'],tn,3),normal_view=r['view'],trojan_view=r['trojan_view']))
 dump('collision_node_pairs.csv',collisions);(O/'collision_tree_witnesses.json').write_text(json.dumps(trees,ensure_ascii=False,indent=2),encoding='utf-8')
 for p in [F/'data/for_train/alignment.json',F/'data/for_train/class_map_orig.json',F/'data/for_train/class_map_trans_transported.json',F/'verilog_lib.v',R/'phase2/ys/assign_to_gates.py',R/'phase2/ys/make_inst_alignment.py',R/'data/verilog_data/parser2.py',R/'phase2/ys/feature_encoding_v2.py',P/'input_contract.json',PRE/'coordinate_manifest.csv',PRE/'role_context.csv']:bindings[str(p.relative_to(R))]=sha(p)
 summary=dict(training=0,SAT=0,model_forward=0,labels_modified=False,unreachable_nodes=len(details),source_objects=len({x['source'] for x in details}),views=len({x['view'] for x in details}),all34_graph_consistent=all(x['lineage_and_transport_consistent'] for x in details),all34_source_reachable=all(x['source_gate_PO_reachable'] for x in details),dead_with_live_sibling=sum(bool(x['same_source_role_live_targets']) for x in details),collision_role_view_records=len(collspec),collision_physical_pairs=len(collisions),collision_T_unreachable=sum(not x['trojan_reachable'] for x in collisions),graph_views_verified=len(graphchecks),inputs=bindings)
 (O/'audit.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');print({k:v for k,v in summary.items() if k!='inputs'})
if __name__=='__main__':main()
