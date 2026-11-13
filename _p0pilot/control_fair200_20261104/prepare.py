"""Freeze train-only role/background pairs and equal-exposure schedules. No torch/SAT."""
from pathlib import Path
import csv,json,hashlib,collections
import numpy as np
from scipy.optimize import linear_sum_assignment
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent
P=R/'_p0pilot/round32_20261029';B=R/'_p0pilot/control_best200_20261104';A=R/'_p0pilot/control_risk_20261104'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def dump(p,aa):
 with p.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(aa[0]));w.writeheader();w.writerows(aa)
def main():
 assert not (O/'manifest.json').exists(),'frozen preparation already exists'
 contract=read(P/'input_contract.json');norm=np.load(P/'normalization.npz')
 rr=[x for x in rows(B/'region_nodes.csv') if x['seed']=='1' and x['split']=='train']
 lookup={(x['domain'],x['view'],x['instance']):int(x['split_row']) for x in rr}
 roles=[x for x in rows(A/'trans_role_descendant_pairs_labelchecked.csv') if x['split']=='train' and x['nodewise_training_candidate']=='True' and ('trans',x['control_view'],x['control_targets'].split('|')[0]) in lookup]
 eligible={x['control_source'] for x in roles};assert len(eligible)==20
 sourcepairs=[x for x in rows(A/'source_node_pairs.csv') if x['split']=='train' and x['role_pair']=='True' and x['control_source'] in eligible]
 requested=collections.defaultdict(set)
 for x in roles:
  for n in x['control_targets'].split('|'):requested[('trans',x['control_view'],x['control_source_gate'])].add(lookup[('trans',x['control_view'],n)])
 for x in sourcepairs:requested[('orig',x['control_source'],x['control_instance'])].add(lookup[('orig',x['control_source'],x['control_instance'])])
 data={};allpairs=[];excluded=[];report={};removed={}
 for domain in ['orig','trans']:
  q=contract['shared_inputs'][domain+'_train'];d=R/q['folder'];a={k:np.load(d/(k+'.npy'),mmap_mode='r') for k in ['x39','y','trusted','physical']};data[domain]=a
  zz=np.clip((a['x39'][:,25:]-norm['mean'][25:])/norm['std'][25:],-10,10);gate=np.argmax(a['x39'][:,:25],axis=1)
  views={x['view']:x for x in q['views']};blocked={int(x['split_row']) for x in rr if x['domain']==domain}
  removed[domain]=np.array(sorted({i for (dm,v,r),ii in requested.items() if dm==domain for i in ii}),dtype=np.int64)
  for view in sorted({v for dm,v,r in requested if dm==domain}):
   v=views[view];ci=np.array(sorted({i for (dm,vv,r),ii in requested.items() if dm==domain and vv==view for i in ii}),dtype=np.int64)
   pool=np.arange(v['start'],v['stop']);pool=pool[a['physical'][pool]&a['trusted'][pool]&(a['y'][pool]==0)];pool=np.array([i for i in pool if i not in blocked],dtype=np.int64)
   for g in sorted(set(gate[ci])):
    cc=ci[gate[ci]==g];hh=pool[gate[pool]==g]
    if len(hh):
     dist=np.sqrt(np.mean((zz[cc,None,:]-zz[hh][None,:,:])**2,axis=2));ii,jj=linear_sum_assignment(dist)
     assignments={int(cc[i]):(int(hh[j]),float(dist[i,j])) for i,j in zip(ii,jj)}
    else:assignments={}
    for i in cc:
     if int(i) not in assignments or assignments[int(i)][1]>2.0:
      excluded.append(dict(domain=domain,view=view,control_row=int(i),reason='no unique same-gate background within RMS 2 train-z units'));continue
     h,dist=assignments[int(i)];rs=sorted(r for (dm,vv,r),ids in requested.items() if dm==domain and vv==view and i in ids)
     src=view if domain=='orig' else next(x['control_source'] for x in roles if x['control_view']==view)
     allpairs.append(dict(domain=domain,source=src,view=view,roles='|'.join(rs),C=int(i),H=h,gate=int(g),topology_rms_z=dist))
 common_sources=set.intersection(*[{x['source'] for x in allpairs if x['domain']==dm} for dm in ['orig','trans']]);assert common_sources
 for x in allpairs:
  if x['source'] not in common_sources:excluded.append(dict(domain=x['domain'],view=x['view'],control_row=x['C'],reason='source lacks dual-domain common support'))
 allpairs=[x for x in allpairs if x['source'] in common_sources]
 for domain in ['orig','trans']:
  aa=[x for x in allpairs if x['domain']==domain];a=data[domain];ci=np.array([x['C'] for x in aa]);hi=np.array([x['H'] for x in aa]);assert len(set(ci))==len(ci)==len(set(hi)) and not set(ci)&set(hi)
  assert a['trusted'][ci].all() and a['trusted'][hi].all() and (a['y'][ci]==0).all() and (a['y'][hi]==0).all()
  base=np.array(a['trusted'],copy=True);base[removed[domain]]=False;base[hi]=False
  assert np.array_equal(np.flatnonzero(base&(a['y']==1)),np.flatnonzero(a['trusted']&(a['y']==1)))
  np.save(O/(domain+'_base_mask.npy'),base)
  # Hierarchical, fixed schedule: equal 16 draws/source/update, cyclic view, then uniform source role and descendant.
  schedule=np.empty((200,len(common_sources)*16),np.int64);rng=np.random.default_rng(20261104+(domain=='trans'))
  for epoch in range(200):
   drawn=[]
   for src in sorted(common_sources):
    vv=sorted({x['view'] for x in aa if x['source']==src});view=vv[epoch%len(vv)]
    rolepool=sorted({r for x in aa if x['source']==src and x['view']==view for r in x['roles'].split('|')})
    for _ in range(16):
     role=rolepool[int(rng.integers(len(rolepool)))];opts=[j for j,x in enumerate(aa) if x['source']==src and x['view']==view and role in x['roles'].split('|')];drawn.append(opts[int(rng.integers(len(opts)))])
   schedule[epoch]=drawn
  cslots=ci[schedule];hslots=hi[schedule];np.save(O/(domain+'_C_slots.npy'),cslots);np.save(O/(domain+'_H_slots.npy'),hslots)
  assert not base[ci].any() and not base[hi].any();assert set(cslots.ravel())==set(ci) and set(hslots.ravel())==set(hi)
  assert np.array_equal(np.sort(np.unique(cslots,return_counts=True)[1]),np.sort(np.unique(hslots,return_counts=True)[1]))
  report[domain]=dict(sources=len(common_sources),views=len({x['view'] for x in aa}),C_unique=len(ci),H_unique=len(hi),slots_per_update=cslots.shape[1],total_slots=int(cslots.size),base_positive=int((base&(a['y']==1)).sum()),base_negative=int((base&(a['y']==0)).sum()),historical_trusted=int(a['trusted'].sum()),unmatched_or_ineligible_C_excluded_from_common=len(removed[domain])-len(ci),topology_rms_mean=float(np.mean([x['topology_rms_z'] for x in aa])),topology_rms_max=max(x['topology_rms_z'] for x in aa),all_C_H_same_gate_same_view=True)
 dump(O/'train_pairs.csv',allpairs)
 if excluded:dump(O/'excluded.csv',excluded)
 inputs=[P/'input_contract.json',P/'normalization.npz',A/'source_node_pairs.csv',A/'trans_role_descendant_pairs_labelchecked.csv',B/'region_nodes.csv']
 for dm in ['orig','trans']:
  d=R/contract['shared_inputs'][dm+'_train']['folder'];inputs += [d/(n+'.npy') for n in ['x39','edge_index','y','trusted','physical']]
 manifest=dict(date='2026-11-04',arms=['H','C'],seeds=[42,1,2],updates=200,slots_per_source=16,sources=sorted(common_sources),counts=report,matching='same view exact 25-way gate category; minimum-cost unique host background; structural RMS z<=2; no prediction matching',sampling='source equal / cyclic implementation / uniform source role / uniform descendant; paired exact exposure',loss='unchanged ASL+1.4 soft-miss on common supervised indices concatenated with equal-length C/H slots; repetitions intentional',selection='unchanged mean injection-view trusted validation AP every5',thresholds='validation trusted negatives 95% quantile (historical); secondary validation positive recall80%/90%; frozen before test',SAT=False,EQ=False,inputs={str(p.relative_to(R)):sha(p) for p in inputs},files={p.name:sha(p) for p in O.glob('*.npy')})
 write(O/'manifest.json',manifest);print(json.dumps(report,indent=2))
if __name__=='__main__':main()
