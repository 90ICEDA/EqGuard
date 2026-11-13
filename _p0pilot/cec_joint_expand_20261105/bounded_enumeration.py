"""Exact small-boundary fallback using already cached raw models; no solver calls."""
from common import *
import time
CASES=[('s35932t200__injalpha_d1_s42__ys_abc','s35932t200__injalpha_d1_s42__ys_aig'),('s38417t100__injepsilon_d1_s42__ys_abc','s38417t100__injepsilon_d1_s42__ys_aig'),('s38417t100__injbeta_d1_s42__ys_abc','s38417t100__injbeta_d1_s42__ys_nand')]
def exact(ms,cs,width_cap=18):
 tokens=sorted({tuple(l[:3]) for c in cs for l in c['leaves']});w=len(tokens);assert w<=width_cap
 pattern=np.arange(1<<w,dtype=np.uint32);env={t:((pattern>>j)&1).astype(bool) for j,t in enumerate(tokens)};outputs=[]
 for m,c in zip(ms,cs):
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
   g=drivers[b];v=[ev(g['connections'][p][0]) for p in SCHEMA[g['type']][1]];t=g['type']
   a=v[0]&v[1] if t in ['AND2X2','$and'] else v[0]|v[1] if t in ['OR2X1','$or'] else v[0]^v[1] if t in ['XOR2X1','$xor'] else ~v[0] if t in ['INVX0','$not'] else np.where(v[2],v[1],v[0]);values[b]=a;return a
  outputs.append(ev(c['root_bit']))
 equal=bool(np.array_equal(*outputs));tt=np.packbits(outputs[0],bitorder='little');witness=None
 if not equal:
  j=int(np.flatnonzero(outputs[0]!=outputs[1])[0]);witness=dict(input_pattern=j,values=[int((j>>k)&1) for k in range(w)],output_a=int(outputs[0][j]),output_b=int(outputs[1][j]))
 return dict(method='complete_two_valued_enumeration',inputs=w,patterns=len(pattern),equal=equal,nonconstant=bool(outputs[0].any() and (~outputs[0]).any()),truth_sha=hashlib.sha256(tt.tobytes()).hexdigest()),dict(semantic_inputs=[list(t) for t in tokens],packed_truth_hex=tt.tobytes().hex(),counterexample=witness)
def main():
 assert not (O/'BOUNDED_COMPLETE.json').exists();store=Store();known={p['pair_id'] for p in read(O/'joint_pairs.json')};accepted=[];cones=[];certs=[];plan=[];out=[];total=0;MAX=1048576
 for ci,(va,vb) in enumerate(CASES):
  try:ma,mb=store.raw(va),store.raw(vb)
  except (AssertionError,FileNotFoundError,StopIteration) as e:plan.append(dict(case=ci,view_a=va,view_b=vb,status='raw_binding_or_totality_blocked',reason=str(e)));continue
  if store.layouts[va]!=store.layouts[vb]:plan.append(dict(case=ci,view_a=va,view_b=vb,status='PI_Q_layout_mismatch'));continue
  ctx=ident(dict(PI=store.layouts[va][0],physicalQ=store.layouts[va][1],free=True));source=store.meta[va]['src_view'];candidates={}
  for net in sorted(set(ma['netnames'])&set(mb['netnames'])):
   aa,bb=ma['netnames'][net]['bits'],mb['netnames'][net]['bits']
   if len(aa)!=1 or len(bb)!=1:continue
   ra,rb=store.root(va,aa[0]),store.root(vb,bb[0])
   if ra is None or rb is None:continue
   ok=True
   for view,rr in [(va,ra),(vb,rb)]:
    if rr[1] not in store.maps[view]:ok=False;break
    ar=store.arrays[store.vm[view][0]];i=store.maps[view][rr[1]]
    if not(ar['physical'][i] and ar['trusted'][i] and ar['y'][i]==1):ok=False;break
   if not ok:continue
   pid=ident([source,ctx,sorted([ra[0],rb[0]])])
   if pid in known or pid in candidates:continue
   ca,cb=store.getcone(va,aa[0]),store.getcone(vb,bb[0])
   if ca is None or cb is None:continue
   w=len({tuple(l[:3]) for z in [ca,cb] for l in z['leaves']});candidates[pid]=dict(pair_id=pid,net=net,cones=[ca,cb],inputs=w)
  chosen=[]
  for p in sorted(candidates.values(),key=lambda x:(x['inputs'],ident(['small_CEC_gap_v1',x['pair_id']]))):
   if len(chosen)>=3:break
   if p['inputs']>18 or total+(1<<p['inputs'])>MAX:continue
   chosen.append(p);total+=1<<p['inputs']
  plan.append(dict(case=ci,view_a=va,view_b=vb,status='enumeration_candidates_selected',candidate_count=len(candidates),over18=sum(p['inputs']>18 for p in candidates.values()),chosen=[dict(pair_id=p['pair_id'],net=p['net'],inputs=p['inputs']) for p in chosen]))
  for p in chosen:
   cs=p['cones'];result,certificate=exact([ma,mb],cs);status='proved' if result['equal'] and result['nonconstant'] else 'refuted' if not result['equal'] else 'constant'
   out.append(dict(case=ci,pair_id=p['pair_id'],source=source,split=cs[0]['split'],status=status,inputs=p['inputs'],patterns=result['patterns']))
   certs.append(dict(pair_id=p['pair_id'],raw_shas=[z['raw_sha'] for z in cs],root_bits=[z['root_bit'] for z in cs],status=status,**certificate,**result))
   if status!='proved':continue
   ends=[store.endpoint(z) for z in cs];accepted.append(dict(pair_id=p['pair_id'],source_object=source,split=cs[0]['split'],context_id=ctx,left_cone=cs[0]['cone_id'],right_cone=cs[1]['cone_id'],proof_ids=[],origins=['label_assisted_small_gap_complete_PI_Q_enumeration'],observations=[p['net']],root_endpoints=ends,labels_used_for_selection=True,labels_used_for_function_acceptance=False,functional_auxiliary_data_eligible=True,current_detection_training_allowed=False,detection_stability_diagnostic_eligible=True,enum=result));cones.extend(cs);known.add(p['pair_id'])
  print('Exact case',ci,'candidates',len(candidates),'chosen',len(chosen),'accepted',sum(x['case']==ci and x['status']=='proved' for x in out),flush=True)
 write('bounded_plan.json',plan);write('bounded_pairs.json',accepted);write('bounded_cones.json',cones);write('bounded_certificates.json',certs);table('bounded_results.csv',out)
 write('BOUNDED_COMPLETE.json',dict(training=0,model_forward=0,new_SAT_queries=0,budget_max_cases=3,budget_max_pairs=9,budget_max_inputs=18,budget_max_total_patterns=MAX,actual_patterns=total,accepted=len(accepted),accepted_splits=dict(collections.Counter(p['split'] for p in accepted)),statuses=dict(collections.Counter(x['status'] for x in out)),solver_blocker='WSL/E_ACCESSDENIED at raw preparation; preserved failed log; used existing bound k4 raw plus exhaustive enumeration instead',inputs=store.inputs))
 print(read(O/'BOUNDED_COMPLETE.json')|{'inputs':'hashes saved'},flush=True)
if __name__=='__main__':main()
