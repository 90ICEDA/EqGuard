"""Reuse source-bound whole PO/D and point proofs. Bounded cones, zero solvers/models."""
from pathlib import Path
import sys,json,csv,re,collections,hashlib
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;OLD=R/'_p0pilot/cec_cone_audit_20261105';T=R/'10.15/06_统一评测协议/N4_三向泛化/tables';F=R/'generate_trans/folds/hosts_bt31'
sys.path.insert(0,str(OLD));from audit import read,rows,sha,ident,cone,module,SCHEMA
sys.path.insert(0,str(R/'_p0pilot/round10_20261025'));import native as N
sys.path.insert(0,str(R/'_p0pilot/round8_20261025'));import case_chain as C8
def forbidden(*a,**k):raise RuntimeError('No solver/subprocess execution authorized')
N.P0.run_yosys=forbidden;C8.P0.run_yosys=forbidden
import subprocess
subprocess.run=forbidden;subprocess.Popen=forbidden
def dump(n,a):
 if not a:return
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(a[0]));w.writeheader();w.writerows(a)
def enumerate_pair(mods,cc,maxinputs=12):
 tokens=sorted({tuple(l[:3]) for c in cc for l in c['leaves']});w=len(tokens)
 if w>maxinputs:return dict(method='not_enumerated_width_cap',inputs=w,patterns=0,equal=None)
 pattern=np.arange(1<<w,dtype=np.uint16);env={t:((pattern>>j)&1).astype(bool) for j,t in enumerate(tokens)};vv=[]
 for m,c in zip(mods,cc):
  values={};drivers={}
  for n,p in m['ports'].items():
   if p['direction']=='input':
    for j,b in enumerate(p['bits']):
     if ('PI',n,j) in env:values[b]=env['PI',n,j]
  for n,g in m['cells'].items():
   if ('Q',n,0) in env:
    for pin in ['Q','QN']:
     for b in g['connections'].get(pin,[]):values[b]=~env['Q',n,0] if pin=='QN' else env['Q',n,0]
   if n in c['members']:drivers[g['connections'][SCHEMA[g['type']][0]][0]]=g
  def ev(b):
   if not isinstance(b,int):assert b in ['0','1'];return np.full(len(pattern),b=='1',bool)
   if b in values:return values[b]
   g=drivers[b];typ=g['type'];v=[ev(g['connections'][p][0]) for p in SCHEMA[typ][1]]
   if typ in ['AND2X2','$and']:o=v[0]&v[1]
   elif typ in ['OR2X1','$or']:o=v[0]|v[1]
   elif typ in ['XOR2X1','$xor']:o=v[0]^v[1]
   elif typ in ['INVX0','$not']:o=~v[0]
   else:o=np.where(v[2],v[1],v[0])
   values[b]=o;return o
  vv.append(ev(c['root_bit']))
 return dict(method='complete_two_valued_enumeration',inputs=w,patterns=len(pattern),equal=bool(np.array_equal(*vv)),nonconstant=bool(vv[0].any() and (~vv[0]).any()),truth_sha=hashlib.sha256(np.packbits(vv[0],bitorder='little').tobytes()).hexdigest())
def main():
 O.mkdir(exist_ok=True);assert not (O/'EXPANDED.json').exists();c=read(R/'_p0pilot/control_boundary_v3_20261104/input_contract.json');viewmap={v['view']:(key,v) for key,q in c['shared_inputs'].items() if key.startswith('trans_') for v in q['views']};meta={v['view']:v for v in rows(F/'views_meta.csv')};names=[n.strip().lstrip('\\') for n in (F/'data/processed/node_names_trans.txt').read_text(encoding='utf-8').splitlines()];raws={};binding={};cellmaps={};inputs={};oldproofs={};candidates=[];accepted={};cones={};reject=[];proofaudit=[];attempts=[];globalplans=[]
 def raw(view):
  if view not in raws:
   found=[]
   for dirname in ['sat_pair_round10','sat_pair_round11','sat_cases_round8']:
    path=T/dirname/('structures/'+view if dirname!='sat_cases_round8' else view)
    if (path/'raw.json').exists():
     src=F/'trans'/(view+'.v');hh=sha(src)
     if (path/'source.json').exists():info=read(path/'source.json');assert info['source_sha']==hh and info['raw_sha']==sha(path/'raw.json')
     else:
      matched=[r for r in rows(T/'sat_cases_round8/sources.csv') if r['view']==view]
      if not matched:continue
      info=matched[0];assert info['source_sha']==hh and info['raw_sha']==sha(path/'raw.json')
     found.append((path,info))
   assert found,view;path,info=found[0];m=next(iter(read(path/'raw.json')['modules'].values()));raws[view]=m;binding[view]=dict(source_sha=sha(F/'trans'/(view+'.v')),raw_sha=sha(path/'raw.json'),raw_path=str((path/'raw.json').relative_to(R)));key,v=viewmap[view];cellmaps[view]={n:v['start']+j for j,n in enumerate(names[v['old_start']:v['old_stop']])};inputs[str((path/'raw.json').relative_to(R))]=sha(path/'raw.json');inputs[str((F/'trans'/(view+'.v')).relative_to(R))]=binding[view]['source_sha']
  return raws[view]
 def checkproof(q,label='Q'):
  folder=R/q['folder'];model=(folder/'model.v').read_text(encoding='utf-8');script=(folder/'run.ys').read_text(encoding='utf-8');log=(folder/'run.log').read_text(encoding='utf-8');assert sha(folder/'model.v')==q['model_sha'] and sha(folder/'run.log')==q['log_sha'];assert hashlib.sha256(script.encode()).hexdigest()==q['script_sha'];assert q['status']=='proved' and 'ERROR:' not in log;lines=[s for s in script.splitlines() if s.startswith('sat ')];qid=int(q['query_id']);assert lines[qid].startswith('sat '+q['args']+' -timeout ');blocks=re.split('^'+label+r'\d{4}\s*$',log,flags=re.M);assert 'no model found: SUCCESS' in blocks[qid+1] and 'TIMEOUT' not in blocks[qid+1];pid=ident([q['model_sha'],q['args']]);oldproofs[pid]=dict(folder=q['folder'],query_id=qid,args=q['args'],model_sha=q['model_sha'],script_sha=q['script_sha'],log_sha=q['log_sha']);inputs.update({str((folder/n).relative_to(R)):sha(folder/n) for n in ['model.v','run.ys','run.log']});return model,pid
 def makecone(view,bit):
  m=raw(view);z=cone(m,bit,cellmaps[view],binding[view]['raw_sha']);rootdriver=[]
  for name in z['members']:
   cell=m['cells'][name];pin=SCHEMA[cell['type']][0]
   if cell['connections'][pin]==[bit]:rootdriver.append((name,pin))
  if len(rootdriver)==1:
   name,pin=rootdriver[0];z.update(cone_id=ident([binding[view]['source_sha'],name,pin]),output_cell=name,output_pin=pin,root_row=cellmaps[view].get(name,-1))
  z.update(view=view,source_sha=binding[view]['source_sha'],raw_path=binding[view]['raw_path'],split=viewmap[view][0].split('_')[1]);return z
 def consider(va,vb,ba,bb,origin,proofid,observation,prior=False):
  assert meta[va]['src_view']==meta[vb]['src_view'];assert viewmap[va][0]==viewmap[vb][0] and not viewmap[va][0].endswith('test');cc=[makecone(va,ba),makecone(vb,bb)];why=[]
  if any(z['errors'] for z in cc):why.append('invalid_boundary')
  if any(not z['nontrivial'] for z in cc):why.append('PI_or_state_anchor')
  if any(z['unmapped_members'] for z in cc):why.append('unmapped_graph_members')
  if why:reject.append(dict(origin=origin,source=meta[va]['src_view'],view_a=va,view_b=vb,observation=observation,reason=';'.join(why)));return
  enum=enumerate_pair([raw(va),raw(vb)],cc)
  if enum['equal'] is False:
   reject.append(dict(origin=origin,source=meta[va]['src_view'],view_a=va,view_b=vb,observation=observation,reason='native_PI_Q_enumeration_refutes_candidate'));return
  if proofid is None and enum['equal'] is not True:
   reject.append(dict(origin=origin,source=meta[va]['src_view'],view_a=va,view_b=vb,observation=observation,reason='width_over12_and_no_current_source_bound_proof'));return
  context=ident(dict(PI=N.layout(raw(va))[0],physicalQ=N.layout(raw(va))[1],free=True));assert N.layout(raw(va))==N.layout(raw(vb));source=meta[va]['src_view'];pairid=ident([source,context,sorted(z['cone_id'] for z in cc)]);fresh=pairid not in accepted
  if fresh:accepted[pairid]=dict(pair_id=pairid,source_object=source,split=cc[0]['split'],context_id=context,left_cone=cc[0]['cone_id'],right_cone=cc[1]['cone_id'],origins=[],proof_ids=[],observations=[],enum=enum,prior_existing=prior,functional_auxiliary_data_eligible=True,current_detection_training_allowed=False)
  p=accepted[pairid];p['origins']=sorted(set(p['origins']+[origin]));p['observations']=sorted(set(p['observations']+[observation]));p['prior_existing']|=prior
  if proofid:p['proof_ids']=sorted(set(p['proof_ids']+[proofid]))
  for z in cc:cones[z['cone_id']]=z
  attempts.append(dict(pair_id=pairid,origin=origin,source=source,split=cc[0]['split'],observation=observation,new_unique_pair=fresh,proof_method='existing_bound_proof_entailment' if proofid else 'bounded_complete_enumeration',enum_width=enum['inputs'],enum_patterns=enum['patterns']))
 # Prior14 are carried forward, with source/pin-based canonical identities.
 oldcones={z['cone_id']:z for z in read(OLD/'cones.json')};oldqueries=read(OLD/'reused_queries.json');priorrefs={(r['folder'],int(r['query_id'])):r for r in rows(R/'_p0pilot/round34_20261029/proof_bindings.csv')}
 for p in read(OLD/'FUNCTIONAL_PAIR_CONTRACT.json')['pairs']:
  ca,cb=oldcones[p['left_cone']],oldcones[p['right_cone']];q=oldqueries[p['proof_ids'][0]];q['script_sha']=priorrefs[q['folder'],int(q['query_id'])]['script_sha'];q['status']='proved';_,pid=checkproof(q);origin='blind_r7' if all(r['relation_id'].startswith('r7|') for r in p['references']) else 'blind_root_in_stratified_view';consider(ca['view'],cb['view'],ca['root_bit'],cb['root_bit'],origin,pid,'prior_point:'+str(p['references']),True)
 # Entire existing PO/D proofs: resolve each query to its frozen selected-view plan.
 for dirname,filename in [('sat_pair_round10','queries_with_repairs.csv'),('sat_pair_round11','queries_batch3.csv')]:
  for q in rows(T/dirname/filename):
   if q['args']!='-prove observation_diff 0' or q['status']!='proved':continue
   folder=q['folder'];phase=3 if 'pairs_batch3' in folder else 2 if 'pairs_batch2' in folder else 1;plan=read(T/dirname/('plan.json' if dirname.endswith('10') or phase==1 else f'plan_batch{phase}.json'));item=plan['selected'][int(q['pair_index'])];va,vb=item['source_view'],item['partner'];code,pid=checkproof(q);aa=[]
   for view,mn in [(va,'left_design'),(vb,'right_design')]:
    m=raw(view);net=next(n for n,b in m['netnames'].items() if len(b['bits'])==1);generated,spec=N.emit(m,mn,[net]*5);strip=lambda x:re.sub(r'assign sigs=\{.*?\};','assign sigs=BOUND;',x);assert strip(generated)==strip(module(code,mn));aa.append(spec)
   assert aa[0]['ports']==aa[1]['ports'] and aa[0]['states']==aa[1]['states'] and aa[0]['obs']==aa[1]['obs'];wrapper=module(code,'check');assert 'assign observation_diff=|(oa^ob);' in wrapper and 'left_design l(env,a,oa)' in wrapper and 'right_design r(env,b,ob)' in wrapper;globalplans.append(dict(va=va,vb=vb,pid=pid,observations=aa[0]['obs'],origin='hash_PO_D_in_preselected_view',qid=q['query_id']))
 # Case8 role-guided proofs: re-enable their candidates, not old training flags.
 r8src={r['view']:r for r in rows(T/'sat_cases_round8/sources.csv')};r8q=rows(T/'sat_cases_round8/queries.csv')
 for inst in ['injalpha','injepsilon']:
  va=f'rs232t1000__{inst}_d1_s42__ys_id';vb=f'rs232t1000__{inst}_d1_s42__ys_abc';qs=[q for q in r8q if q['folder'].endswith(inst+'_cross_impl')];layout=[]
  for q in qs:
   if q['status']!='proved':continue
   code,pid=checkproof(q,'QUERY');layout=[]
   for view,mn in [(va,'design_ys_id'),(vb,'design_ys_abc')]:
    generated,spec=C8.emit(raw(view),mn,'TrojanA' if inst=='injalpha' else 'TrojanE');assert generated==module(code,mn);layout.append(spec)
   assert layout[0]['input_offsets']==layout[1]['input_offsets'] and layout[0]['state_offsets']==layout[1]['state_offsets'] and layout[0]['observations']==layout[1]['observations'];wrapper=module(code,'check');assert "left(env,1'b0,1'b0,a,oa)" in wrapper and "right(env,1'b0,1'b0,b,ob)" in wrapper
   if q['args']=='-prove po_d_diff 0':assert 'assign po_d_diff=|(oa^ob)' in wrapper;globalplans.append(dict(va=va,vb=vb,pid=pid,observations=layout[0]['observations'],origin='hash_PO_D_in_label_assisted_case',qid=q['query_id']))
   else:
    mm=re.fullmatch(r'-prove delta\[(\d+)\] 0',q['args']);assert mm;slot=int(mm[1]);consider(va,vb,layout[0]['probes'][slot],layout[1]['probes'][slot],'label_assisted_mechanism',pid,'mechanism:'+['selector','data_A','data_B','target','rec_readyH'][slot])
 # Deduplicate full-proof view pairs before selecting observations, no new SAT.
 seen=set();obscontracts=[]
 for g in globalplans:
  va,vb=g['va'],g['vb'];key=tuple(sorted([va,vb]))
  if key in seen:continue
  seen.add(key);obs=g['observations'];pool=sorted(obs,key=lambda x:ident(['po_d_cone_v1',meta[va]['src_view'],x]));selected=pool[:64];obscontracts.append(dict(source=meta[va]['src_view'],view_a=va,view_b=vb,observations_proved=len(obs),observations_selected=len(selected),proof_id=g['pid'],root_selection='first64 by frozen hash, no node labels'))
  for name,j in selected:
   bits=[]
   for view in [va,vb]:
    m=raw(view);bits.append(m['cells'][name[:-2]]['connections']['D'][0] if name.endswith('.D') and name[:-2] in m['cells'] else m['ports'][name]['bits'][j])
   consider(va,vb,*bits,g['origin'],g['pid'],f'{name}[{j}]')
 # Old region-prefix/sweep pairs are proposals only; certify bounded current cones.
 pairviews={}
 for g in globalplans:
  va,vb=g['va'],g['vb'];ma,mb=meta[va],meta[vb]
  if 'keep' not in va and 'keep' not in vb:
   key=(ma['host'],ma['src_view'].split('__')[1].split('_d1')[0],va.split('__')[-1].replace('ys_',''),vb.split('__')[-1].replace('ys_',''));pairviews[key]=(va,vb);pairviews[(key[0],key[1],key[3],key[2])]=(vb,va)
 proposals=collections.defaultdict(dict)
 with (T/'node_pairs_sat_node.csv').open(encoding='utf-8-sig') as f:
  for q in csv.DictReader(f):
   key=q['host'],q['inst_a'],q['recipe_a'],q['recipe_b']
   if q['status']!='proved' or q['inst_a']!=q['inst_b'] or key not in pairviews:continue
   if not(q['net_a'].lstrip('\\').startswith('Trojan') or q['net_b'].lstrip('\\').startswith('Trojan')):continue
   va,vb=pairviews[key];ma,mb=raw(va),raw(vb);na,nb=q['net_a'],q['net_b']
   if na not in ma['netnames'] or nb not in mb['netnames']:continue
   ba,bb=ma['netnames'][na]['bits'],mb['netnames'][nb]['bits']
   if len(ba)!=1 or len(bb)!=1 or not isinstance(ba[0],int) or not isinstance(bb[0],int):continue
   h=ident([va,vb,ba,bb]);proposals[va,vb][h]=(ba[0],bb[0],na,nb)
 for (va,vb),pp in sorted(proposals.items()):
  for h,(ba,bb,na,nb) in sorted(pp.items())[:8]:consider(va,vb,ba,bb,'label_assisted_legacy_Trojan_prefix',None,'legacy_candidate:'+na+'|'+nb)
 # Current labels are read only after functional acceptance, for evaluation grading.
 graded=[];arr={};predsource=[]
 for p in accepted.values():
  ends=[]
  for cid in [p['left_cone'],p['right_cone']]:
   z=cones[cid];key=viewmap[z['view']][0]
   if key not in arr:
    d=R/c['shared_inputs'][key]['folder'];arr[key]={n:np.load(d/(n+'.npy'),mmap_mode='r') for n in ['y','trusted','physical']}
   a=arr[key];i=z['root_row'];ends.append(dict(view=z['view'],row=i,cell=z['output_cell'],pin=z['output_pin'],label=int(a['y'][i]),trusted=bool(a['trusted'][i]),physical=bool(a['physical'][i])))
  diagnostic=all(x['trusted'] and x['physical'] for x in ends) and ends[0]['label']==ends[1]['label'];p['detection_stability_diagnostic_eligible']=diagnostic;p['diagnostic_scope']='same proven signal observation and equal independent root labels; not normative risk invariance, no label transfer';p['labels_used_for_function_acceptance']=False;p['root_endpoints']=ends;graded.append(dict(pair_id=p['pair_id'],split=p['split'],source=p['source_object'],origins='|'.join(p['origins']),left_cells=len(cones[p['left_cone']]['members']),right_cells=len(cones[p['right_cone']]['members']),boundary_inputs=p['enum']['inputs'],proofs=len(p['proof_ids']),enum=p['enum']['method'],detection_diagnostic=diagnostic,root_label_a=ends[0]['label'],root_label_b=ends[1]['label'],trusted_a=ends[0]['trusted'],trusted_b=ends[1]['trusted'],prior_existing=p['prior_existing']))
 dump('pair_inventory.csv',graded);dump('rejected_candidates.csv',reject);dump('accepted_references.csv',attempts);dump('whole_proof_observation_sources.csv',obscontracts)
 for n,obj in [('pairs.json',list(accepted.values())),('cones.json',list(cones.values())),('reused_proofs.json',oldproofs)]: (O/n).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
 for p in [OLD/'COMPLETE.json',Path(__file__),R/'_p0pilot/round10_20261025/native.py',R/'_p0pilot/round8_20261025/case_chain.py',T/'node_pairs_sat_node.csv',F/'views_meta.csv',R/'_p0pilot/control_boundary_v3_20261104/input_contract.json']:inputs[str(p.relative_to(R))]=sha(p)
 report=dict(training=0,model_forward=0,new_SAT_queries=0,old_pair_count=14,unique_pairs=len(accepted),pair_splits=dict(collections.Counter(p['split'] for p in accepted.values())),source_objects=len({p['source_object'] for p in accepted.values()}),source_objects_by_split={s:len({p['source_object'] for p in accepted.values() if p['split']==s}) for s in ['train','val','test']},unique_proof_queries=len(oldproofs),whole_view_pairs=len(obscontracts),sampled_observations=sum(x['observations_selected'] for x in obscontracts),rejected=len(reject),rejection_reasons=dict(collections.Counter(x['reason'] for x in reject)),diagnostic_pairs=sum(p['detection_stability_diagnostic_eligible'] for p in accepted.values()),eligible_functional_aux_train=sum(p['split']=='train' for p in accepted.values()),detector_risk_consistency_training_allowed=0,proof_scope='unrestricted named PI/physicalQ, no reset/state reachability',label_assistance_allowed=True,inputs=inputs)
 (O/'EXPANDED.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k!='inputs'},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
