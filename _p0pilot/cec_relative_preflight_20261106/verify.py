"""Independent cached NumPy verification; no model execution or new gradients."""
from pathlib import Path
import collections,csv,hashlib,json
import numpy as np
O=Path(__file__).resolve().parent;R=O.parents[1];C=R/'_p0pilot/cec_relative_contract_20261106'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(n):
 with (O/n).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def table(n,rr):
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def cosine(a,b):
 den=np.linalg.norm(a)*np.linalg.norm(b);return float(np.dot(a,b)/den) if den else None
def main():
 done=read(O/'COMPLETE.json');ex=read(O/'EXECUTION_CONTRACT.json');layout=read(O/'PARAMETER_LAYOUT.json');loaded=read(O/'loaded_batches.json');tr={t['triple_id']:t for t in read(C/'triple_pool.json')};schedule=read(C/'schedule_seed42.json');cones={c['cone_id']:c for c in read(R/'_p0pilot/cec_joint_expand_20261105/final_cones.json')}
 assert done['optimizer_steps']==done['SAT']==done['test_reads']==0
 assert done['all_original_parameters_and_BN_buffers_unchanged'] and done['no_parameter_grad_accumulation']
 for p,h in ex['frozen_files'].items():assert sha(R/p)==h,p
 groups={g:np.concatenate([np.arange(v['start'],v['stop']) for v in layout['names'].values() if v['group']==g]) for g in ['backbone','shared_boundary','pin_boundary','pin_internal','projection']};groups['all']=np.arange(layout['total_dimensions'])
 assert sorted(np.concatenate([groups[g] for g in groups if g!='all']).tolist())==list(range(layout['total_dimensions']))
 totals=collections.Counter();source=collections.Counter();tc=collections.Counter();nc=collections.Counter();pos={k:set() for k in ['R','P']};neg=set();compete={k:set() for k in ['R','P']}
 def addr(cid):c=cones[cid];return (c['view'],c['root_row'])
 def edge(a,b):return tuple(sorted([a,b]))
 for b in loaded:
  rr=[r for r in schedule if r['update']==b['update']];assert rr==b['rows'];ids=b['cone_ids'];assert len(set(ids))==len(ids)
  gold_queries=[];gold_neg=[]
  for r in rr:
   t=tr[r['triple_id']];assert t['split']=='train';a,ar,d,dr,e,er=t['cones'];source[r['source']]+=1;tc[r['triple_id']]+=1
   gold_queries +=[(a,[ar,dr,er],0,1),(d,[ar,dr,er],1,0),(ar,[a,d,e],0,1),(dr,[a,d,e],1,0)]
   gold_neg +=[(a,d),(ar,dr),(a,er),(d,er),(ar,e),(dr,e)]
   for cid in t['cones']:
    co=cones[cid];nc.update((co['view'],v) for v in co['graph_rows'])
  actual=[(ids[a],[ids[c] for c in cs],ir,ip) for a,cs,ir,ip in zip(b['anchors'],b['candidates'],b['real'],b['permuted'])];assert actual==gold_queries
  assert [(ids[a],ids[c]) for a,c in b['negative_edges']]==gold_neg
  for anchor,cs,ir,ip in actual:
   for mode,it in [('R',ir),('P',ip)]:
    pos[mode].add(edge(addr(anchor),addr(cs[it])));compete[mode].update(edge(addr(anchor),addr(c)) for j,c in enumerate(cs) if j!=it)
  neg.update(edge(addr(a),addr(c)) for a,c in gold_neg)
  totals.update(dict(queries=len(actual),candidate_distances=3*len(actual),common_negative_terms=len(gold_neg),readout_slots=6*len(rr)))
 for mode in ['R','P']:assert not pos[mode]&neg and not pos[mode]&compete[mode]
 assert totals==dict(queries=800,candidate_distances=2400,common_negative_terms=1200,readout_slots=1200) and set(source.values())=={25} and len(source)==8 and len(tc)==143 and max(tc.values())==2 and max(nc.values())==27
 # Independent physical graph attachment check on all selected roots and members.
 inp=read(R/'_p0pilot/control_boundary_v3_20261104/input_contract.json');z=inp['shared_inputs']['trans_train'];physical=np.load(R/z['folder']/'physical.npy',mmap_mode='r');vm={v['view']:v for v in z['views']};checked=set()
 for row in schedule:
  for cid in tr[row['triple_id']]['cones']:
   if cid in checked:continue
   checked.add(cid);co=cones[cid];v=vm[co['view']];ix=np.array(co['graph_rows']);assert physical[ix].all() and ((ix>=v['start'])&(ix<v['physical_stop'])).all() and co['root_row'] in ix
 norms=rows('gradient_norms.csv');angles=rows('gradient_angles.csv');max_numeric=0;sum_errors=[]
 for mode in ['contract_train','frozen_eval']:
  for u in [1,2,25,50]:
   b=next(x for x in loaded if x['update']==u)
   with np.load(O/f'forward_{mode}_u{u}.npz') as f:
    assert f['cone_ids'].tolist()==b['cone_ids'];zz=f['projection32'].astype(np.float64)
   mse=np.mean((zz[np.array(b['anchors'])][:,None,:]-zz[np.array(b['candidates'])])**2,-1);d=np.sqrt(mse+1e-12);s=-d;mx=s.max(1);lse=mx+np.log(np.exp(s-mx[:,None]).sum(1));w=np.array(b['query_weights']);q=np.arange(len(d));ne=np.array(b['negative_edges']);nw=np.array(b['negative_weights'])
   ref={k:float((w*mse[q,np.array(b['real' if k=='A_R' else 'permuted'])]).sum()) for k in ['A_R','A_P']};ref.update({k:float((w*(lse-s[q,np.array(b['real' if k=='S_R' else 'permuted'])])).sum()) for k in ['S_R','S_P']})
   ref['different']=float((nw*np.maximum(0,1-np.sqrt(((zz[ne[:,0]]-zz[ne[:,1]])**2).mean(1)+1e-12))**2).sum());ref['variance_weighted']=float(.1*np.maximum(0,.5-np.sqrt(zz.var(0)+1e-4)).mean())
   for arm in ['Z','A_R','A_P','S_R','S_P']:ref[arm+'_total']=ref['different']+ref['variance_weighted']+(ref[arm] if arm!='Z' else 0)
   with np.load(O/f'vectors_{mode}_u{u}.npz') as vg:
    assert set(vg.files)==set(ref)
    for row in [r for r in norms if r['mode']==mode and int(r['batch'])==u]:
     vec=vg[row['term']][groups[row['group']]].astype(np.float64);actual=np.linalg.norm(vec);assert np.isfinite(vec).all() and abs(actual-float(row['grad_norm']))<1e-10
     err=abs(ref[row['term']]-float(row['loss']));max_numeric=max(max_numeric,err);assert err<3e-5
    for row in [r for r in angles if r['mode']==mode and int(r['batch'])==u]:
     a=vg[row['left']][groups[row['group']]].astype(np.float64);bb=vg[row['right']][groups[row['group']]].astype(np.float64);cs=cosine(a,bb);assert abs(cs-float(row['cosine']))<1e-12
    # BF16 separate VJPs need not add bitwise to the joint backward.
    for arm in ['Z','A_R','A_P','S_R','S_P']:
     expected=vg['different']+vg['variance_weighted']+(vg[arm] if arm!='Z' else 0);actual=vg[arm+'_total'];relative=float(np.linalg.norm(actual-expected)/(np.linalg.norm(actual)+1e-30));sum_errors.append(dict(mode=mode,batch=u,arm=arm,separate_joint_VJP_relative_error=relative))
 table('BF16_gradient_linearity.csv',sum_errors)
 summary=[]
 for mode in ['contract_train','frozen_eval']:
  for g in groups:
   rr=[r for r in angles if r['mode']==mode and r['group']==g]
   for l,r in [('A_R','A_P'),('S_R','S_P'),('A_R_total','A_P_total'),('S_R_total','S_P_total')]:
    aa=[float(x['cosine']) for x in rr if x['left']==l and x['right']==r];summary.append(dict(mode=mode,group=g,left=l,right=r,cosine_mean=np.mean(aa),cosine_min=min(aa),cosine_max=max(aa),batches=len(aa)))
 table('gradient_summary.csv',summary)
 replays=rows('first_batch_arm_replays.csv');assert len(replays)==10 and all(float(x['relative_projection_RMS'])<.02 for x in replays)
 for p,h in ex['frozen_files'].items():assert sha(R/p)==h,p
 result=dict(passed=True,independent_loaded_candidates_and_targets_match=True,selected_physical_cones_checked=len(checked),independent_budget=dict(totals),global_positive_negative_and_competitor_overlap=0,max_loss_numeric_error=max_numeric,all_gradient_norms_and_cosines_independently_recomputed=True,initialization_and_original_BN_unchanged=done['all_original_parameters_and_BN_buffers_unchanged'],model_forwards=done['model_forwards'],parameter_VJP=done['parameter_vector_jacobian_products'],leaf_VJP=done['leaf_vector_jacobian_products'],optimizer_steps=0,SAT=0,test_reads=0,frozen_files_unchanged=True,outputs_sha={p.name:sha(p) for p in O.glob('vectors_*.npz')})
 (O/'VERIFIED.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
