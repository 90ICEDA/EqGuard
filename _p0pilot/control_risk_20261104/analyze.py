"""Existing-score only region audit; never imports torch or a solver."""
from pathlib import Path
import sys,json,csv,collections,hashlib,datetime
import numpy as np
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(OUT.parent/'control_retention_20261104'))
from audit import cells,norm
F=ROOT/'generate_trans/folds/hosts_bt31';H=ROOT/'_p0pilot/p2b_main_20261031';P=ROOT/'_p0pilot/round32_20261029'
def read(p):return p.read_text(encoding='utf-8-sig')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(name,a):
 if not a:return
 with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(a[0]));w.writeheader();w.writerows(a)
def mean(a):return float(np.mean(a)) if len(a) else None

def main():
 OUT.mkdir(exist_ok=True);contract=json.loads(read(P/'input_contract.json'))
 cohort=list(csv.DictReader((OUT.parent/'control_retention_20261104/cohort_candidates.csv').open(encoding='utf-8-sig')))
 main=[r for r in cohort if r['proposed_cohort']=='primary_candidate'];contexts={};views={};wanted={};bindings={}
 for split in ['train','val','test']:
  q=contract['shared_inputs']['trans_'+split];folder=ROOT/q['folder'];contexts[split]={n:np.load(folder/(n+'.npy'),mmap_mode='r') for n in ['y','physical','trusted']}
  contexts[split]['new']=np.load(H/f'new_mask_{split}.npy',mmap_mode='r')
  for v in q['views']:views[v['view']]=dict(v,split=split)
 # Map actual ordered physical node names, never assume emitted cell order.
 ranges=sorted((v['old_start'],v['old_stop'],name) for name,v in views.items());idx=0
 for name,v in views.items():wanted[name]={}
 with (F/'data/processed/node_names_trans.txt').open(encoding='utf-8') as f:
  for gid,line in enumerate(f):
   while idx<len(ranges) and gid>=ranges[idx][1]:idx+=1
   if idx>=len(ranges):break
   lo,hi,name=ranges[idx]
   if gid>=lo:wanted[name][norm(line)]=views[name]['start']+gid-lo
 # Source records used only to define injection target region, not score selection.
 prov=collections.defaultdict(list)
 for p in (ROOT/'generate_trans').glob('hosts*/*/provenance.json'):
  try:
   a=json.loads(read(p))
   if isinstance(a,list):
    for d in a:
     if d.get('view'):prov[d['view']].append((p,d))
  except (ValueError,OSError):pass
 pairfamily={'ctlmatcha':'injalpha','ctlmatchb':'injbeta','ctlmatchc':'injgamma','ctlmatchd':'injdelta','ctlmatche':'injepsilon','ctlmatchf':'injzeta'}
 regions=[];pairs={};missing=[]
 for r in main:
  name=r['view'];v=views[name];ns=r['target_instances'].split('|');lookup=wanted[name]
  ids=[lookup[x] for x in ns if x in lookup]
  if len(ids)!=len(ns):raise ValueError(('target missing graph node',name,set(ns)-lookup.keys()))
  a=contexts[v['split']];ids=np.array(sorted(set(ids)),int)
  assert a['physical'][ids].all() and (a['y'][ids]==0).all()
  regions.append(dict(r,ids=ids,old_trusted=int(a['trusted'][ids].sum()),new_trusted=int(a['new'][ids].sum())))
  family=r['family'].split('_d1')[0];targetfam=pairfamily.get(family)
  if family.startswith('a4ctl'):targetfam=family.replace('a4ctldead','a4trojan').replace('a4ctlequiv','a4trojan')
  if not targetfam:missing.append(dict(view=name,reason='no prespecified matching Trojan family'));continue
  src=r['host']+'__'+targetfam+'_d1_s42';targetview=name.replace(r['source_view'],src,1)
  if targetview not in views:missing.append(dict(view=name,reason='matching Trojan view absent from frozen split'));continue
  tv=views[targetview];assert tv['split']==v['split']
  sf=F/'orig'/(src+'.v');mp=F/'mappings'/(targetview+'.json');sc,_=cells(sf)
  choices=[(p,d) for p,d in prov[src] if d.get('new_gates') and all(norm(g) in sc for g in d['new_gates'])]
  if not choices:missing.append(dict(view=name,reason='Trojan provenance unavailable'));continue
  pp,pd=choices[0];mapping=json.loads(read(mp));assert mapping['src_view']==src and mapping['rw_view']==targetview
  gates=set(map(norm,pd['new_gates']));names=set();covered=0;bad=[]
  for g in gates:
   ns={norm(x) for x in mapping['node_alignment'].get(g,[])}
   if g in wanted[targetview]:ns.add(g)
   valid=ns & wanted[targetview].keys()
   if valid:covered+=1
   names.update(valid)
  ti=np.array(sorted(wanted[targetview][n] for n in names),int)
  if covered!=len(gates) or not len(ti):missing.append(dict(view=name,reason=f'Trojan added-object trace incomplete {covered}/{len(gates)}'));continue
  # Avoid treating mixed/normal mapped nodes as a fully labelled Trojan region.
  if not (a['y'][ti]==1).all() or not a['new'][ti].all():missing.append(dict(view=name,reason='Trojan trace contains nonpositive or untrusted nodes'));continue
  pairs[name]=dict(view=targetview,source=src,ids=ti)
  for p in [sf,mp,pp]:bindings[str(p.relative_to(ROOT))]=sha(p)
 scores=[];nodes=[];pairrows=[];prechecks=[];missing_predictions=[]
 for seed in [42,1,2]:
  metrics=json.loads(read(H/f'seed{seed}_AB.json'))
  for arm in ['A','B']:
   run=H/'runs'/f'seed{seed}'/arm;threshold=float(metrics[arm]['threshold']);sel=json.loads(read(run/'SELECTED.json'))
   assert sel['path']==metrics[arm]['selected']['path']
   for split in ['train','val','test']:
    sp=run/f'{split}_scores.npy'
    if not sp.exists():
     missing_predictions.append(dict(seed=seed,arm=arm,split=split,reason='no saved score array; no forward recomputation'))
     continue
    pred=np.load(sp,mmap_mode='r');a=contexts[split];assert len(pred)==len(a['y']) and np.isfinite(pred).all()
    pv=list(csv.DictReader((run/f'{split}_per_view.csv').open(encoding='utf-8-sig')))
    for x in pv:
     if x['scope']!='trusted':continue
     v=views[x['view']];sl=slice(v['start'],v['stop']);mask=a['new'][sl]&(a['y'][sl]==0)
     got=mean(pred[sl][mask]>=threshold)
     if got is not None and x['fpr']:assert abs(got-float(x['fpr']))<1e-7,(seed,arm,split,x['view'])
    prechecks.append(dict(seed=seed,arm=arm,split=split,length=len(pred),per_view_fpr_reproduced=True,score_sha=sha(sp),selected_sha=sha(run/'SELECTED.json')))
    bindings[str(sp.relative_to(ROOT))]=sha(sp)
    for r in regions:
     if r['split']!=split:continue
     name=r['view'];v=views[name];sl=slice(v['start'],v['stop']);ids=r['ids'];pr=np.asarray(pred[ids]);phys=a['physical'][sl];allp=np.asarray(pred[sl][phys]);ordered=np.sort(allp);n=len(allp)
     # Strict-above rank with tied interval; no arbitrary tie ordering.
     ranks=n-np.searchsorted(ordered,pr,side='right')+1;worst=n-np.searchsorted(ordered,pr,side='left')
     alerts=int((pr>=threshold).sum());best=int(ranks.min());worstbest=int(worst[np.argmax(pr)])
     row=dict(seed=seed,arm=arm,split=split,view=name,source_view=r['source_view'],host=r['host'],family=r['family'],recipe=r['recipe'],region_nodes=len(ids),old_trusted_nodes=r['old_trusted'],new_eval_nodes=r['new_trusted'],threshold=threshold,
       alert_nodes=alerts,node_fpr=alerts/len(ids),region_alarm=int(alerts>0),risk_mean=float(pr.mean()),risk_max=float(pr.max()),best_rank=best,best_rank_fraction=best/n,best_tie_worst_rank=worstbest,physical_view_nodes=n,
       top1_possible=int(best<=int(np.ceil(.01*n))),top1_guaranteed=int(worstbest<=int(np.ceil(.01*n))),top5_possible=int(best<=int(np.ceil(.05*n))),top5_guaranteed=int(worstbest<=int(np.ceil(.05*n))))
     bg=a['new'][sl]&(a['y'][sl]==0);bg=bg.copy();bg[ids-v['start']]=False
     row.update(background_nodes=int(bg.sum()),background_fpr=mean(pred[sl][bg]>=threshold))
     scores.append(row)
     for j,p,ra,rw in zip(ids,pr,ranks,worst):nodes.append(dict(seed=seed,arm=arm,split=split,view=name,source_view=r['source_view'],split_row=int(j),score=float(p),label=int(a['y'][j]),old_trust=bool(a['trusted'][j]),new_eval_trust=bool(a['new'][j]),rank_best=int(ra),rank_worst=int(rw),alert=bool(p>=threshold)))
     if name in pairs:
      t=pairs[name];tp=np.asarray(pred[t['ids']]);pairrows.append(dict(seed=seed,arm=arm,split=split,control_source=r['source_view'],trojan_source=t['source'],control_view=name,trojan_view=t['view'],control_nodes=len(ids),trojan_nodes=len(tp),control_max=float(pr.max()),trojan_max=float(tp.max()),margin=float(tp.max()-pr.max()),correct_order=float(tp.max()>pr.max())+.5*float(tp.max()==pr.max()),control_alarm=int(pr.max()>=threshold),trojan_hit=int(tp.max()>=threshold),joint_success=int(pr.max()<threshold<=tp.max()),both_low=int(tp.max()<threshold and pr.max()<threshold),both_high=int(tp.max()>=threshold and pr.max()>=threshold),pair_kind='same-host/source-template/recipe; not newly SAT-certified'))
 groups=collections.defaultdict(list)
 for x in scores:groups[(x['seed'],x['arm'],x['split'],x['source_view'])].append(x)
 obj=[]
 for (seed,arm,split,src),a in groups.items():
  row=dict(seed=seed,arm=arm,split=split,source_view=src,host=a[0]['host'],family=a[0]['family'],views=len(a),region_node_occurrences=sum(x['region_nodes'] for x in a),alarm_views=sum(x['region_alarm'] for x in a),source_any_alarm=int(any(x['region_alarm'] for x in a)),view_macro_node_fpr=mean([x['node_fpr'] for x in a]),view_macro_maxrisk=mean([x['risk_max'] for x in a]),view_macro_best_rank_fraction=mean([x['best_rank_fraction'] for x in a]),top1_possible_views=sum(x['top1_possible'] for x in a),top1_guaranteed_views=sum(x['top1_guaranteed'] for x in a),top5_guaranteed_views=sum(x['top5_guaranteed'] for x in a))
  obj.append(row)
 totals=[]
 for split in ['val','test']:
  for arm in ['A','B']:
   for seed in [42,1,2]:
    a=[x for x in obj if (x['split'],x['arm'],x['seed'])==(split,arm,seed)];b=[x for x in pairrows if (x['split'],x['arm'],x['seed'])==(split,arm,seed)]
    # Pair metrics aggregate within source before across independent source objects.
    pg=collections.defaultdict(list)
    for x in b:pg[x['control_source']].append(x)
    totals.append(dict(seed=seed,arm=arm,split=split,sources=len(a),source_any_alarm=sum(x['source_any_alarm'] for x in a),source_macro_node_fpr=mean([x['view_macro_node_fpr'] for x in a]),source_macro_best_rank_fraction=mean([x['view_macro_best_rank_fraction'] for x in a]),sources_top1_possible=sum(x['top1_possible_views']>0 for x in a),sources_top1_guaranteed=sum(x['top1_guaranteed_views']>0 for x in a),paired_sources=len(pg),pair_correct_order=mean([mean([x['correct_order'] for x in v]) for v in pg.values()]),pair_joint_success=mean([mean([x['joint_success'] for x in v]) for v in pg.values()]),pair_both_low=mean([mean([x['both_low'] for x in v]) for v in pg.values()])))
 dump('region_per_view.csv',scores);dump('region_nodes.csv',nodes);dump('per_source_object.csv',obj);dump('trojan_control_pairs.csv',pairrows);dump('summary.csv',totals);dump('pair_exclusions.csv',missing);dump('missing_predictions.csv',missing_predictions);dump('prediction_prechecks.csv',prechecks)
 info=dict(time=datetime.datetime.now().astimezone().isoformat(),models='latest runs (new mask), A/B seeds42/1/2; historical variants excluded',training_forward_calls=0,inference_forward_calls=0,new_sat_calls=0,
   region_views=len(regions),evaluated_region_views=len({r['view'] for r in scores}),paired_views=len(pairs),score_records=len(scores),source_records=len(obj),inputs=bindings,coordinate='global old_start + ordered node_names -> split start; physical only',threshold='existing saved seed*_AB.json threshold; reproduced saved per-view trusted FPR',limitations=['train arrays absent; no model recomputation','retention is trace not functional certification','paired max-risk depends on size; raw size recorded','val was used for selection and threshold calibration; only test is holdout'])
 for p in [P/'input_contract.json',F/'data/processed/node_names_trans.txt',OUT.parent/'control_retention_20261104/cohort_candidates.csv']:
  bindings[str(p.relative_to(ROOT))]=sha(p)
 for split in ['val','test']:bindings[str((H/f'new_mask_{split}.npy').relative_to(ROOT))]=sha(H/f'new_mask_{split}.npy')
 (OUT/'audit.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({k:v for k,v in info.items() if k!='inputs'},ensure_ascii=False,indent=2))
 for x in totals:print(x)
if __name__=='__main__':main()
