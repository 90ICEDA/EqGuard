"""PO matching within the frozen105 units and their310 existing pairs. No model/SAT."""
from pathlib import Path
import collections,csv,hashlib,itertools,json,time,traceback
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent
H=R/'_p0pilot/cec_hard_boundary_20261106';V=R/'_p0pilot/cec_hard_validation_20261106';J=R/'_p0pilot/cec_joint_expand_20261105'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def ident(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def write(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def table(n,rr):
 if not rr:return
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def po_bin(d):return 'unreachable' if d==-1 else '0' if d==0 else '1_2' if d<=2 else '3_5' if d<=5 else '6plus'
def main():
 assert not (O/'AUDIT_COMPLETE.json').exists();assert read(V/'VERIFIED.json')['passed']
 protected=dict(read(V/'INTERFACE_VERIFIED.json')['protected_files'])
 paths=[H/'hard_panel.json',H/'PANEL_COMPLETE.json',V/'VERIFIED.json',V/'OUTPUT_MANIFEST.json',V/'local_graphs.json',Path(__file__),R/'_p0pilot/control_boundary_v3_20261104/input_contract.json']
 for p in paths:protected[str(p.relative_to(R))]=sha(p)
 for p,h in protected.items():assert sha(R/p)==h,p
 # Declare all support rules before looking at coordinates; no predictions or safety labels loaded.
 write('SELECTION_RULES.json',dict(universe='exact105units and their310 existing pair_ids ONLY;no wider pool/search',primary='exact raw v3 PO column30 integer;all candidate functions share(leftPO,rightPO)',within_unit='keep complete original triple if exact;otherwise group functions by identicalPOpair;2functions evaluation-only,never pad/repeat to3',reassemble='only same split/source/query/viewpair;exact root gate,comb size/depth,cut,5op/PIQpin/constant/phase/repeated-pin profile on BOTH sides;subdivide T3 by exact aligned boundary token sets;group PO last;different saved signatures required',secondary='predeclared PO strata and exact equal cross-distance matrices;diagnostic only,not substitute for exact coordinate matching',tie_break='maximal disjoint triples then remaining pair;fixed SHA order of existing observed-function signatures;source cap16',claims='posthoc support audit,not confirmatory;128saved input signatures do not prove equality;original positive proofs retained',no_safety_labels_or_predictions_for_selection=True,training=0,SAT=0,new_real_patterns=0,test_reads=0))
 units=read(H/'hard_panel.json');cones={c['cone_id']:c for c in read(J/'final_cones.json')};pairs={p['pair_id']:p for p in read(J/'final_pairs.json')};jj=read(V/'local_graphs.json');gg=dict(zip(jj['cone_ids'],jj['graphs']));con=read(paths[-1]);depth=read(R/'_p0pilot/cec_cause_audit_20261106/panel_cone_depths.json')
 used_ids=sorted({p for u in units for p in u['pair_ids']});assert len(used_ids)==310
 po={};rootx={}
 for split in ['train','val']:
  path=R/con['shared_inputs']['trans_'+split]['folder']/'x39.npy';assert sha(path)==con['files'][str(path.relative_to(R))];protected[str(path.relative_to(R))]=sha(path);x=np.load(path,mmap_mode='r')
  for cid in {c for u in units if u['split']==split for c in u['cones']}:
   val=float(x[cones[cid]['root_row'],30]);assert np.isfinite(val) and val==int(val) and val>=-1;po[cid]=int(val);rootx[cid]=x[cones[cid]['root_row']].tolist()
 def describe(cid):
  c=cones[cid];g=gg[cid];hist=collections.Counter();pins=collections.Counter();inc=collections.defaultdict(list);leaf={tuple(t[:3]) for t in c['leaves']}
  for op in g['op']:
   if op>=4:hist[op]+=1
  for a,b,role,phase in g['edge']:
   inc[b].append((a,phase));pins['phase']+=phase
   if g['op'][a] in [0,1]:pins['PI' if g['op'][a]==0 else 'Q']+=1
   elif g['op'][a] in [2,3]:pins['C'+str(g['op'][a]-2)]+=1
  gate=tuple(rootx[cid][:25]);base=(gate,len(c['members']),depth[cid]['gate_depth'],len(leaf));ext=base+tuple(hist[k] for k in range(4,9))+tuple(pins[k] for k in ['PI','Q','C0','C1','phase'])+(sum(len(v)-len(set(v)) for v in inc.values()),)
  return ext,tuple(sorted(leaf))
 canonical={pid:sorted([pairs[pid]['left_cone'],pairs[pid]['right_cone']],key=lambda c:cones[c]['view']) for pid in used_ids};parents={p:u for u in units for p in u['pair_ids']};signatures={p:s for u in units for p,s in zip(u['pair_ids'],u['function_signatures'])}
 entries=[]
 for pid in used_ids:
  cids=canonical[pid];u=parents[pid];p=pairs[pid];a,b=[describe(c) for c in cids]
  assert p['functional_auxiliary_data_eligible'] and (p['proof_ids'] or p.get('enum',{}).get('equal'))
  entries.append(dict(pair_id=pid,split=u['split'],source=u['source'],context_id=u['context_id'],views=u['view_direction'],cones=cids,parent_unit=u['unit_id'],signature=signatures[pid],po=[po[c] for c in cids],profile=[a[0],b[0]],boundary=[a[1],b[1]],proof_ids=p['proof_ids'],original_enum=p.get('enum',{})))
 write('pair_inventory.json',entries)
 within=[];original=[];queries=[]
 for u in units:
  vals=[tuple(po[c] for c in canonical[p]) for p in u['pair_ids']];buckets=collections.defaultdict(list)
  for pid,z in zip(u['pair_ids'],vals):buckets[z].append(pid)
  whole=len(buckets)==1;coarse=len({tuple(po_bin(v) for v in z) for z in vals})==1
  dl=np.array([z[0] for z in vals]);dr=np.array([z[1] for z in vals]);dm=np.abs(dl[:,None]-dr[None,:]);neutral=bool(np.all(dm==dm[0,0]))
  original.append(dict(unit_id=u['unit_id'],split=u['split'],source=u['source'],tier=u['tier'],functions=u['functions'],po_pairs=json.dumps(vals),whole_exact=whole,whole_coarse=coarse,all_crossdistances_equal=neutral,max_side_PO_span=max(int(np.ptp(dl)),int(np.ptp(dr))),reachable_state_matched=len({tuple(v!=-1 for v in z) for z in vals})==1,exact_subsets=sum(len(pp)>=2 for pp in buckets.values())))
  for coord,pp in buckets.items():
   if len(pp)>=2:within.append(dict(subset_id=ident(['within_original_exactPO',u['unit_id'],pp]),parent_unit=u['unit_id'],split=u['split'],source=u['source'],tier=u['tier'],functions=len(pp),pair_ids=pp,cones=[c for p in pp for c in canonical[p]],po_pair=list(coord),use='triple' if len(pp)==3 else 'two_function_eval_only'))
  for f in range(u['functions']):
   for side in [0,1]:
    for w in range(u['functions']):
     if w==f:continue
     dtrue=abs(vals[f][side]-vals[f][1-side]);dwrong=abs(vals[f][side]-vals[w][1-side]);queries.append(dict(unit_id=u['unit_id'],split=u['split'],source=u['source'],anchor_function=f,anchor_side=side,wrong_function=w,true_PO_distance=dtrue,wrong_PO_distance=dwrong,tie=dtrue==dwrong,PO_prefers_true=dtrue<dwrong))
 table('original_unit_PO_audit.csv',original);table('original_query_PO_audit.csv',queries);write('within_original_exact_subsets.json',within)
 # Repartition only alreadyselected functions; original105 is immutable, no new proofs.
 assembled={};support=[]
 for mode in ['T2_PO_exact','T3_PO_exact']:
  buckets=collections.defaultdict(list)
  for e in entries:
   key=[e['split'],e['source'],e['context_id'],e['views'],e['profile'],e['po']]
   if mode.startswith('T3'):key+=[e['boundary']]
   buckets[ident(key)].append(e)
  selected=[];singletons=[]
  for key,ee in sorted(buckets.items()):
   seen={}
   for e in sorted(ee,key=lambda e:ident(['representative',e['pair_id']])):seen.setdefault(e['signature'],e)
   ee=sorted(seen.values(),key=lambda e:ident(['PO_group_functions',e['signature']]))
   for start in range(0,len(ee),3):
    zz=ee[start:start+3]
    if len(zz)==1:singletons.append(zz[0]);continue
    pp=[z['pair_id'] for z in zz];u=zz[0];selected.append(dict(unit_id=ident([mode,key,pp]),split=u['split'],source=u['source'],context_id=u['context_id'],view_direction=u['views'],tier=mode,functions=len(zz),pair_ids=pp,cones=[c for z in zz for c in z['cones']],function_signatures=[z['signature'] for z in zz],po_pair=u['po'],parent_units=sorted({z['parent_unit'] for z in zz}),has_mux=any(8 in gg[c]['op'] for z in zz for c in z['cones']),shallow_small=all(len(cones[c]['members'])<=16 and depth[c]['gate_depth']<=4 for z in zz for c in z['cones']),use='three_candidate' if len(zz)==3 else 'two_function_eval_only'))
  assembled[mode]=selected;write(mode+'_units.json',selected);write(mode+'_unmatched_singletons.json',singletons)
  for split in ['train','val']:
   ee=[e for e in entries if e['split']==split];ss=[u for u in selected if u['split']==split];un=[e for e in singletons if e['split']==split]
   support.append(dict(mode=mode,split=split,original_pairs=len(ee),units=len(ss),triples=sum(u['functions']==3 for u in ss),pairs_only=sum(u['functions']==2 for u in ss),sources=len({u['source'] for u in ss}),paired_functions=sum(u['functions'] for u in ss),unmatched_functions=len(un),mux_units=sum(u['has_mux'] for u in ss),shallow_small_units=sum(u['shallow_small'] for u in ss)))
 table('reassembled_support.csv',support)
 summaries=[]
 for split in ['train','val']:
  for source in sorted({u['source'] for u in units if u['split']==split}):
   rr=[r for r in original if r['split']==split and r['source']==source];ss=[u for u in within if u['split']==split and u['source']==source]
   summaries.append(dict(split=split,source=source,original_units=len(rr),whole_exact=sum(r['whole_exact'] for r in rr),whole_coarse=sum(r['whole_coarse'] for r in rr),cross_distance_neutral=sum(r['all_crossdistances_equal'] for r in rr),within_exact_triples=sum(u['functions']==3 for u in ss),within_exact_pairs=sum(u['functions']==2 for u in ss),**{mode+'_triples':sum(u['split']==split and u['source']==source and u['functions']==3 for u in assembled[mode]) for mode in assembled},**{mode+'_pairs':sum(u['split']==split and u['source']==source and u['functions']==2 for u in assembled[mode]) for mode in assembled}))
 table('matching_by_source.csv',summaries)
 for p,h in protected.items():assert sha(R/p)==h,p
 write('AUDIT_COMPLETE.json',dict(passed=True,original_units=len(units),original_pairs=len(entries),original_cones=len(po),within_original_subsets=len(within),support=support,exact_unit_counts={s:sum(r['split']==s and r['whole_exact'] for r in original) for s in ['train','val']},whole_coarse_counts={s:sum(r['split']==s and r['whole_coarse'] for r in original) for s in ['train','val']},whole_distance_neutral={s:sum(r['split']==s and r['all_crossdistances_equal'] for r in original) for s in ['train','val']},new_model_forwards=0,training=0,SAT=0,new_input_patterns=0,test_reads=0,predictions_used_for_selection=False,protected_files=protected))
 print(json.dumps(dict(within=len(within),support=support),ensure_ascii=False),flush=True)
if __name__=='__main__':
 try:main()
 except Exception:
  O.mkdir(exist_ok=True);(O/f'failure_{time.strftime("%H%M%S")}.log').write_text(traceback.format_exc(),encoding='utf-8');raise
