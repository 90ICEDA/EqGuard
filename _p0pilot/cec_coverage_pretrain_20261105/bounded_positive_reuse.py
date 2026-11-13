"""Bounded recovery of old positive locators with full PI/Q enumeration, no SAT."""
from pathlib import Path
import collections,csv,json,sys
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;T=R/'10.15/06_统一评测协议/N4_三向泛化/tables'
sys.path.insert(0,str(R/'_p0pilot/cec_cone_audit_20261105'));from audit import read,rows,sha,ident,cone,SCHEMA
sys.path.insert(0,str(R/'_p0pilot/cec_cone_expand_20261105'));from expand import enumerate_pair
import native as N
def main():
 assert not (O/'BOUNDED_POSITIVE_COMPLETE.json').exists()
 contract=read(R/'_p0pilot/control_boundary_v3_20261104/input_contract.json');vm={v['view']:(key,v) for key,q in contract['shared_inputs'].items() if key in ['trans_train','trans_val'] for v in q['views']};meta={x['view']:x for x in rows(R/'generate_trans/folds/hosts_bt31/views_meta.csv')}
 names=[x.strip().lstrip('\\') for x in (R/'generate_trans/folds/hosts_bt31/data/processed/node_names_trans.txt').read_text(encoding='utf-8').splitlines()]
 bykey=collections.defaultdict(list);raws={};maps={};bindings={};arrays={};drivers={};layouts={}
 for key in ['trans_train','trans_val']:
  folder=R/contract['shared_inputs'][key]['folder'];arrays[key]={n:np.load(folder/(n+'.npy'),mmap_mode='r') for n in ['y','trusted','physical']}
 for dirname in ['sat_pair_round10','sat_pair_round11','sat_pair_round12']:
  for path in (T/dirname/'structures').glob('*/raw.json'):
   view=path.parent.name
   if view not in vm or view in raws:continue
   source=R/'generate_trans/folds/hosts_bt31/trans'/(view+'.v');s=read(path.parent/'source.json');assert s['raw_sha']==sha(path) and s['source_sha']==sha(source)
   m=next(iter(read(path)['modules'].values()));raws[view]=m;bindings[view]=dict(raw_path=str(path.relative_to(R)),raw_sha=s['raw_sha'],source_sha=s['source_sha']);layouts[view]=N.layout(m)
   key,v=vm[view];maps[view]={n:v['start']+j for j,n in enumerate(names[v['old_start']:v['old_stop']])};dm=collections.defaultdict(list)
   for name,g in m['cells'].items():
    if g['type'] in SCHEMA:pin=SCHEMA[g['type']][0];dm[g['connections'][pin][0]].append((name,pin))
   drivers[view]=dm;mm=meta[view];bykey[mm['host'],mm['inst_id'],mm['op'].removeprefix('ys_')].append(view)
 known=read(O/'candidate_pairs.json');knownids={p['pair_id'] for p in known};pool={};scanned=0
 for q in rows(T/'node_pairs_sat_node.csv'):
  scanned+=1
  if q['status']!='proved' or q['inst_a']!=q['inst_b']:continue
  for va in bykey.get((q['host'],q['inst_a'],q['recipe_a']),[]):
   for vb in bykey.get((q['host'],q['inst_b'],q['recipe_b']),[]):
    if va==vb or meta[va]['src_view']!=meta[vb]['src_view'] or vm[va][0]!=vm[vb][0] or layouts[va]!=layouts[vb]:continue
    bits=[];roots=[]
    for view,net in [(va,q['net_a']),(vb,q['net_b'])]:
     m=raws[view];net=net if net in m['netnames'] else net.lstrip('\\')
     bs=m['netnames'].get(net,{}).get('bits',[])
     if len(bs)!=1 or len(drivers[view].get(bs[0],[]))!=1:break
     cell,pin=drivers[view][bs[0]][0]
     if cell not in maps[view]:break
     i=maps[view][cell];ar=arrays[vm[view][0]]
     if not (ar['physical'][i] and ar['trusted'][i] and ar['y'][i]==1):break
     bits.append(bs[0]);roots.append((cell,pin,i))
    if len(bits)!=2:continue
    ctx=ident(dict(PI=layouts[va][0],physicalQ=layouts[va][1],free=True));source=meta[va]['src_view'];ids=[ident([bindings[v]['source_sha'],rr[0],rr[1]]) for v,rr in zip([va,vb],roots)];pid=ident([source,ctx,sorted(ids)])
    if pid in knownids or pid in pool:continue
    cc=[]
    for view,b,rr,cid in zip([va,vb],bits,roots,ids):
     z=cone(raws[view],b,maps[view],bindings[view]['raw_sha']);z.update(cone_id=cid,view=view,split=vm[view][0].split('_')[1],root_row=rr[2],output_cell=rr[0],output_pin=rr[1],**bindings[view]);cc.append(z)
    if any(z['errors'] or z['unmapped_members'] or not z['nontrivial'] for z in cc):continue
    width=len({tuple(l[:3]) for z in cc for l in z['leaves']});pool[pid]=dict(pair_id=pid,source_object=source,split=cc[0]['split'],context_id=ctx,cones=cc,width=width,views=[va,vb],legacy_status_locator_only=True)
 # Selection depends on coverage, boundary width and frozen hash, never model scores.
 alreadypositive={p['source_object'] for p in known if all(e['trusted'] and e['label']==1 for e in p['root_endpoints'])}
 ordered=sorted(pool.values(),key=lambda p:(p['split']!='val',p['source_object'] in alreadypositive,p['width']>12,ident(['bounded_positive_v1',p['pair_id']])))
 selected=[];per_source=collections.Counter()
 for p in ordered:
  if len(selected)>=24:break
  if per_source[p['source_object']]>=4:continue
  selected.append(p);per_source[p['source_object']]+=1
 out=[];accepted=[];newcones=[]
 for p in selected:
  cc=p['cones'];result=enumerate_pair([raws[v] for v in p['views']],cc,12)
  status='proved_complete_enumeration' if result.get('equal') is True and result.get('nonconstant') else 'refuted' if result.get('equal') is False else 'deferred_width_or_constant'
  out.append(dict(pair_id=p['pair_id'],split=p['split'],source=p['source_object'],inputs=p['width'],status=status,patterns=result['patterns']))
  if status!='proved_complete_enumeration':continue
  ends=[dict(view=z['view'],row=z['root_row'],cell=z['output_cell'],pin=z['output_pin'],label=1,trusted=True,physical=True) for z in cc]
  accepted.append(dict(pair_id=p['pair_id'],source_object=p['source_object'],split=p['split'],context_id=p['context_id'],left_cone=cc[0]['cone_id'],right_cone=cc[1]['cone_id'],origins=['label_assisted_legacy_locator_current_full_enumeration'],proof_ids=[],enum=result,root_endpoints=ends,labels_used_for_selection=True,labels_used_for_function_acceptance=False,functional_auxiliary_data_eligible=True,current_detection_training_allowed=False,detection_stability_diagnostic_eligible=True))
  newcones.extend(cc)
 def wr(n,z):
  path=O/n;assert not path.exists();path.write_text(json.dumps(z,ensure_ascii=False,indent=2),encoding='utf-8')
 wr('bounded_positive_pairs.json',accepted);wr('bounded_positive_cones.json',newcones);wr('bounded_positive_ledger.json',out)
 wr('BOUNDED_POSITIVE_COMPLETE.json',dict(training=0,model_forward=0,new_SAT_queries=0,legacy_rows_scanned=scanned,legacy_proved_not_reused_as_proof=True,positive_current_candidates=len(pool),selected=len(selected),accepted=len(accepted),accepted_splits=dict(collections.Counter(p['split'] for p in accepted)),statuses=dict(collections.Counter(p['status'] for p in out)),selection='val first, uncovered positive sources first, <=12 inputs first, frozen hash;max24 and4/source;no predictions/test',total_patterns=sum(p['patterns'] for p in out),remaining_width_capped=sum(p['width']>12 for p in ordered),candidate_inventory=[{k:v for k,v in p.items() if k!='cones'} for p in ordered]))
 print({k:v for k,v in read(O/'BOUNDED_POSITIVE_COMPLETE.json').items() if k!='candidate_inventory'},flush=True)
if __name__=='__main__':main()
