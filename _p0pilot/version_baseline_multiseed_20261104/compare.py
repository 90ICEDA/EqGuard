"""Three-seed paired version comparison; no training/model calls in analysis."""
from pathlib import Path
import csv,json,hashlib,collections
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;B=R/'_p0pilot/control_fair200_20261104';S=R/'_p0pilot/version_baseline_seed42_20261104'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(n,a):
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(a[0]));w.writeheader();w.writerows(a)
def main():
 assert read(O/'TRAINING_COMPLETE.json')['new_runs']==2;code=(S/'adapter_snapshot.py').read_text(encoding='utf-8');assert code==(B/'region_diagnostic_adapter.py').read_text(encoding='utf-8');g=[];reg=[];source=[];role=[];bindings={}
 for seed in [42,1,2]:
  old=read(B/f'seed{seed}/H/EVALUATED.json');v3root=S if seed==42 else O;new=read(v3root/f'seed{seed}/H/EVALUATED.json');assert old['init_sha']==new['init_sha']==sha(B/f'init_s{seed}.pt')
  for version,root,ev in [('v2',B,old),('v3',v3root,new)]:
   run=root/f'seed{seed}'/'H';hist=read(run/'history.json');sel=read(run/'SELECTED.json');assert [x['update'] for x in hist]==list(range(1,201));assert sel['updates']==200 and sel['score']==max(x['val_ap'] for x in hist if 'val_ap' in x);assert sha(run/'best.pt')==ev['checkpoint_sha']
   for name,h in ev['prediction_sha'].items():assert sha(run/(name+'_scores.npy'))==h;bindings[str((run/(name+'_scores.npy')).relative_to(R))]=h
   bindings[str((run/'EVALUATED.json').relative_to(R))]=sha(run/'EVALUATED.json')
   for op in ['historical_fpr5','val_recall80','val_recall90']:
    if seed==42:out=S/'diagnostics'/version/op
    elif version=='v2':out=run/op
    else:
     out=O/'diagnostics'/f'seed{seed}'/version/op;out.mkdir(parents=True,exist_ok=True);ns={'__file__':str(O/'adapter_snapshot.py'),'__name__':'offline_region','SEED':seed,'RUN':run,'MODE':op};exec(compile(code,str(O/'adapter_snapshot.py'),'exec'),ns);ns['O']=out;ns['main']()
    for filename,dest in [('summary.csv',reg),('per_source.csv',source),('role_pairs_per_source.csv',role)]:
     for x in rows(out/filename):assert int(x['seed'])==seed;dest.append(dict(version=version,operation=op,**x))
    for sp in ['val','test']:g.append(dict(seed=seed,version=version,operation=op,split=sp,selected_update=ev['selected']['epoch'],threshold=ev['thresholds'][op],**ev[sp][op]['trusted']))
 (O/'adapter_snapshot.py').write_text(code,encoding='utf-8');dump('per_seed_metrics.csv',g);dump('region_summary.csv',reg);dump('source_details.csv',source);dump('role_pairs_per_source.csv',role)
 delta=[]
 for seed in [42,1,2]:
  for sp in ['val','test']:
   for op in ['historical_fpr5','val_recall80','val_recall90']:
    a=next(x for x in g if (x['seed'],x['version'],x['split'],x['operation'])==(seed,'v2',sp,op));b=next(x for x in g if (x['seed'],x['version'],x['split'],x['operation'])==(seed,'v3',sp,op));ar=next(x for x in reg if int(x['seed'])==seed and (x['version'],x['domain'],x['split'],x['operation'])==('v2','trans',sp,op));br=next(x for x in reg if int(x['seed'])==seed and (x['version'],x['domain'],x['split'],x['operation'])==('v3','trans',sp,op))
    d=dict(seed=seed,split=sp,operation=op)
    for k in ['ap','auc','r1','r5','recall','control_fpr']:d['v2_'+k]=a[k];d['v3_'+k]=b[k];d['delta_'+k]=b[k]-a[k]
    for k in ['source_mean_node_fpr','pair_joint_success','pair_correct_order','source_mean_best_rank_fraction']:d['v2_'+k]=float(ar[k]);d['v3_'+k]=float(br[k]);d['delta_'+k]=float(br[k])-float(ar[k])
    delta.append(d)
 dump('paired_global_deltas.csv',delta)
 agg=[]
 for sp in ['val','test']:
  for op in ['historical_fpr5','val_recall80','val_recall90']:
   for ver in ['v2','v3']:
    aa=[x for x in g if (x['version'],x['split'],x['operation'])==(ver,sp,op)];bb=[x for x in reg if (x['version'],x['domain'],x['split'],x['operation'])==(ver,'trans',sp,op)];r=dict(split=sp,operation=op,version=ver,seeds=3)
    for k in ['ap','auc','r1','r5','recall','control_fpr']:r[k+'_mean']=float(np.mean([x[k] for x in aa]));r[k+'_sd']=float(np.std([x[k] for x in aa],ddof=1))
    for k in ['source_mean_node_fpr','pair_joint_success','pair_correct_order','source_mean_best_rank_fraction']:r[k+'_mean']=float(np.mean([float(x[k]) for x in bb]))
    agg.append(r)
 dump('aggregate.csv',agg)
 so=[]
 for sp in ['val','test']:
  for op in ['historical_fpr5','val_recall80','val_recall90']:
   for src in sorted({x['source_view'] for x in source if x['domain']=='trans' and x['split']==sp}):
    aa=[x for x in source if x['domain']=='trans' and x['split']==sp and x['operation']==op and x['source_view']==src];v2={int(x['seed']):x for x in aa if x['version']=='v2'};v3={int(x['seed']):x for x in aa if x['version']=='v3'};assert v2.keys()==v3.keys()=={42,1,2}
    h=float(np.mean([float(x['view_mean_node_fpr']) for x in v2.values()]));j=float(np.mean([float(x['view_mean_node_fpr']) for x in v3.values()]));so.append(dict(split=sp,operation=op,source=src,v2_fpr=h,v3_fpr=j,delta_fpr=j-h,seeds_improved=sum(float(v3[s]['view_mean_node_fpr'])<float(v2[s]['view_mean_node_fpr']) for s in v2)))
 dump('source_averages.csv',so)
 stability={}
 for sp in ['val','test']:
  aa=[x for x in delta if x['split']==sp and x['operation']=='historical_fpr5'];ds=np.array([x['delta_ap'] for x in aa]);stability[sp]=dict(AP_improved_seeds=int((ds>0).sum()),AP_delta_mean=float(ds.mean()),AP_delta_sd=float(ds.std(ddof=1)),min_AP_delta=float(ds.min()),max_AP_delta=float(ds.max()))
 for p,h in read(B/'manifest.json')['files'].items():assert sha(B/p)==sha(O/p)==h,p
 result=dict(new_runs=2,new_updates=400,total_v3_seeds=[42,1,2],v2_all_reused=True,v3_seed42_reused=True,SAT=0,region_weights_changed=False,pool_changed=False,old_H_schedule=True,stability=stability,prediction_bindings=bindings,limitations=['3 initialization seeds not independent hosts','test already inspected exploratory','actual recall differs under each validation-calibrated operating point','new233 pool not used; no role weight conclusions'])
 (O/'COMPARISON_COMPLETE.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(stability)
if __name__=='__main__':main()
