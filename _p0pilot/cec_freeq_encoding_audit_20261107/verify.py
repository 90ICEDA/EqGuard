"""Independent CPU checks of code sensitivity,encoder hardties and frozen VJPs."""
from pathlib import Path
import collections,csv,gzip,hashlib,json,math
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;OLD=R/'_p0pilot/cec_freeq_zrp_seed42_20261107';C=R/'_p0pilot/cec_po_contract_20261106';P=R/'_p0pilot/cec_boundary_panel_expand_20261107';PRE=R/'_p0pilot/cec_freeq_preflight_20261106'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
 frozen=read(O/'FROZEN_COMPLETE.json');assert frozen['passed'] and read(O/'SUMMARY_COMPLETE.json')['passed'];protected=read(O/'FROZEN_EXECUTION.json')['protected_files']
 for p,h in protected.items():assert sha(R/p)==h,p
 pp=read(OLD/'EVALUATION_PANELS.json');val=[u for u in pp['val_boundary_all'] if u['tier']=='H3'];train=pp['train_frozen_pool'];prior=rows(O/'six_code_metrics.csv');checked=0
 for tag in range(9000,9006):
  for arm in ['INIT','Z','R','P']:
   z=np.load((OLD if tag<9002 else O)/f'val_{arm}_tag{tag}.npz');ix={c:j for j,c in enumerate(z['cone_ids'].tolist())};x=z['root64'].astype(float);wins=[]
   for u in val:
    v=x[[ix[c] for c in u['cones']]];n=u['functions'];unit=[]
    for f in range(n):
     for side in [0,1]:
      a=2*f+side;dt=math.sqrt(math.dist(v[a],v[2*f+1-side])**2/64+1e-12)
      for other in range(n):
       if other==f:continue
       dw=math.sqrt(math.dist(v[a],v[2*other+1-side])**2/64+1e-12);unit.append(float(dt<dw)+.5*float(dt==dw))
    wins.append(np.mean(unit))
   recorded=next(r for r in prior if int(r['tag'])==tag and r['arm']==arm);assert abs(float(recorded['win'])-np.mean(wins))<1e-12;checked+=1
 # Reconstruct encoder-equivalence classes by interned actual SLOT/OP/ROLE expressions,
 # independently from the physical-name/hash construction in tie_audit.py.
 local=read(R/'_p0pilot/cec_hard_validation_20261106/local_graphs.json');gg=dict(zip(local['cone_ids'],local['graphs']));context=dict(zip(local['cone_ids'],local['contexts']))
 with gzip.open(P/'local_graphs.json.gz','rt',encoding='utf-8') as f:z=json.load(f)
 gg.update(zip(z['cone_ids'],z['graphs']));context.update(zip(z['cone_ids'],z['contexts']));intern={};rootclass={}
 for cid in sorted({c for u in train+val for c in u['cones']}):
  g=gg[cid];inc=collections.defaultdict(list)
  for s,d,r,p in g['edge']:inc[d].append((s,r,p))
  states=[]
  for j,op in enumerate(g['op']):
   if op<2:key=('variable',op,context[cid],g['slot'][j])
   elif op<4:key=('constant',op)
   else:key=('operation',op,tuple(sorted((r,p,states[s]) for s,r,p in inc[j])))
   if key not in intern:intern[key]=len(intern)
   states.append(intern[key])
  rootclass[cid]=states[g['root']]
 tie_rows=rows(O/'root_encoder_hardties.csv');direct={}
 for panel,us in [('train21',train),('valH3',val)]:
  for u in us:
   for j,pid in enumerate(u['pair_ids']):
    a,b=u['cones'][2*j:2*j+2];equal=rootclass[a]==rootclass[b];recorded=next(r for r in tie_rows if r['panel']==panel and r['pair_id']==pid);assert equal==(recorded['identical_typed_unfolded_expression']=='True')
    if panel=='train21':direct[pid]=equal
 scheduled=read(C/'SCHEDULE_SEED42.json');blocked=allq=0;weight=0
 for step in scheduled:
  for r in step['units']:
   for a,candidates,t,w in zip(r['anchors'],r['candidates'],r['real_targets'],r['permuted_targets']):
    allq+=1
    if rootclass[a]==rootclass[candidates[t]]:blocked+=1;weight+=r['query_weight']
    assert rootclass[a]!=rootclass[candidates[w]]
 assert allq==576 and blocked==192 and abs(weight/32-1/3)<1e-12
 # Merge actual encoder classes FIRST,then compare targets and common negatives.
 class_conflicts={}
 for arm,target_key in [('R','real_targets'),('P','permuted_targets')]:
  parent={};neg=set()
  def find(x):
   parent.setdefault(x,x)
   if parent[x]!=x:parent[x]=find(parent[x])
   return parent[x]
  for step in scheduled:
   for r in step['units']:
    for a,candidates,target in zip(r['anchors'],r['candidates'],r[target_key]):parent[find(rootclass[a])]=find(rootclass[candidates[target]])
    neg.update(tuple(sorted(e)) for e in r['common_negative_edges'])
  class_conflicts[arm]=sum(find(rootclass[a])==find(rootclass[b]) for a,b in neg)
 assert class_conflicts=={'R':0,'P':72}
 correction=read(O/'AUDIT_CORRECTION.json');assert correction['P_blocked_scheduled_queries']==blocked and correction['P_negative_edges_in_conflicted_components_after_implicit_equalities']==class_conflicts['P']
 # Independently verify the input-set shortcut uses no ops,roles,outputs or scores.
 tokenmaps={m['context_key']:{t['slot']:(t['kind'],t['audit_name'],t['bit']) for t in m['tokens']} for m in read(R/'_p0pilot/cec_interface_minimal_20261105/boundary_maps_audit_only.json')}
 def leaves(c):return frozenset(tokenmaps[context[c]][s] for s in gg[c]['slot'] if s>=0)
 for us,expected in [(train,1.),(val,.5)]:
  for u in us:
   b=[leaves(c) for c in u['cones']];n=u['functions'];ww=[]
   for f in range(n):
    for s in [0,1]:
     a=2*f+s;t=2*f+1-s;dt=1-len(b[a]&b[t])/len(b[a]|b[t])
     for j in range(n):
      if j==f:continue
      k=2*j+1-s;dw=1-len(b[a]&b[k])/len(b[a]|b[k]);ww.append(float(dt<dw)+.5*float(dt==dw))
   assert abs(np.mean(ww)-expected)<1e-12
 # Full saved VJPs prove local additivity and signs;no optimizer or backprop here.
 gradient_rows=rows(O/'component_gradient_summary.csv');nsets=0
 with np.load(O/'final_component_vectors.npz') as vectors,np.load(PRE/'gradient_vectors.npz') as original:
  for checkpoint in ['INIT','Z','R','P']:
   for batch in [1,2,16,32]:
    vv={k:(original[f'update{batch}_{k}'] if checkpoint=='INIT' else vectors[f'{checkpoint}_batch{batch}_{k}']).astype(float) for k in ['CE_R','CE_P','different','variance_weighted','total_Z','total_R','total_P']};common=vv['different']+vv['variance_weighted'];r=next(r for r in gradient_rows if r['checkpoint']==checkpoint and int(r['batch'])==batch)
    for group,g in [('Z',common),('R',common+vv['CE_R']),('P',common+vv['CE_P'])]:assert np.linalg.norm(vv['total_'+group]-g)/np.linalg.norm(vv['total_'+group])<2e-5
    cn=np.linalg.norm(common);rn=np.linalg.norm(vv['CE_R']);wn=np.linalg.norm(vv['CE_P']);assert abs(float(r['common_over_real'])-cn/rn)<1e-10;assert abs(float(r['real_common_cos'])-common@vv['CE_R']/(cn*rn))<1e-10;assert abs(float(r['wrong_common_cos'])-common@vv['CE_P']/(cn*wn))<1e-10;nsets+=1
    assert float(r['real_CE_directional_slope_under_common_descent'])<0 and float(r['wrong_CE_directional_slope_under_common_descent'])>0
 assert read(O/'REPEAT_CONTROL.json')['root_max_abs_repeat']<2e-5
 # Independent algebraic truth check for the old16 synthetic positions.
 expected=[]
 for rule in [lambda a,b,s:(s&b)|((1-s)&a),lambda a,b,s:(s&a)|((1-s)&b),lambda a,b,s:(a&b)|((1-a)&s)]:
  value=sum(rule((p>>0)&1,(p>>1)&1,(p>>2)&1)<<p for p in range(16));expected +=[value,value]
 assert all(v==expected for v in read(O/'MUX_TOY_TRUTH.json').values())
 assert frozen['optimizer_objects']==frozen['optimizer_updates']==frozen['training']==frozen['SAT']==0
 for p,h in protected.items():assert sha(R/p)==h,p
 manifest={str(p.relative_to(O)):sha(p) for p in O.rglob('*') if p.is_file() and p.suffix in ['.py','.json','.csv','.npz'] and '__pycache__' not in p.parts and p.name not in ['VERIFIED.json','OUTPUT_MANIFEST.json','PUBLISHED.json']};write('OUTPUT_MANIFEST.json',manifest)
 write('VERIFIED.json',dict(passed=True,independent_code_metric_sets=checked,independent_encoder_equivalence_class_construction=True,encoder_blocked_P_queries=blocked,scheduled_queries=allq,weighted_blocked_fraction=weight/32,independent_boundary_shortcut_allunits=True,independent_full_gradient_sets=nsets,all_shared_descent_realCE_slopes_negative_and_wrongCE_positive=True,model_forwards=frozen['counters']['model_forwards'],autograd_calls=frozen['counters']['autograd_calls'],initial_gradients_reused=True,training=0,optimizer_updates=0,SAT=0,new_real_boolean_patterns=0,test_reads=0,all_old_files_and_weights_unchanged=True,main_metrics_not_replaced=True,posthoc_diagnostic_only=True,manifest_sha=sha(O/'OUTPUT_MANIFEST.json')))
 print('INDEPENDENT_ENCODING_CAUSE_AUDIT_VERIFIED',flush=True)
if __name__=='__main__':main()
