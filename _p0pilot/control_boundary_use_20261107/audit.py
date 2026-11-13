"""No-model boundary-use audit of the prior frozen train/val nodes and matches."""
import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import csv,json,hashlib,collections,sys,importlib.util
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;P=R/'_p0pilot/control_role_pattern_20261107';V=R/'_p0pilot/control_boundary_v3_20261104';F=R/'generate_trans/folds/hosts_bt31'
sys.path.insert(0,str(R));sys.path.insert(0,str(V));from independent_net import raw_network
from phase2 import netlist_lib as NL
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
def pinrole(p):
 p=p.upper()
 return 1 if p=='D' else 2 if p in ['CK','CLK','CLOCK'] else 4 if p in ['SI','SCANIN'] else 8 if p in ['RN','SN','RST','RESET','RESETN','SET','SETN','CLR','PRE'] else 16 if p in ['SE','EN','ENABLE'] else 64
def reverse_distance(succ,seeds):
 pred=collections.defaultdict(set)
 for u,vs in succ.items():
  for v in vs:pred[v].add(u)
 d={s:0 for s in seeds};q=collections.deque(sorted(seeds))
 while q:
  v=q.popleft()
  for u in sorted(pred[v]):
   if u not in d:d[u]=d[v]+1;q.append(u)
 return d
def main():
 assert not (O/'AUDIT_COMPLETE.json').exists();assert read(P/'VERIFIED.json')['passed'];fc=read(V/'input_contract.json');lin=rows(P/'NODE_LINEAGE.csv');keys=list(dict.fromkeys(r['key'] for r in lin));views=[v for v in rows(R/'_p0pilot/control_loader_po_20261105/view_dictionary.csv') if v['key'] in keys];protected={};out=[];witness=[];viewstats=[];inputrows=[]
 def bind(p):protected[str(p.relative_to(R))]=sha(p)
 for p in [Path(__file__),P/'NODE_LINEAGE.csv',P/'FEATURE_NEAREST_LINKS.csv',P/'PAIR_TIE_ROBUSTNESS.csv',P/'VERIFIED.json',P/'LOCAL_DESCRIPTORS.csv',P/'PAIR_FEATURE_DETAILS.csv',V/'input_contract.json',V/'feature_encoding_v3_po.py',V/'independent_net.py',F/'verilog_lib.v',R/'phase2/netlist_lib.py',R/'_p0pilot/control_loader_po_20261105/supervision_loader.py',R/'_p0pilot/control_best200_20261104/evaluate.py',R/'_p0pilot/control_five_seed42_20261107/run.py',R/'models/gin_net.py']:bind(p)
 lib=NL.load_library(F/'verilog_lib.v');names={}
 for dm,p in [('orig',R/'_p0pilot/round32_20261029/orig_names/node_names_orig.txt'),('trans',F/'data/processed/node_names_trans.txt')]:bind(p);names[dm]=[s.strip().lstrip('\\') for s in p.read_text(encoding='utf-8').splitlines()]
 for key in keys:
  folder=R/fc['shared_inputs'][key]['folder'];a={n:np.load(folder/(n+'.npy'),mmap_mode='r') for n in ['x39','edge_index','edge_roles','physical','trusted','y']}
  for n in a:p=folder/(n+'.npy');assert sha(p)==fc['files'][str(p.relative_to(R))];bind(p)
  edge=a['edge_index'];order=np.argsort(edge[0],kind='stable');sorted_src=edge[0,order]
  for v in [v for v in views if v['key']==key]:
   rr=[r for r in lin if r['key']==key and r['view']==v['view']]
   if not rr:continue
   path=F/('trans' if key.startswith('trans') else 'orig')/(v['view']+'.v');bind(path);cache=V/'view_cache'/key/v['view']/'DONE.json';old=read(cache);assert old['binding']['source_sha']==sha(path) and old['binding']['library_sha']==sha(F/'verilog_lib.v');bind(cache)
   raw=raw_network(path,lib);nn=names[key.split('_')[0]][int(v['old_start']):int(v['old_stop'])]+raw['virtual_names'];lo,hi=int(v['start']),int(v['stop']);assert len(nn)==hi-lo and set(nn)==set(raw['cells']);ix={n:i+lo for i,n in enumerate(nn)};isff={n for n,(typ,_) in raw['pins'].items() if 'DFF' in typ.upper()};pocells=raw['pocells'];assert pocells=={nn[i] for i in range(len(nn)) if a['x39'][lo+i,30]==0}
   # Independently reconstruct destination pin roles from actual library directions and aliased nets.
   ep=collections.defaultdict(set)
   for t,(typ,conn) in raw['pins'].items():
    inputs=lib[typ]['inputs'] if typ in lib else [p for p,_ in conn if p!='Y']
    for pin,net in conn:
     if pin in inputs:
      for u in raw['drivers'].get(net,[]):ep[u,t].add(pin)
   es={(ix[u],ix[t]) for u,ts in raw['succ'].items() for t in ts};sel=order[np.searchsorted(sorted_src,lo):np.searchsorted(sorted_src,hi)];saved={tuple(map(int,p)):int(role) for p,role in zip(edge[:,sel].T,a['edge_roles'][sel])};assert es==set(saved)
   rolechecks=0
   for (u,t),pins in ep.items():
    mask=0
    for p in pins:mask|=pinrole(p) if t in isff else 1
    assert saved[ix[u],ix[t]]==mask,(key,v['view'],u,t,pins,mask,saved[ix[u],ix[t]]);rolechecks+=1
   functional_succ={u:{t for t in ts if t not in isff or any(p.upper()=='D' for p in ep[u,t])} for u,ts in raw['succ'].items()};d_mode=reverse_distance(functional_succ,pocells)
   for r in rr:
    root=r['node_name'];assert ix[root]==int(r['row']);q=collections.deque([root]);dist={root:0};prev={};ends=collections.defaultdict(set);enddist={};first={};sinknodes=set();poends=set();po_dist=-1
    while q:
     u=q.popleft();d=dist[u]
     if u in pocells:
      poends.add(u)
      if po_dist<0:po_dist=d;first['PO']=u
     nxt=raw['succ'][u]
     if not nxt and u not in pocells:sinknodes.add(u)
     for t in sorted(nxt):
      if t in isff:
       for pin in sorted(ep[u,t]):
        kind='D' if pin.upper()=='D' else 'SI' if pin.upper() in ['SI','SCANIN'] else 'CLK' if pinrole(pin)==2 else 'RESET' if pinrole(pin)==8 else 'ENABLE' if pinrole(pin)==16 else 'OTHER'
        ends[kind].add(t+'.'+pin)
        if kind not in enddist or d+1<enddist[kind]:enddist[kind]=d+1;first[kind]=(u,t,pin)
      elif t not in dist:dist[t]=d+1;prev[t]=u;q.append(t)
    fields=dict(key=key,row=int(r['row']),view=r['view'],source=r['source'],side=r['side'],role=r['role'],parents=r['parents'],node_name=root,type=raw['cells'][root][0],flow_full=r['flow_full'],root_is_register=root in isff,M_exposure_200=int(r['M_exposure_200']),root_is_terminal_load=(not raw['succ'][root] and root not in pocells),comb_nodes_visited=len(dist),dead_end_count=len(sinknodes),PO_before_register=bool(poends),PO_before_register_distance=po_dist,PO_endpoints=len(poends),D=bool(ends['D']),D_distance=enddist.get('D',-1),D_pins=len(ends['D']),SI=bool(ends['SI']),SI_distance=enddist.get('SI',-1),SI_pins=len(ends['SI']),other_register_pin=any(ends[k] for k in ['CLK','RESET','ENABLE','OTHER']),CLK_pins=len(ends['CLK']),RESET_pins=len(ends['RESET']),ENABLE_pins=len(ends['ENABLE']),OTHER_pins=len(ends['OTHER']),no_output_or_register_boundary=not (poends or any(ends.values())),scan_only=bool(ends['SI']) and not (poends or ends['D'] or any(ends[k] for k in ['CLK','RESET','ENABLE','OTHER'])),PO_Donly_structural_path=root in d_mode,PO_Donly_structural_distance=d_mode.get(root,-1),old_PO_distance=float(a['x39'][int(r['row']),30]),old_register_input_distance=float(a['x39'][int(r['row']),34]),boundary_signature='|'.join(k for k,b in [('PO',bool(poends)),('D',bool(ends['D'])),('SI',bool(ends['SI'])),('CTRL',any(ends[k] for k in ['CLK','RESET','ENABLE','OTHER'])),('DEAD',bool(sinknodes))] if b))
    out.append(fields)
    def chain(u):
     path=[u]
     while u in prev:u=prev[u];path.append(u)
     return list(reversed(path))
    for kind,item in first.items():
     if kind=='PO':path0=chain(item);endpoint=item;pin='OUTPUT';nets=sorted(net for p,net in raw['pins'][item][1] if net in raw['po'])
     else:u,t,pin=item;path0=chain(u)+[t];endpoint=t+'.'+pin;nets=sorted(net for pp,net in raw['pins'][t][1] if pp==pin)
     witness.append(dict(key=key,row=int(r['row']),kind=kind,endpoint=endpoint,endpoint_pin=pin,distance=len(path0)-1,path=json.dumps(path0,ensure_ascii=False),normalized_endpoint_nets='|'.join(nets),source_netlist=str(path.relative_to(R)),interpretation='structural path,not sensitization/CEC or operational scan-mode proof'))
   viewstats.append(dict(key=key,view=v['view'],roots=len(rr),graph_nodes=len(nn),edges=len(saved),edge_pin_role_checks=rolechecks,PO_seeds_verified=True,independent_pin_graph_matches_saved=True));print('BOUNDARY',key,v['view'],len(rr),flush=True)
 table('NODE_BOUNDARIES.csv',out);table('PATH_WITNESSES.csv',witness);table('VIEW_PIN_CHECKS.csv',viewstats)
 # Record the precise information path in the frozen model, without importing torch or forwarding.
 inputrows=[dict(information='actual PO-driver distance',stored='x39 column30',consumed='yes as normalized scalar',limit='graph distance may traverse register edges of any pin;not functional sensitization'),dict(information='generic register-boundary distance/context',stored='x39 columns33..36',consumed='yes as normalized scalars',limit='does not distinguish D/SI/clock/reset/enable;register-reset here means distance reset,not reset-pin semantic role'),dict(information='D/SI/clock/reset/enable destination role',stored='edge_roles.npy bit1/4/2/8/16',consumed='no:torch_graph returns x,edge,y only',limit='saved to disk but not forwarded to current detector'),dict(information='outgoing fanout and first boundary usage',stored='x39 fanout counts/distance summaries partly reflect it',consumed='partially;GIN messages follow incoming edges only',limit='no explicit first-D/SI endpoint signature or output-use class'),dict(information='MUX data/select role, Q/QN output phase',stored='raw netlist pins;non-register edge_roles all1',consumed='no explicit pin or output phase',limit='gate type can encode primitive class,not which edge carries each role'),dict(information='terminal unused output',stored='inferable partly from graph degree/PO flag',consumed='only implicit through existing features',limit='a root may feed a long dead chain;zero fanout alone misses upstream members')]
 table('MODEL_INFORMATION_AUDIT.csv',inputrows)
 for p,h in protected.items():assert sha(R/p)==h,p
 result=dict(passed=True,scope=keys,frozen_nodes=len(out),views=len(viewstats),pin_role_checks=sum(x['edge_pin_role_checks'] for x in viewstats),model_forwards=0,training=0,SAT=0,labels_changed=False,definition='Traverse combinational successors until first register;PO may be encountered before register;D-only PO path additionally allows only D dependencies through registers;all structural,not logical influence',root_registers_excluded_from_pair_mechanism=True,protected_inputs=protected)
 (O/'AUDIT_COMPLETE.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print('AUDIT_COMPLETE',len(out),len(witness),flush=True)
if __name__=='__main__':main()
