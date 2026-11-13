"""Freeze physical PO strata, existing region cohorts and train-only reference weights."""
from pathlib import Path
import numpy as np
import csv,json,collections
from supervision_loader import FiveGroupLoader,sha,read,archive
from po_policy import BIN_NAMES,bin_distance,boundary_checks
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;F=R/'generate_trans/folds/hosts_bt31';P=R/'_p0pilot/control_overall_contract_20261105';RET=R/'_p0pilot/control_retention_20261104'
def csvrows(p):return list(csv.DictReader(Path(p).open(encoding='utf-8-sig')))
def dump(name,rr):
 with (O/name).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def clean(n):return n.strip().lstrip('\\')
def main():
 assert (O/'LOADING_VERIFIED.json').exists();assert not (O/'PO_POLICY.json').exists();boundary_checks();l=FiveGroupLoader();c=l.feature_contract;meta=csvrows(F/'views_meta.csv');sourcekind={}
 for v in meta:
  if v['src_view'] in sourcekind:assert sourcekind[v['src_view']]==v['kind']
  sourcekind[v['src_view']]=v['kind']
 metadata={v['view']:v for v in meta};viewdict={};data={};need=collections.defaultdict(set);primary=csvrows(RET/'cohort_candidates.csv');co=[v for v in primary if v['proposed_cohort']=='primary_candidate'];roles=[v for v in csvrows(R/'_p0pilot/control_risk_20261104/trans_role_descendant_pairs_labelchecked.csv') if v['nodewise_training_candidate']=='True' and any(x['view']==v['control_view'] for x in co)];inputs={};prov={}
 for key,q in c['shared_inputs'].items():
  dm,split=key.split('_');a=l.arrays(dm,split);data[key]=a
  for vi,v in enumerate(q['views']):
   source=v['view'] if dm=='orig' else metadata[v['view']]['src_view'];viewdict[key,v['view']]=dict(key=key,view_id=vi,source=source,kind=sourcekind[source],host=source.split('__')[0],recipe='orig' if dm=='orig' else metadata[v['view']]['op'],**v)
 for v in co:
  key='trans_'+v['split'];assert (key,v['view']) in viewdict;need[key,v['view']].update(filter(None,v['target_instances'].split('|')))
  p=R/v['provenance'];inputs[str(p.relative_to(R))]=sha(p)
  if str(p) not in prov:prov[str(p)]=read(p)
  candidates=[d for d in prov[str(p)] if d.get('view')==v['source_view'] and d.get('new_gates')];assert candidates;assert len({tuple(sorted(d['new_gates'])) for d in candidates})==1
  need['orig_'+v['split'],v['source_view']].update(map(clean,candidates[0]['new_gates']))
 for v in roles:
  need['trans_'+v['split'],v['trojan_view']].update(filter(None,v['trojan_targets'].split('|')))
 resolved={};regions={key:np.zeros(len(a['y']),bool) for key,a in data.items()};partner={key:np.zeros(len(a['y']),bool) for key,a in data.items()}
 for dm,path in [('orig',R/'_p0pilot/round32_20261029/orig_names/node_names_orig.txt'),('trans',F/'data/processed/node_names_trans.txt')]:
  spans=sorted((viewdict[k]['old_start'],viewdict[k]['old_stop'],k) for k in need if k[0].startswith(dm));j=0
  with path.open(encoding='utf-8') as f:
   for gid,line in enumerate(f):
    while j<len(spans) and gid>=spans[j][1]:j+=1
    if j==len(spans):break
    lo,hi,key=spans[j];name=clean(line)
    if gid>=lo and name in need[key]:resolved[key,name]=viewdict[key]['start']+gid-lo
  inputs[str(path.relative_to(R))]=sha(path)
 for k,names in need.items():
  assert all((k,name) in resolved for name in names),(k,'unresolved old primary region')
  ids=np.array([resolved[k,n] for n in names],np.int64);a=data[k[0]];v=viewdict[k];assert a['trusted'][ids].all() and a['physical'][ids].all();expected=0 if v['kind']=='control' else 1;assert (a['y'][ids]==expected).all();(regions if expected==0 else partner)[k[0]][ids]=True
 policy_rows=[];population=[];availability=[];references=[];rowviews=[];keybins={};scopes={};role_records=[]
 scope_names=['trusted_all','normal_all','trojan_positive','trojan_background','normal_primary_added','trojan_partner_roles','normal_B','normal_M','normal_U']
 for key,a in data.items():
  dm,split=key.split('_');n=len(a['y']);physical=a['physical'];b=np.full(n,-9,np.int8);b[physical]=bin_distance(a['x39'][physical,30]);keybins[key]=b;viewid=np.full(n,-1,np.int16);normal=np.zeros(n,bool)
  for (kk,view),v in viewdict.items():
   if kk!=key:continue
   viewid[v['start']:v['stop']]=v['view_id'];normal[v['start']:v['physical_stop']]=v['kind']=='control'
   rowviews.append({k:v[k] for k in ['key','view_id','view','source','kind','host','recipe','start','stop','physical_stop','old_start','old_stop']})
  trusted=physical&a['trusted'];cat=np.full(n,-1,np.int8);partition_available=split!='test'
  if partition_available:
   p=P/('normal_'+key+'.npz');part=archive(p);cat[part['rows']]=part['category'];inputs[str(p.relative_to(R))]=sha(p)
  scope=[trusted,trusted&normal,trusted&~normal&(a['y']==1),trusted&~normal&(a['y']==0),regions[key],partner[key]]+[trusted&(cat==j) for j in range(3)];scopes[key]=dict(zip(scope_names,scope));assert not (regions[key]&~trusted).any()
  np.savez_compressed(O/('PO_membership_'+key+'.npz'),bin=b,view_id=viewid,normal=normal,**{name:mask for name,mask in zip(scope_names,scope)})
  for name,mask in zip(scope_names,scope):
   available=not(name.startswith('normal_') and name in ['normal_B','normal_M','normal_U'] and not partition_available);availability.append(dict(key=key,scope=name,available=available,reason='test B/M/U partition not audited; NA, not U' if not available else 'fixed trusted physical population; primary regions reuse historical eligible cohort'))
   if not available:continue
   for j,label in enumerate(BIN_NAMES):
    ids=np.flatnonzero(mask&(b==j));vv=set(map(int,viewid[ids]));src={viewdict[key,v['view']]['source'] for v in c['shared_inputs'][key]['views'] if v['start']<=v['stop'] and list(c['shared_inputs'][key]['views']).index(v) in vv};population.append(dict(key=key,scope=name,PO_bin=label,nodes=len(ids),positive=int((a['y'][ids]==1).sum()),negative=int((a['y'][ids]==0).sum()),views=len(vv),sources=len(src)))
   for (kk,view),v in viewdict.items():
    if kk!=key:continue
    for j,label in enumerate(BIN_NAMES):
     m=mask[v['start']:v['physical_stop']]&(b[v['start']:v['physical_stop']]==j);yy=a['y'][v['start']:v['physical_stop']][m];policy_rows.append(dict(key=key,scope=name,view=view,source=v['source'],host=v['host'],recipe=v['recipe'],PO_bin=label,nodes=len(yy),positive=int((yy==1).sum()),negative=int((yy==0).sum())))
  # A separate fixed train-only source-equal reference for FPR and recall.
  if split=='train':
   for name,metric in [('normal_primary_added','FPR'),('trojan_positive','recall')]:
    bysource=collections.defaultdict(list)
    for (kk,view),v in viewdict.items():
     if kk!=key:continue
     mask=scopes[key][name][v['start']:v['physical_stop']];bins=b[v['start']:v['physical_stop']][mask]
     if len(bins):bysource[v['source']].append(np.bincount(bins,minlength=5)/len(bins))
    assert bysource;weights=np.mean([np.mean(a,axis=0) for a in bysource.values()],axis=0);assert np.isclose(weights.sum(),1)
    for j,label in enumerate(BIN_NAMES):references.append(dict(domain=dm,scope=name,metric=metric,PO_bin=label,weight=float(weights[j]),source_objects=len(bysource),fitting_split='train_only'))
 for v in roles:
  key='trans_'+v['split'];nk=(key,v['control_view']);tk=(key,v['trojan_view']);ni=sorted({resolved[nk,n] for n in v['control_targets'].split('|') if n});ti=sorted({resolved[tk,n] for n in v['trojan_targets'].split('|') if n});nb=sorted(set(map(int,keybins[key][ni])));tb=sorted(set(map(int,keybins[key][ti])));role_records.append(dict(key=key,normal_source=v['control_source'],trojan_source=v['trojan_source'],normal_view=v['control_view'],trojan_view=v['trojan_view'],normal_source_gate=v['control_source_gate'],trojan_source_gate=v['trojan_source_gate'],normal_rows=ni,trojan_rows=ti,normal_PO_bins=nb,trojan_PO_bins=tb,homogeneous_same_bin=bool(len(nb)==len(tb)==1 and nb==tb),functional_SAT_proved=False,interpretation='manufacturing-role descendant sets, not Cartesian node pairs'))
 exposure=[]
 for dm in ['orig','trans']:
  key=dm+'_train';s=l.pools[dm];b=keybins[key];a=data[key];vm={v['view_id']:v for (kk,_),v in viewdict.items() if kk==key}
  for variant in l.contract['variants']:
   for arm in l.contract['arms']:
    counts={k:np.zeros(len(a['y']),np.int32) for k in ['positive','common','B','M','U']}
    for step in range(200):
     ss=l.step(dm,arm,step,variant);counts['positive'][ss.positive]+=1;counts['common'][ss.common_negative]+=1;cursor=0
     for block,nslots in l.contract['domains'][dm]['block_entries'].items():counts[block][ss.replacement_negative[cursor:cursor+nslots]]+=1;cursor+=nslots
    for block,w in counts.items():
     for j,label in enumerate(BIN_NAMES):
      ids=np.flatnonzero((w>0)&(b==j));exposure.append(dict(domain=dm,variant=variant,arm=arm,block=block,PO_bin=label,unique_nodes=len(ids),entries_200=int(w[ids].sum()),mean_raw_distance=float(np.average(a['x39'][ids,30],weights=w[ids])) if len(ids) else None))
 for name,rr in [('PO_population.csv',population),('PO_population_per_view.csv',policy_rows),('scope_availability.csv',availability),('train_reference_weights.csv',references),('training_PO_exposure.csv',exposure),('view_dictionary.csv',rowviews)]:dump(name,rr)
 (O/'ROLE_PO_PAIRS.json').write_text(json.dumps(role_records,ensure_ascii=False,indent=2),encoding='utf-8');dump('historical_region_status.csv',[{k:v[k] for k in ['split','view','source_view','status','proposed_cohort','source_added_nodes','target_nodes','unresolved_source_nodes','elimination_confirmed']} for v in primary])
 for p in [RET/'cohort_candidates.csv',R/'_p0pilot/control_risk_20261104/trans_role_descendant_pairs_labelchecked.csv',F/'views_meta.csv',O/'po_policy.py',O/'freeze_po.py'] :inputs[str(p.relative_to(R))]=sha(p)
 policy=dict(status='FROZEN_BEFORE_ANY_NEW_TRAINING_OR_PREDICTIONS',training=0,model_forward=0,SAT=0,predictions_read=0,bin_column=dict(index0=30,name='directed_distance_to_PO_driver',source='raw physical v3, before normalization',auxiliary_excluded=True),bins=[dict(id=j,name=name,rule=rule) for j,(name,rule) in enumerate(zip(BIN_NAMES,['d==-1','d==0','1<=d<=2','3<=d<=5','d>=6']))],threshold='one global trans-val calibration per arm/run per frozen rule, reused across all bins/sides; no per-bin threshold tuning',model_selection='unchanged legacy __inj trusted val mean AP every5; PO strata do not select model',metrics=dict(primary=['normal primary-added source-macro FPR and source any-alarm by bin','Trojan positive source-macro recall by bin'],secondary=['trusted mixed-label AP/AUC per bin only when both classes present','whole-view physical tie-worst risk rank','common-support/train-reference standardized FPR/recall']),aggregation='per view/bin ratios -> equal-view mean within source -> equal-source mean; empty cells NA with counts, never0; report eligible source denominator for every cell; fixed membership same all arms',standardization='fixed train-only, equal-source equal-view reference weights separately orig/trans for normal-primary FPR and Trojan-positive recall; if any positive-weight bin missing in eval return NA, no renormalization; not claim causal adjustment',primary_region_scope='reuse historical cohort primary_candidate with existing trusted physical0 labels; eliminated/unknown/partial held regions separately inventoried, not scored0; not all manufactured normal nodes',B_M_U_scope='train,val existing partition only; test partition unverified ->NA, do not label unknown asU',joint='full legacy manufacturing-role descendant sets; source-macro joint=(max normal<threshold<=maxTrojan); stratify by both PO-bin-set signatures, do not trim/split mixed sets or count Cartesian pairs; not SAT equivalence',comparisons=['GB-G0','GM-G0','GBM-GB','GBM-GM','GAll-G0','GAll-GBM','interaction GBM-GB-GM+G0'],paired_deltas='same source,bin,seed,threshold rule and membership; FPR lower/recall higher favorable; evaluate unweighted and standardized, report coverage differences; no source drop based on outcome',interpretation='descriptive location-stratified normal-label supervision effect, residual within-bin/other-feature confounding remains; test exploratory; no independent SAT/function contribution claim',inputs=inputs,supervision_contract_sha=sha(l.folder/'EXPERIMENT_CONTRACT.json'),feature_contract_sha=sha(R/'_p0pilot/control_boundary_v3_20261104/input_contract.json'))
 (O/'PO_POLICY.json').write_text(json.dumps(policy,ensure_ascii=False,indent=2),encoding='utf-8');print('Frozen PO populations:',len(population),'per-view cells',len(policy_rows),'role records',len(role_records),flush=True)
if __name__=='__main__':main()
