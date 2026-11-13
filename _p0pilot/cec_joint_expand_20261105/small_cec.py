"""At most three fixed train/val implementation pairs and nine 5s CEC queries."""
from common import *
import time
CASES=[('s35932t200__injalpha_d1_s42__ys_abc','s35932t200__injalpha_d1_s42__ys_aig'),('s38417t100__injepsilon_d1_s42__ys_abc','s38417t100__injepsilon_d1_s42__ys_aig'),('s38417t100__injbeta_d1_s42__ys_abc','s38417t100__injbeta_d1_s42__ys_nand')]
def main():
 if (O/'SMALL_COMPLETE.json').exists():print('Reuse completed bounded CEC ledger');return
 start=time.monotonic();store=Store();existing={p['pair_id'] for p in read(O/'joint_pairs.json')};plans=[];results=[];accepted=[];newcones=[];proofs={};attempts=[]
 # Export only four missing raw snapshots, keeping all previous snapshots intact.
 for va,vb in CASES:
  for view in [va,vb]:
   assert view in store.vm
   available=any((T/d/'structures'/view/'raw.json').exists() for d in ['sat_pair_round10','sat_pair_round11','sat_pair_round12'])
   if available:continue
   folder=O/'structures'/view;folder.mkdir(parents=True,exist_ok=True);src=R/'generate_trans/folds/hosts_bt31/trans'/(view+'.v')
   if not (folder/'raw.json').exists():
    assert not (folder/'prepare.log').exists(),'Prior parse attempt retained; do not silently rerun'
    top=N.P0.module_name(src);script=f'read_verilog "{N.P0.wsl(src)}"\nhierarchy -top {top}\nflatten\nproc -noopt\nwrite_json "{N.P0.wsl(folder/"raw.json")}"\n'
    text=N.P0.run_yosys(script,folder/'prepare.log',timeout=90);assert 'ERROR:' not in text and (folder/'raw.json').exists()
    (folder/'source.json').write_text(json.dumps(dict(view=view,source_sha=sha(src),raw_sha=sha(folder/'raw.json')),indent=2),encoding='utf-8')
   else:
    info=read(folder/'source.json');assert info['source_sha']==sha(src) and info['raw_sha']==sha(folder/'raw.json')
 # Same-name signal aliases propose candidates only. Acceptance still requires CEC.
 total_queries=0
 for ci,(va,vb) in enumerate(CASES):
  if time.monotonic()-start>240:attempts.append(dict(case=ci,status='wall_budget_deferred'));continue
  ma,mb=store.raw(va),store.raw(vb)
  if store.layouts[va]!=store.layouts[vb]:attempts.append(dict(case=ci,status='PI_Q_layout_mismatch'));continue
  ctx=ident(dict(PI=store.layouts[va][0],physicalQ=store.layouts[va][1],free=True));source=store.meta[va]['src_view'];candidates={}
  for net in sorted(set(ma['netnames'])&set(mb['netnames'])):
   aa,bb=ma['netnames'][net]['bits'],mb['netnames'][net]['bits']
   if len(aa)!=1 or len(bb)!=1:continue
   ra,rb=store.root(va,aa[0]),store.root(vb,bb[0])
   if ra is None or rb is None:continue
   ok=True
   for view,rr in [(va,ra),(vb,rb)]:
    ar=store.arrays[store.vm[view][0]]
    if rr[1] not in store.maps[view]:ok=False;break
    i=store.maps[view][rr[1]]
    if not(ar['physical'][i] and ar['trusted'][i] and ar['y'][i]==1):ok=False;break
   if not ok:continue
   pid=ident([source,ctx,sorted([ra[0],rb[0]])])
   if pid in existing or pid in candidates:continue
   av,bv=store.evaluators[va][aa[0]],store.evaluators[vb][bb[0]]
   if av!=bv:
    attempts.append(dict(case=ci,status='candidate_refuted_by_explicit_boolean_witness'));continue
   if av in [0,(1<<128)-1]:continue
   ca,cb=store.getcone(va,aa[0]),store.getcone(vb,bb[0])
   if ca is None or cb is None:continue
   w=len({tuple(l[:3]) for z in [ca,cb] for l in z['leaves']});candidates[pid]=dict(pair_id=pid,net=net,cones=[ca,cb],inputs=w,mask=av)
  # Favor small explicit boundaries then fixed hash. No prediction/test information.
  chosen=sorted(candidates.values(),key=lambda p:(p['inputs'],ident(['small_CEC_gap_v1',p['pair_id']])))[:3]
  plans.append(dict(case=ci,source=source,view_a=va,view_b=vb,eligible_positive_candidates=len(candidates),chosen=[dict(pair_id=p['pair_id'],net=p['net'],inputs=p['inputs']) for p in chosen],selection='same-name locator;both independently trusted positive;matching explicit Boolean samples;smallest boundary then frozen hash;max3'))
  if not chosen:continue
  nets=[p['net'] for p in chosen];nets=(nets+[nets[0]]*5)[:5];a,sa=N.emit(ma,'left_design',nets);b,sb=N.emit(mb,'right_design',nets);assert sa['ports']==sb['ports'] and sa['states']==sb['states']
  code=a+'\n'+b+f"\nmodule check(input [{sa['width']-1}:0] env,output [4:0] delta);wire [4:0] a,b;wire [{len(sa['obs'])-1}:0] oa,ob;left_design l(env,a,oa);right_design r(env,b,ob);assign delta=a^b;endmodule\n"
  qq=[dict(case=ci,kind='gap_positive_native_CEC',pattern=str(j),prove=0,args=f'-prove delta[{j}] 0') for j in range(len(chosen))];assert total_queries+len(qq)<=9;total_queries+=len(qq)
  folder=O/'small_queries'/str(ci);folder.mkdir(parents=True,exist_ok=True)
  if (folder/'run.log').exists():
   assert (folder/'model.v').read_text(encoding='utf-8')==code
   log=(folder/'run.log').read_text(encoding='utf-8');blocks=re.split(r'^Q\d{4}\s*$',log,flags=re.M);rr=[]
   for j,q in enumerate(qq):
    block=blocks[j+1] if len(blocks)>j+1 else '';status='error' if 'ERROR:' in log else 'proved' if 'no model found: SUCCESS' in block else 'refuted' if 'model found: FAIL' in block else 'unknown'
    rr.append(dict(**q,status=status,timeout='TIMEOUT' in block,query_id=j,folder=str(folder.relative_to(R)),model_sha=sha(folder/'model.v'),script_sha=hashlib.sha256((folder/'run.ys').read_text(encoding='utf-8').encode()).hexdigest(),log_sha=sha(folder/'run.log'),reused_existing_log=True))
  else:rr=N.run(folder,code,qq)
  results.extend(rr);(folder/'query_records.json').write_text(json.dumps(rr,ensure_ascii=False,indent=2),encoding='utf-8')
  for p,q in zip(chosen,rr):
   if q['status']!='proved':continue
   exact=store.check_query(q);assert exact==code;pid=ident([q['model_sha'],q['args']]);proofs[pid]={k:q[k] for k in ['folder','query_id','args','model_sha','script_sha','log_sha']};ca,cb=p['cones'];ends=[store.endpoint(z) for z in [ca,cb]]
   accepted.append(dict(pair_id=p['pair_id'],source_object=source,split=ca['split'],context_id=ctx,left_cone=ca['cone_id'],right_cone=cb['cone_id'],proof_ids=[pid],origins=['label_assisted_small_gap_CEC'],observations=[f"exact_probe:{q['pattern']}"],root_endpoints=ends,labels_used_for_selection=True,labels_used_for_function_acceptance=False,functional_auxiliary_data_eligible=True,current_detection_training_allowed=False,detection_stability_diagnostic_eligible=True,enum=dict(method='new_bounded_native_CEC_with_nonconstant_witness',inputs=p['inputs'],equal=None)))
   for z in [ca,cb]:newcones.append(z)
   existing.add(p['pair_id'])
  print('Bounded case',ci,'selected',len(chosen),'statuses',[q['status'] for q in rr],flush=True)
 write('small_plan.json',plans);write('small_pairs.json',accepted);write('small_cones.json',newcones);write('small_proofs.json',proofs);table('small_queries.csv',results);table('small_candidate_attempts.csv',attempts)
 write('SMALL_COMPLETE.json',dict(training=0,model_forward=0,new_SAT_queries=total_queries,max_queries=9,per_query_timeout_s=5,selected_cases=len(CASES),accepted=len(accepted),accepted_by_split=dict(collections.Counter(p['split'] for p in accepted)),statuses=dict(collections.Counter(q['status'] for q in results)),new_raw_parses=4,elapsed_s=time.monotonic()-start,test_used=False,inputs=store.inputs))
 print(read(O/'SMALL_COMPLETE.json')|{'inputs':'hashes saved'},flush=True)
if __name__=='__main__':main()
