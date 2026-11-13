"""Freeze 116/233 qualified matched pairs, equal C/H exposure and unchanged common supervision."""
from pathlib import Path
import csv,json,hashlib,shutil,collections
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;B=R/'_p0pilot/control_fair200_20261104';V=R/'_p0pilot/control_boundary_v3_20261104'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 O.mkdir(exist_ok=True);assert not (O/'manifest.json').exists(),'preparation already frozen'
 review=rows(V/'C_H_pairs_v3_review.csv');selected=[x for x in review if x['proposed_matching_status']=='structural_and_local_checks_passed_function_unproved'];assert collections.Counter(x['domain'] for x in selected)=={'orig':116,'trans':233}
 c=read(V/'input_contract.json');report={};sources=set(read(B/'manifest.json')['sources']);assert len(sources)==20
 for dm in ['orig','trans']:
  aa=[x for x in selected if x['domain']==dm];assert {x['source'] for x in aa}==sources
  ci=np.array([int(x['C']) for x in aa],dtype=np.int64);hi=np.array([int(x['H']) for x in aa],dtype=np.int64);assert len(set(ci))==len(ci)==len(set(hi));assert not set(ci)&set(hi)
  folder=R/c['shared_inputs'][dm+'_train']['folder'];y=np.load(folder/'y.npy');trust=np.load(folder/'trusted.npy');physical=np.load(folder/'physical.npy');base=np.load(B/(dm+'_base_mask.npy'));assert (y[ci]==0).all() and (y[hi]==0).all() and trust[ci].all() and trust[hi].all() and physical[ci].all() and physical[hi].all();assert not base[ci].any() and not base[hi].any();shutil.copyfile(B/(dm+'_base_mask.npy'),O/(dm+'_base_mask.npy'))
  if dm=='orig':
   # The original-side eligible pool is identical; preserve its exact historical role schedule.
   cs=np.load(B/'orig_C_slots.npy');hs=np.load(B/'orig_H_slots.npy');mp={int(x['C']):int(x['H']) for x in aa};assert set(cs.ravel())==set(ci) and np.array_equal(np.array([[mp[int(i)] for i in row] for row in cs]),hs)
  else:
   rng=np.random.default_rng(20261105);draw=np.empty((200,320),dtype=np.int64)
   for epoch in range(200):
    indices=[]
    for src in sorted(sources):
     vv=sorted({x['view'] for x in aa if x['source']==src});view=vv[epoch%len(vv)];roles=sorted({r for x in aa if x['source']==src and x['view']==view for r in x['roles'].split('|')})
     for k in range(16):
      role=roles[int(rng.integers(len(roles)))];opts=[i for i,x in enumerate(aa) if x['source']==src and x['view']==view and role in x['roles'].split('|')];indices.append(opts[int(rng.integers(len(opts)))])
    draw[epoch]=indices
   cs,hs=ci[draw],hi[draw]
  assert cs.shape==hs.shape==(200,320);mp={int(x['C']):int(x['H']) for x in aa};assert np.array_equal(np.array([[mp[int(i)] for i in row] for row in cs]),hs);assert set(cs.ravel())==set(ci) and set(hs.ravel())==set(hi)
  own={int(x['C']):x['source'] for x in aa}
  for row in cs:assert collections.Counter(own[int(i)] for i in row)=={s:16 for s in sources}
  assert np.array_equal(np.sort(np.unique(cs,return_counts=True)[1]),np.sort(np.unique(hs,return_counts=True)[1]))
  np.save(O/(dm+'_C_slots.npy'),cs);np.save(O/(dm+'_H_slots.npy'),hs)
  olda=np.load(folder/'trusted.npy');assert np.array_equal(np.flatnonzero(base&(y==1)),np.flatnonzero(olda&(y==1)))
  report[dm]=dict(sources=20,views=len({x['view'] for x in aa}),C_unique=len(ci),H_unique=len(hi),slots_per_update=320,total_slots=64000,base_positive=int((base&(y==1)).sum()),base_negative=int((base&(y==0)).sum()),base_mask_sha=sha(O/(dm+'_base_mask.npy')),base_identical_to_previous=True,weights='all selected entries equal, unchanged domain_loss')
 for seed in [42,1,2]:shutil.copyfile(B/f'init_s{seed}.pt',O/f'init_s{seed}.pt')
 with (O/'train_pairs.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(selected[0]));w.writeheader();w.writerows(selected)
 rejected=[x for x in review if x['proposed_matching_status']!='structural_and_local_checks_passed_function_unproved'];assert len(rejected)==61 and all(x['domain']=='trans' for x in rejected)
 with (O/'held_pairs.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rejected[0]));w.writeheader();w.writerows(rejected)
 cs=np.load(O/'trans_C_slots.npy');hs=np.load(O/'trans_H_slots.npy');assert not np.isin(cs,[int(x['C']) for x in rejected]).any() and not np.isin(hs,[int(x['H']) for x in rejected]).any()
 manifest=dict(date='2026-11-04',seeds=[42,1,2],arms=['H','C'],updates=200,slots_per_source=16,sources=sorted(sources),counts=report,feature_contract_sha=sha(V/'input_contract.json'),normalization_sha=sha(V/'normalization.npz'),qualification_sha=sha(V/'C_H_pairs_v3_review.csv'),pool='orig116/trans233 structure/local checks passed; not SAT functional certification',sampling='equal-source then cyclic view then source role then descendant; exact paired index exposure; orig schedule reused',loss='unchanged equal-entry ASL +1.4 soft-miss; no separate region weight',common_supervision='exact previous base masks, excluded old C/H union retained; 61 held pairs not reintroduced to base or slots',SAT=False,EQ=False,files={p.name:sha(p) for p in O.glob('*.npy')},initializations={str(s):sha(O/f'init_s{s}.pt') for s in [42,1,2]})
 (O/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8');print(report)
if __name__=='__main__':main()
