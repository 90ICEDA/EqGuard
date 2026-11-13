"""All existing whole-proof observations plus exact review provenance recovery."""
from common import *
def main():
 assert not (O/'JOINT_COMPLETE.json').exists();store=Store();old=read(PRE/'pool_pairs.json');pairs={p['pair_id']:p for p in old};cones={c['cone_id']:c for c in read(PRE/'pool_cones.json')};proofs=read(PRE/'reused_proofs.json');projections=[];reject=[];witness=[];whole=[];reviews=[]
 def admit(va,vb,ba,bb,pid,index,origin):
  ra,rb=store.root(va,ba),store.root(vb,bb)
  if ra is None or rb is None:reject.append(dict(proof_id=pid,index=index,reason='PI_Q_or_constant_anchor'));return
  assert store.layouts[va]==store.layouts[vb];ctx=ident(dict(PI=store.layouts[va][0],physicalQ=store.layouts[va][1],free=True));source=store.meta[va]['src_view'];assert source==store.meta[vb]['src_view'] and store.vm[va][0]==store.vm[vb][0]
  pairid=ident([source,ctx,sorted([ra[0],rb[0]])]);projections.append(dict(pair_id=pairid,proof_id=pid,index=index,view_a=va,view_b=vb,root_a=ba,root_b=bb))
  if pairid in pairs:return
  av,bv=store.evaluators[va][ba],store.evaluators[vb][bb];assert av==bv,('proof/simulator contradiction',pairid)
  if av in [0,(1<<128)-1]:reject.append(dict(proof_id=pid,index=index,reason='nonconstancy_not_demonstrated_128_patterns'));return
  aa,bb=store.getcone(va,ba),store.getcone(vb,bb)
  if aa is None or bb is None:reject.append(dict(proof_id=pid,index=index,reason='invalid_or_unmapped_nontrivial_cone'));return
  ends=[store.endpoint(z) for z in [aa,bb]];split=aa['split'];p=dict(pair_id=pairid,source_object=source,split=split,context_id=ctx,left_cone=aa['cone_id'],right_cone=bb['cone_id'],proof_ids=[pid],origins=[origin],observations=[f'exact_proved_index:{index}'],root_endpoints=ends,labels_used_for_selection=False,labels_used_for_function_acceptance=False,functional_auxiliary_data_eligible=True,current_detection_training_allowed=False,detection_stability_diagnostic_eligible=all(e['trusted'] and e['physical'] for e in ends) and ends[0]['label']==ends[1]['label'],enum=dict(method='existing_source_bound_proof_and_explicit_nonconstant_witness',inputs=len({tuple(l[:3]) for z in [aa,bb] for l in z['leaves']}),equal=None))
  pairs[pairid]=p
  for z in [aa,bb]:cones[z['cone_id']]=z
  bit0=((1<<128)-1)^av;witness.append(dict(pair_id=pairid,context_id=ctx,pattern_for1=(av&-av).bit_length()-1,pattern_for0=(bit0&-bit0).bit_length()-1,source_bound_equivalence_proof=pid,scope='two explicit witnesses prove nonconstancy;128-pattern equality is not the equivalence proof'))
 # Rebind full modules and exact joint proof, then expand every observation bit.
 for g in rows(R/'_p0pilot/cec_cone_expand_20261105/whole_proof_observation_sources.csv'):
  va,vb=g['view_a'],g['view_b'];pid=g['proof_id'];q=proofs[pid];code=store.check_query(q);check=module(code,'check');terms=[]
  if q['args']=='-prove observation_diff 0':
   assert 'assign observation_diff=|(oa^ob);' in check and 'left_design l(env,a,oa)' in check and 'right_design r(env,b,ob)' in check;mods=['left_design','right_design']
   for view,mn in zip([va,vb],mods):store.bind_native(view,module(code,mn),mn)
  else:
   assert q['args']=='-prove po_d_diff 0' and 'assign po_d_diff=|(oa^ob)' in check and "left(env,1'b0,1'b0,a,oa)" in check and "right(env,1'b0,1'b0,b,ob)" in check;mods=['design_ys_id','design_ys_abc']
   sys.path.insert(0,str(R/'_p0pilot/round8_20261025'));import case_chain as C8
   prefix='TrojanA' if '__injalpha_' in va else 'TrojanE'
   for view,mn in zip([va,vb],mods):assert C8.emit(store.raw(view),mn,prefix)[0]==module(code,mn)
  for mn in mods:terms.append([s.strip() for s in re.search(r'assign obs\s*=\s*\{(.*?)\};',module(code,mn)).group(1).split(',')][::-1])
  assert len(terms[0])==len(terms[1])==int(g['observations_proved'])
  before=len(pairs)
  for j,(a,b) in enumerate(zip(*terms)):
   if re.fullmatch(r'b\d+',a) and re.fullmatch(r'b\d+',b):admit(va,vb,int(a[1:]),int(b[1:]),pid,j,'all_existing_PO_D_observations_no_label_filter')
  whole.append(dict(view_a=va,view_b=vb,proof_id=pid,positions=len(terms[0]),new_pairs=len(pairs)-before));print('Whole',va,len(terms[0]),'new',len(pairs)-before,flush=True)
 # Review numbering is NOT pair numbering. Resolve by model+args to original query.
 qq=rows(T/'sat_pair_round11/queries_batch3.csv');excluded=[q for q in qq if q['status']=='proved' and ('reviews_batch2' in q['folder'] or 'reviews_batch3' in q['folder'])]
 for q in excluded:
  originals=[x for x in qq if 'reviews' not in x['folder'] and x['model_sha']==q['model_sha'] and x['args']==q['args'] and x['status']=='proved'];assert len(originals)==1;original=originals[0]
  phase=3 if 'pairs_batch3' in original['folder'] else 2 if 'pairs_batch2' in original['folder'] else 1;planpath=T/'sat_pair_round11'/('plan.json' if phase==1 else f'plan_batch{phase}.json');plan=read(planpath);item=plan['selected'][int(original['pair_index'])];va,vb=item['source_view'],item['partner'];assert int(q['pair_index'])==int(original['pair_index'])
  store.inputs[str(planpath.relative_to(R))]=sha(planpath);code=store.check_query(q);originalcode=store.check_query(original);assert code==originalcode
  terms=[]
  for view,mn in [(va,'left_design'),(vb,'right_design')]:store.bind_native(view,module(code,mn),mn);terms.append([s.strip() for s in re.search(r'assign sigs=\{(.*?)\};',module(code,mn)).group(1).split(',')][::-1])
  check=module(code,'check');assert 'assign delta=a^b;' in check and 'left_design l(env,a,oa)' in check and 'right_design r(env,b,ob)' in check;j=int(re.fullmatch(r'-prove delta\[(\d+)\] 0',q['args']).group(1));aa,bb=terms[0][j],terms[1][j];assert re.fullmatch(r'b\d+',aa) and re.fullmatch(r'b\d+',bb)
  pid=ident([q['model_sha'],q['args']]);proofs.setdefault(pid,{k:original[k] for k in ['folder','query_id','args','model_sha','script_sha','log_sha']});before=len(pairs);admit(va,vb,int(aa[1:]),int(bb[1:]),pid,j,'recovered_review_exact_original_model')
  reviews.append(dict(review_folder=q['folder'],review_query=q['query_id'],original_folder=original['folder'],original_query=original['query_id'],batch=phase,pair_index=original['pair_index'],view_a=va,view_b=vb,bit_a=int(aa[1:]),bit_b=int(bb[1:]),same_model_sha=q['model_sha'],args=q['args'],recovery='exact duplicate proof; reviews directory index is review ordinal',new_pairs=len(pairs)-before))
 assert len(reviews)==18
 write('joint_pairs.json',list(pairs.values()));write('joint_cones.json',list(cones.values()));write('proofs.json',proofs);write('witness_contexts.json',store.contexts);write('nonconstant_witnesses.json',witness);table('whole_expansion.csv',whole);table('review_recovery.csv',reviews);table('proof_projection.csv',projections);table('rejections.csv',reject)
 write('JOINT_COMPLETE.json',dict(training=0,model_forward=0,new_SAT_queries=0,pairs=len(pairs),new_pairs=len(pairs)-len(old),new_by_split=dict(collections.Counter(p['split'] for p in pairs.values() if p['pair_id'] not in {z['pair_id'] for z in old})),reviews_recovered=len(reviews),reviews_new_pairs=sum(x['new_pairs'] for x in reviews),all_PO_D_positions=sum(x['positions'] for x in whole),raw_models=len(store.raws),rejections=dict(collections.Counter(x['reason'] for x in reject)),inputs=store.inputs))
 print(read(O/'JOINT_COMPLETE.json')|{'inputs':'hashes saved'},flush=True)
if __name__=='__main__':main()
