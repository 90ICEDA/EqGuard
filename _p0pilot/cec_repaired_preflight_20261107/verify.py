"""Independent saved-output checks; no model execution or updates."""
from pathlib import Path
import collections,csv,hashlib,json,sys
import numpy as np
O=Path(__file__).resolve().parent;R=O.parents[1];C=R/'_p0pilot/cec_repaired_contract_20261107'
sys.path.insert(0,str(R/'_p0pilot/cec_freeq_preflight_20261106'))
from verify import cpu_losses
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 complete=read(O/'COMPLETE.json');assert complete['passed']
 with (O/'loaded_batches.csv').open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
 budget=collections.Counter();error=0
 for s,row in zip(read(C/'SCHEDULE_SEED42.json'),rows):
  u=s['update'];ids=sorted({c for r in s['units'] for c in r['cone_ids']});ix={c:i for i,c in enumerate(ids)};e=collections.defaultdict(list)
  for r in s['units']:
   e['anchors'] += [ix[c] for c in r['anchors']]
   e['candidates'] += [[ix[c] for c in cc] for cc in r['candidates']]
   e['real']+=r['real_targets'];e['permuted']+=r['permuted_targets']
   e['negative_edges'] += [[ix[a],ix[b]] for a,b in r['negative_edges']]
   e['query_weight'] += [r['query_weight']]*len(r['anchors'])
   e['negative_weight'] += [r['negative_weight']]*len(r['negative_edges'])
  with np.load(O/f'preview{u:02}.npz') as z:
   assert z['cone_ids'].tolist()==ids
   for k,v in e.items():assert np.array_equal(z[k],np.asarray(v,dtype=z[k].dtype)),(u,k)
   metrics=cpu_losses(z['root64'],{k:z[k] for k in e})
   for k,v in metrics.items():
    delta=abs(v-float(row[k]));error=max(error,delta);assert delta<1e-6,(u,k,delta)
   mass=[]
   for key in ['real','permuted']:
    mass.append(collections.Counter(e['candidates'][i][t] for i,t in enumerate(e[key])))
   assert mass[0]==mass[1]==collections.Counter(e['anchors'])
  budget.update(unit_slots=len(s['units']),queries=len(e['anchors']),candidate_distances=sum(map(len,e['candidates'])),negatives=len(e['negative_edges']))
 assert len(rows)==32 and dict(budget)==complete['per_group_budget']
 maxgrad=0
 with np.load(O/'gradient_vectors.npz') as z:
  for u in complete['gradient_batches']:
   v={k:z[f'step{u}_{k}'].astype(float) for k in ['CE_R','CE_P','different','variance_weighted','total_Z','total_R','total_P']};common=v['different']+v['variance_weighted']
   for arm,expected in [('Z',common),('R',common+v['CE_R']),('P',common+v['CE_P'])]:
    d=np.linalg.norm(v['total_'+arm]-expected)/np.linalg.norm(v['total_'+arm]);maxgrad=max(maxgrad,d);assert d<2e-5
 for p,h in read(O/'EXECUTION_CONTRACT.json')['protected_files'].items():assert sha(R/p)==h,p
 result=dict(passed=True,batches_independently_rebuilt=32,losses_independently_recomputed=224,max_loss_error=error,gradient_vectors_checked=12,max_gradient_additivity_relative_error=maxgrad,budget=dict(budget),protected_files_unchanged=True,extra_model_forwards=0,training=0,SAT=0)
 (O/'VERIFIED.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
if __name__=='__main__':main()
