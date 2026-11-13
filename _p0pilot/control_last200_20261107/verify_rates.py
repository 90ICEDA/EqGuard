"""Independent no-model audit of fixed200 operating metrics."""
import compare as C
import numpy as np,json,collections
O=C.O;R=C.R
def main():
 views=C.rows(R/'_p0pilot/control_loader_po_20261105/view_dictionary.csv');fc=C.read(R/'_p0pilot/control_boundary_v3_20261104/input_contract.json');checks=0
 for seed in C.SEEDS:
  f=O/f'seed{seed}';vr=C.rows(f/'per_view_scope_PO.csv');wr=C.rows(f/'whole_normal_views.csv');rr=C.rows(f/'role_per_view.csv');ra=C.rows(f/'frozen_role_assignments.csv')
  for key,q in fc['shared_inputs'].items():
   a={n:np.load(R/q['folder']/(n+'.npy'),mmap_mode='r') for n in ['y','trusted','physical']};mem=np.load(R/f'_p0pilot/control_loader_po_20261105/PO_membership_{key}.npz');role=np.full(len(a['y']),'unclassified',dtype='<U20')
   for r in ra:
    if r['key']==key:role[int(r['row'])]=r['role_class']
   for arm in C.ARMS:
    p=np.load(f/arm/(key+'_scores.npy'),mmap_mode='r');ev=C.read(f/arm/'EVALUATED.json')
    for r in vr:
     if r['key']!=key or r['arm']!=arm or r['PO_bin']!='all' or r['operation']!='val_recall80':continue
     v=next(v for v in views if v['key']==key and v['view']==r['view']);lo,hi=int(v['start']),int(v['physical_stop']);ids=np.arange(lo,hi);ids=ids[mem[r['scope']][ids]&a['physical'][ids]];y=a['y'][ids];hit=p[ids]>=ev['thresholds']['val_recall80']
     assert len(ids)==int(r['nodes'])
     for col,mask in [('FPR',y==0),('recall',y==1)]:
      if mask.any():assert abs(float(hit[mask].mean())-float(r[col]))<1e-12;checks+=1
    for r in wr:
     if r['key']!=key or r['arm']!=arm or r['operation']!='val_recall80':continue
     v=next(v for v in views if v['key']==key and v['view']==r['view']);ids=np.arange(int(v['start']),int(v['physical_stop']));ids=ids[a['physical'][ids]];hit=p[ids]>=ev['thresholds']['val_recall80'];assert int(hit.any())==int(r['alarm']) and int(hit.sum())==int(r['alarm_nodes']);checks+=1
    for r in rr:
     if r['key']!=key or r['arm']!=arm or r['operation']!='val_recall80':continue
     v=next(v for v in views if v['key']==key and v['view']==r['view']);ids=np.arange(int(v['start']),int(v['physical_stop']));ids=ids[a['trusted'][ids]&a['physical'][ids]&(a['y'][ids]==1)&(role[ids]==r['role_class'])];assert len(ids)==int(r['nodes']) and abs(float((p[ids]>=ev['thresholds']['val_recall80']).mean())-float(r['recall']))<1e-12;checks+=1
 v=C.read(O/'VERIFIED.json');v.update(independent_operating_metric_checks=checks,operating_metric_mode='val_recall80,all6splits15models,allreportedscopes and frozenroles',whole_alarm_population='allphysical,no labels promoted');(O/'VERIFIED.json').write_text(json.dumps(v,indent=2),encoding='utf-8');print('RATES_VERIFIED',checks)
if __name__=='__main__':main()
