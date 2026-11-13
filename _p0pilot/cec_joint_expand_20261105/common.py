"""Source-bound cone/graph bookkeeping and deterministic Boolean witness replay."""
from pathlib import Path
import collections,csv,hashlib,json,re,sys
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent
T=R/'10.15/06_统一评测协议/N4_三向泛化/tables';PRE=R/'_p0pilot/cec_coverage_pretrain_20261105'
sys.path.insert(0,str(R/'_p0pilot/cec_cone_audit_20261105'))
from audit import read,rows,sha,ident,cone,module,SCHEMA
sys.path.insert(0,str(R/'_p0pilot/round10_20261025'));import native as N
def write(name,value):
 p=O/name;assert not p.exists(),name;p.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
def table(name,values):
 if not values:return
 p=O/name;assert not p.exists(),name
 with p.open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(values[0]));w.writeheader();w.writerows(values)
class Store:
 def __init__(self):
  self.contract=read(R/'_p0pilot/control_boundary_v3_20261104/input_contract.json')
  self.vm={v['view']:(key,v) for key,q in self.contract['shared_inputs'].items() if key in ['trans_train','trans_val'] for v in q['views']}
  self.meta={x['view']:x for x in rows(R/'generate_trans/folds/hosts_bt31/views_meta.csv')}
  self.names=[x.strip().lstrip('\\') for x in (R/'generate_trans/folds/hosts_bt31/data/processed/node_names_trans.txt').read_text(encoding='utf-8').splitlines()]
  self.raws={};self.bindings={};self.maps={};self.layouts={};self.drivers={};self.arrays={};self.cones={};self.evaluators={};self.contexts={};self.inputs={}
  for key in ['trans_train','trans_val']:
   folder=R/self.contract['shared_inputs'][key]['folder'];self.arrays[key]={}
   for n in ['x39','y','trusted','physical']:
    path=folder/(n+'.npy');hh=sha(path);assert hh==self.contract['files'][str(path.relative_to(R))];self.inputs[str(path.relative_to(R))]=hh;self.arrays[key][n]=np.load(path,mmap_mode='r')
 def raw(self,view):
  if view in self.raws:return self.raws[view]
  assert view in self.vm,'Only train/val views'
  options=[T/d/'structures'/view/'raw.json' for d in ['sat_pair_round10','sat_pair_round11','sat_pair_round12']]+[T/'sat_cases_round8'/view/'raw.json',O/'structures'/view/'raw.json']
  path=next((p for p in options if p.exists()),None);cache_binding=None
  if path is None:
   for cache in ['sat_k4_alltrain_round27','sat_k4_validation_round29']:
    manifest=T/cache/'views'/view/'snapshots.json'
    if not manifest.exists():continue
    for item in reversed(read(manifest)):
     candidate=R/item['folder']/'raw.json'
     if candidate.exists():path=candidate;cache_binding=item;break
    if path is not None:break
  if path is None:raise FileNotFoundError('No bound existing raw: '+view)
  source=R/'generate_trans/folds/hosts_bt31/trans'/(view+'.v');hh=sha(path);ss=sha(source)
  if (path.parent/'source.json').exists():
   binding=read(path.parent/'source.json');assert binding['raw_sha']==hh and binding['source_sha']==ss
  elif cache_binding is not None:
   assert cache_binding['view']==view and cache_binding['raw_sha']==hh and cache_binding['source_sha']==ss
  else:
   binding=next(x for x in rows(T/'sat_cases_round8/sources.csv') if x['view']==view);assert binding['raw_sha']==hh and binding['source_sha']==ss
  self.inputs[str(path.relative_to(R))]=hh;self.inputs[str(source.relative_to(R))]=ss
  m=next(iter(read(path)['modules'].values()));self.raws[view]=m;self.bindings[view]=dict(raw_path=str(path.relative_to(R)),raw_sha=hh,source_sha=ss)
  key,v=self.vm[view];self.maps[view]={n:v['start']+j for j,n in enumerate(self.names[v['old_start']:v['old_stop']])};self.layouts[view]=N.layout(m)
  # Verify total acyclic two-valued combinational model, including unused cones.
  drv={};comb={};leaf={}
  def add(b,driver):assert isinstance(b,int) and b not in drv,(view,'duplicate/constant driver',b);drv[b]=driver
  for n,p in m['ports'].items():
   if p['direction']=='input':
    for j,b in enumerate(p['bits']):add(b,('PI',n,j,0));leaf[b]=('PI',n,j,0)
  for n,g in m['cells'].items():
   if 'DFF' in g['type'].upper():
    for pin in ['Q','QN']:
     for b in g['connections'].get(pin,[]):add(b,('Q',n,0,int(pin=='QN')));leaf[b]=('Q',n,0,int(pin=='QN'))
   else:
    assert g['type'] in SCHEMA;pin,ins=SCHEMA[g['type']];assert len(g['connections'][pin])==1;out=g['connections'][pin][0];add(out,n);comb[n]=g
  degree={n:0 for n in comb};succ=collections.defaultdict(set)
  for n,g in comb.items():
   for pin in SCHEMA[g['type']][1]:
    assert len(g['connections'][pin])==1;b=g['connections'][pin][0]
    if not isinstance(b,int):assert b in ['0','1'];continue
    assert b in drv,(view,'undriven',b)
    if isinstance(drv[b],str) and n not in succ[drv[b]]:succ[drv[b]].add(n);degree[n]+=1
  queue=collections.deque(n for n,d in degree.items() if not d);order=[]
  while queue:
   n=queue.popleft();order.append(n)
   for child in succ[n]:
    degree[child]-=1
    if not degree[child]:queue.append(child)
  assert len(order)==len(comb),(view,'cycle')
  self.drivers[view]={b:(name,SCHEMA[comb[name]['type']][0]) for b,name in drv.items() if isinstance(name,str)}
  ctx=ident(dict(PI=self.layouts[view][0],physicalQ=self.layouts[view][1],free=True));MASK=(1<<128)-1;values={}
  env={}
  for b,token in leaf.items():
   t=tuple(token[:3]);seed=json.dumps(['cone_witness_v1',ctx,t],ensure_ascii=True,separators=(',',':')).encode();value=(int.from_bytes(hashlib.sha256(seed).digest()[:16],'little') & ~3)|2
   env[t]=value;values[b]=value ^ (MASK if token[3] else 0)
  self.contexts[ctx]=dict(input_masks=[dict(token=list(k),mask_hex=hex(v)) for k,v in sorted(env.items())],patterns=128,meaning='pattern0 all0;pattern1 all1;others deterministic hash bits;existence witnesses only')
  def val(b):
   if isinstance(b,int):return values[b]
   assert b in ['0','1'];return MASK if b=='1' else 0
  for n in order:
   g=comb[n];vs=[val(g['connections'][p][0]) for p in SCHEMA[g['type']][1]];typ=g['type']
   if typ in ['AND2X2','$and']:a=vs[0]&vs[1]
   elif typ in ['OR2X1','$or']:a=vs[0]|vs[1]
   elif typ in ['XOR2X1','$xor']:a=vs[0]^vs[1]
   elif typ in ['INVX0','$not']:a=MASK^vs[0]
   else:assert typ in ['MX2X1_RS','$mux'];a=(vs[2]&vs[1])|((MASK^vs[2])&vs[0])
   values[g['connections'][SCHEMA[typ][0]][0]]=a
  self.evaluators[view]=values
  return m
 def root(self,view,bit):
  self.raw(view)
  if bit not in self.drivers[view]:return None
  name,pin=self.drivers[view][bit];cid=ident([self.bindings[view]['source_sha'],name,pin]);return cid,name,pin
 def getcone(self,view,bit):
  root=self.root(view,bit)
  if root is None:return None
  cid,name,pin=root
  if cid not in self.cones:
   z=cone(self.raws[view],bit,self.maps[view],self.bindings[view]['raw_sha'])
   if z['errors'] or z['unmapped_members'] or not z['nontrivial']:return None
   z.update(cone_id=cid,view=view,split=self.vm[view][0].split('_')[1],root_row=self.maps[view][name],output_cell=name,output_pin=pin,**self.bindings[view]);self.cones[cid]=z
   key,v=self.vm[view];ii=np.asarray(z['graph_rows']);assert ((ii>=v['start'])&(ii<v['physical_stop'])).all() and self.arrays[key]['physical'][ii].all() and np.isfinite(self.arrays[key]['x39'][ii]).all()
  return self.cones[cid]
 def endpoint(self,c):
  ar=self.arrays[self.vm[c['view']][0]];i=c['root_row'];return dict(view=c['view'],row=i,cell=c['output_cell'],pin=c['output_pin'],label=int(ar['y'][i]),trusted=bool(ar['trusted'][i]),physical=bool(ar['physical'][i]))
 def check_query(self,q):
  folder=R/q['folder'];script=(folder/'run.ys').read_text(encoding='utf-8');log=(folder/'run.log').read_text(encoding='utf-8')
  assert sha(folder/'model.v')==q['model_sha'] and sha(folder/'run.log')==q['log_sha'] and hashlib.sha256(script.encode()).hexdigest()==q['script_sha']
  command=[s for s in script.splitlines() if s.startswith('sat ')][int(q['query_id'])]
  assert re.fullmatch(r'sat '+re.escape(q['args'])+r' -timeout \d+ -show-inputs -show-outputs -dump_json "[^"]+"',command)
  blocks=re.split(r'^(?:Q|QUERY)\d{4}\s*$',log,flags=re.M);block=blocks[int(q['query_id'])+1];assert 'no model found: SUCCESS' in block and 'TIMEOUT' not in block and 'ERROR:' not in log
  for n in ['model.v','run.ys','run.log']:self.inputs[str((folder/n).relative_to(R))]=sha(folder/n)
  return (folder/'model.v').read_text(encoding='utf-8')
 def bind_native(self,view,body,mn):
  m=self.raw(view);net=next(n for n,z in m['netnames'].items() if len(z['bits'])==1);generated=N.emit(m,mn,[net]*5)[0]
  strip=lambda s:re.sub(r'assign sigs=\{.*?\};','assign sigs=BOUND;',s)
  assert strip(generated)==strip(body),(view,'model mismatch')
