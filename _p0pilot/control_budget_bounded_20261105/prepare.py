"""CPU-only bounded five-arm schedules and fanout audit. No torch, models, SAT."""
from pathlib import Path
import numpy as np
from scipy.sparse import csr_matrix
import json,csv,collections,hashlib
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;P=R/'_p0pilot/control_overall_contract_20261105';V=R/'_p0pilot/control_boundary_v3_20261104'
UPDATES=200;NODE_CAP=128;COMMON=8192;COMMON_SOURCE_CAP=160000;EXTRA_SOURCE_CAP=3200;EXTRA_STEP_SOURCE_CAP=32
ARMS={'G0':['H','H','H'],'GB':['N','H','H'],'GM':['H','N','H'],'GBM':['N','N','H'],'GAll':['N','N','N']}
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def load(p):
 with np.load(p) as z:return {k:z[k] for k in z.files}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(name,rr):
 with (O/name).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def waterfill(cap,total):
 cap=np.array(cap,np.int64);assert cap.sum()>=total
 lo,hi=0,int(cap.max())+1
 while hi-lo>1:
  mid=(lo+hi)//2
  if np.minimum(cap,mid).sum()<=total:lo=mid
  else:hi=mid
 q=np.minimum(cap,lo);ii=np.flatnonzero(q<cap);q[ii[:int(total-q.sum())]]+=1;assert q.sum()==total and (q<=cap).all();return q
def common_schedule(rows,row_source,rng):
 sources=sorted(set(row_source));lists=[rows[row_source==s] for s in sources];quota=waterfill([min(len(ii)*NODE_CAP,COMMON_SOURCE_CAP) for ii in lists],COMMON*UPDATES);counts=np.tile(quota//UPDATES,(UPDATES,1));cursor=0
 for j,q in enumerate(quota):
  rem=int(q%UPDATES);counts[(cursor+np.arange(rem))%UPDATES,j]+=1;cursor+=rem
 assert (counts.sum(1)==COMMON).all();result=[];pointers=np.zeros(len(lists),np.int64);lists=[rng.permutation(ii) for ii in lists]
 for step in range(UPDATES):
  pp=[]
  for j,ii in enumerate(lists):
   n=int(counts[step,j]);assert n<=len(ii);pp.append(ii[(pointers[j]+np.arange(n))%len(ii)]);pointers[j]+=n
  result.append(np.concatenate(pp))
 return np.array(result,np.int64),dict(zip(sources,map(int,quota)))
def choose(candidates,n,step,uses,source_total,source_step,ns,hs,rank):
 # Least exposed physical pair first. Source use breaks ties, then frozen RNG.
 ids=np.asarray(candidates,np.int64);source_score=source_total[ns[ids]]+source_total[hs[ids]];block_source_use=np.bincount(ns[ids],weights=uses[ids],minlength=len(source_total));already_seen=block_source_use[ns[ids]]>0;order=ids[np.lexsort((rank[ids],source_score,uses[ids],already_seen))];picked=[]
 for i in order:
  if uses[i]>=NODE_CAP:continue
  ni,hi=ns[i],hs[i]
  if max(source_total[ni],source_total[hi])>=EXTRA_SOURCE_CAP:continue
  if max(source_step[step,ni],source_step[step,hi])>=EXTRA_STEP_SOURCE_CAP:continue
  picked.append(int(i));uses[i]+=1;source_total[ni]+=1;source_total[hi]+=1;source_step[step,ni]+=1;source_step[step,hi]+=1
  if len(picked)==n:break
 assert len(picked)==n,('capacity exhausted',step,n,len(picked));return np.array(picked,np.int64)
def main():
 O.mkdir(exist_ok=True);assert not (O/'PREPARED.json').exists();c=read(V/'input_contract.json');norm=load(V/'normalization.npz');views=list(csv.DictReader((P/'view_dictionary.csv').open(encoding='utf-8-sig')));coverage=[];fanout=[];source_coverage=[];domains={};inputhash={};urows=[]
 for dm in ['orig','trans']:
  key=dm+'_train';s=load(P/('supervision_'+key+'.npz'));normal=load(P/('normal_'+key+'.npz'));vm={int(v['view_id']):v for v in views if v['key']==key};d=R/c['shared_inputs'][key]['folder'];x=np.load(d/'x39.npy',mmap_mode='r');e=np.load(d/'edge_index.npy',mmap_mode='r');physical=np.load(d/'physical.npy',mmap_mode='r');assert c['columns39'][32]=='log1p_exact2_fanout'
  allsources=sorted({v['source'] for v in vm.values()});sid={v:i for i,v in enumerate(allsources)};ns=np.array([sid[vm[int(vi)]['source']] for vi in s['Nview']]);hs=np.array([sid[vm[int(vi)]['source']] for vi in s['Hview']]);assert not set(ns)&set(hs)
  row_source=np.empty(len(s['common_negative']),dtype=object)
  for v in vm.values():
   m=(s['common_negative']>=int(v['start']))&(s['common_negative']<int(v['physical_stop']));row_source[m]=v['source']
  assert all(isinstance(v,str) for v in row_source)
  common,quotas=common_schedule(s['common_negative'],row_source,np.random.default_rng(202611051+(dm=='trans')));np.save(O/('common_'+key+'.npy'),common)
  # Independent two-edge path endpoint sets on saved directed physical graph.
  # Length exactly2, unique endpoints, self excluded; direct neighbors also count
  # if a two-edge path reaches them. It is not shortest-distance-exactly2.
  mask=physical[e[0]]&physical[e[1]];adj=csr_matrix((np.ones(int(mask.sum()),np.int8),(e[0,mask],e[1,mask])),shape=(len(x),len(x)));adj.sum_duplicates();adj.sort_indices();mi=np.flatnonzero(s['category']==1);nodes=np.unique(np.r_[s['N'][mi],s['H'][mi]]);actual={}
  for i in nodes:
   second=set()
   for j in adj.indices[adj.indptr[i]:adj.indptr[i+1]]:second.update(map(int,adj.indices[adj.indptr[j]:adj.indptr[j+1]]))
   second.discard(int(i));actual[int(i)]=len(second);assert abs(float(np.log1p(len(second)))-float(x[i,32]))<2e-6,(dm,int(i))
  rawdelta=(x[s['N'],32]-x[s['H'],32])/norm['std'][32];strict=mi[np.abs(rawdelta[mi])<=.5];eligible=np.ones(len(s['N']),bool);eligible[mi]=np.abs(rawdelta[mi])<=.5
  for i in mi:
   vn,vh=vm[int(s['Nview'][i])],vm[int(s['Hview'][i])];fanout.append(dict(domain=dm,pair_id=int(i),normal_row=int(s['N'][i]),H_row=int(s['H'][i]),normal_source=vn['source'],H_source=vh['source'],normal_view=vn['view'],H_view=vh['view'],host=vn['host'],recipe=vn['recipe'],normal_count=actual[int(s['N'][i])],H_count=actual[int(s['H'][i])],normal_log1p=float(x[s['N'][i],32]),H_log1p=float(x[s['H'][i],32]),signed_train_z=float(rawdelta[i]),main_eligible=bool(eligible[i])))
  for rc in sorted(set(map(int,normal['reason'][normal['category']==2]))):
   jj=(normal['category']==2)&(normal['reason']==rc);urows.append(dict(domain=dm,reason=rc,candidates=int(jj.sum()),meaning={5:'other added incl dup',6:'mixed added/host lineage',7:'incomplete added trace',8:'unresolved',9:'foreign/unknown/positive parent'}.get(rc,'unknown')))
  sizes=[48,48,8 if dm=='orig' else 48];rank=np.random.default_rng(202611052+(dm=='trans')).random(len(s['N']));uses=np.zeros(len(s['N']),np.int64);st=np.zeros(len(allsources),np.int64);ss=np.zeros((UPDATES,len(allsources)),np.int64);bup=np.zeros((UPDATES,sizes[0]+sizes[2]),np.int64)
  for step in range(UPDATES):
   uu=choose(np.flatnonzero(s['category']==2),sizes[2],step,uses,st,ss,ns,hs,rank);bb=choose(np.flatnonzero(s['category']==0),sizes[0],step,uses,st,ss,ns,hs,rank);bup[step]=np.r_[bb,uu]
  for variant,mcandidates in [('main_fanout05',strict),('sensitivity_wideM',mi)]:
   vu,vt,vs=uses.copy(),st.copy(),ss.copy();ms=[]
   for step in range(UPDATES):ms.append(choose(mcandidates,sizes[1],step,vu,vt,vs,ns,hs,rank))
   pairseq=np.c_[bup[:,:sizes[0]],np.array(ms),bup[:,sizes[0]:]];assert pairseq.shape==(UPDATES,sum(sizes));np.save(O/(variant+'_'+key+'_pairs.npy'),pairseq)
   used=np.unique(pairseq);assert vu.max()<=NODE_CAP and vt.max()<=EXTRA_SOURCE_CAP and vs.max()<=EXTRA_STEP_SOURCE_CAP
   for cat,name in enumerate(['B','M','U']):
    ids=np.flatnonzero(s['category']==cat);pool=mcandidates if cat==1 else ids;uu=used[s['category'][used]==cat];ww=vu[uu];coverage.append(dict(domain=dm,variant=variant,block=name,old_matched=len(ids),eligible=len(pool),used_unique=len(uu),eligible_not_used=len(pool)-len(uu),fanout_held=len(ids)-len(pool),sources=len(set(ns[uu])),H_sources=len(set(hs[uu])),views=len(set(s['Nview'][uu])),entries_per_update=sizes[cat],entries_200=sizes[cat]*UPDATES,min_node_exposure=int(ww.min()),max_node_exposure=int(ww.max())))
   for source in allsources:
    j=sid[source];source_coverage.append(dict(domain=dm,variant=variant,source=source,kind=next(v['kind'] for v in vm.values() if v['source']==source),common_entries_200=quotas.get(source,0),extra_counterfactual_entries_200=int(vt[j]),extra_per_update_max=int(vs[:,j].max()),combined_counterfactual_bound_200=int(quotas.get(source,0)+vt[j])))
  np.savez_compressed(O/('pools_'+key+'.npz'),**s,main_eligible=eligible,normal_source=ns,H_source=hs);(O/('sources_'+key+'.json')).write_text(json.dumps(allsources,ensure_ascii=False,indent=2),encoding='utf-8')
  domains[dm]=dict(positive=len(s['positive']),common_pool=len(s['common_negative']),common_per_update=COMMON,block_entries=dict(zip(['B','M','U'],sizes)),negative_per_update=COMMON+sum(sizes),main_M=len(strict),wide_M=len(mi),main_M_held=len(mi)-len(strict),common_source_quota=quotas)
  for p in [P/('supervision_'+key+'.npz'),P/('normal_'+key+'.npz')]:inputhash[str(p.relative_to(R))]=sha(p)
  print(dm,domains[dm]['negative_per_update'],'mainM',len(strict),'wideM',len(mi),flush=True)
 dump('coverage.csv',coverage);dump('M_fanout_pair_audit.csv',fanout);dump('source_budget_bounds.csv',source_coverage);dump('U_interpretation.csv',urows)
 # Freeze the existing graph/label/features by the original v3 hashes.
 for name,hh in c['files'].items():assert sha(R/name)==hh,name;inputhash[name]=hh
 for name in ['COMPLETE.json','FIVE_GROUP_CONTRACT.json','REVIEW_FINDINGS.json','view_dictionary.csv']:inputhash[str((P/name).relative_to(R))]=sha(P/name)
 for p in [V/'input_contract.json',V/'normalization.npz',Path(__file__)]:inputhash[str(p.relative_to(R))]=sha(p)
 old=read(P/'FIVE_GROUP_CONTRACT.json');contract=dict(status='OFFLINE_ONLY_PENDING_VERIFICATION',training=0,model_forward=0,SAT=0,arms=ARMS,variants=['main_fanout05','sensitivity_wideM'],recommended_variant='main_fanout05',domains=domains,limits=dict(updates=UPDATES,negative_node_round=NODE_CAP,negative_node_step=1,common_source_round_per_domain=COMMON_SOURCE_CAP,common_source_step_per_domain=1024,extra_source_round_per_domain=EXTRA_SOURCE_CAP,extra_source_step_per_domain=EXTRA_STEP_SOURCE_CAP,total_source_round_two_domains=2*(COMMON_SOURCE_CAP+EXTRA_SOURCE_CAP),total_source_step_two_domains=2*(1024+EXTRA_STEP_SOURCE_CAP)),U='residual existing trusted normal labels; reason7 is lineage uncertainty, not unknown label or coherent functional type; no label promotion',scope='matched-source-control negative supervision with identical full graph exposure; not removal/addition of control graphs; main strictM coverage reduced',frozen={k:old[k] for k in ['seeds','updates','feature','model','optimizer','loss','AMP','selection','thresholds','evaluation']},sampler='common capacity-aware source waterfill + shuffled cyclic unique nodes; replacements least-used pairs, endpoint-source caps; no same-step repeats; paired indices identical for all5 arms; wideM sensitivity shares exact common/B/U sequences',budget_change='five arms all use new smaller common negative budget; old H/C is not a valid G0 comparison; positive counts unchanged; aggregate source cap applies negative supervision only, positives remain fixed',no_training_queue=True,inputs=inputhash)
 (O/'CONTRACT.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2),encoding='utf-8');(O/'PREPARED.json').write_text(json.dumps(dict(contract_sha=sha(O/'CONTRACT.json'),training=0,SAT=0)),encoding='utf-8')
if __name__=='__main__':main()
