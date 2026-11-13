"""Alpha test positive lineage audit;sidecar roles only,no labels changed."""
from pathlib import Path
import collections,csv,hashlib,importlib.util,json,re
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;F=R/'generate_trans/folds/hosts_bt31';C=R/'_p0pilot/control_boundary_v3_20261104';SRC='s38584t100__injalpha_d1_s42'
s=importlib.util.spec_from_file_location('retained_netlist_parser',R/'_p0pilot/control_retention_20261104/audit.py');A=importlib.util.module_from_spec(s);s.loader.exec_module(A)
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def table(n,rr):
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def main():
 sp=F/'orig'/(SRC+'.v');source,st=A.cells(sp);provpath=R/'generate_trans/hosts/s38584t100/provenance.json';prov=next(x for x in read(provpath) if x.get('view')==SRC);protected={str(p.relative_to(R)):sha(p) for p in [sp,provpath,Path(__file__)]};vvs=[v for v in rows(R/'_p0pilot/control_loader_po_20261105/view_dictionary.csv') if v['key']=='trans_test' and v['source']==SRC];fc=read(C/'input_contract.json');d=R/fc['shared_inputs']['trans_test']['folder'];y=np.load(d/'y.npy',mmap_mode='r');trusted=np.load(d/'trusted.npy',mmap_mode='r');physical=np.load(d/'physical.npy',mmap_mode='r');needed={};vbyrow={}
 for v in vvs:
  lo,hi=int(v['start']),int(v['physical_stop']);ii=np.flatnonzero(trusted[lo:hi]&physical[lo:hi]&(y[lo:hi]==1))+lo
  for i in ii:needed[int(v['old_start'])+int(i)-lo]=int(i);vbyrow[int(i)]=v
 names={};path=F/'data/processed/node_names_trans.txt';protected[str(path.relative_to(R))]=sha(path)
 with path.open(encoding='utf-8') as f:
  for gid,line in enumerate(f):
   if gid in needed:names[needed[gid]]=A.norm(line)
   if len(names)==len(needed):break
 assert len(names)==len(needed);rr=[];bindings=[]
 for v in vvs:
  view=v['view'];mp=F/'mappings'/(view+'.json');tp=F/'trans'/(view+'.v');m=read(mp);target,tt=A.cells(tp);assert m['src_view']==SRC and m['rw_view']==view
  for p in [mp,tp]:protected[str(p.relative_to(R))]=sha(p)
  rev=collections.defaultdict(set)
  for parent,children in m['node_alignment'].items():
   for c in children:rev[A.norm(c)].add(A.norm(parent))
  uf={}
  def find(a):
   uf.setdefault(a,a)
   while uf[a]!=a:uf[a]=uf[uf[a]];a=uf[a]
   return a
  def union(a,b):uf[find(a)]=find(b)
  for a,b in re.findall(r'\bassign\s+([^=;]+)\s*=\s*([^;]+);',tt):
   a,b=A.norm(a),A.norm(b)
   if re.fullmatch(r'[\w.$\[\]/]+',a) and re.fullmatch(r'[\w.$\[\]/]+',b):union(a,b)
  nets={net for typ,con in source.values() for net in con.values()};classes=collections.defaultdict(set)
  allw=set(uf)|{n for typ,con in target.values() for n in con.values()}
  for wire in allw:
   if wire in nets:classes[find(wire)].add(wire)
   if '.' in wire:
    inst,pin=wire.rsplit('.',1)
    if inst in source and pin in source[inst][1]:classes[find(wire)].add(source[inst][1][pin])
  for i,name in names.items():
   if vbyrow[i]['view']!=view:continue
   assert name in target,(view,name);parents=sorted(rev[name]);roles=[]
   for parent in parents:
    if parent=='TrojanAHJ':roles.append('output_hijack')
    elif re.fullmatch(r'TrojanAP[0-2]',parent):roles.append('payload')
    elif parent=='TrojanAT1':roles.append('trigger')
    else:roles.append('host_or_other')
   role=roles[0] if len(parents)==1 else 'mixed_source';typ,con=target[name];nature='sequential_descendant' if 'DFF' in typ.upper() else 'combinational_descendant';verified=False
   if len(parents)==1 and parents[0] in source and view.endswith(('__ys_id','__ys_opt')):
    parent=parents[0];src_type,sc=source[parent];pinmap={'A':'IN1','B':'IN2','S0':'S','Y':'Q'} if parent=='TrojanAHJ' else {p:p for p in sc}
    if not ('DFF' in typ.upper()) and set(pinmap)<=set(con):
     checks={pin:sc[srcpin] in classes[find(con[pin])] for pin,srcpin in pinmap.items()};verified=all(checks.values());bindings.append(dict(view=view,row=i,target=name,parent=parent,source_type=src_type,target_type=typ,port_bindings=json.dumps(checks,sort_keys=True),all_source_ports_match=verified))
     if verified:nature='direct_role_port_bound'
   rr.append(dict(view=view,row=i,node_name=name,target_type=typ,parents='|'.join(parents),parent_count=len(parents),manufacturing_role=role,nature=nature,all_original_ports_bound=verified,old_y=int(y[i]),old_trusted=bool(trusted[i]),scope='supplemental lineage audit,not securityrole transfer or CEC'))
 table('ALPHA_POSITIVE_LINEAGE.csv',rr);table('ALPHA_DIRECT_PORT_BINDINGS.csv',bindings)
 # Exact manufacturing-function wiring of source chain;no new functional solver proof.
 assert source['TrojanAP0'][1]['IN1']==source['TrojanAT1'][1]['Q'];assert source['TrojanAP1'][1]['IN1']==source['TrojanAP0'][1]['Q'];assert source['TrojanAP2'][1]['IN1']==source['TrojanAP1'][1]['Q'];assert source['TrojanAHJ'][1]['IN2']==source['TrojanAP2'][1]['Q'] and source['TrojanAHJ'][1]['S']==source['TrojanAT1'][1]['Q']
 critical={'g__TrojanAHJ.IN2_8':'TrojanAP2','g_g8918_2':'TrojanAHJ','g__TrojanAP0.Q_4':'TrojanAP0','g__TrojanAP1.Q_6':'TrojanAP1','g__TrojanAHJ.S_10':'TrojanAT1'}
 for view in [SRC+'__ys_id',SRC+'__ys_opt']:
  for name,parent in critical.items():
   row=next(r for r in rr if r['view']==view and r['node_name']==name);assert row['parents']==parent and row['all_original_ports_bound'],row
 result=dict(passed=True,alpha_positive_nodes=len(rr),source_chain_verified=True,critical_id_opt_ports_bound=10,provenance_list_missing_from_fold_source=sorted(set(prov['new_gates'])-set(source)),source_hijack_not_listed_as_new='TrojanAHJ' not in prov['new_gates'],all_source_roles_are_audit_only=True,labels_trusted_and_old_roles_unchanged=True,new_model_forwards=0,training=0,SAT=0,protected_inputs=protected)
 (O/'LINEAGE_VERIFIED.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in result.items() if k!='protected_inputs'}))
if __name__=='__main__':main()
