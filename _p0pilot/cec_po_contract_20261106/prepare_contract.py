"""Prepare a not-authorized-to-train model contract and exact equal-budget indices."""
from pathlib import Path
import collections,csv,hashlib,importlib.util,itertools,json,math
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;V=R/'_p0pilot/cec_hard_validation_20261106'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def ident(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def write(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def table(n,rr):
 if not rr:return
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def load(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def main():
 assert read(O/'AUDIT_COMPLETE.json')['passed'] and not (O/'PUBLISHED.json').exists()
 rules=dict(version='freeQ_newmodel_contract_v1',selection='before any cache metric reads;dedup same context+observed128 signature set across manufactured sources,then maximum disjoint function-signature triples per context;fixedhash ties;no extra pairs',family='shared nativePIQ query context is an exposure family,not an independent source;conservative observedsignature merge is NOT a new equality proof',budget='32 updates,one unit per each retained context family/update,per-unit and function-family <=16;exact same schedule in Z/R/P',strict_evaluation='T3_PO_exact units,2 candidates;no fabricated third function;source-macro then source details;too small for confirmatory gate',wider_evaluation='T2_PO_exact and original105 reported separately;not substitute for strict panel',training_authorized=False)
 write('MODEL_DESIGN_RULES.json',rules)
 units=read(O/'T2_PO_exact_units.json');candidates=[u for u in units if u['split']=='train' and u['functions']==3]
 groups=collections.defaultdict(list)
 for u in candidates:groups[(u['context_id'],tuple(sorted(u['function_signatures'])))].append(u)
 representatives=[];aliases=[]
 for key,uu in sorted(groups.items()):
  representative=min(uu,key=lambda u:ident(['representative_view_evidence',u['unit_id']]))
  representatives.append(representative)
  aliases.append(dict(context_id=key[0],signature_set=list(key[1]),representative=representative['unit_id'],members=[u['unit_id'] for u in uu],sources=sorted({u['source'] for u in uu}),aliases_are_new_proofs=False))
 byctx=collections.defaultdict(list)
 for u in representatives:byctx[u['context_id']].append(u)
 training=[];packing=[]
 for ctx,uu in sorted(byctx.items()):
  uu=sorted(uu,key=lambda u:ident(['packing_order',u['unit_id']]));best=[];bestkey=None
  def search(j,selected,seen):
   nonlocal best,bestkey
   if len(selected)+len(uu)-j<len(best):return
   if j==len(uu):
    key=ident(sorted(u['unit_id'] for u in selected))
    if len(selected)>len(best) or (len(selected)==len(best) and (bestkey is None or key<bestkey)):best=selected[:];bestkey=key
    return
   fs=set(uu[j]['function_signatures'])
   if not fs&seen:search(j+1,selected+[uu[j]],seen|fs)
   search(j+1,selected,seen)
  search(0,[],set());training+=best;packing.append(dict(context_id=ctx,representative_triples=len(uu),retained_disjoint_triples=len(best),manufactured_sources=sorted({u['source'] for u in best}),observed_function_classes=3*len(best)))
 training=sorted(training,key=lambda u:u['unit_id']);assert len({(u['context_id'],s) for u in training for s in u['function_signatures']})==3*len(training)
 write('TRAINING_POOL.json',training);write('ALIAS_FAMILIES.json',aliases);write('PACKING.json',packing)
 # New negative edges reuse only existing128 masks; replay an already stored input bit.
 L=load('frozen_semantic_loader',R/'_p0pilot/cec_hard_boundary_20261106/local_interface.py')
 local=read(V/'local_graphs.json');graphs=dict(zip(local['cone_ids'],local['graphs']));keys=dict(zip(local['cone_ids'],local['contexts']))
 maps={m['context_key']:m['tokens'] for m in read(R/'_p0pilot/cec_interface_minimal_20261105/boundary_maps_audit_only.json')};ctx=read(R/'_p0pilot/cec_pretrain_ready_20261105/witness_contexts.json');ctx.update(read(R/'_p0pilot/cec_cert_expand_20261105/validation_witness_contexts.json'))
 # Certificate all reassembled panels,not just the train subset; input assignments are never features.
 certificate=[]
 for mode in ['T2_PO_exact','T3_PO_exact']:
  for u in read(O/(mode+'_units.json')):
   env={tuple(z['token']):int(z['mask_hex'],16) for z in ctx[u['context_id']]['input_masks']}
   for a,b in itertools.combinations(range(u['functions']),2):
    diff=int(u['function_signatures'][a],16)^int(u['function_signatures'][b],16);assert diff;pattern=(diff&-diff).bit_length()-1;out=[]
    for index in [2*a,2*a+1,2*b,2*b+1]:
     cid=u['cones'][index];tokens=maps[keys[cid]];values={t['slot']:(env[t['kind'],t['audit_name'],t['bit']]>>pattern)&1 for t in tokens};out.append(L.replay(graphs[cid],values))
    assert out[0]==out[1] and out[2]==out[3] and out[0]!=out[2]
    certificate.append(dict(certificate_id=ident([mode,u['unit_id'],a,b]),panel=mode,unit_id=u['unit_id'],split=u['split'],source=u['source'],context_id=u['context_id'],pair_ids=[u['pair_ids'][a],u['pair_ids'][b]],pattern=pattern,outputs=out,origin='saved128_input_replay_after_reassembly',new_input_patterns=0,SAT=0))
 write('REASSEMBLED_NEGATIVE_CERTIFICATES.json',certificate)
 # Fixed family-balanced schedule. All association groups receive exactly identical endpoints.
 active=collections.defaultdict(list)
 for u in training:active[u['context_id']].append(u)
 schedule=[];unit_count=collections.Counter();function_count=collections.Counter();node_count=collections.Counter();boundary_count=collections.Counter();source_count=collections.Counter()
 for update in range(1,33):
  selected=[]
  for key,pool in sorted(active.items()):
   pool=sorted(pool,key=lambda u:ident(['schedule_roundrobin',u['unit_id']]));u=pool[(update-1)%len(pool)];selected.append(u)
   unit_count[u['unit_id']]+=1;source_count[u['source']]+=1
   for sig in u['function_signatures']:function_count[key,sig]+=1
   for cid in u['cones']:
    g=graphs[cid]
    for name in g['comb_names']:node_count[key,read_source_view(cid,u),name]+=1
    for slot in g['slot']:
     if slot>=0:boundary_count[key,slot]+=1
  # R/P candidate target assignments are inverse across directions; both are bijections.
  loaded=[]
  for u in selected:
   shift=1+int(ident(['permutation_orientation',u['unit_id']]),16)%2
   anchors=[];cand=[];real=[];perm=[]
   for fun in range(3):
    for side in [0,1]:
     anchors.append(u['cones'][2*fun+side]);cand.append([u['cones'][2*j+1-side] for j in range(3)]);real.append(fun);perm.append((fun+shift)%3 if side==0 else (fun-shift)%3)
   negatives=[(u['cones'][2*a+side],u['cones'][2*b+side]) for side in [0,1] for a,b in itertools.combinations(range(3),2)]
   real_edges={tuple(sorted([a,c[t]])) for a,c,t in zip(anchors,cand,real)};perm_edges={tuple(sorted([a,c[t]])) for a,c,t in zip(anchors,cand,perm)};neg={tuple(sorted(e)) for e in negatives}
   assert len(real_edges)==len(perm_edges)==3 and not real_edges&neg and not perm_edges&neg
   loaded.append(dict(unit_id=u['unit_id'],source=u['source'],context_id=u['context_id'],cone_ids=u['cones'],anchors=anchors,candidates=cand,real_targets=real,permuted_targets=perm,common_negative_edges=negatives,unit_weight=1/len(selected),query_weight=1/(6*len(selected)),negative_weight=1/(6*len(selected)),boundary_tag=update))
  schedule.append(dict(update=update,units=loaded))
 assert max(unit_count.values())<=16 and max(function_count.values())<=16
 write('SCHEDULE_SEED42.json',schedule)
 budget=dict(updates_each=32,groups=['Z','R','P'],active_context_families=len(active),unique_training_triples=len(training),unique_observed_function_classes=3*len(training),unique_equal_pairs=3*len(training),unique_cone_endpoints=6*len(training),unit_slots=sum(len(s['units']) for s in schedule),equal_pair_slots=3*sum(len(s['units']) for s in schedule),anchor_query_slots=6*sum(len(s['units']) for s in schedule),candidate_distance_slots=18*sum(len(s['units']) for s in schedule),common_negative_terms=6*sum(len(s['units']) for s in schedule),endpoint_readout_slots=6*sum(len(s['units']) for s in schedule),max_unit_exposure=max(unit_count.values()),max_function_family_exposure=max(function_count.values()),max_comb_gate_occurrence_exposure=max(node_count.values()),max_boundary_token_occurrence_exposure=max(boundary_count.values()),exposure_by_manufactured_source=dict(source_count),exposure_by_family={k:32 for k in active},scope='physical gate occurrences include overlapping cones;Q token occurrences counted separately,not independent functions;same in allarms')
 write('SUPERVISION_BUDGET.json',budget)
 table('UNIT_EXPOSURE.csv',[dict(unit_id=u['unit_id'],source=u['source'],context_id=u['context_id'],exposures=unit_count[u['unit_id']]) for u in training])
 # Evaluate frozen historical caches only AFTER indices/sampling have been fixed.
 F=load('independent_cpu_metrics',V/'verify_and_controls.py');metrics=[];source_metrics=[]
 panels={'within_original_exact':read(O/'within_original_exact_subsets.json'),'T2_PO_exact':read(O/'T2_PO_exact_units.json'),'T3_PO_exact':read(O/'T3_PO_exact_units.json')}
 for us in panels.values():
  for u in us:
   if 'unit_id' not in u:u['unit_id']=u['subset_id']
 for panel,us in panels.items():
  for split in ['train','val']:
   uu=[u for u in us if u['split']==split]
   if not uu:continue
   for arm in ['INIT','Z','A_R','A_P','S_R','S_P']:
    z=np.load(V/f'{split}_{arm}.npz');ids=z['cone_ids'].tolist();x=z['concat128'][:,:64]
    metrics.append(dict(panel=panel,split=split,arm=arm,units=len(uu),sources=len({u['source'] for u in uu}),**F.direct_metrics(uu,ids,x)))
    for source in sorted({u['source'] for u in uu}):
     ss=[u for u in uu if u['source']==source];source_metrics.append(dict(panel=panel,split=split,arm=arm,source=source,units=len(ss),**F.direct_metrics(ss,ids,x)))
 table('CACHED_MODEL_METRICS.csv',metrics);table('CACHED_MODEL_BY_SOURCE.csv',source_metrics)
 # Verify both PO-only and boundary-bag controls are ties on the strict panel.
 entries={e['pair_id']:e for e in read(O/'pair_inventory.json')};controls=[]
 for split in ['train','val']:
  ss=[u for u in panels['T3_PO_exact'] if u['split']==split];ids=sorted({c for u in ss for c in u['cones']});coords={c:entries[p]['po'][j] for u in ss for p in u['pair_ids'] for j,c in enumerate(entries[p]['cones'])}
  m=F.direct_metrics(ss,ids,np.array([[coords[c]] for c in ids],float));assert m['pairwise_win']==.5 and abs(m['function_auc']-.5)<1e-12
  controls.append(dict(split=split,control='raw_PO_column30',units=len(ss),**m))
 table('STRICT_PO_BASELINE.csv',controls)
 contract=dict(status='DESIGN_AND_OFFLINE_INDEX_CHECKED_NOT_TRAINED',authorization='current user requested contract only;no automatic training queue',purpose='new boundary-restricted encoder: true function association vs bijective wrong association under identical architecture/input/compute;NOT causal comparison to old39 model',data=dict(train='TRAINING_POOL.json (T2 exactPO,disjoint observedsignature triples)',primary_val='T3_PO_exact_units.json splitval:4twofunctionunits,2sources,1host;no3candidateval',secondary_val=['T2 exactPO 7twofunction units','original105 val32triple units,POunmatched'],test='none',strict_train='4twofunction units diagnostic only;not silently treated as3candidate training',source_caution='training source aliases grouped by nativecontext;128same signatures conservative duplicate suppression,not new equivalence proofs'),model=dict(name='freeQ_typed_topological_GRU64_v1',input='validated25d:9op/kind onehot+16neutral boundary codes;edge5roles andphase;no39feature projection',forbidden=['POdistance or reachability','globalgateposition or graphrow','host/source/context identifier as feature','Qupstream_Dlogic','safetylabels','truth tables,witnessinputs or signaturebits as features'],parameters_expected=47360,base='Linear25to64 bias=True then ReLU',messages='five independent Linear64to64 bias=False role maps;message=(1-2phase)*Wrole*hsrc+learned_phase_embedding[phase];sum/sqrt(number_of_input_pins)',comb_update='shared GRUCell64to64(input=aggregate,hidden=base);shared LayerNorm64;one update percombnode in increasing topologicallevel',leaf_update='LayerNorm(ReLU(Linear25to64(x)))',phase_embeddings='2x64 learned,zero initialized',readout='root64 trained and primary;membermean64 andconcat128 diagnostic only;no projectionhead/classifier',dropout=0.,normalization='LayerNorm only,noBN;no fixeddepth truncation;allcone nodes consumed',expected_parameter_breakdown=dict(input_linear=1664,role_maps=20480,phase_embedding=128,GRUCell=24960,LayerNorm=128)),objectives=dict(R='weighted CE(-RMS(rootanchor,threecandidates),real target)',P='same CE,bijective cyclic wrong targets;reverse direction MUST inverse shift',Z='compute both CE terms but association coefficient0',common='all three within-view function pairs per side,hinge squared max(0,1-RMS)^2;NOT old crossview thirdfunction terms',variance='.1*mean(max(0,.5-sqrt(populationvar(root64)+1e-4)));same actual endpoints',weights='association1 commonnegative1 variance0.1;eachquery andnegative term 1/(6families)',numerics='FP32 distances with sqrt(mean squared+1e-12);shared AMP policy across arms;log raw unregularized distances and class probabilities'),execution=dict(seed=42,updates=32,optimizer='Adam lr0.0002 weight_decay0.001 clip_global_norm1',init='one common full state saved and SHA matched;fresh encoder required;old39 weights not loaded',all_groups_same='SCHEDULE_SEED42,graphs,fullcontext codes at tag=update,roles,states,lossweights,updates',selection='fixed last32,no best-val checkpoint;initial and final evaluation only',validation_tags=[9000,9001],primary_tag=9000,wider_seeds='not authorized'),acceptance=dict(implementation='loading and no-update gradient preflight required before any train;not performed by this contract task',noncollapse='finite nonzero gradients,nonzero root variance,rank/PCenergy reported;withintraining real/wrong ordering checked,not just loss',performance='report paired R-P andR-Z per-source and source-macro;primary panel only4units so exploratory,NO significance claim or robust transfer acceptance;PO/boundarybag controls musttie',causal_scope='allthreegroups newencoder;no singlefactor attribution relative to old39/fullgraph/50step experiments',reporting='family and source exposures,unmatched portions,2candidate main and3candidate secondary separate;no safetyAP or Trojanrecall claims'))
 contract['execution']['device']='ginvenv_gpu CUDA;FP32 encoder/loss and validation,no autocast in any arm'
 contract['objectives']['numerics']='FP32 distances sqrt(mean squared+1e-12),CE on negative distances;log raw distances and probabilities;all three groups identical'
 contract['acceptance']['boundary_control']='unsigned unique PI/Q identity-set bag musttie;phase/roles are functional information and are not forced to tie'
 contract['data']['strict_train_observed_classes']=6
 contract['data']['strict_val_observed_classes']=8
 assert sum(contract['model']['expected_parameter_breakdown'].values())==contract['model']['parameters_expected']
 write('FAIR_MODEL_CONTRACT.json',contract)
 write('CONTRACT_READY.json',dict(prepared=True,training_authorized=False,model_instantiated=False,gradient_preflight_done=False,training=0,SAT=0,new_model_forwards=0,reassembled_negative_witnesses=len(certificate),training_triples_before_alias_dedup=len(candidates),after_exacttriple_alias_dedup=len(representatives),after_function_disjoint_packing=len(training),budget=budget,strict_validation_units=4))
 print(json.dumps(dict(packing=packing,budget=budget),ensure_ascii=False),flush=True)
def read_source_view(cid,u):return u['view_direction'][u['cones'].index(cid)%2]
if __name__=='__main__':main()
