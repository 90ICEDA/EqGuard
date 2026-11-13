"""Independent equal-budget, matched-node exposure and held-pair audit; no model calls."""
from pathlib import Path
import json,csv,hashlib,collections
import numpy as np
O=Path(__file__).resolve().parent;R=O.parents[1];B=R/'_p0pilot/control_fair200_20261104';V=R/'_p0pilot/control_boundary_v3_20261104'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def main():
 m=read(O/'manifest.json');c=read(V/'input_contract.json');pairs=rows(O/'train_pairs.csv');held=rows(O/'held_pairs.csv');z=np.load(V/'normalization.npz');checks=[]
 for dm,n in [('orig',116),('trans',233)]:
  a=[x for x in pairs if x['domain']==dm];assert len(a)==n;mp={int(x['C']):int(x['H']) for x in a};own={int(x['C']):x['source'] for x in a};assert len(mp)==len(set(mp.values()))==n
  f=R/c['shared_inputs'][dm+'_train']['folder'];x=np.load(f/'x39.npy',mmap_mode='r');y=np.load(f/'y.npy');tr=np.load(f/'trusted.npy');ph=np.load(f/'physical.npy');base=np.load(O/(dm+'_base_mask.npy'));cs=np.load(O/(dm+'_C_slots.npy'));hs=np.load(O/(dm+'_H_slots.npy'));assert sha(O/(dm+'_base_mask.npy'))==sha(B/(dm+'_base_mask.npy'))
  ci=np.array(sorted(mp));hi=np.array([mp[int(i)] for i in ci]);assert not base[ci].any() and not base[hi].any();assert (y[ci]==0).all() and (y[hi]==0).all() and tr[ci].all() and tr[hi].all() and ph[ci].all() and ph[hi].all();assert np.array_equal(np.flatnonzero(base&(y==1)),np.flatnonzero(tr&(y==1)))
  assert cs.shape==hs.shape==(200,320);assert np.array_equal(np.array([[mp[int(i)] for i in row] for row in cs]),hs);assert set(cs.ravel())==set(mp)
  for t in range(200):assert collections.Counter(own[int(i)] for i in cs[t])=={s:16 for s in m['sources']}
  views={v['view']:v for v in c['shared_inputs'][dm+'_train']['views']}
  for p in a:
   i,j=int(p['C']),int(p['H']);v=views[p['view']];assert v['start']<=i<v['physical_stop'] and v['start']<=j<v['physical_stop'];assert np.array_equal(x[i,:25],x[j,:25]);zz=np.clip((x[[i,j],25:]-z['mean'][25:])/z['std'][25:],-10,10);assert np.sqrt(np.mean((zz[0]-zz[1])**2))<=2
  if dm=='trans':
   hc=[int(x['C']) for x in held];hh=[int(x['H']) for x in held];assert not base[hc].any() and not base[hh].any() and not np.isin(cs,hc).any() and not np.isin(hs,hh).any()
  checks.append(dict(domain=dm,unique_C_H=n,sources=20,slots_per_step=320,total_extra_exposures_each_arm=64000,base_positive=int((base&(y==1)).sum()),base_negative=int((base&(y==0)).sum()),negative_entries_per_update=int((base&(y==0)).sum())+320,same_gate_view_and_caliper=True,exact_nodewise_paired_exposure=True,base_unchanged=True,all_positive_supervision_preserved=True))
 for seed in [42,1,2]:assert sha(O/f'init_s{seed}.pt')==sha(B/f'init_s{seed}.pt')
 (O/'FAIRNESS_VERIFIED.json').write_text(json.dumps(dict(passed=True,checks=checks,held_pairs=61,held_pairs_excluded_symmetrically=True,labels_modified=False,training_probe_updates=0,SAT=0),ensure_ascii=False,indent=2),encoding='utf-8');print(checks)
if __name__=='__main__':main()
