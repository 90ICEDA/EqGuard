"""Bounded label-assisted PO/D selection, existing whole proofs only; no SAT."""
from pathlib import Path
import sys,json,csv,re,collections
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent
sys.path.insert(0,str(R/'_p0pilot/cec_cone_audit_20261105'));from audit import read,rows,sha,ident,cone,SCHEMA,module
def main():
 assert not (O/'POSITIVE_SUPPLEMENT.json').exists();c=read(R/'_p0pilot/control_boundary_v3_20261104/input_contract.json');pairs=read(O/'pairs.json');cones={z['cone_id']:z for z in read(O/'cones.json')};proofs=read(O/'reused_proofs.json');plan=rows(O/'whole_proof_observation_sources.csv');byview={z['view']:z for z in cones.values()};vm={v['view']:(key,v) for key,q in c['shared_inputs'].items() for v in q['views'] if key.startswith('trans_')};meta={v['view']:v for v in rows(R/'generate_trans/folds/hosts_bt31/views_meta.csv')};names=[n.strip().lstrip('\\') for n in (R/'generate_trans/folds/hosts_bt31/data/processed/node_names_trans.txt').read_text(encoding='utf-8').splitlines()];raws={};maps={};arrays={};added=[];ledger=[];seen=set();qcert=[]
 allpairs={p['pair_id']:p for p in pairs}
 for g in plan:
  va,vb=g['view_a'],g['view_b'];key,v=vm[va];assert key==vm[vb][0] and not key.endswith('test');source=meta[va]['src_view'];pid=g['proof_id'];q=proofs[pid];model=(R/q['folder']/'model.v').read_text(encoding='utf-8');modnames=['left_design','right_design'] if q['args']=='-prove observation_diff 0' else ['design_ys_id','design_ys_abc'];terms=[];drivers=[]
  if key not in arrays:
   folder=R/c['shared_inputs'][key]['folder'];arrays[key]={n:np.load(folder/(n+'.npy'),mmap_mode='r') for n in ['y','trusted','physical']}
   for n in ['y','trusted','physical']:assert sha(folder/(n+'.npy'))==c['files'][str((folder/(n+'.npy')).relative_to(R))]
  for view,mn in zip([va,vb],modnames):
   if view not in raws:
    raws[view]=next(iter(read(R/byview[view]['raw_path'])['modules'].values()));_,item=vm[view];maps[view]={n:item['start']+j for j,n in enumerate(names[item['old_start']:item['old_stop']])}
   m=raws[view];dm={}
   for name,cell in m['cells'].items():
    if cell['type'] in SCHEMA:
     pin=SCHEMA[cell['type']][0];dm[cell['connections'][pin][0]]=name,pin
   drivers.append(dm);obs=re.search(r'assign obs\s*=\s*\{(.*?)\};',module(model,mn)).group(1);terms.append([z.strip() for z in obs.split(',')][::-1])
  eligible=[]
  for j,(aa,bb) in enumerate(zip(*terms)):
   if not(re.fullmatch(r'b\d+',aa) and re.fullmatch(r'b\d+',bb)):continue
   bits=[int(aa[1:]),int(bb[1:])]
   if any(b not in dm for b,dm in zip(bits,drivers)):continue
   ca,pa=drivers[0][bits[0]];cb,pb=drivers[1][bits[1]]
   if ca not in maps[va] or cb not in maps[vb]:continue
   ia,ib=maps[va][ca],maps[vb][cb];ar=arrays[key]
   if not(ar['physical'][ia] and ar['trusted'][ia] and ar['y'][ia]==1):continue
   eligible.append((ident(['positive_PO_D_v1',source,j]),j,bits,[(ca,pa,ia),(cb,pb,ib)]))
  for _,j,bits,roots in sorted(eligible)[:4]:
   cc=[]
   for view,b,(cell,pin,i) in zip([va,vb],bits,roots):
    z=cone(raws[view],b,maps[view],byview[view]['raw_sha']);assert not z['errors'] and not z['unmapped_members'] and z['nontrivial'];z.update(cone_id=ident([byview[view]['source_sha'],cell,pin]),view=view,source_sha=byview[view]['source_sha'],raw_path=byview[view]['raw_path'],split=key.split('_')[1],output_cell=cell,output_pin=pin,root_row=i);cc.append(z)
   # Existing dataset identities use canonical PI/Q layout, independent of class.
   sys.path.insert(0,str(R/'_p0pilot/round10_20261025'));import native as N
   assert N.layout(raws[va])==N.layout(raws[vb]);context=ident(dict(PI=N.layout(raws[va])[0],physicalQ=N.layout(raws[va])[1],free=True));pairid=ident([source,context,sorted(z['cone_id'] for z in cc)]);isnew=pairid not in allpairs
   if isnew:
    ends=[dict(view=view,row=i,cell=cell,pin=pin,label=int(arrays[key]['y'][i]),trusted=bool(arrays[key]['trusted'][i]),physical=bool(arrays[key]['physical'][i])) for view,(cell,pin,i) in zip([va,vb],roots)];diagnostic=all(x['trusted'] and x['physical'] for x in ends) and ends[0]['label']==ends[1]['label'];p=dict(pair_id=pairid,source_object=source,split=key.split('_')[1],context_id=context,left_cone=cc[0]['cone_id'],right_cone=cc[1]['cone_id'],origins=['label_assisted_positive_PO_D'],proof_ids=[pid],observations=[f'whole_observation_index:{j}'],enum=dict(method='not_enumerated_width_cap',inputs=len({tuple(l[:3]) for z in cc for l in z['leaves']}),patterns=0,equal=None),prior_existing=False,functional_auxiliary_data_eligible=True,current_detection_training_allowed=False,detection_stability_diagnostic_eligible=diagnostic,diagnostic_scope='same proved observation; positive label selected on source only; counterpart label independently audited',labels_used_for_function_acceptance=False,labels_used_for_selection=True,root_endpoints=ends);allpairs[pairid]=p;added.append(p)
    for z in cc:cones[z['cone_id']]=z
   else:
    p=allpairs[pairid];p['origins']=sorted(set(p['origins']+['label_assisted_positive_PO_D']));p['labels_used_for_selection']=True
   qcert.append(dict(pair_id=pairid,proof_id=pid,observation_index=j,root_a=bits[0],root_b=bits[1],actual_source_module=modnames[0],actual_partner_module=modnames[1],same_shared_env=True,new_pair=isnew));ledger.append(dict(source=source,split=key.split('_')[1],pair_id=pairid,source_label=1,observation_index=j,new_pair=isnew))
 primary=[p for p in allpairs.values() if p['proof_ids']];report=dict(training=0,model_forward=0,SAT=0,rule='at most4 source-positive observations per already-proved view pair by frozen hash; train/val only; class not used to accept equivalence',new_pairs=len(added),new_splits=dict(collections.Counter(p['split'] for p in added)),observations_checked=len(ledger),primary_pairs=len(primary),primary_splits=dict(collections.Counter(p['split'] for p in primary)),primary_positive_roots={s:sum(p['split']==s and p['root_endpoints'][0]['label']==1 for p in primary) for s in ['train','val']},primary_prediction_diagnostic=sum(p['detection_stability_diagnostic_eligible'] for p in primary),all_source_bound_existing_CEC=True,test_label_positions_used=False)
 for n,obj in [('final_pairs.json',list(allpairs.values())),('final_cones.json',list(cones.values())),('positive_observation_proof_certificates.json',qcert)]: (O/n).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
 with (O/'positive_selection_ledger.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(ledger[0]));w.writeheader();w.writerows(ledger)
 (O/'POSITIVE_SUPPLEMENT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(report,flush=True)
if __name__=='__main__':main()
