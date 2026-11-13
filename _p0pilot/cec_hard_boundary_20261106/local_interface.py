"""Isolated free-PI/Q cone arrays and an audit-only Boolean consumer. No learning."""
import collections,hashlib,json
import numpy as np
OPS=['PI','Q','CONST0','CONST1','AND','OR','XOR','NOT','MUX']
SCHEMA={'AND2X2':('Q','AND',['IN1','IN2']),'OR2X1':('Q','OR',['IN1','IN2']),'XOR2X1':('Q','XOR',['IN1','IN2']),'INVX0':('QN','NOT',['IN']),'MX2X1_RS':('Y','MUX',['A','B','S0']),'$and':('Y','AND',['A','B']),'$or':('Y','OR',['A','B']),'$xor':('Y','XOR',['A','B']),'$not':('Y','NOT',['A']),'$mux':('Y','MUX',['A','B','S'])}
def code(kind,slot):
 b=hashlib.sha256(json.dumps(['boundary_vector_v1',kind,int(slot)],separators=(',',':')).encode()).digest();v=np.frombuffer(b,dtype='<u2').astype(np.float32)-32767.5;return v/np.linalg.norm(v)
class ModuleIndex:
 def __init__(self,module,tokens):
  self.module=module;self.slots={(t['kind'],t['audit_name'],t['bit']):int(t['slot']) for t in tokens};self.kind={int(t['slot']):t['kind'] for t in tokens};self.leaf={};self.drivers={}
  def add_leaf(bit,value):
   if bit in self.leaf and self.leaf[bit]!=value:raise ValueError('ambiguous boundary aliases')
   if bit in self.drivers:raise ValueError('duplicate driver')
   self.leaf[bit]=value
  for name,p in module['ports'].items():
   if p['direction']=='input':
    for j,bit in enumerate(p['bits']):add_leaf(bit,(self.slots['PI',name,j],0))
  for name,g in module['cells'].items():
   if 'DFF' in g['type'].upper():
    for pin in ['Q','QN']:
     for j,bit in enumerate(g['connections'].get(pin,[])):add_leaf(bit,(self.slots['Q',name,j],int(pin=='QN')))
   else:
    out=SCHEMA[g['type']][0] if g['type'] in SCHEMA else None
    ports=[out] if out else [p for p,d in g.get('port_directions',{}).items() if d=='output']
    for pin in ports:
     for bit in g['connections'][pin]:
      if bit in self.drivers or bit in self.leaf:raise ValueError('duplicate driver')
      self.drivers[bit]=name
 def cone(self,root_bit):
  order=[];visited=set();visiting=set();boundary=set();constants=set();edges=[]
  def visit(bit):
   if isinstance(bit,str):
    if bit not in ['0','1']:raise ValueError('non-two-valued constant')
    constants.add(int(bit));return ('const',int(bit)),0
   if bit in self.leaf:
    slot,phase=self.leaf[bit];boundary.add(slot);return ('boundary',slot),phase
   if bit not in self.drivers:raise ValueError('undriven required bit '+str(bit))
   name=self.drivers[bit]
   if name in visiting:raise ValueError('cycle inside functional cone')
   if name in visited:return ('comb',name),0
   g=self.module['cells'][name]
   if g['type'] not in SCHEMA:raise ValueError('unsupported reached cell '+g['type'])
   output,op,ports=SCHEMA[g['type']]
   if len(g['connections'][output])!=1:raise ValueError('non-bitwise output')
   visiting.add(name)
   for j,pin in enumerate(ports):
    if len(g['connections'][pin])!=1:raise ValueError('non-bitwise input')
    src,phase=visit(g['connections'][pin][0]);role=1 if op=='NOT' else 2+j if op=='MUX' else 0;edges.append((src,('comb',name),role,phase))
   visiting.remove(name);visited.add(name);order.append(name);return ('comb',name),0
  root,root_phase=visit(root_bit)
  if root[0]!='comb' or root_phase:raise ValueError('root must be nontrivial combination output')
  keys=[('boundary',s) for s in sorted(boundary)]+[('const',v) for v in sorted(constants)]+[('comb',n) for n in order];ix={k:i for i,k in enumerate(keys)};ops=[];slots=[];levels=[]
  incoming=collections.defaultdict(list)
  for src,dst,role,phase in edges:incoming[dst].append(src)
  for key in keys:
   if key[0]=='boundary':op=self.kind[key[1]];slot=key[1];lev=0
   elif key[0]=='const':op='CONST'+str(key[1]);slot=-1;lev=0
   else:op=SCHEMA[self.module['cells'][key[1]]['type']][1];slot=-1;lev=1+max(levels[ix[k]] for k in incoming[key])
   ops.append(OPS.index(op));slots.append(slot);levels.append(lev)
  ee=[(ix[src],ix[dst],role,phase) for src,dst,role,phase in edges]
  return dict(op=ops,slot=slots,level=levels,root=ix[root],edge=ee,comb_names=order,keys=keys)
def validate(g):
 n=len(g['op']);assert len(g['slot'])==len(g['level'])==n and 0<=g['root']<n;inc=collections.defaultdict(list)
 for s,d,r,p in g['edge']:
  assert 0<=s<n and 0<=d<n and s<d and p in [0,1] and r in range(5);assert g['level'][s]<g['level'][d];inc[d].append((s,r,p))
 for j,opid in enumerate(g['op']):
  op=OPS[opid];incoming=inc[j]
  if op in ['PI','Q','CONST0','CONST1']:assert not incoming and g['level'][j]==0
  else:
   assert len(incoming)==(1 if op=='NOT' else 3 if op=='MUX' else 2)
   assert sorted(r for _,r,_ in incoming)==([1] if op=='NOT' else [2,3,4] if op=='MUX' else [0,0])
 assert g['level'][g['root']]==max(g['level'])
 return True
def replay(g,env,mask=1):
 """Audit only: env holds witness bits; it is NEVER a neural input feature."""
 validate(g);inc=collections.defaultdict(list)
 for src,dst,role,phase in g['edge']:inc[dst].append((src,role,phase))
 values=[]
 for j,opid in enumerate(g['op']):
  op=OPS[opid]
  if op in ['PI','Q']:v=env[g['slot'][j]]
  elif op=='CONST0':v=0
  elif op=='CONST1':v=mask
  else:
   vv=[(role,values[src]^(mask if phase else 0)) for src,role,phase in inc[j]];aa=[v for _,v in vv]
   if op=='AND':v=aa[0]&aa[1]
   elif op=='OR':v=aa[0]|aa[1]
   elif op=='XOR':v=aa[0]^aa[1]
   elif op=='NOT':v=mask^aa[0]
   else:d=dict(vv);v=(d[4]&d[3])|((mask^d[4])&d[2])
  values.append(v)
 return values[g['root']]
def collate(graphs,contexts,token_tables,tag=9000):
 """25d features=9 op/kind bits+16 neutral input-code bits; no global39."""
 vectors={}
 for key in sorted(set(contexts)):
  tokens=token_tables[key];v={}
  for ki,kind in enumerate(['PI','Q']):
   slots=[t['slot'] for t in tokens if t['kind']==kind]
   # Full-context vocabulary and count/tag seed, never a per-cone rank map or
   # a batch-order/context-name seed. Standalone and batched inputs agree.
   rng=np.random.default_rng([420000,int(tag),ki,len(slots)]);perm=rng.permutation(len(slots))
   for j,s in enumerate(slots):v[s]=code(kind,slots[int(perm[j])])
  vectors[key]=v
 features=[];edges=[];roles=[];phases=[];levels=[];roots=[];ptr=[0];graph_index=[]
 for gi,(g,key) in enumerate(zip(graphs,contexts)):
  validate(g);base=ptr[-1];x=np.zeros((len(g['op']),25),np.float32);x[np.arange(len(x)),g['op']]=1
  for j,slot in enumerate(g['slot']):
   if slot>=0:x[j,9:]=vectors[key][slot]
  features.append(x);edges.extend((s+base,d+base) for s,d,r,p in g['edge']);roles.extend(r for s,d,r,p in g['edge']);phases.extend(p for s,d,r,p in g['edge']);levels.extend(g['level']);roots.append(base+g['root']);ptr.append(base+len(x));graph_index.extend([gi]*len(x))
 result=dict(x=np.concatenate(features),edge_index=np.array(edges,np.int64).reshape(-1,2).T,edge_role=np.array(roles,np.int64),edge_phase=np.array(phases,np.int64),level=np.array(levels,np.int64),root_index=np.array(roots,np.int64),graph_ptr=np.array(ptr,np.int64),graph_index=np.array(graph_index,np.int64))
 assert np.isfinite(result['x']).all();src,dst=result['edge_index'];assert np.array_equal(result['graph_index'][src],result['graph_index'][dst]);return result
