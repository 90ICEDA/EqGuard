"""Offline validation-only single-threshold guards; no test threshold fitting or model calls."""
from pathlib import Path
import csv,json,collections
import numpy as np
O=Path(__file__).resolve().parent;R=O.parents[1];B=R/'_p0pilot/control_v3_eligible_20261104'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def dump(n,a):
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(a[0]));w.writeheader();w.writerows(a)
def mean_view_recall(aa,score_key,cutoff):
 groups=collections.defaultdict(list)
 for x in aa:groups[x['view']].append(float(x[score_key])>=cutoff)
 return float(np.mean([np.mean(x) for x in groups.values()]))
def max_threshold(aa,target):
 # Validation only. Weights exactly reproduce the macro recall over nonempty views in this subset.
 if target<=0:return float('inf')
 counts=collections.Counter(x['view'] for x in aa);weights=np.array([1/(len(counts)*counts[x['view']]) for x in aa]);scores=np.array([float(x['C_score']) for x in aa]);order=np.argsort(-scores,kind='stable');acc=np.cumsum(weights[order]);j=min(int(np.searchsorted(acc,target-1e-12,side='left')),len(order)-1);return float(scores[order[j]])
def main():
 aa=[x for x in rows(O/'positive_node_changes.csv') if x['domain']=='trans' and x['operation']=='val_recall80'];normal=rows(B/'normal_node_deltas.csv');out=[];cuts=[];classout=[]
 for seed in [42,1,2]:
  val=[x for x in aa if int(x['seed'])==seed and x['split']=='val'];hcut=float(val[0]['threshold_H']);ccut=float(val[0]['threshold_C']);target=mean_view_recall(val,'H_score',hcut);macrocut=min(ccut,max_threshold(val,target));rolecuts={}
  for cl in ['trigger','payload','payload_select','output_hijack']:
   rr=[x for x in val if x['role_class']==cl]
   if rr:rolecuts[cl]=max_threshold(rr,mean_view_recall(rr,'H_score',hcut))
  rolecut=min([ccut]+list(rolecuts.values()));modes={'H_original':hcut,'C_original':ccut,'C_validation_macro_guard':macrocut,'C_validation_role_guard':rolecut}
  cuts.append(dict(seed=seed,H_cutoff=hcut,C_cutoff=ccut,validation_macro_guard_cutoff=macrocut,validation_role_guard_cutoff=rolecut,validation_role_caps=json.dumps({k:(v if np.isfinite(v) else None) for k,v in rolecuts.items()}),missing_validation_roles='|'.join(cl for cl in ['trigger','payload','payload_select','output_hijack'] if cl not in rolecuts)))
  assert mean_view_recall(val,'C_score',macrocut)>=target-1e-12
  for cl in rolecuts:
   rr=[x for x in val if x['role_class']==cl];assert mean_view_recall(rr,'C_score',rolecut)>=mean_view_recall(rr,'H_score',hcut)-1e-12
  for sp in ['val','test']:
   rr=[x for x in aa if int(x['seed'])==seed and x['split']==sp]
   for mode,cutoff in modes.items():
    key='H_score' if mode=='H_original' else 'C_score';arm='H' if mode=='H_original' else 'C';pred=np.load(B/f'seed{seed}'/arm/('trans_'+sp+'_scores.npy'),mmap_mode='r');ng=collections.defaultdict(list)
    for x in normal:
     if int(x['seed'])==seed and x['operation']=='val_recall80' and x['domain']=='trans' and x['split']==sp:ng[(x['source'],x['view'])].append(float(pred[int(x['row'])])>=cutoff)
    sg=collections.defaultdict(list)
    for (source,view),v in ng.items():sg[source].append(float(np.mean(v)))
    out.append(dict(seed=seed,split=sp,mode=mode,cutoff=cutoff,actual_T_macro_recall=mean_view_recall(rr,key,cutoff),normal_region_source_FPR=float(np.mean([np.mean(v) for v in sg.values()])),threshold_fit='validation only; one global constant; source roles not used at inference'))
    for cl in ['trigger','payload','payload_select','output_hijack']:
     cc=[x for x in rr if x['role_class']==cl]
     if cc:classout.append(dict(seed=seed,split=sp,mode=mode,role_class=cl,actual_class_view_macro_recall=mean_view_recall(cc,key,cutoff),nodes=len(cc)))
 dump('validation_guard_thresholds.csv',cuts);dump('calibration_diagnostic.csv',out);dump('calibration_role_recalls.csv',classout)
 ag=[]
 for sp in ['val','test']:
  for mode in ['H_original','C_original','C_validation_macro_guard','C_validation_role_guard']:
   rr=[x for x in out if x['split']==sp and x['mode']==mode];ag.append(dict(split=sp,mode=mode,actual_T_macro_recall=float(np.mean([x['actual_T_macro_recall'] for x in rr])),normal_region_source_FPR=float(np.mean([x['normal_region_source_FPR'] for x in rr]))))
 dump('calibration_summary.csv',ag);(O/'CALIBRATION_COMPLETE.json').write_text(json.dumps(dict(training=0,SAT=0,model_forward=0,thresholds_fit_on='validation only',one_global_threshold_per_model=True,role_names_not_required_at_inference=True,payload_select_has_no_validation_support=all(x['missing_validation_roles']=='payload_select' for x in cuts),not_selected_for_deployment=True,test_is_exploratory=True),ensure_ascii=False,indent=2),encoding='utf-8');print(ag)
if __name__=='__main__':main()
