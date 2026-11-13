"""Bounded independent Boolean enumeration of existing14 cone pairs. No SAT/model."""
from pathlib import Path
import json,csv,re,collections,hashlib
import numpy as np
from audit import read,rows,sha,ident,SCHEMA,cone,module
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;T=R/'10.15/06_统一评测协议/N4_三向泛化/tables'
def anchor(leaf):return tuple(leaf[:3])
def main():
 assert (O/'AUDIT_COMPLETE.json').exists();assert not (O/'CONES_VERIFIED.json').exists();pairs=read(O/'functional_cone_pairs.json');cones={c['cone_id']:c for c in read(O/'cones.json')};coords=rows(T/'sat_pair_round15/signal_coordinates.csv');cv={c['view']:c for c in coords};cache={};out=[];fkeys={};root=O/'local_miters';root.mkdir(exist_ok=True);complete_proofs=[];tables={};total=0
 def getraw(view):
  if view not in cache:cache[view]=next(iter(read(R/cv[view]['raw_snapshot']/'raw.json')['modules'].values()))
  return cache[view]
 for p in pairs:
  cc=[cones[p['left_cone']],cones[p['right_cone']]];tokens=sorted({anchor(l) for c in cc for l in c['leaves']});width=len(tokens);assert 0<width<=12;pattern=np.arange(1<<width,dtype=np.uint16);env={t:((pattern>>j)&1).astype(bool) for j,t in enumerate(tokens)};vectors=[];codes=[];bitenvs=[]
  for side,c in zip(['left','right'],cc):
   m=getraw(c['view']);drivers={}
   for name in c['members']:
    cell=m['cells'][name];op=SCHEMA[cell['type']][0];bits=cell['connections'][op];assert len(bits)==1;drivers[bits[0]]=(name,cell)
   leafvalues={l[0]:None for l in []};leafexpressions={}
   # Derive boundary bit identities again, rather than trusting only saved labels.
   for n,q in m['ports'].items():
    if q['direction']=='input':
     for j,b in enumerate(q['bits']):
      t=('PI',n,j)
      if t in env:leafvalues[b]=env[t];leafexpressions[b]='env['+str(tokens.index(t))+']'
   for n,cell in m['cells'].items():
    t=('Q',n,0)
    if t not in env:continue
    for pin in ['Q','QN']:
     for b in cell['connections'].get(pin,[]):leafvalues[b]=~env[t] if pin=='QN' else env[t];leafexpressions[b]=('~' if pin=='QN' else '')+'env['+str(tokens.index(t))+']'
   seen={};expressions={};visiting=set()
   def ev(b):
    if not isinstance(b,int):assert b in ['0','1'];return np.full(len(pattern),b=='1',bool)
    if b in seen:return seen[b]
    if b in leafvalues:seen[b]=leafvalues[b];expressions[b]=leafexpressions[b];return seen[b]
    assert b in drivers and b not in visiting,(c['view'],b);visiting.add(b);name,cell=drivers[b];typ=cell['type'];conn=cell['connections'];args=SCHEMA[typ][1];vals=[ev(conn[a][0]) for a in args];bitname=lambda q:'b'+str(q) if isinstance(q,int) else "1'b"+q;terms=[bitname(conn[a][0]) for a in args]
    if typ in ['AND2X2','$and']:v=vals[0]&vals[1];exp=terms[0]+'&'+terms[1]
    elif typ in ['OR2X1','$or']:v=vals[0]|vals[1];exp=terms[0]+'|'+terms[1]
    elif typ in ['XOR2X1','$xor']:v=vals[0]^vals[1];exp=terms[0]+'^'+terms[1]
    elif typ in ['INVX0','$not']:v=~vals[0];exp='~'+terms[0]
    else:assert typ in ['MX2X1_RS','$mux'];v=np.where(vals[2],vals[1],vals[0]);exp=terms[2]+'?'+terms[1]+':'+terms[0]
    seen[b]=v;expressions[b]=exp;visiting.remove(b);return v
   vector=ev(c['root_bit']);assert len(drivers)==len(c['members']);vectors.append(vector);bitenvs.append(leafexpressions);code=[f'module {side}_cone(input [{width-1}:0] env,output value);','wire '+','.join('b'+str(b) for b in sorted(expressions))+';']+[f'assign b{b}={exp};' for b,exp in sorted(expressions.items())]+[f'assign value=b{c["root_bit"]};','endmodule'];codes.append('\n'.join(code));assert set(c['graph_rows']) and len(c['graph_rows'])==len(c['members'])
  assert np.array_equal(vectors[0],vectors[1]),('local cone mismatch',p['pair_id']);total+=len(pattern);assert vectors[0].any() and (~vectors[0]).any(),'constant pairs excluded'
  tt=np.packbits(vectors[0],bitorder='little');tables[p['pair_id']]=tt;host=p['source_object'].split('__')[0];fkey=ident([host,tokens,tt.tobytes().hex()]);fkeys[p['pair_id']]=fkey
  code='\n'.join(codes)+f'\nmodule check(input [{width-1}:0] env,output mismatch);wire a,b;left_cone l(env,a);right_cone r(env,b);assign mismatch=a^b;endmodule\n';path=root/(p['pair_id']+'.v');path.write_text(code,encoding='utf-8');(root/(p['pair_id']+'.ys')).write_text(f'read_verilog "{path.as_posix()}"\nhierarchy -top check\nproc\nflatten\nopt_clean\nsat -prove mismatch 0 -show-inputs\n',encoding='utf-8')
  record=dict(pair_id=p['pair_id'],split=p['split'],source_object=p['source_object'],shared_inputs=width,enumerated_assignments=len(pattern),unequal_assignments=int((vectors[0]!=vectors[1]).sum()),nonconstant=True,left_cells=len(cc[0]['members']),right_cells=len(cc[1]['members']),physical_graph_members_complete=True,boundary_anchor_sets_equal=set(map(anchor,cc[0]['leaves']))==set(map(anchor,cc[1]['leaves'])),host_function_key=fkey,miter_sha=sha(path),verification='complete Boolean enumeration plus revalidated prior unconditional proof; no new solver execution');out.append(record);complete_proofs.append(dict(**record,semantic_inputs=[list(t) for t in tokens],canonical_env_order='input j maps to token j, low-bit-first enumeration',counterexample=None,executed_ys=False,proof_references=p['proof_ids']))
 # Final proof wrappers: same unrestricted env, no label/reset/extra assumptions.
 queries=read(O/'reused_queries.json')
 for p in queries.values():
  text=(R/p['folder']/'model.v').read_text(encoding='utf-8');wrapper=module(text,'check');assert re.search(r'left_design\s+\w+\(env,a,oa\)',wrapper);assert re.search(r'right_design\s+\w+\(env,b,ob\)',wrapper);assert not re.search(r'\bassume\b|assign\s+env\s*=',wrapper)
 with (O/'cone_enumeration.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
 (O/'cone_proof_certificates.json').write_text(json.dumps(complete_proofs,ensure_ascii=False,indent=2),encoding='utf-8');np.savez_compressed(O/'cone_truth_tables.npz',**tables)
 manifest=[]
 for p in pairs:
  p=dict(p);p['host_function_key']=fkeys[p['pair_id']];p['local_independent_PI_Q_boundary_verified']=True;p['functional_consistency_data_ready']=True;p['current_node_risk_or_whole_embedding_consistency_allowed']=False;p['boundary_feature_head_and_anti_collapse_protocol_defined']=False;manifest.append(p)
 (O/'FUNCTIONAL_PAIR_CONTRACT.json').write_text(json.dumps(dict(training=0,SAT=0,pairs=manifest,train_only=[p['pair_id'] for p in manifest if p['split']=='train'],validation_only=[p['pair_id'] for p in manifest if p['split']=='val'],test_pairs=[],eligibility_uses_labels=False,training_scope='functional-cone/output observation consistency only; current detector-risk head not authorized; no security label transfer',current_training_runs_allowed=False),ensure_ascii=False,indent=2),encoding='utf-8')
 report=dict(training=0,model_forward=0,new_SAT_queries=0,local_enumeration_pairs=len(out),maximum_shared_inputs=max(r['shared_inputs'] for r in out),total_pair_input_assignments=total,all_local_truth_equal=True,all_nonconstant=True,all_interfaces_aligned=True,independent_source_objects=len({r['source_object'] for r in out}),source_objects_by_split={s:len({r['source_object'] for r in out if r['split']==s}) for s in ['train','val','test']},source_cones_by_split=dict(collections.Counter(r['split'] for r in out)),unique_host_functions=len(set(fkeys.values())),host_functions_by_split={s:len({r['host_function_key'] for r in out if r['split']==s}) for s in ['train','val','test']},single_gate_both_sides=sum(r['left_cells']==r['right_cells']==1 for r in out),multi_gate_both_sides=sum(min(r['left_cells'],r['right_cells'])>=2 for r in out),miters_generated_not_executed=True,shared_environment_wrappers_checked=len(queries),no_label_or_trusted_arrays_loaded=True,discovery_caveat='r5/r6 view kinds were selected as strata; target acceptance not based on node labels; not an unbiased population census')
 (O/'CONES_VERIFIED.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
