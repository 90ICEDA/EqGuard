"""Cached-code sensitivity,training shortcuts and MUX support audit;no GNN calls."""
from pathlib import Path
import collections,csv,gzip,hashlib,json,math,time
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;OLD=R/'_p0pilot/cec_freeq_zrp_seed42_20261107';C=R/'_p0pilot/cec_po_contract_20261106';P=R/'_p0pilot/cec_boundary_panel_expand_20261107';PRE=R/'_p0pilot/cec_freeq_preflight_20261106'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def table(n,rr):
 if not rr:return
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def cached(domain,arm,tag,space='root64'):
 z=np.load(OLD/f'{domain}_{arm}_tag{tag}.npz');return z['cone_ids'].tolist(),z[space].astype(float)
def query_records(units,ids,x):
 ix={c:j for j,c in enumerate(ids)};rr=[]
 for u in units:
  n=u['functions'];v=x[[ix[c] for c in u['cones']]]
  for f in range(n):
   for side in [0,1]:
    for other in range(n):
     if other==f:continue
     a=2*f+side;t=2*f+1-side;b=2*other+1-side;dt=float(np.sqrt(np.mean((v[a]-v[t])**2)+1e-12));dw=float(np.sqrt(np.mean((v[a]-v[b])**2)+1e-12))
     rr.append(dict(unit_id=u['unit_id'],source=u['source'],context_id=u['context_id'],functions=n,has_mux=u.get('has_mux',False),anchor_function=f,anchor_side=side,wrong_function=other,true_distance=dt,wrong_distance=dw,margin=dw-dt,win=float(dt<dw)+.5*float(dt==dw),weight=1/(len(units)*2*n*(n-1))))
 return rr
def qkey(r):return (r['unit_id'],r['anchor_function'],r['anchor_side'],r['wrong_function'])
def main():
 assert not (O/'CACHE_COMPLETE.json').exists();assert read(OLD/'VERIFIED.json')['passed']
 protected=dict(read(OLD/'EXECUTION_CONTRACT.json')['protected_files'])
 for n,h in read(OLD/'OUTPUT_MANIFEST.json').items():assert sha(OLD/n)==h;protected[str((OLD/n).relative_to(R))]=h
 for p in [OLD/'VERIFIED.json',OLD/'PUBLISHED.json',PRE/'gradient_vectors.npz',Path(__file__)]:protected[str(p.relative_to(R))]=sha(p)
 for p,h in protected.items():assert sha(R/p)==h,p
 write('ANALYSIS_CONTRACT.json',dict(scope='posthoc mechanism audit,NOT a new primary or training run',cached='all four states/two tags,same85H3;query flips and codevsmodel margin scales;unsigned boundary-set shortcuts;MUX matched within same source/flow',frozen_gradient='INIT reused old vectors;finalZ/R/P on same frozensteps1,2,16,32;rawnorm,angles,CE directional derivatives;no optimizer/no parameter perturbation',extra_code_tags=[9002,9003,9004,9005],extra_code_scope='all85H3,all4states,fixed prior to new inference;all results reported,not choosing best mapping',MUX='within ctlmatchb abc-aig;nativeMUXvsdecomposed side;training support;small sameboundary native/decomposed synthetic identity stresspanel;rolecycle andidentityzero frozen diagnostics',causal_limits='code replacement at fixedcheckpoint/inputstructure is intervention;gradient local only,not optimized trajectory contribution;ablation distribution shift not proof of uselessness;no detection claims',training=0,SAT=0,new_real_boolean_input_patterns=0,test_reads=0,protected_files=protected))
 pp=read(OLD/'EVALUATION_PANELS.json');val=[u for u in pp['val_boundary_all'] if u['tier']=='H3'];train=pp['train_frozen_pool'];assert len(val)==85
 query={};sensitivity=[];units=[]
 for arm in ['INIT','Z','R','P']:
  a,b=[cached('val',arm,t) for t in [9000,9001]];assert a[0]==b[0];query[arm]={t:{qkey(r):r for r in query_records(val,ids,x)} for t,(ids,x) in zip([9000,9001],[a,b])}
  r0,r1=query[arm][9000],query[arm][9001];keys=list(r0)
  shift=np.array([r1[k]['margin']-r0[k]['margin'] for k in keys]);w=np.array([r0[k]['weight'] for k in keys]);flips=np.array([r0[k]['win']!=r1[k]['win'] for k in keys]);sensitivity.append(dict(arm=arm,query_count=len(keys),directional_query_flips=int(flips.sum()),unit_weighted_flip_fraction=float(w@flips),margin_shift_RMS=float(np.sqrt(w@(shift**2))),weighted_win_change=float(sum(r0[k]['weight']*(r1[k]['win']-r0[k]['win']) for k in keys)),absolute_root_code_delta_RMS=float(np.sqrt(np.mean((a[1]-b[1])**2)))))
  for u in val:
   kk=[k for k in keys if k[0]==u['unit_id']];units.append(dict(arm=arm,unit_id=u['unit_id'],source=u['source'],has_mux=u['has_mux'],functions=u['functions'],win9000=float(np.mean([r0[k]['win'] for k in kk])),win9001=float(np.mean([r1[k]['win'] for k in kk])),margin9000=float(np.mean([r0[k]['margin'] for k in kk])),margin9001=float(np.mean([r1[k]['margin'] for k in kk])),flipped_queries=sum(r0[k]['win']!=r1[k]['win'] for k in kk)))
 table('encoding_sensitivity.csv',sensitivity);table('unit_encoding_sensitivity.csv',units)
 contrasts=[];contribution=[];scale=[]
 for u in val:
  rows={r['arm']:r for r in units if r['unit_id']==u['unit_id']};d0=rows['R']['win9000']-rows['P']['win9000'];d1=rows['R']['win9001']-rows['P']['win9001'];contribution.append(dict(unit_id=u['unit_id'],source=u['source'],has_mux=u['has_mux'],functions=u['functions'],RminusP9000=d0,RminusP9001=d1,change=d1-d0,primary_change_contribution=(d1-d0)/85,R_win_change=rows['R']['win9001']-rows['R']['win9000'],P_win_change=rows['P']['win9001']-rows['P']['win9000']))
 for source in sorted({u['source'] for u in val}):
  rr=[r for r in contribution if r['source']==source];contrasts.append(dict(source=source,units=len(rr),RminusP9000=float(np.mean([r['RminusP9000'] for r in rr])),RminusP9001=float(np.mean([r['RminusP9001'] for r in rr])),gap_change=float(np.mean([r['change'] for r in rr])),weighted_primary_gap_change=sum(r['primary_change_contribution'] for r in rr),changed_units=sum(abs(r['change'])>1e-12 for r in rr)))
 keys=list(query['R'][9000]);w=np.array([query['R'][9000][k]['weight'] for k in keys]);rp0=np.array([query['R'][9000][k]['margin']-query['P'][9000][k]['margin'] for k in keys]);rp1=np.array([query['R'][9001][k]['margin']-query['P'][9001][k]['margin'] for k in keys]);codeR=np.array([query['R'][9001][k]['margin']-query['R'][9000][k]['margin'] for k in keys]);scale=dict(RP_margin_difference_RMS9000=float(np.sqrt(w@(rp0**2))),RP_margin_difference_RMS9001=float(np.sqrt(w@(rp1**2))),R_code_margin_shift_RMS=float(np.sqrt(w@(codeR**2))),code_shift_over_RP_effect=float(np.sqrt(w@(codeR**2))/np.sqrt(w@(rp0**2))))
 table('primary_reversal_by_source.csv',contrasts);table('primary_reversal_by_unit.csv',sorted(contribution,key=lambda r:-abs(r['change'])));write('MARGIN_SCALE_COMPARISON.json',scale)
 # Load only audit topology;the root encoder never receives names/PO/signatures.
 original=read(R/'_p0pilot/cec_hard_validation_20261106/local_graphs.json');graphs=dict(zip(original['cone_ids'],original['graphs']));contexts=dict(zip(original['cone_ids'],original['contexts']))
 with gzip.open(P/'local_graphs.json.gz','rt',encoding='utf-8') as f:expanded=json.load(f)
 graphs.update(zip(expanded['cone_ids'],expanded['graphs']));contexts.update(zip(expanded['cone_ids'],expanded['contexts']))
 tokenmaps={m['context_key']:m['tokens'] for m in read(R/'_p0pilot/cec_interface_minimal_20261105/boundary_maps_audit_only.json')}
 def boundary(cid):
  g=graphs[cid];used=set(s for s in g['slot'] if s>=0);return frozenset((t['kind'],t['audit_name'],t['bit']) for t in tokenmaps[contexts[cid]] if t['slot'] in used)
 bd={cid:boundary(cid) for u in train+val for cid in u['cones']};support=[];baselines=[];relationships=[]
 for panel,uu in [('train_frozen21',train),('val_H3_85',val)]:
  for u in uu:
   n=u['functions'];allbd=[bd[c] for c in u['cones']];mux=[sum(o==8 for o in graphs[c]['op']) for c in u['cones']];left=any(mux[0::2]);right=any(mux[1::2]);same=all(s==allbd[0] for s in allbd);wins=[]
   for f in range(n):
    for side in [0,1]:
     a=2*f+side;t=2*f+1-side
     for other in range(n):
      if other==f:continue
      b=2*other+1-side;distance=lambda x,y:1-len(allbd[x]&allbd[y])/len(allbd[x]|allbd[y]);dt,dw=distance(a,t),distance(a,b);wins.append(float(dt<dw)+.5*float(dt==dw))
   flow='|'.join(v.rsplit('__',1)[-1] for v in u['view_direction']);relationships.append(dict(panel=panel,unit_id=u['unit_id'],source=u['source'],context_id=u['context_id'],flow=flow,functions=n,all_candidate_boundary_equal=same,MUX_left=left,MUX_right=right,MUX_left_only=left and not right,MUX_both=left and right,root_MUX_left=any(graphs[c]['op'][graphs[c]['root']]==8 for c in u['cones'][0::2]),root_MUX_right=any(graphs[c]['op'][graphs[c]['root']]==8 for c in u['cones'][1::2]),boundary_jaccard_win=float(np.mean(wins))))
  rr=[r for r in relationships if r['panel']==panel]
  for source in sorted({r['source'] for r in rr}):
   ss=[r for r in rr if r['source']==source];support.append(dict(panel=panel,source=source,units=len(ss),same_boundary_units=sum(r['all_candidate_boundary_equal'] for r in ss),MUX_units=sum(r['MUX_left'] or r['MUX_right'] for r in ss),MUX_left_only=sum(r['MUX_left_only'] for r in ss),MUX_both=sum(r['MUX_both'] for r in ss),flows=';'.join(sorted({r['flow'] for r in ss})),boundary_jaccard_win=float(np.mean([r['boundary_jaccard_win'] for r in ss]))))
  family=np.mean([np.mean([r['boundary_jaccard_win'] for r in rr if r['context_id']==key]) for key in {r['context_id'] for r in rr}]);baselines.append(dict(panel=panel,units=len(rr),same_boundary_units=sum(r['all_candidate_boundary_equal'] for r in rr),family_macro_boundary_jaccard_win=float(family)))
 table('boundary_shortcut_by_unit.csv',relationships);table('MUX_training_validation_support.csv',support);table('BOUNDARY_SHORTCUT_BASELINE.csv',baselines)
 # MUX only against NONMUX within the SAME source/flow;separate the easy other source.
 strata=[];distances=[]
 for tag in [9000,9001]:
  for arm in ['INIT','Z','R','P']:
   q=query[arm][tag]
   for source in sorted({u['source'] for u in val}):
    for muxflag in [False,True]:
     uu=[u for u in val if u['source']==source and u['has_mux']==muxflag]
     if not uu:continue
     per=[]
     for u in uu:
      rr=[r for r in q.values() if r['unit_id']==u['unit_id']];per.append(dict(win=np.mean([r['win'] for r in rr]),true=np.mean([r['true_distance'] for r in rr]),wrong=np.mean([r['wrong_distance'] for r in rr]),margin=np.mean([r['margin'] for r in rr])))
     strata.append(dict(tag=tag,arm=arm,source=source,MUX=muxflag,units=len(uu),win=float(np.mean([r['win'] for r in per])),true_distance=float(np.mean([r['true'] for r in per])),wrong_distance=float(np.mean([r['wrong'] for r in per])),margin=float(np.mean([r['margin'] for r in per]))))
   # Same-view negative separation vs cross-view actual association on frozen training pool.
   ids,x=cached('train',arm,tag);ix={c:j for j,c in enumerate(ids)};per=[]
   for u in train:
    n=u['functions'];v=x[[ix[c] for c in u['cones']]];d=lambda a,b:np.sqrt(np.mean((v[a]-v[b])**2)+1e-12);neg=[d(2*a+s,2*b+s) for s in [0,1] for a in range(n) for b in range(a+1,n)];true=[d(2*f,2*f+1) for f in range(n)];wrong=[d(2*a,2*b+1) for a in range(n) for b in range(n) if a!=b];per.append(dict(family=u['context_id'],negative=np.mean(neg),true=np.mean(true),wrong=np.mean(wrong),active=np.mean(np.array(neg)<1),negative_hinge=np.mean(np.maximum(0,1-np.array(neg))**2)))
   avg=lambda key:float(np.mean([np.mean([r[key] for r in per if r['family']==f]) for f in {r['family'] for r in per}]))
   distances.append(dict(tag=tag,arm=arm,sameview_different_distance=avg('negative'),crossview_true_distance=avg('true'),crossview_wrong_distance=avg('wrong'),common_hinge_active_fraction=avg('active'),common_hinge_value=avg('negative_hinge')))
 table('MUX_matched_source_metrics.csv',strata);table('common_vs_association_distances.csv',distances)
 for p,h in protected.items():assert sha(R/p)==h,p
 write('CACHE_COMPLETE.json',dict(passed=True,primary_units=85,cache_only=True,training=0,SAT=0,new_model_forwards=0,signature_as_feature=False,margin_scale=scale,old_files_unchanged=True))
 print('CACHE_ANALYSIS_COMPLETE',json.dumps(dict(scale=scale,boundary=baselines),ensure_ascii=False),flush=True)
if __name__=='__main__':main()
