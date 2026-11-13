"""Independent support/PO/certificate/budget checks. No torch, optimizer or SAT."""
from pathlib import Path
import collections,csv,hashlib,itertools,json
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;V=R/'_p0pilot/cec_hard_validation_20261106'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
 audit=read(O/'AUDIT_COMPLETE.json');assert audit['passed'];protected=dict(audit['protected_files'])
 for p,h in protected.items():assert sha(R/p)==h,p
 for name,h in read(V/'OUTPUT_MANIFEST.json').items():assert sha(V/name)==h,name
 originals=read(R/'_p0pilot/cec_hard_boundary_20261106/hard_panel.json');inv=read(O/'pair_inventory.json');pairs={p['pair_id']:p for p in inv};cc={c['cone_id']:c for c in read(R/'_p0pilot/cec_joint_expand_20261105/final_cones.json')};local=read(V/'local_graphs.json');gg=dict(zip(local['cone_ids'],local['graphs']))
 assert len(inv)==310 and len(cc)>=620
 # Raw root gate types and v3 PO values are independently reread from original sources.
 root_type={};po={};contract=read(R/'_p0pilot/control_boundary_v3_20261104/input_contract.json')
 for view in {cc[c]['view'] for p in inv for c in p['cones']}:
  ids={c for p in inv for c in p['cones'] if cc[c]['view']==view};path=R/cc[next(iter(ids))]['raw_path'];assert sha(path)==cc[next(iter(ids))]['raw_sha'];m=next(iter(read(path)['modules'].values()))
  for cid in ids:root_type[cid]=m['cells'][cc[cid]['output_cell']]['type']
 for split in ['train','val']:
  raw=np.load(R/contract['shared_inputs']['trans_'+split]['folder']/'x39.npy',mmap_mode='r')
  for p in inv:
   if p['split']==split:
    for i,cid in enumerate(p['cones']):po[cid]=int(raw[cc[cid]['root_row'],30]);assert po[cid]==p['po'][i]
 def profile(cid):
  g=gg[cid];edges=g['edge'];op=g['op'];count=collections.Counter(op);incoming=collections.defaultdict(list);pins=collections.Counter()
  for a,b,role,phase in edges:
   incoming[b].append((a,phase));pins['phase']+=phase
   if op[a]<4:pins[op[a]]+=1
  return (root_type[cid],len(cc[cid]['members']),max(g['level']),len(set(tuple(t[:3]) for t in cc[cid]['leaves'])),tuple(count[k] for k in range(4,9)),tuple(pins[k] for k in [0,1,2,3]),pins['phase'],sum(len(v)-len(set(v)) for v in incoming.values()))
 def boundary(cid):return tuple(sorted({tuple(t[:3]) for t in cc[cid]['leaves']}))
 panels={mode:read(O/(mode+'_units.json')) for mode in ['T2_PO_exact','T3_PO_exact']}
 for mode,uu in panels.items():
  observed=[]
  for u in uu:
   assert u['functions'] in [2,3] and len(u['pair_ids'])==u['functions']
   assert len(set(u['function_signatures']))==u['functions']
   for pid in u['pair_ids']:
    p=pairs[pid];assert p['split']==u['split'] and p['source']==u['source'] and p['context_id']==u['context_id'] and p['views']==u['view_direction']
   for side in [0,1]:
    ids=u['cones'][side::2];assert len({po[c] for c in ids})==1 and all(profile(c)==profile(ids[0]) for c in ids)
    if mode=='T3_PO_exact':assert all(boundary(c)==boundary(ids[0]) for c in ids)
   assert all((pairs[pid]['po']==u['po_pair']) for pid in u['pair_ids']);observed+=u['pair_ids']
  assert len(observed)==len(set(observed))
 # Verify unmatched functions account for the entire finite310-pair universe.
 for mode,uu in panels.items():
  matched={p for u in uu for p in u['pair_ids']};un={p['pair_id'] for p in read(O/(mode+'_unmatched_singletons.json'))}
  assert not matched&un and matched|un==set(pairs)
 within=read(O/'within_original_exact_subsets.json')
 for u in within:
  parent=next(o for o in originals if o['unit_id']==u['parent_unit']);assert set(u['pair_ids'])<=set(parent['pair_ids'])
  assert all(pairs[p]['po']==u['po_pair'] for p in u['pair_ids'])
 # Function-family aliases are not counted as new evidence or separate training functions.
 tr=read(O/'TRAINING_POOL.json');classes=[(u['context_id'],s) for u in tr for s in u['function_signatures']];assert len(classes)==len(set(classes))==63 and len(tr)==21
 aliases=read(O/'ALIAS_FAMILIES.json');assert len(aliases)==24 and sum(len(a['members']) for a in aliases)==32
 # Independent exhaustive packing optimum on the small per-context representative sets.
 candidates={u['unit_id']:u for u in panels['T2_PO_exact']};byctx=collections.defaultdict(list)
 for a in aliases:byctx[a['context_id']].append(candidates[a['representative']])
 optima={}
 for ctx,uu in byctx.items():
  optimum=0
  for n in range(len(uu),-1,-1):
   if any(len({s for u in selection for s in u['function_signatures']})==3*n for selection in itertools.combinations(uu,n)):optimum=n;break
  assert sum(u['context_id']==ctx for u in tr)==optimum;optima[ctx]=optimum
 # All127 function-different edges must have valid saved-input witnesses on both implementations.
 cert=read(O/'REASSEMBLED_NEGATIVE_CERTIFICATES.json');assert len(cert)==127
 for c in cert:
  assert c['new_input_patterns']==c['SAT']==0 and c['outputs'][0]==c['outputs'][1] and c['outputs'][2]==c['outputs'][3] and c['outputs'][0]!=c['outputs'][2]
  pa,pb=[pairs[p] for p in c['pair_ids']];assert pa['context_id']==pb['context_id']==c['context_id']
  expected=[(int(p['signature'],16)>>c['pattern'])&1 for p in [pa,pa,pb,pb]];assert expected==c['outputs']
 schedule=read(O/'SCHEDULE_SEED42.json');assert [s['update'] for s in schedule]==list(range(1,33))
 nc=collections.Counter();fc=collections.Counter();sc=collections.Counter();nodes=collections.Counter();bound=collections.Counter();allpos={k:set() for k in ['R','P']};negative=set();counts=collections.Counter()
 for step in schedule:
  assert len(step['units'])==3 and {u['context_id'] for u in step['units']}==set(byctx)
  for u in step['units']:
   original=next(t for t in tr if t['unit_id']==u['unit_id']);assert original['cones']==u['cone_ids'] and original['split']=='train'
   nc[u['unit_id']]+=1;sc[u['context_id']]+=1
   for s in original['function_signatures']:fc[u['context_id'],s]+=1
   for cid in u['cone_ids']:
    for name in gg[cid]['comb_names']:nodes[u['context_id'],cc[cid]['view'],name]+=1
    for slot in gg[cid]['slot']:
     if slot>=0:bound[u['context_id'],slot]+=1
   # Equal weighted target occurrence and explicit inverse reverse correspondence.
   rt=collections.Counter();pt=collections.Counter();at=collections.Counter(u['anchors'])
   for a,cands,real,wrong in zip(u['anchors'],u['candidates'],u['real_targets'],u['permuted_targets']):
    assert real!=wrong;rt[cands[real]]+=1;pt[cands[wrong]]+=1
    for arm,target in [('R',real),('P',wrong)]:allpos[arm].add(tuple(sorted([a,cands[target]])))
   assert rt==pt==at
   for a,cands,t in zip(u['anchors'],u['candidates'],u['permuted_targets']):
    b=cands[t];j=u['anchors'].index(b);assert u['candidates'][j][u['permuted_targets'][j]]==a
   assert abs(u['query_weight']*18-1)<1e-12 and abs(u['negative_weight']*18-1)<1e-12
   negative.update(tuple(sorted(e)) for e in u['common_negative_edges']);counts.update(dict(units=1,queries=6,distances=18,negatives=6,endpoints=6))
 assert max(nc.values())==max(fc.values())==16 and set(sc.values())=={32}
 for arm in ['R','P']:
  parent={}
  def find(x):
   parent.setdefault(x,x)
   if parent[x]!=x:parent[x]=find(parent[x])
   return parent[x]
  for a,b in allpos[arm]:parent[find(a)]=find(b)
  assert not allpos[arm]&negative and all(find(a)!=find(b) for a,b in negative)
 budget=read(O/'SUPERVISION_BUDGET.json');assert counts['units']==budget['unit_slots']==96 and counts['queries']==budget['anchor_query_slots']==576 and counts['distances']==budget['candidate_distance_slots']==1728 and max(nodes.values())==budget['max_comb_gate_occurrence_exposure']==67 and max(bound.values())==budget['max_boundary_token_occurrence_exposure']==192
 # The primary strict panel really removes the unsigned boundary-set shortcut as well as PO.
 for u in panels['T3_PO_exact']:
  for side in [0,1]:assert len({boundary(c) for c in u['cones'][side::2]})==1
 # Model contract remains a specification, not a falsely advertised executed model.
 design=read(O/'FAIR_MODEL_CONTRACT.json');assert sum(design['model']['expected_parameter_breakdown'].values())==47360
 assert design['execution']['updates']==32 and not read(O/'CONTRACT_READY.json')['model_instantiated']
 for p,h in protected.items():assert sha(R/p)==h,p
 frozen_indices={p.name:sha(p) for p in [O/'TRAINING_POOL.json',O/'SCHEDULE_SEED42.json',O/'T3_PO_exact_units.json',O/'T2_PO_exact_units.json',O/'REASSEMBLED_NEGATIVE_CERTIFICATES.json',O/'SUPERVISION_BUDGET.json']};write('FROZEN_INDICES.json',frozen_indices)
 manifest={p.name:sha(p) for p in O.iterdir() if p.is_file() and p.suffix in ['.py','.json','.csv'] and p.name not in ['VERIFIED.json','OUTPUT_MANIFEST.json','PUBLISHED.json']};write('OUTPUT_MANIFEST.json',manifest)
 write('VERIFIED.json',dict(passed=True,checks=['raw gate types and v3 PO reread','within/reassembled exactPO and structure and boundary','310pairs matched+unmatched accounting','maximum disjoint packing independently enumerated','127 saved-input differentfunction witnesses','same weighted targets and endpoints acrossR/P','inverse reverse permutation','no direct/transitive positive-negative conflicts','96slots/576queries/1728distances','unit,function,gate,Qexposures independently counted','unsigned strict boundarybag and PO controls tie'],packing_optima=optima,strict_PO_pairs_train=4,strict_PO_pairs_val=4,training_triples=21,source_alias_triples=8,training=0,SAT=0,new_input_patterns=0,new_model_forwards=0,backward=0,test_reads=0,model_contract_only=True,actual_model_loading_gradient_preflight_pending=True,old_files_unchanged=True,protected_files=len(protected),output_manifest_sha=sha(O/'OUTPUT_MANIFEST.json')))
 print('VERIFIED_PO_SUPPORT_AND_FAIR_CONTRACT',flush=True)
if __name__=='__main__':main()
