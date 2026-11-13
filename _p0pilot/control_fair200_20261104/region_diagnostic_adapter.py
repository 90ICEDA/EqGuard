from pathlib import Path
import json,csv,collections,sys,hashlib
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;F=R/'generate_trans/folds/hosts_bt31';P=R/'_p0pilot/round32_20261029';OLD=R/'_p0pilot/control_risk_20261104'
sys.path.insert(0,str(OLD.parent/'control_retention_20261104'));from audit import cells,norm
def read(p):return p.read_text(encoding='utf-8-sig')
def csvread(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def dump(n,a):
 if not a:return
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(a[0]));w.writeheader();w.writerows(a)
def mean(a):return float(np.mean(a)) if len(a) else None
def main():
 c=json.loads(read(P/'input_contract.json'));co=[r for r in csvread(OLD.parent/'control_retention_20261104/cohort_candidates.csv') if r['proposed_cohort']=='primary_candidate'];regions={r['view']:r for r in co}
 roles=[r for r in csvread(OLD/'trans_role_descendant_pairs_labelchecked.csv') if r['nodewise_training_candidate']=='True' and r['control_view'] in regions]
 ctx={};views={};need=collections.defaultdict(set)
 for key in ['orig_train','trans_train','trans_val','trans_test']:
  q=c['shared_inputs'][key];p=R/q['folder'];ctx[key]={k:np.load(p/(k+'.npy'),mmap_mode='r') for k in ['y','trusted','physical']}
  for v in q['views']:views[(key,v['view'])]=v
 for r in co:need[('trans_'+r['split'],r['view'])].update(r['target_instances'].split('|'))
 for r in roles:need[('trans_'+r['split'],r['trojan_view'])].update(r['trojan_targets'].split('|'))
 # Original control objects corresponding to the same eligible training sources.
 prov=collections.defaultdict(list)
 for p in (R/'generate_trans').glob('hosts*/*/provenance.json'):
  try:
   a=json.loads(read(p))
   if isinstance(a,list):
    for x in a:
     if x.get('view'):prov[x['view']].append(x)
  except (ValueError,OSError):pass
 for src in {r['source_view'] for r in co if r['split']=='train'}:
  sc,_=cells(F/'orig'/(src+'.v'));a=[d for d in prov[src] if d.get('new_gates') and all(norm(g) in sc for g in d['new_gates'])];assert a
  need[('orig_train',src)].update(map(norm,a[0]['new_gates']))
 idxmap={}
 for domain,namesfile in [('trans',F/'data/processed/node_names_trans.txt'),('orig',P/'orig_names/node_names_orig.txt')]:
  rr=sorted((views[k]['old_start'],views[k]['old_stop'],k) for k in need if k[0].startswith(domain));i=0
  with namesfile.open(encoding='utf-8') as f:
   for gid,line in enumerate(f):
    while i<len(rr) and gid>=rr[i][1]:i+=1
    if i==len(rr):break
    lo,hi,k=rr[i];name=norm(line)
    if gid>=lo and name in need[k]:idxmap[(k,name)]=views[k]['start']+gid-lo
 for k,ns in need.items():assert all((k,n) in idxmap for n in ns),(k,ns)
 rv=[];nr=[];pr=[]
 for seed in [SEED]:
  ev=json.loads(read(RUN/'EVALUATED.json'));th=ev['thresholds'][MODE]
  for key in ['orig_train','trans_train','trans_val','trans_test']:
   pred=np.load(RUN/(key+'_scores.npy'),mmap_mode='r');a=ctx[key];domain,split=key.split('_')
   assert len(pred)==len(a['y'])
   targets=[(r['view'],r['source_view'],r['target_instances'].split('|')) for r in co if key=='trans_'+r['split']] if domain=='trans' else [(k[1],k[1],sorted(ns)) for k,ns in need.items() if k[0]==key]
   for view,src,ns in targets:
    k=(key,view);v=views[k];sl=slice(v['start'],v['stop']);ids=np.array(sorted(idxmap[(k,n)] for n in ns),int);assert a['physical'][ids].all() and (a['y'][ids]==0).all() and a['trusted'][ids].all()
    pp=np.asarray(pred[ids]);allp=np.asarray(pred[sl][a['physical'][sl]]);ordered=np.sort(allp);n=len(allp);rank=n-np.searchsorted(ordered,pp,side='right')+1;worst=n-np.searchsorted(ordered,pp,side='left');j=int(np.argmax(pp));b=int(rank[j]);w=int(worst[j]);bg=a['trusted'][sl]&(a['y'][sl]==0);bg=bg.copy();bg[ids-v['start']]=False
    rv.append(dict(seed=seed,domain=domain,split=split,view=view,source_view=src,region_nodes=len(ids),alert_nodes=int((pp>=th).sum()),node_fpr=mean(pp>=th),region_alarm=int((pp>=th).any()),risk_mean=float(pp.mean()),risk_max=float(pp.max()),threshold=th,best_rank=b,best_rank_fraction=b/n,tie_worst_rank=w,top1_guaranteed=int(w<=int(np.ceil(.01*n))),top5_guaranteed=int(w<=int(np.ceil(.05*n))),view_physical_nodes=n,background_fpr=mean(pred[sl][bg]>=th),all_normal_labels_verified=True))
    for name in ns:
     i=idxmap[(k,name)];p=float(pred[i]);nr.append(dict(seed=seed,domain=domain,split=split,view=view,source_view=src,instance=name,split_row=i,score=p,alert=p>=th,label=int(a['y'][i]),trusted=bool(a['trusted'][i])))
   if domain=='trans':
    grouped=collections.defaultdict(list)
    for r in roles:
     if r['split']==split:grouped[r['control_view']].append(r)
    for cv,rr in grouped.items():
     cn={n for r in rr for n in r['control_targets'].split('|')};tn={n for r in rr for n in r['trojan_targets'].split('|')};tv=rr[0]['trojan_view']
     ci=np.array(sorted(idxmap[((key,cv),n)] for n in cn),int);ti=np.array(sorted(idxmap[((key,tv),n)] for n in tn),int)
     assert a['trusted'][ci].all() and a['trusted'][ti].all() and (a['y'][ci]==0).all() and (a['y'][ti]==1).all()
     cp=np.asarray(pred[ci]);tp=np.asarray(pred[ti]);cm=float(cp.max());tm=float(tp.max())
     pr.append(dict(seed=seed,split=split,control_source=rr[0]['control_source'],trojan_source=rr[0]['trojan_source'],control_view=cv,trojan_view=tv,source_role_occurrences=len(rr),control_nodes=len(ci),trojan_nodes=len(ti),control_max=cm,trojan_max=tm,margin=tm-cm,correct_order=float(tm>cm)+.5*float(tm==cm),control_alarm=int(cm>=th),trojan_hit=int(tm>=th),joint_success=int(cm<th<=tm),both_low=int(cm<th and tm<th),both_high=int(cm>=th and tm>=th),threshold=th,control_node_fpr=mean(cp>=th),trojan_node_recall=mean(tp>=th),mapping_scope='matched source roles; descendant sets; not full functional equality'))
 ob=[];groups=collections.defaultdict(list)
 for r in rv:groups[(r['seed'],r['domain'],r['split'],r['source_view'])].append(r)
 for (seed,domain,split,src),aa in groups.items():
  ob.append(dict(seed=seed,domain=domain,split=split,source_view=src,views=len(aa),region_node_occurrences=sum(x['region_nodes'] for x in aa),alarm_views=sum(x['region_alarm'] for x in aa),any_alarm=int(any(x['region_alarm'] for x in aa)),view_mean_node_fpr=mean([x['node_fpr'] for x in aa]),view_mean_best_rank_fraction=mean([x['best_rank_fraction'] for x in aa]),top1_views=sum(x['top1_guaranteed'] for x in aa),top5_views=sum(x['top5_guaranteed'] for x in aa),view_mean_background_fpr=mean([x['background_fpr'] for x in aa])))
 po=[];groups=collections.defaultdict(list)
 for r in pr:groups[(r['seed'],r['split'],r['control_source'])].append(r)
 for (seed,split,src),aa in groups.items():po.append(dict(seed=seed,split=split,control_source=src,views=len(aa),correct_order=mean([x['correct_order'] for x in aa]),joint_success=mean([x['joint_success'] for x in aa]),both_low=mean([x['both_low'] for x in aa]),both_high=mean([x['both_high'] for x in aa]),trojan_hit=mean([x['trojan_hit'] for x in aa]),trojan_node_recall=mean([x['trojan_node_recall'] for x in aa]),control_node_fpr=mean([x['control_node_fpr'] for x in aa])))
 total=[]
 for seed in [SEED]:
  for domain,split in [('orig','train'),('trans','train'),('trans','val'),('trans','test')]:
   aa=[x for x in ob if (x['seed'],x['domain'],x['split'])==(seed,domain,split)];bb=[x for x in po if x['seed']==seed and x['split']==split] if domain=='trans' else []
   total.append(dict(seed=seed,domain=domain,split=split,sources=len(aa),alarm_sources=sum(x['any_alarm'] for x in aa),source_mean_node_fpr=mean([x['view_mean_node_fpr'] for x in aa]),source_mean_best_rank_fraction=mean([x['view_mean_best_rank_fraction'] for x in aa]),sources_top1=sum(x['top1_views']>0 for x in aa),sources_top5=sum(x['top5_views']>0 for x in aa),pair_sources=len(bb),pair_correct_order=mean([x['correct_order'] for x in bb]),pair_joint_success=mean([x['joint_success'] for x in bb]),pair_both_low=mean([x['both_low'] for x in bb]),pair_trojan_recall=mean([x['trojan_node_recall'] for x in bb])))
 for n,a in [('region_per_view.csv',rv),('region_nodes.csv',nr),('per_source.csv',ob),('role_pairs_per_view.csv',pr),('role_pairs_per_source.csv',po),('summary.csv',total)]:dump(n,a)
 (O/'analysis_complete.json').write_text(json.dumps(dict(training=0,SAT=0,regions=len(regions),source_rows=len(ob),role_pair_rows=len(pr),seeds=[SEED]),indent=2),encoding='utf-8')
 for x in total:print(x)
if __name__=='__main__':main()
