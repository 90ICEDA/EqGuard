"""Independent budget and matching audit; no graph model or solver."""
from pathlib import Path
import csv,json,hashlib,collections
import numpy as np
O=Path(__file__).resolve().parent;R=O.parents[1];P=R/'_p0pilot/round32_20261029'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 m=read(O/'manifest.json');contract=read(P/'input_contract.json');norm=np.load(P/'normalization.npz');pairs=list(csv.DictReader((O/'train_pairs.csv').open(encoding='utf-8-sig')));out=[]
 for dm in ['orig','trans']:
  q=contract['shared_inputs'][dm+'_train'];d=R/q['folder'];x=np.load(d/'x39.npy',mmap_mode='r');y=np.load(d/'y.npy');tr=np.load(d/'trusted.npy');ph=np.load(d/'physical.npy');base=np.load(O/f'{dm}_base_mask.npy');cs=np.load(O/f'{dm}_C_slots.npy');hs=np.load(O/f'{dm}_H_slots.npy');aa=[a for a in pairs if a['domain']==dm];mp={int(a['C']):a for a in aa};view={a['view']:a for a in q['views']}
  assert set(base.nonzero()[0]).issubset(set(tr.nonzero()[0]));assert np.array_equal(np.flatnonzero(base&(y==1)),np.flatnonzero(tr&(y==1)))
  assert cs.shape==hs.shape==(200,320) and set(cs.ravel())==set(mp)
  for a in aa:
   c=int(a['C']);h=int(a['H']);v=view[a['view']];assert v['start']<=c<v['physical_stop'] and v['start']<=h<v['physical_stop'];assert y[c]==y[h]==0 and ph[c] and ph[h] and tr[c] and tr[h] and not base[c] and not base[h]
   assert (x[[c,h],:25].sum(axis=1)==1).all() and np.array_equal(x[c,:25],x[h,:25])
   z=np.clip((x[[c,h],25:]-norm['mean'][25:])/norm['std'][25:],-10,10);distance=float(np.sqrt(np.mean((z[0]-z[1])**2)));assert abs(distance-float(a['topology_rms_z']))<1e-5 and distance<=2
  for t in range(200):
   expected=np.array([int(mp[int(c)]['H']) for c in cs[t]]);assert np.array_equal(expected,hs[t]);counts=collections.Counter(mp[int(c)]['source'] for c in cs[t]);assert len(counts)==20 and set(counts.values())=={16}
  out.append(dict(domain=dm,passed=True,sources=20,updates=200,equal_slots=320,positive_count=int((base&(y==1)).sum()),negative_count_per_update=int((base&(y==0)).sum())+320,role_negative_budget_fraction=320/(int(base.sum())+320),unique_per_arm=len(aa),same_view_and_gate=True,no_new_labels=True,exact_paired_exposure=True))
 # Retain the first runner's exact source snapshot. Only the top-level failure-log filename handler was corrected during startup.
 current=(O/'run.py').read_text(encoding='utf-8');initial=current.replace("(O/('failure_'+str(int(time.time()))+'.log'))","(O/'failure_'+str(int(time.time()))+'.log')")
 p=O/'runner_initial_snapshot.py';p.write_bytes(initial.encode('utf-8'));binding=read(O/'seed42/H/binding.json');assert sha(p)==binding['runner_sha']
 (O/'FAIRNESS_VERIFIED.json').write_text(json.dumps(dict(checks=out,initial_runner_sha=sha(p),current_runner_sha=sha(O/'run.py'),runner_difference='exception-log path construction only; no training/evaluation logic changed',new_SAT=0),ensure_ascii=False,indent=2),encoding='utf-8');print(out)
if __name__=='__main__':main()
