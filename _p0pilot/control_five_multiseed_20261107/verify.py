"""Independent statistics.mean/stdev checks for all three-seed summary tables."""
from pathlib import Path
import collections,csv,hashlib,json,statistics
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def main():
 done=read(O/'AGGREGATION_COMPLETE.json');assert done['passed'];seeds={42,1,2};checks=0;maxerr=0
 for stem in ['macro','source','whole_macro','whole_source','role_macro','role_source','paired_source','rank_source','standardized','joint_source','KEY_RESULTS','PAIRED_KEY_DELTAS','PAIRED_ROLE_SOURCE']:
  raw=rows(O/(stem+'_all_seeds.csv'));summary=rows(O/(stem+'_meanSD.csv'));metrics=[k[:-5] for k in summary[0] if k.endswith('_mean')];keys=[k for k in summary[0] if k not in ['seeds'] and not k.endswith(('_improving_seeds','_worsening_seeds')) and not any(k.startswith(m+'_') for m in metrics)];groups=collections.defaultdict(list)
  for r in raw:groups[tuple(r[k] for k in keys)].append(r)
  assert len(groups)==len(summary),(stem,len(groups),len(summary))
  for row in summary:
   rr=groups[tuple(row[k] for k in keys)];assert len(rr)==3 and {int(x['seed']) for x in rr}==seeds
   for m in metrics:
    vals=[float(x[m]) for x in rr if x[m]!=''];assert len(vals) in [0,3];assert int(row[m+'_n_seeds'])==len(vals)
    if not vals:assert row[m+'_mean']==row[m+'_sampleSD']=='';continue
    mean,sd=statistics.mean(vals),statistics.stdev(vals)
    for x,col in [(mean,m+'_mean'),(sd,m+'_sampleSD')]:delta=abs(x-float(row[col]));maxerr=max(maxerr,delta);assert delta<1e-12,(stem,m,col,delta)
    checks+=1
 # paired differences use SAMEseed G0,etc beforeSD;do notsubtract armSDs.
 raw=rows(O/'KEY_RESULTS_all_seeds.csv');lookup={(r['seed'],r['arm'],r['key'],r['operation']):r for r in raw};paired=rows(O/'PAIRED_KEY_DELTAS_all_seeds.csv');delta_checks=0
 for r in paired:
  a,b=r['comparison'].split('-');x=lookup[r['seed'],a,r['key'],r['operation']];y=lookup[r['seed'],b,r['key'],r['operation']]
  for col in ['node_AP','normal_added_FPR','normal_all_FPR','all_positive_recall','trigger_recall','payload_recall','payload_select_recall','whole_normal_view_alarm','whole_normal_source_alarm']:
   if x[col]=='' or y[col]=='':assert r[col]==''
   else:assert abs(float(r[col])-(float(x[col])-float(y[col])))<1e-12;delta_checks+=1
 # Recheck distinct seed initializations,per-seed matching across5arms,sampler identity,and committed checkpoints.
 initial=[];initial_tensor_digests=[];sampler_digests=[]
 import torch
 for seed in [42,1,2]:
  f=R/f'_p0pilot/control_five_seed{seed}_20261107';assert read(f/'VERIFIED.json')['passed'];init=sha(f/f'init_s{seed}.pt');initial.append(init);sampler_digests.append(read(f/'LOADER_INTEGRATION_VERIFIED.json')['ordered_digests']);state=torch.load(f/f'init_s{seed}.pt',map_location='cpu',weights_only=True);d=hashlib.sha256()
  for n,t in sorted(state.items()):d.update((n+str(t.dtype)+str(tuple(t.shape))).encode());d.update(t.contiguous().numpy().tobytes())
  initial_tensor_digests.append(d.hexdigest())
  for arm in ['G0','GB','GM','GBM','GAll']:
   ev=read(f/arm/'EVALUATED.json');assert ev['initial_sha']==init and ev['seed']==seed and ev['updates']==200;assert ev['checkpoint_sha']==sha(f/arm/'best.pt')
 assert len(set(initial))==len(set(initial_tensor_digests))==3 and sampler_digests[0]==sampler_digests[1]==sampler_digests[2]
 for p,h in done['protected_inputs'].items():assert sha(R/p)==h,p
 result=dict(passed=True,seeds=[42,1,2],new_updates=2000,reused_seed42_updates=1000,aggregate_total_updates=3000,sampleSD_ddof=1,independent_meanSD_cells=checks,max_statistics_error=maxerr,paired_metric_differences_checked=delta_checks,distinct_initializations=True,initial_tensor_digests=initial_tensor_digests,same_indices_all_seeds=True,old_seed42_and_inputs_unchanged=True,SAT=0,EQ=0,new_model_forwards_during_aggregation=0,limitation='3randomseeds are not3newhosts;descriptive SD,no significanceclaim')
 (O/'VERIFIED.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
if __name__=='__main__':main()
