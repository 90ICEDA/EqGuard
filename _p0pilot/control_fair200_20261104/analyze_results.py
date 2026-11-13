"""Reuse frozen region/role diagnostic; aggregate paired seeds and source objects."""
from pathlib import Path
import json,csv,hashlib,collections
import numpy as np
O=Path(__file__).resolve().parent;R=O.parents[1];B=R/'_p0pilot/control_best200_20261104'
def rows(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def dump(n,a):
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(a[0]));w.writeheader();w.writerows(a)
def main():
 complete=read(O/'TRAINING_COMPLETE.json');assert len(complete['runs'])==6
 original=(B/'analyze.py').read_text(encoding='utf-8');src=original
 changes={
  'for seed in [1,2]:':'for seed in [SEED]:',
  "ev=json.loads(read(O/f'seed{seed}/evaluation.json'));th=ev['threshold']":"ev=json.loads(read(RUN/'EVALUATED.json'));th=ev['thresholds'][MODE]",
  "pred=np.load(O/f'seed{seed}'/(key+'_scores.npy'),mmap_mode='r')":"pred=np.load(RUN/(key+'_scores.npy'),mmap_mode='r')",
  "seeds=[1,2]":"seeds=[SEED]",
 }
 for old,new in changes.items():assert old in src,old;src=src.replace(old,new)
 (O/'region_diagnostic_adapter.py').write_text(src,encoding='utf-8')
 summaries=[];sources=[];roles=[];globalrows=[]
 for seed in [42,1,2]:
  hh=read(O/f'seed{seed}/H/EVALUATED.json');cc=read(O/f'seed{seed}/C/EVALUATED.json');assert hh['init_sha']==cc['init_sha']
  for arm in ['H','C']:
   run=O/f'seed{seed}'/arm;ev=read(run/'EVALUATED.json')
   for mode in ['historical_fpr5','val_recall80','val_recall90']:
    out=run/mode;out.mkdir(exist_ok=True)
    ns={'__file__':str(O/'region_diagnostic_adapter.py'),'__name__':'offline_adapter','SEED':seed,'RUN':run,'MODE':mode};exec(compile(src,str(O/'region_diagnostic_adapter.py'),'exec'),ns);ns['O']=out;ns['main']()
    for name,dest in [('summary.csv',summaries),('per_source.csv',sources),('role_pairs_per_source.csv',roles)]:
     for x in rows(out/name):dest.append(dict(arm=arm,operation=mode,**x))
    for sp in ['val','test']:
     x=ev[sp][mode]['trusted'];globalrows.append(dict(seed=seed,arm=arm,operation=mode,split=sp,threshold=ev['thresholds'][mode],selected_update=ev['selected']['epoch'],**x))
 dump('region_summary.csv',summaries);dump('per_source_all.csv',sources);dump('role_pairs_per_source_all.csv',roles);dump('global_metrics.csv',globalrows)
 # Match source identities and seeds, then give every source equal weight.
 deltas=[]
 for seed in [42,1,2]:
  for mode in ['historical_fpr5','val_recall80','val_recall90']:
   for split in ['train','val','test']:
    for domain in (['orig','trans'] if split=='train' else ['trans']):
     ss=[x for x in sources if int(x['seed'])==seed and x['operation']==mode and x['split']==split and x['domain']==domain];h={x['source_view']:x for x in ss if x['arm']=='H'};c={x['source_view']:x for x in ss if x['arm']=='C'};assert h.keys()==c.keys()
     for source in sorted(h):
      a=h[source];b=c[source];deltas.append(dict(seed=seed,operation=mode,domain=domain,split=split,source=source,H_fpr=float(a['view_mean_node_fpr']),C_fpr=float(b['view_mean_node_fpr']),delta_fpr=float(b['view_mean_node_fpr'])-float(a['view_mean_node_fpr']),H_alarm=int(a['any_alarm']),C_alarm=int(b['any_alarm']),H_rank=float(a['view_mean_best_rank_fraction']),C_rank=float(b['view_mean_best_rank_fraction'])))
 dump('paired_source_deltas.csv',deltas)
 aggregate=[]
 for mode in ['historical_fpr5','val_recall80','val_recall90']:
  for sp in ['val','test']:
   for arm in ['H','C']:
    aa=[x for x in globalrows if x['operation']==mode and x['split']==sp and x['arm']==arm];bb=[x for x in summaries if x['operation']==mode and x['split']==sp and x['arm']==arm and x['domain']=='trans']
    rec=dict(operation=mode,split=sp,arm=arm,seeds=3)
    for k in ['ap','auc','r1','r5','recall','control_fpr']:rec[k+'_mean']=float(np.mean([x[k] for x in aa]));rec[k+'_sd']=float(np.std([x[k] for x in aa],ddof=1))
    for k in ['source_mean_node_fpr','pair_correct_order','pair_joint_success','pair_both_low','pair_trojan_recall']:rec[k+'_mean']=float(np.mean([float(x[k]) for x in bb]))
    aggregate.append(rec)
 dump('aggregate.csv',aggregate)
 # Final audit checks both budgets, paired per-node exposure, original files and finite outputs.
 m=read(O/'manifest.json');checks=[]
 for dm in ['orig','trans']:
  base=np.load(O/f'{dm}_base_mask.npy');c=np.load(O/f'{dm}_C_slots.npy');h=np.load(O/f'{dm}_H_slots.npy');assert c.shape==h.shape==(200,320) and not base[c].any() and not base[h].any()
  assert np.array_equal(np.sort(np.unique(c,return_counts=True)[1]),np.sort(np.unique(h,return_counts=True)[1]));checks.append(dict(domain=dm,equal_exposure=True,slots_each=64000))
 for p,h in m['inputs'].items():assert hashlib.sha256((R/p).read_bytes()).hexdigest()==h,p
 for seed in [42,1,2]:
  for arm in ['H','C']:
   run=O/f'seed{seed}'/arm;assert read(run/'SELECTED.json')['updates']==200
   for p in run.glob('*_scores.npy'):assert np.isfinite(np.load(p,mmap_mode='r')).all()
 (O/'ANALYSIS_COMPLETE.json').write_text(json.dumps(dict(runs=6,updates=1200,SAT=0,checks=checks,source_rows=len(sources),paired_deltas=len(deltas),diagnostic_original_sha=hashlib.sha256(original.encode()).hexdigest(),limitations=['same host dependence','previously inspected test exploratory','pooled validation recall calibration not guaranteed same test recall','C subset role supervision, not all-control removal','small budget fraction may limit detectable benefit']),ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(aggregate,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
