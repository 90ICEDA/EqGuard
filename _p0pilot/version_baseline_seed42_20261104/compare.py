"""Compare the single new seed42 run with exact reused v2/H evidence. No model calls."""
from pathlib import Path
import csv,json,hashlib,collections
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;B=R/'_p0pilot/control_fair200_20261104';V=R/'_p0pilot/control_boundary_v3_20261104'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(n,a):
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(a[0]));w.writeheader();w.writerows(a)
def main():
 assert (O/'TRAINING_COMPLETE.json').exists();old=read(B/'seed42/H/EVALUATED.json');new=read(O/'seed42/H/EVALUATED.json');assert old['init_sha']==new['init_sha']==sha(B/'init_s42.pt')
 assert (B/'run.py').read_text(encoding='utf-8').split('def main():')[0]==(B/'runner_initial_snapshot.py').read_text(encoding='utf-8').split('def main():')[0]
 oldhistory=read(B/'seed42/H/history.json');history=read(O/'seed42/H/history.json');assert [x['update'] for x in history]==[x['update'] for x in oldhistory]==list(range(1,201))
 for run in [B/'seed42/H',O/'seed42/H']:
  e=read(run/'EVALUATED.json');sel=read(run/'SELECTED.json');assert sha(run/'best.pt')==e['checkpoint_sha'];assert sel['score']==max(x['val_ap'] for x in read(run/'history.json') if 'val_ap' in x)
  for k,h in e['prediction_sha'].items():assert sha(run/(k+'_scores.npy'))==h,k
 for p,h in read(B/'manifest.json')['files'].items():assert sha(O/p)==sha(B/p)==h,p
 # Reuse identical offline region/role coordinate analysis on both frozen prediction sets.
 code=(B/'region_diagnostic_adapter.py').read_text(encoding='utf-8');region=[];source=[];role=[];globalrows=[]
 for version,run,ev in [('v2',B/'seed42/H',old),('v3',O/'seed42/H',new)]:
  for op in ['historical_fpr5','val_recall80','val_recall90']:
   out=O/'diagnostics'/version/op;out.mkdir(parents=True,exist_ok=True);ns={'__file__':str(O/'adapter_snapshot.py'),'__name__':'offline_region','SEED':42,'RUN':run,'MODE':op};exec(compile(code,str(O/'adapter_snapshot.py'),'exec'),ns);ns['O']=out;ns['main']()
   for name,dest in [('summary.csv',region),('per_source.csv',source),('role_pairs_per_source.csv',role)]:
    for x in rows(out/name):dest.append(dict(version=version,operation=op,**x))
   for sp in ['val','test']:globalrows.append(dict(version=version,split=sp,operation=op,seed=42,selected_update=ev['selected']['epoch'],threshold=ev['thresholds'][op],**ev[sp][op]['trusted']))
 (O/'adapter_snapshot.py').write_text(code,encoding='utf-8');dump('global_metrics.csv',globalrows);dump('region_summary.csv',region);dump('per_source.csv',source);dump('role_pairs_per_source.csv',role)
 groups=collections.defaultdict(dict)
 for x in source:groups[(x['operation'],x['domain'],x['split'],x['source_view'])][x['version']]=x
 delta=[]
 for (op,dm,sp,src),g in groups.items():
  a,b=g['v2'],g['v3'];delta.append(dict(operation=op,domain=dm,split=sp,source=src,v2_fpr=float(a['view_mean_node_fpr']),v3_fpr=float(b['view_mean_node_fpr']),delta_fpr=float(b['view_mean_node_fpr'])-float(a['view_mean_node_fpr']),v2_alarm=int(a['any_alarm']),v3_alarm=int(b['any_alarm']),v2_best_rank_fraction=float(a['view_mean_best_rank_fraction']),v3_best_rank_fraction=float(b['view_mean_best_rank_fraction'])))
 dump('source_deltas.csv',delta)
 # Source-preserving protocol invariants, without treating matching seed as bitwise deterministic CUDA training.
 result=dict(seed=42,v2_reused=True,new_training_runs=1,new_updates=200,SAT=0,initialization_identical=True,base_masks_and_H_sampling_identical=True,original_seed42_training_body_identical=True,only_changed='x39 column30 and its matching train-only normalization; feature folders changed with identical graph/labels',selected_v2=old['selected'],selected_v3=new['selected'],v2_test_AP=old['test']['historical_fpr5']['trusted']['ap'],v3_test_AP=new['test']['historical_fpr5']['trusted']['ap'],v2_val_AP=old['val']['historical_fpr5']['trusted']['ap'],v3_val_AP=new['val']['historical_fpr5']['trusted']['ap'],seed1_2_started=False,limitations=['single seed','previously inspected test exploratory','new233 pool and region reweighting not used','GPU aggregation not declared bitwise deterministic'])
 (O/'COMPARISON_COMPLETE.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(result)
if __name__=='__main__':main()
