"""Three frozen cases: pin/alias trace plus tiny Boolean replay; no solver/model calls."""
import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import json,csv,hashlib,collections,sys,re
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;F=R/'generate_trans/folds/hosts_bt31';T=R/'10.15/06_统一评测协议/N4_三向泛化/tables';P=R/'_p0pilot/control_role_pattern_20261107'
sys.path.insert(0,str(R));sys.path.insert(0,str(R/'_p0pilot/control_boundary_v3_20261104'));from independent_net import raw_network
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
def evaluate(g,signal,env,lib,used=None):
 cache={g['find'](s):v for s,v in env.items()};active=set()
 def ev(net):
  net=g['find'](net)
  if net in cache:return cache[net]
  if net in ['#0','#1']:return net=='#1'
  assert net not in active,('cycle',net);active.add(net);drivers=g['drivers'].get(net,set());assert len(drivers)==1,('unbound',net,drivers);name=next(iter(drivers));typ,con=g['pins'][name];assert 'DFF' not in typ.upper(),('unbound_state',name);d=dict(con);ins=[ev(d[p]) for p in lib[typ]['inputs']];stem=re.sub(r'X\d+.*$','',typ)
  if typ.startswith('XNOR'):out=~np.logical_xor.reduce(ins)
  elif typ.startswith('XOR'):out=np.logical_xor.reduce(ins)
  elif typ.startswith('NAND'):out=~np.logical_and.reduce(ins)
  elif typ.startswith('NOR'):out=~np.logical_or.reduce(ins)
  elif typ.startswith('AND'):out=np.logical_and.reduce(ins)
  elif typ.startswith('OR'):out=np.logical_or.reduce(ins)
  elif typ.startswith('INV'):out=~ins[0]
  elif typ.startswith('BUF'):out=ins[0]
  elif typ.startswith(('MUX','MX2')):
   pins=lib[typ]['inputs'];si=pins.index('S' if 'S' in pins else 'S0');data=[ins[j] for j in range(len(ins)) if j!=si];out=np.where(ins[si],data[1],data[0])
  else:raise AssertionError(('unsupported_local_cell',typ,name))
  cache[net]=out;active.remove(net)
  if used is not None:used.add(name)
  return out
 return ev(signal)
def main():
 assert not (O/'TRACE_COMPLETE.json').exists();assert read(R/'_p0pilot/control_boundary_use_20261107/VERIFIED.json')['passed'];lib=NL.load_library(F/'verilog_lib.v');protected={};nets=[];details=[];checks=[];cutcert=[];labels=[];paths=[]
 def bind(p):protected[str(p.relative_to(R))]=sha(p)
 for p in [Path(__file__),F/'verilog_lib.v',R/'_p0pilot/control_boundary_v3_20261104/independent_net.py',R/'phase2/netlist_lib.py',P/'NODE_LINEAGE.csv',R/'_p0pilot/control_boundary_use_20261107/FIXED_CASES_BOUNDARY_RESULT.csv']:bind(p)
 fc=read(R/'_p0pilot/control_boundary_v3_20261104/input_contract.json');bind(R/'_p0pilot/control_boundary_v3_20261104/input_contract.json');vv={v['view']:v for v in fc['shared_inputs']['trans_train']['views']};folder=R/fc['shared_inputs']['trans_train']['folder'];a={n:np.load(folder/(n+'.npy'),mmap_mode='r') for n in ['y','trusted','physical']}
 for n in a:bind(folder/(n+'.npy'));assert sha(folder/(n+'.npy'))==fc['files'][str((folder/(n+'.npy')).relative_to(R))]
 npth=F/'data/processed/node_names_trans.txt';bind(npth);allnames=[s.strip().lstrip('\\') for s in npth.read_text(encoding='utf-8').splitlines()]
 definitions=[dict(source='s15850t100__injdelta_d1_s42',flow='ys_nand',parents=['TrojanDP0','TrojanDP2'],signals=['n533','TrojanD_p0','TrojanD_p1','TrojanD_p2','TrojanD_t4','g10801_orig','g10801'],live=['g__0473__923','g_g10801_1672','g_g10801_1673'],output='g10801',host='g10801_orig'),dict(source='s35932t200__injalpha_d1_s42',flow='ys_abc',parents=['TrojanAP2'],signals=['TrojanA_p0','TrojanA_p1','TrojanA_p2','TrojanA_t1','test_so62_orig','test_so62'],live=['g__0384__527','g__0383__520','g_test_so62_530'],output='test_so62',host='test_so62_orig')]
 for case in definitions:
  src=case['source'];view=src+'__'+case['flow'];sp=F/'orig'/(src+'.v');tp=F/'trans'/(view+'.v');mp=F/'mappings'/(view+'.json');[bind(p) for p in [sp,tp,mp]];source=raw_network(sp,lib);target=raw_network(tp,lib);mapping=read(mp);assert mapping['src_view']==src and mapping['rw_view']==view;layout=vv[view];nm={n:layout['start']+j for j,n in enumerate(allnames[layout['old_start']:layout['old_stop']])}
  for side,g in [('orig',source),('trans',target)]:
   for signal in case['signals']:
    canonical=g['find'](signal);ds=sorted(g['drivers'].get(canonical,[]));cs=sorted(g['cons'].get(canonical,[]));pins=[n+'.'+p for n in cs for p,net in g['pins'][n][1] if net==canonical and p in lib[g['pins'][n][0]]['inputs']];nets.append(dict(source=src,view=view if side=='trans' else src,side=side,signal=signal,canonical=canonical,drivers='|'.join(ds),consumers='|'.join(cs),consumer_pins='|'.join(pins),primary_output=canonical in g['po']))
   assert g['find'](case['output']) in g['po']
  # Keep exact pin/net records of source manufacture chain and live transformed output cone.
  for side,g,selected in [('orig',source,[n for n in source['pins'] if n.startswith('Trojan')]+list(source['drivers'][source['find'](case['host'])])),('trans',target,case['live']+sum([mapping['node_alignment'][p] for p in case['parents']],[]))]:
   for n in sorted(set(selected)):details.append(dict(source=src,side=side,cell=n,type=g['pins'][n][0],pins=json.dumps(g['pins'][n][1],ensure_ascii=False),successors='|'.join(sorted(g['succ'][n])),primary_output_driver=n in g['pocells']))
  for name in sorted(set(case['live']+sum([mapping['node_alignment'][p] for p in case['parents']],[]))):
   i=nm[name];owners=sorted(p for p,ch in mapping['node_alignment'].items() if name in ch);labels.append(dict(source=src,view=view,cell=name,row=i,old_y=int(a['y'][i]),old_trusted=bool(a['trusted'][i]),physical=bool(a['physical'][i]),current_parents='|'.join(owners),kind='existing_live_helper_or_output' if name in case['live'] else 'named_payload_descendant',note='0 with trusted=False is unlabelled,not supervised negative'))
  # Enumerate only a 3- or 5-input local Boolean cut. This is not a SAT/CEC solver run.
  width=3 if 'delta' in src else 5;pattern=np.arange(1<<width,dtype=np.uint8);bits=[((pattern>>j)&1).astype(bool) for j in range(width)]
  if 'delta' in src:
   x,u,v=bits;T0=~u;H=~v;env_s={'n533':x,'TrojanD_t4':T0,'g10801_orig':H};env_t={'n533':x,'_0473_':u,'_0729_':v};signals=['TrojanD_p0','TrojanD_p1','TrojanD_p2','g10801'];expected={'TrojanD_p0':x|T0,'TrojanD_p1':x,'TrojanD_p2':x|T0,'g10801':T0|H};phase_carrier='_0473_';complement_signal='TrojanD_t4';out_formula='g10801 = T OR H; P0=P2=x OR T; P1=x';carrier_formula='_0473_ = NOT T';names_cut=['x=n533','u=NOT T','v=NOT H'];payload_influence=False
  else:
   aa,bb,cc,u,v=bits;T0=~u;H=~v;env_s={'n8566':aa,'WX3484':bb,'DFF_955_n1':cc,'TrojanA_t1':T0,'test_so62_orig':H};env_t={'n8566':aa,'WX3484':bb,'DFF_955_n1':cc,'_0383_':u,'_0001_':v};p0=~(T0^aa);p1=~(p0^bb);p2=~(p1^cc);signals=['TrojanA_p0','TrojanA_p1','TrojanA_p2','test_so62'];expected={'TrojanA_p0':p0,'TrojanA_p1':p1,'TrojanA_p2':p2,'test_so62':~(H|p2|T0)};phase_carrier='_0384_';complement_signal='TrojanA_p2';out_formula='test_so62 = NOT H AND NOT P2 AND NOT T';carrier_formula='_0384_ = NOT P2';names_cut=['a=n8566','b=WX3484','c=DFF_955_n1','u=NOT T','v=NOT H'];payload_influence=True
  for sig in signals:
   used_s=set();used_t=set();left=evaluate(source,sig,env_s,lib,used_s);right=evaluate(target,sig,env_t,lib,used_t);assert np.array_equal(left,expected[sig]) and np.array_equal(right,expected[sig]),(src,sig);checks.append(dict(source=src,signal=sig,patterns=1<<width,source_matches_formula=True,target_matches_formula=True,local_equal=True,source_cells='|'.join(sorted(used_s)),target_cells='|'.join(sorted(used_t)),formula=out_formula if sig==case['output'] else 'see LOCAL_TRUTH_CERTIFICATES.json'))
  carrier=evaluate(target,phase_carrier,env_t,lib);named=evaluate(target,complement_signal,env_t,lib);assert np.array_equal(carrier,~named);assert np.array_equal(evaluate(target,case['output'],env_t,lib),expected[case['output']]);cutcert.append(dict(source=src,view=view,inputs=names_cut,patterns=1<<width,variables=[b.astype(int).tolist() for b in bits],source_target_outputs={sig:expected[sig].astype(int).tolist() for sig in signals},carrier=phase_carrier,carrier_truth=carrier.astype(int).tolist(),carrier_formula=carrier_formula,output_formula=out_formula,cut_binding='exact aliases and explicit INV/AND connections;T/H positive counterparts verified from target gates',payload_tap_remains_in_output_expression=payload_influence,scope='local two-valued combination under aligned named cut;not whole-design equivalence or reachable-state proof'))
  # Trace each named mapped payload and each live helper to PO and first actual register pins.
  for start in sorted(set(case['live']+sum([mapping['node_alignment'][p] for p in case['parents']],[]))):
   q=collections.deque([start]);previous={start:None};po=[];reg=[]
   def route(n):
    z=[]
    while n is not None:z.append(n);n=previous[n]
    return list(reversed(z))
   while q:
    n=q.popleft()
    if n in target['pocells']:po.append(route(n))
    for t in sorted(target['succ'][n]):
     if 'DFF' in target['pins'][t][0].upper():
      shared={net for pin,net in target['pins'][n][1] if pin in lib[target['pins'][n][0]]['outputs']};ps=[pin for pin,net in target['pins'][t][1] if net in shared and pin in lib[target['pins'][t][0]]['inputs']];reg.append(dict(path=route(n)+[t],pins=ps))
     elif t not in previous:previous[t]=n;q.append(t)
   paths.append(dict(source=src,view=view,start=start,row=nm[start],PO_paths=po,first_register_paths=reg,closed_no_PO_no_register=not (po or reg),visited_nodes=sorted(previous),scope='pin/alias graph only;no sensitivity solver'))
  print('TRACED',src,flush=True)
 table('SIGNAL_CHAIN.csv',nets);table('CELL_PIN_DETAILS.csv',details);table('LIVE_AND_NAMED_LABELS.csv',labels);table('LOCAL_BOOLEAN_REPLAY.csv',checks);(O/'LOCAL_TRUTH_CERTIFICATES.json').write_text(json.dumps(cutcert,ensure_ascii=False,indent=2),encoding='utf-8');(O/'CARRIER_TO_HOST_PATHS.json').write_text(json.dumps(paths,ensure_ascii=False,indent=2),encoding='utf-8')
 for p,h in protected.items():assert sha(R/p)==h,p
 (O/'TRACE_COMPLETE.json').write_text(json.dumps(dict(passed=True,sources=2,frozen_cases=3,local_cuts=2,local_truth_patterns=40,local_signal_equalities=8,training=0,SAT=0,solver_calls=0,model_forwards=0,labels_changed=False,protected_inputs=protected),ensure_ascii=False,indent=2),encoding='utf-8');print('TRACE_COMPLETE',flush=True)
if __name__=='__main__':main()
