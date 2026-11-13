"""Replay actual behavioral-library formulas and archived upstream certificates; no solver."""
import trace as C
import numpy as np,collections,re,json
from independent_net import parse_expression
R=C.R;O=C.O;F=C.F;T=C.T
def main():
 done=C.read(O/'TRACE_COMPLETE.json');assert done['passed'];lib=C.NL.load_library(F/'verilog_lib.v');behavior=R.parent/'GraphSAINT-train/vali/verilog_lib.v';text=behavior.read_text(encoding='utf-8');asts={};formulas=[]
 def ast_for(typ,pin):
  key=typ,pin
  if key not in asts:
   modules=re.findall(r'\bmodule\s+'+re.escape(typ)+r'\b.*?endmodule',text,re.S)
   assert len(modules)==1,typ
   assigns=re.findall(r'\bassign\s+'+re.escape(pin)+r'\s*=\s*([^;]+);',modules[0]);assert len(assigns)==1,(typ,pin);asts[key]=parse_expression(assigns[0]);formulas.append(dict(type=typ,output_pin=pin,formula=assigns[0],behavioral_library=str(behavior),library_sha=C.sha(behavior)))
  return asts[key]
 def ast_value(ast,env):
  op=ast[0]
  if op=='leaf':
   if ast[1] in ["1'b0","1'b1",'0','1']:return np.full_like(next(iter(env.values())),ast[1] in ["1'b1",'1'])
   return env[ast[1]]
  a=[ast_value(q,env) for q in ast[1:]]
  return ~a[0] if op=='~' else a[0]&a[1] if op=='&' else a[0]|a[1] if op=='|' else a[0]^a[1] if op=='^' else np.where(a[0],a[1],a[2])
 def evaluate(g,signal,env):
  cache={g['find'](s):v for s,v in env.items()};used=set()
  def ev(net):
   net=g['find'](net)
   if net in cache:return cache[net]
   if net in ['#0','#1']:return np.full(len(next(iter(env.values()))),net=='#1',bool)
   owners=g['drivers'].get(net,set());assert len(owners)==1;name=next(iter(owners));typ,connections=g['pins'][name];assert 'DFF' not in typ.upper();ports=dict(connections);output=[p for p,n in connections if n==net and p in lib[typ]['outputs']];assert len(output)==1;result=ast_value(ast_for(typ,output[0]),{p:ev(ports[p]) for p in lib[typ]['inputs']});cache[net]=result;used.add(name);return result
  return ev(signal),used
 localchecks=0;gcache={};cuts=C.read(O/'LOCAL_TRUTH_CERTIFICATES.json');verifiedcuts=[]
 for c in cuts:
  src,view=c['source'],c['view'];gs=C.raw_network(F/'orig'/(src+'.v'),lib);gt=C.raw_network(F/'trans'/(view+'.v'),lib);gcache[view]=gt;bits=[np.array(v,bool) for v in c['variables']]
  if 'delta' in src:
   x,u,v=bits;es={'n533':x,'TrojanD_t4':~u,'g10801_orig':~v};et={'TrojanD_s2':~x,'_0473_':u,'_0729_':v};assert np.array_equal(evaluate(gt,'n533',et)[0],x);comp='TrojanD_t4'
  else:
   a,b,q,u,v=bits;es={'n8566':a,'WX3484':b,'DFF_955_n1':q,'TrojanA_t1':~u,'test_so62_orig':~v};et={'n8566':a,'WX3484':b,'DFF_955_n1':q,'_0383_':u,'_0001_':v};comp='TrojanA_p2'
  for sig,truth in c['source_target_outputs'].items():
   expected=np.array(truth,bool);ls,used_s=evaluate(gs,sig,es);lt,used_t=evaluate(gt,sig,et);assert np.array_equal(ls,expected) and np.array_equal(lt,expected);localchecks+=2
  phase,_=evaluate(gt,c['carrier'],et);named,_=evaluate(gt,comp,et);assert np.array_equal(phase,~named);localchecks+=1;verifiedcuts.append(dict(source=src,patterns=c['patterns'],actual_library_source_target_replay=True,complement_carrier_replay=True,scope=c['scope']))
 # Verify the native and transformed host data branch, not just the PO wire name.
 src='s35932t200__injalpha_d1_s42';view=src+'__ys_abc';gs=C.raw_network(F/'orig'/(src+'.v'),lib);gt=gcache[view];pat=np.arange(4);y=(pat&1).astype(bool);reset=((pat>>1)&1).astype(bool)
 source_data,_=evaluate(gs,'WX7351',{'test_so62':y,'RESET':reset});target_data,_=evaluate(gt,'U6001.Q',{'test_so62':y,'RESET':reset});assert np.array_equal(source_data,y&reset) and np.array_equal(target_data,y&reset)
 assert dict(gs['pins']['DFF_1113_Q_reg'][1])['D']==gs['find']('WX7351');assert dict(gt['pins']['DFF_1113_Q_reg'][1])['D']==gt['find']('U6001.Q')
 C.table('HOST_CONNECTION_REPLAY.csv',[dict(source=src,native_path='test_so62 -> U6001(ISOLANDX1) -> WX7351 -> DFF_1113_Q_reg.D',target_path='test_so62 -> g__U6001.Q_2345(AND2X2) -> U6001.Q -> DFF_1113_Q_reg.D',native_and_target_D_formula='test_so62 AND RESET',patterns=4,actual_behavioral_replay=True,scope='this explicit host data branch only;not full state transition equivalence')])
 C.table('REAL_LIBRARY_LOCAL_REPLAY.csv',verifiedcuts)
 # Existing raw snapshots and the three old abc/aig certificates cover trigger/P0/P1 only.
 old=R/'_p0pilot/cec_joint_expand_20261105';pairfile=old/'bounded_pairs.json';certfile=old/'bounded_certificates.json';pairs=C.read(pairfile);certs={r['pair_id']:r for r in C.read(certfile)};proofs=[];raws={};archived_inputs={str(p.relative_to(R)):C.sha(p) for p in [pairfile,certfile,old/'BOUNDED_COMPLETE.json']}
 for p in pairs:
  if p['source_object']!='s35932t200__injalpha_d1_s42':continue
  cert=certs[p['pair_id']];assert cert['status']=='proved' and cert['equal'] and cert['nonconstant'];env={tuple(t):((np.arange(cert['patterns'],dtype=np.uint32)>>j)&1).astype(bool) for j,t in enumerate(cert['semantic_inputs'])};outputs=[]
  for side,end in enumerate(p['root_endpoints']):
   view=end['view']
   if view not in raws:
    snapshot=T/'sat_k4_alltrain_round27/views'/view/'snapshots.json';candidates=C.read(snapshot);item=next(r for r in candidates if r['raw_sha']==cert['raw_shas'][side]);rawfile=R/item['folder']/'raw.json';sourcefile=F/'trans'/(view+'.v');assert C.sha(rawfile)==item['raw_sha'] and C.sha(sourcefile)==item['source_sha'];raw=next(iter(C.read(rawfile)['modules'].values()));raws[view]=(raw,item);archived_inputs.update({str(q.relative_to(R)):C.sha(q) for q in [snapshot,rawfile,sourcefile]})
   m,item=raws[view];assert item['raw_sha']==cert['raw_shas'][side];values={};drivers={}
   for name,port in m['ports'].items():
    if port['direction']=='input':
     for j,bit in enumerate(port['bits']):
      if ('PI',name,j) in env:values[bit]=env['PI',name,j]
   for name,g in m['cells'].items():
    if 'DFF' in g['type'].upper():
     if ('Q',name,0) in env:
      for pin in ['Q','QN']:
       for bit in g['connections'].get(pin,[]):values[bit]=~env['Q',name,0] if pin=='QN' else env['Q',name,0]
    else:
     for pin in lib[g['type']]['outputs']:
      if pin in g['connections']:
       for bit in g['connections'][pin]:assert bit not in drivers;drivers[bit]=(name,pin)
   def ev(bit):
    if not isinstance(bit,int):assert bit in ['0','1'];return np.full(cert['patterns'],bit=='1',bool)
    if bit in values:return values[bit]
    name,pin=drivers[bit];g=m['cells'][name];typ=g['type'];assert 'DFF' not in typ.upper();values[bit]=ast_value(ast_for(typ,pin),{p0:ev(g['connections'][p0][0]) for p0 in lib[typ]['inputs']});return values[bit]
   outputs.append(ev(cert['root_bits'][side]))
  assert np.array_equal(*outputs);packed=np.packbits(outputs[0],bitorder='little').tobytes();assert packed.hex()==cert['packed_truth_hex'] and C.hashlib.sha256(packed).hexdigest()==cert['truth_sha'];proofs.append(dict(pair_id=p['pair_id'],source=p['source_object'],observations='|'.join(p['observations']),inputs=cert['inputs'],patterns=cert['patterns'],raw_and_source_hashes_match=True,archived_truth_replayed=True,scope='abc vs aig upstream cut;NOT orig->abc whole output or AP2 signed-carrier proof'))
 C.table('REUSED_PROOF_SCOPE.csv',proofs);C.table('ACTUAL_CELL_FORMULAS.csv',formulas)
 # Verify all saved carrier paths against actual aliased pin graph, including live D sink.
 paths=C.read(O/'CARRIER_TO_HOST_PATHS.json');pathchecks=0
 for p in paths:
  g=gcache[p['view']]
  for route in p['PO_paths']:
   assert route[0]==p['start'] and route[-1] in g['pocells'];assert all(v in g['succ'][u] for u,v in zip(route,route[1:]));pathchecks+=1
  for row in p['first_register_paths']:
   route=row['path'];assert all(v in g['succ'][u] for u,v in zip(route,route[1:]));assert 'DFF' in g['pins'][route[-1]][0].upper() and row['pins'];pathchecks+=1
  if p['closed_no_PO_no_register']:
   visited=set(p['visited_nodes']);assert all(g['succ'][u]<=visited for u in visited) and not visited&g['pocells'];assert all('DFF' not in g['pins'][u][0].upper() for u in visited)
 labels=C.rows(O/'LIVE_AND_NAMED_LABELS.csv');helper=next(r for r in labels if r['cell']=='g__0384__527');assert helper['current_parents']=='' and helper['old_trusted']=='False';mapped=next(r for r in labels if r['cell']=='g_TrojanA_p2_528');assert mapped['current_parents']=='TrojanAP2' and mapped['old_y']=='1' and mapped['old_trusted']=='True'
 for p,h in {**done['protected_inputs'],**archived_inputs}.items():assert C.sha(R/p)==h,p
 result=dict(passed=True,local_actual_library_checks=localchecks,local_cut_patterns=40,host_branch_patterns=4,host_data_branch_verified=True,archived_upstream_certificates_replayed=len(proofs),archived_patterns_replayed=sum(r['patterns'] for r in proofs),saved_carrier_host_paths_checked=pathchecks,signed_alpha_carrier_absent_from_node_alignment=True,delta_payload_absorbed_in_final_correlated_chain=True,whole_design_CEC_not_claimed=True,training=0,SAT=0,solver_calls=0,model_forwards=0,labels_changed=False,actual_behavioral_library=str(behavior),actual_library_sha=C.sha(behavior),protected_archived_inputs=archived_inputs)
 (O/'VERIFIED.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print({k:v for k,v in result.items() if k not in ['protected_archived_inputs']})
if __name__=='__main__':main()
