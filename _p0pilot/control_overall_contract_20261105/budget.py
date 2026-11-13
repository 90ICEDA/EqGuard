"""CPU-only five-arm review contract and frozen sampling schedules. Never trains/imports torch."""
from pathlib import Path
import csv,json,hashlib,collections
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;V=R/'_p0pilot/control_boundary_v3_20261104'
ARMS={'G0':['H','H','H'],'GB':['N','H','H'],'GM':['H','N','H'],'GBM':['N','N','H'],'GAll':['N','N','N']}
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(n,a):
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(a[0]));w.writeheader();w.writerows(a)
def schedule(pairids,views,viewmap,slots,rng):
 groups=collections.defaultdict(lambda:collections.defaultdict(list))
 for i in pairids:
  vi=int(views[i]);groups[viewmap[vi]['source']][vi].append(int(i))
 order=[];units=[];sources=sorted(groups)
 for s in sources:
  for vi,ii in sorted(groups[s].items()):
   units.append(dict(source=s,view_id=vi,view=viewmap[vi]['view'],offset=len(order),size=len(ii)))
   order.extend(rng.permutation(ii))
 starts=np.zeros((200,len(units)),np.int64);counts=np.zeros_like(starts);cursor=np.zeros(len(units),np.int64)
 for step in range(200):
  for si,s in enumerate(sources):
   qty=slots//len(sources)+int((si-step)%len(sources)<slots%len(sources))
   ids=[j for j,u in enumerate(units) if u['source']==s];j=ids[(step+si)%len(ids)]
   starts[step,j]=cursor[j];counts[step,j]=qty;cursor[j]+=qty
 assert (counts.sum(axis=1)==slots).all()
 return np.array(order,np.int64),units,starts,counts
def sample(order,units,starts,counts,step):
 return np.concatenate([order[u['offset']+(starts[step,j]+np.arange(counts[step,j]))%u['size']] for j,u in enumerate(units) if counts[step,j]])
def main():
 assert (O/'MATCHING_COMPLETE.json').exists()
 c=read(V/'input_contract.json');dictionary=list(csv.DictReader((O/'view_dictionary.csv').open(encoding='utf-8-sig')));norm=np.load(V/'normalization.npz');allbudget=[];blockbudget=[];exposure=[];stepbudget=[];domains={}
 for dm,target in [('orig',110230),('trans',420365)]:
  key=dm+'_train';d=R/c['shared_inputs'][key]['folder'];a={n:np.load(d/(n+'.npy'),mmap_mode='r') for n in ['x39','y','trusted','physical']};vm={int(v['view_id']):v for v in dictionary if v['key']==key};p=np.load(O/('matching_'+key+'.npz'));n=np.load(O/('normal_'+key+'.npz'));h=np.load(O/('trojan_host_'+key+'.npz'));mi=np.flatnonzero(p['Hindex']>=0);N=p['Nrows'][mi];H=p['Hrows'][mi];cat=p['category'][mi];nv=p['Nview'][mi];hv=p['Hview'][mi]
  assert len(np.unique(H))==len(H)==len(np.unique(N));assert np.isin(H,h['rows'][h['eligible']]).all();assert not np.intersect1d(N,H).size
  # Independently check matching and fixed old labels, not just matcher's summary.
  for ni,hi,nvi,hvi in zip(N,H,nv,hv):
   vn,vh=vm[int(nvi)],vm[int(hvi)];assert vn['kind']=='control' and vh['kind']=='trojan';assert all(vn[k]==vh[k] for k in ['host','recipe']);assert int(vn['start'])<=ni<int(vn['physical_stop']) and int(vh['start'])<=hi<int(vh['physical_stop'])
  z=np.clip((a['x39'][N,25:]-norm['mean'][25:])/norm['std'][25:],-10,10);zh=np.clip((a['x39'][H,25:]-norm['mean'][25:])/norm['std'][25:],-10,10);rms=np.sqrt(np.mean((z-zh)**2,axis=1));assert (rms<=2+1e-6).all();assert np.allclose(rms,p['distance'][mi],atol=1e-5)
  assert (np.argmax(a['x39'][N,:25],axis=1)==np.argmax(a['x39'][H,:25],axis=1)).all()
  for ii in [N,H]:assert (a['physical'][ii]&a['trusted'][ii]&(a['y'][ii]==0)).all()
  trojanmask=np.zeros(len(a['y']),bool);controlmask=np.zeros_like(trojanmask)
  for v in vm.values():
   (trojanmask if v['kind']=='trojan' else controlmask)[int(v['start']):int(v['physical_stop'])]=True
  pos=np.flatnonzero(trojanmask&a['physical']&a['trusted']&(a['y']==1));neg=np.flatnonzero(trojanmask&a['physical']&a['trusted']&(a['y']==0));assert np.array_equal(neg,h['rows']);common=np.setdiff1d(neg,H)
  assert not controlmask[common].any();assert not np.intersect1d(common,H).size
  poolcounts=np.bincount(cat,minlength=3);assert (poolcounts>0).all();extra=target-len(common);m=320;rem=extra-m;b=int(round(rem*int(poolcounts[0])/(int(poolcounts[0])+int(poolcounts[2]))));slots=[b,m,rem-b];assert min(slots)>0
  np.savez_compressed(O/('supervision_'+key+'.npz'),positive=pos,common_negative=common,N=N,H=H,category=cat,Nview=nv,Hview=hv)
  totalvis=np.zeros(len(N),np.int64);schedules=[]
  for k,name in enumerate(['B','M','U']):
   ids=np.flatnonzero(cat==k);order,units,starts,counts=schedule(ids,nv,vm,slots[k],np.random.default_rng(20261105+k+10*(dm=='trans')));np.savez_compressed(O/('schedule_'+key+'_'+name+'.npz'),order=order,starts=starts,counts=counts);(O/('units_'+key+'_'+name+'.json')).write_text(json.dumps(units,ensure_ascii=False,indent=2),encoding='utf-8');schedules.append((order,units,starts,counts))
   blockbudget.append(dict(domain=dm,block=name,unique_pairs=len(ids),sources=len({u['source'] for u in units}),views=len(units),entries_per_update=slots[k],entries_200=slots[k]*200))
   for source in sorted({u['source'] for u in units}):
    jj=[j for j,u in enumerate(units) if u['source']==source];dd=counts[:,jj].sum(axis=1);assert dd.max()-dd.min()<=1
    exposure.append(dict(domain=dm,block=name,source=source,unique_pairs=sum(units[j]['size'] for j in jj),views=len(jj),entries_200=int(dd.sum()),per_update_min=int(dd.min()),per_update_max=int(dd.max())))
  for step in range(200):
   ids=np.concatenate([sample(*s,step) for s in schedules]);bc=np.bincount(ids,minlength=len(N));totalvis+=bc;assert len(ids)==extra
   unique=int((bc>0).sum())+len(common)
   # Bijection: common, N and H disjoint, all pair endpoints unique. Therefore
   # identical pair-index sequences imply identical node repeat histograms in all arms.
   for arm,modes in ARMS.items():
    cn=sum(slots[k] for k in range(3) if modes[k]=='N');assert arm!='G0' or cn==0
    if step in [0,99,199]:
     endpoint=np.where(np.array([modes[int(k)]=='N' for k in cat]),N,H);actual=np.r_[common,endpoint[ids]];_,freq=np.unique(actual,return_counts=True);expected=np.r_[np.ones(len(common),np.int64),bc[bc>0]]
     assert len(actual)==target and len(freq)==unique and np.array_equal(np.sort(freq),np.sort(expected));assert (a['trusted'][actual]&a['physical'][actual]&(a['y'][actual]==0)).all();assert int(controlmask[actual].sum())==cn
    stepbudget.append(dict(domain=dm,update=step+1,arm=arm,positive_entries=len(pos),negative_entries=target,unique_negative=unique,repeated_negative_entries=target-unique,normal_control_entries=cn))
  assert (totalvis>0).all(),('unvisited pairs',dm,int((totalvis==0).sum()))
  for k,name in enumerate(['B','M','U']):
   vv=totalvis[cat==k];blockbudget[-3+k].update(min_visits_200=int(vv.min()),max_visits_200=int(vv.max()),all_unique_pairs_visited=True)
  for arm,modes in ARMS.items():
   normal=sum(slots[k] for k in range(3) if modes[k]=='N');allbudget.append(dict(domain=dm,arm=arm,positive_entries=len(pos),common_negative_unique=len(common),B_entries=slots[0],M_entries=slots[1],U_entries=slots[2],total_negative_entries=target,normal_control_entries=normal,negative_unique_over_200=len(neg),positive_unique_over_200=len(pos),updates=200))
  domains[dm]=dict(positive=len(pos),all_Trojan_view_negative=len(neg),common_negative=len(common),paired_unique=dict(zip(['B','M','U'],map(int,poolcounts))),block_entries=dict(zip(['B','M','U'],slots)),negative_entries=target,all_pairs_exposed=True)
  print(dm,domains[dm],flush=True)
 dump('group_budgets.csv',allbudget);dump('block_budgets.csv',blockbudget);dump('source_exposures.csv',exposure);dump('budget_per_update.csv',stepbudget)
 inputs={}
 for k,q in c['shared_inputs'].items():
  for name in ['x39','edge_index','edge_roles','y','trusted','physical']:
   p=R/q['folder']/(name+'.npy');hh=sha(p);assert hh==c['files'][str(p.relative_to(R))],p;inputs[str(p.relative_to(R))]=hh
 for p in [V/'input_contract.json',V/'normalization.npz',O/'PARTITION_COMPLETE.json',O/'MATCHING_COMPLETE.json',R/'train_test2.2.py',R/'_p0pilot/control_best200_20261104/evaluate.py',R/'_p0pilot/control_v3_eligible_20261104/frozen_engine_v3.py',Path(__file__)]+[R/('_p0pilot/control_fair200_20261104/init_s'+str(s)+'.pt') for s in [42,1,2]]:inputs[str(p.relative_to(R))]=sha(p)
 contract=dict(status='REVIEW_ONLY_NOT_AUTHORIZED_TO_TRAIN',date='2026-11-05',training=0,model_forward=0,SAT=0,arms=ARMS,block_order=['B','M','U'],domains=domains,seeds=[42,1,2],updates=200,feature='39v3 noSAT',model='dual_mix_post_cat split29 hidden64 branches2+2 post1 46620 parameters',optimizer=dict(name='Adam',lr=.0002,weight_decay=.001,clip=1),loss='frozen domain_loss ASL +1.4 softmiss squared; each domain same positive/negative entries; orig/trans backward then one step',AMP='BF16',selection='mean old trusted __inj Trojan-view validation AP every5; same rule for all arms',thresholds='same rule all arms: trans-val trusted-positive pooled score quantiles0.2/0.1 method=lower for recall80/90; historical nextafter(trusted-negative quantile0.95,+inf); report achieved macro recall separately; no positive-protection adaptation',sampling='frozen source-equal/cyclic-view/cyclic-shuffled-unique-pair schedules, same 200 steps across arms and model seeds; per-pair repetition preserved by bijection',scope='matched common-support normal-control label supervision under identical full-graph exposure; not effect of adding/removing control graphs',budget_caveat='block sizes B/M/U unequal; GB versus GM is not equal-budget intrinsic type efficiency; all-arm total P/N and unique/repetition budgets identical',evaluation='report both sides; trusted global and B/M/U regions; source macro FPR/alarm/rank plus Trojan source-role recall and joint success; test exploratory, no test driven pools',inputs=inputs)
 (O/'FIVE_GROUP_CONTRACT.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2),encoding='utf-8')
 (O/'BUDGET_VERIFIED.json').write_text(json.dumps(dict(training=0,model_forward=0,SAT=0,pair_labels_coordinates_gate_host_recipe_caliper_verified=True,G0_no_control_supervision=True,all_five_identical_per_update_positive_negative_unique_repeat_budgets=True,all_paired_nodes_visited=True,normal_untrusted_never_promoted=True,contract_sha=sha(O/'FIVE_GROUP_CONTRACT.json')),indent=2),encoding='utf-8')
if __name__=='__main__':main()
