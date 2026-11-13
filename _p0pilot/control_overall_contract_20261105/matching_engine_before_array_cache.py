"""Train-only matching to Trojan-view host background. No prediction/positive-location selection."""
from pathlib import Path
import csv,json,collections,hashlib,os
import numpy as np
from scipy.spatial import cKDTree
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;V=R/'_p0pilot/control_boundary_v3_20261104'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def dump(n,a):
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(a[0]));w.writeheader();w.writerows(a)
def source_order(indices,normal,viewmap,rng):
 g=collections.defaultdict(list)
 for i in indices:g[viewmap[int(normal['view_id'][i])]['source']].append(int(i))
 lists=[rng.permutation(v).tolist() for k,v in sorted(g.items())];out=[]
 for j in range(max(map(len,lists),default=0)):
  for a in lists:
   if j<len(a):out.append(a[j])
 return np.array(out,np.int64)
def greedy(cidx,hidx,nfeatures,hfeatures,rng):
 """Bounded nearest-neighbor greedy, recompute free pool up to4 times. Lower bound, not optimal matching."""
 cidx=np.asarray(cidx,dtype=np.int64);free=np.asarray(hidx,dtype=np.int64);assigned=[];pending=cidx;cap=2*np.sqrt(14)
 for attempt in range(4):
  if not len(free) or not len(pending):break
  hu,hinv=np.unique(hfeatures[free],axis=0,return_inverse=True);hsort=np.argsort(hinv,kind='stable');hptr=np.r_[0,np.cumsum(np.bincount(hinv,minlength=len(hu)))];cursor=hptr[:-1].copy();nu,ninv=np.unique(nfeatures[pending],axis=0,return_inverse=True)
  tree=cKDTree(hu);k=min(64,len(hu));ds,js=tree.query(nu,k=k,distance_upper_bound=cap,workers=min(8,os.cpu_count() or 1))
  if k==1:ds=ds[:,None];js=js[:,None]
  used=np.zeros(len(free),bool);remain=[]
  for z,i in enumerate(pending):
   zz=ninv[z];choices=js[zz];valid=(choices<len(hu))&np.isfinite(ds[zz]);choices=choices[valid];dd=ds[zz][valid];found=False
   for j,d in zip(choices,dd):
    jj=int(j)
    if cursor[jj]<hptr[jj+1]:
     loc=int(hsort[cursor[jj]]);cursor[jj]+=1;used[loc]=True;assigned.append((int(i),int(free[loc]),float(d/np.sqrt(14))));found=True;break
   if not found:remain.append(int(i))
  if not used.any():break
  free=free[~used];pending=np.array(remain,np.int64)
 return assigned,free,pending
def main():
 assert (O/'PARTITION_COMPLETE.json').exists();c=read(V/'input_contract.json');norm=np.load(V/'normalization.npz');dictionary=rows(O/'view_dictionary.csv');summary=[];viewcover=[];matchrecords=[]
 for dm in ['orig','trans']:
  key=dm+'_train';normal=np.load(O/('normal_'+key+'.npz'));hp=np.load(O/('trojan_host_'+key+'.npz'));nview={int(v['view_id']):v for v in dictionary if v['key']==key and v['kind']=='control'};hview={int(v['view_id']):v for v in dictionary if v['key']==key and v['kind']=='trojan'};x=np.load(R/c['shared_inputs'][key]['folder']/'x39.npy',mmap_mode='r');eligible=np.flatnonzero(hp['eligible']);hrows=hp['rows'][eligible];hvid=hp['view_id'][eligible];hgate=hp['gate'][eligible];nf=np.clip((x[normal['rows'],25:]-norm['mean'][25:])/norm['std'][25:],-10,10);hf=np.clip((x[hrows,25:]-norm['mean'][25:])/norm['std'][25:],-10,10)
  ns=collections.defaultdict(list);hs=collections.defaultdict(list)
  for i,(vi,g) in enumerate(zip(normal['view_id'],normal['gate'])):v=nview[int(vi)];ns[(v['host'],v['recipe'],int(g))].append(i)
  for i,(vi,g) in enumerate(zip(hvid,hgate)):v=hview[int(vi)];hs[(v['host'],v['recipe'],int(g))].append(i)
  assigned=np.full(len(normal['rows']),-1,np.int64);distance=np.full(len(normal['rows']),np.nan,np.float32);support=np.zeros(len(normal['rows']),bool);reason=np.full(len(normal['rows']),23,np.int16);reserve_count=0;matched_cat=collections.Counter();rng=np.random.default_rng(20261105+(dm=='trans'))
  cache=O/('matching_'+key+'.npz');cached=cache.exists()
  if cached:
   prev=np.load(cache);assert np.array_equal(prev['Nrows'],normal['rows']) and np.array_equal(prev['Nview'],normal['view_id']) and np.array_equal(prev['category'],normal['category']);assigned=prev['Hindex'].copy();distance=prev['distance'].copy();support=prev['unrestricted_geometric_support'].copy();reason=prev['reason'].copy();ii=np.flatnonzero(assigned>=0);assert np.array_equal(prev['Hrows'][ii],hrows[assigned[ii]]);assert np.all(np.sqrt(np.mean((nf[ii]-hf[assigned[ii]])**2,axis=1))<=2+1e-6);reserve_count=sum(len(h)//2 for h in hs.values());matched_cat=collections.Counter(map(int,normal['category'][ii]))
  for stratum,ni0 in ([] if cached else sorted(ns.items())):
   ni=np.array(ni0,np.int64);hi=np.array(hs.get(stratum,[]),np.int64)
   if not len(hi):reason[ni]=20;continue
   hu=np.unique(hf[hi],axis=0);nu,ninv=np.unique(nf[ni],axis=0,return_inverse=True);ud,_=cKDTree(hu).query(nu,k=1,workers=min(8,os.cpu_count() or 1));nearest=ud[ninv];ok=nearest<=2*np.sqrt(14);support[ni]=ok;reason[ni[~ok]]=21
   # Keep at least half each host/recipe/gate H stratum out of replacements as common supervision.
   reserve=rng.permutation(hi)[:len(hi)//2];reserve_count+=len(reserve)
   if not len(reserve):reason[ni[ok]]=22;continue
   def run_cat(cat,capacity):
    candidates=source_order(ni[(normal['category'][ni]==cat)&support[ni]&(assigned[ni]<0)],normal,nview,rng);got,free,left=greedy(candidates,capacity,nf,hf,rng)
    for i,j,d in got:assigned[i]=j;distance[i]=d;reason[i]=0;matched_cat[cat]+=1
    return free
   free=run_cat(1,reserve);order=rng.permutation(free);hb=order[:(len(order)+1)//2];hu=order[(len(order)+1)//2:];fb=run_cat(0,hb);fu=run_cat(2,hu)
   # Reclaim unused quota. Existing matched pairs remain untouched; M retains first priority.
   free=np.r_[fb,fu]
   for cat in [1,2,0]:free=run_cat(cat,free)
  matched=np.flatnonzero(assigned>=0);assert len(set(map(int,hrows[assigned[matched]])))==len(matched)
  if not cached:np.savez_compressed(cache,Nrows=normal['rows'],category=normal['category'],Nview=normal['view_id'],Hindex=assigned,Hrows=np.where(assigned>=0,hrows[np.maximum(assigned,0)],-1),Hview=np.where(assigned>=0,hvid[np.maximum(assigned,0)],-1),distance=distance,unrestricted_geometric_support=support,reason=reason)
  for cat,name in [(0,'B'),(1,'M'),(2,'U')]:
   allidx=np.flatnonzero(normal['category']==cat);mi=allidx[assigned[allidx]>=0];src={nview[int(normal['view_id'][i])]['source'] for i in mi};vv={int(normal['view_id'][i]) for i in mi};summary.append(dict(domain=dm,category=name,candidates=len(allidx),unrestricted_same_stratum_caliper_support=int(support[allidx].sum()),unique_matched=len(mi),matched_source_objects=len(src),matched_views=len(vv),no_H_stratum=int((reason[allidx]==20).sum()),outside_caliper=int((reason[allidx]==21).sum()),common_reservation_or_bounded_matching=int(((reason[allidx]==22)|(reason[allidx]==23)).sum()),strict_H_unique=len(hrows),H_half_reserve_capacity=reserve_count))
  for vi,v in nview.items():
   ii=np.flatnonzero(normal['view_id']==vi)
   for cat,name in [(0,'B'),(1,'M'),(2,'U')]:
    jj=ii[normal['category'][ii]==cat];mm=jj[assigned[jj]>=0];viewcover.append(dict(domain=dm,source=v['source'],view=v['view'],host=v['host'],recipe=v['recipe'],category=name,candidates=len(jj),geometric_support=int(support[jj].sum()),matched=len(mm),unmatched=len(jj)-len(mm)))
  for i in matched:
   nv=nview[int(normal['view_id'][i])];hv=hview[int(hvid[assigned[i]])];matchrecords.append(dict(domain=dm,category=['B','M','U'][int(normal['category'][i])],normal_row=int(normal['rows'][i]),H_row=int(hrows[assigned[i]]),normal_source=nv['source'],normal_view=nv['view'],H_source=hv['source'],H_view=hv['view'],host=nv['host'],recipe=nv['recipe'],gate=int(normal['gate'][i]),topology_RMS=float(distance[i])))
  print(dm,dict(matched_cat),'matched total',len(matched),'strict H',len(hrows),'cache_reused',cached,flush=True)
 dump('matching_summary.csv',summary);dump('matching_by_source_view.csv',viewcover);dump('matched_pairs.csv',matchrecords)
 (O/'MATCHING_COMPLETE.json').write_text(json.dumps(dict(training=0,model_forward=0,SAT=0,labels_modified=False,selection_uses='training only; host/recipe/exact gate and14d train-normalized topology RMS<=2; source round-robin; no scores',half_H_reserved_common=True,algorithm='bounded KDTree greedy with up to4 free-pool passes and quota reclaim; coverage is lower bound, not maximum-cardinality proof',categories_disjoint=True,H_unique_across_B_M_U=True,reason_codes={0:'matched',20:'no strict H same host/recipe/gate',21:'all unrestricted strict H outside RMS2',22:'stratum H retained for common supervision',23:'not assigned under reserved capacity and bounded greedy; not proved impossible'},summary=summary),ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
