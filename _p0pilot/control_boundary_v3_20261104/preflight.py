"""Offline invariant checks, v3 local-collision audit and future C/H pool review."""
from pathlib import Path
import json,csv,hashlib,collections,functools
import numpy as np
from load_v3 import load_arrays
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;P=R/'_p0pilot/round32_20261029';B=R/'_p0pilot/control_fair200_20261104'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(n,a):
 if not a:return
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(a[0]));w.writeheader();w.writerows(a)
def main():
 assert (O/'FEATURES_COMPLETE.json').exists();c=read(O/'input_contract.json');old=read(P/'input_contract.json');norm=np.load(O/'normalization.npz');oldnorm=np.load(P/'normalization.npz');checks=[];data={};oldx={}
 for key,q in c['shared_inputs'].items():
  new=load_arrays(key,normalized=True);folder=R/old['shared_inputs'][key]['folder'];xold=np.load(folder/'x39.npy',mmap_mode='r');x=new['x39'];assert x.shape==xold.shape and np.isfinite(new['x']).all();assert np.array_equal(x[:,:30],xold[:,:30]) and np.array_equal(x[:,31:],xold[:,31:]);assert not new['trusted'][~new['physical']].any()
  for n in ['edge_index','edge_roles','y','trusted','physical']:assert sha(R/q['folder']/(n+'.npy'))==sha(folder/(n+'.npy'))
  e=new['edge_index'];d=x[:,30];assert ((d==-1)|(d>=0)).all() and np.all(d==d.astype(np.int64));u,v=e;reach=d[v]>=0;assert (d[u[reach]]>=0).all() and (d[u[reach]]<=d[v[reach]]+1).all()
  witness=d==0;dec=(d[u]>0)&(d[v]>=0)&(d[u]==d[v]+1);witness=witness.copy();witness[u[dec]]=True;assert witness[d>=0].all();assert not ((xold[:,30]<0)&(d>=0)).any();assert (d[(d>=0)&(xold[:,30]>=0)]>=xold[:,30][(d>=0)&(xold[:,30]>=0)]).all()
  same=np.delete(np.arange(39),30);xo=np.array(xold,copy=True);xo[:,25:]=np.clip((xo[:,25:]-oldnorm['mean'][25:])/oldnorm['std'][25:],-10,10);assert np.array_equal(new['x'][:,same],xo[:,same])
  checks.append(dict(key=key,finite_loader=True,other38_raw_and_normalized_columns_identical=True,labels_edges_roles_masks_identical=True,shortest_distance_bellman_verified=True,rows=len(x),changed_raw=int((d!=xold[:,30]).sum()),changed_normalized=int((new['x'][:,30]!=xo[:,30]).sum())))
  if not key.endswith('_test'):data[key]=new;oldx[key]=xold
  del xo
 # Recheck local indistinguishability on all audited source roles, using both versions.
 targets=rows(O/'target_activity.csv');qualification=rows(O/'role_boundary_qualification.csv');lookup=collections.defaultdict(set)
 for x in targets:lookup[(x['domain'],x['split'],x['view'],x['role'],x['side'])].add(int(x['row']))
 context=[];collision_roots=set();collision_roles=set()
 for key,a in data.items():
  e=a['edge_index'];order=np.argsort(e[1],kind='stable');src=np.asarray(e[0][order]);ptr=np.r_[0,np.cumsum(np.bincount(e[1],minlength=len(a['x39'])))];keynorm={0:oldnorm,1:norm};keyx={0:oldx[key],1:a['x39']}
  @functools.lru_cache(None)
  def tree(version,i,depth):
   x=np.array(keyx[version][i],copy=True);z=keynorm[version];x[25:]=np.clip((x[25:]-z['mean'][25:])/z['std'][25:],-10,10);b=x.astype('<f4').tobytes()
   if depth:b+=tree(version,i,depth-1)+b''.join(sorted(tree(version,int(j),depth-1) for j in src[ptr[i]:ptr[i+1]]))
   return hashlib.sha256(b).digest()
  for x in qualification:
   if x['domain']+'_'+x['split']!=key:continue
   ni=sorted(lookup[(x['domain'],x['split'],x['view'],x['role'],'normal')]);ti=sorted(lookup[(x['domain'],x['split'],x['trojan_view'],x['role'],'trojan')]);counts=[]
   for version in [0,1]:
    pairs=[(i,j) for i in ni for j in ti if tree(version,i,3)==tree(version,j,3)];counts.append(len(pairs))
    if version==1 and pairs:
     collision_roots.update((x['domain'],x['split'],i) for i,j in pairs);collision_roles.add((x['domain'],x['split'],x['view'],x['role']))
   context.append(dict(domain=x['domain'],split=x['split'],source=x['source'],view=x['view'],role=x['role'],old_equal3_pairs=counts[0],v3_equal3_pairs=counts[1]))
 dump('context_v2_v3.csv',context)
 nodes=rows(O/'normal_candidate_qualification.csv');newstatus=[]
 for x in nodes:
  rs=x['source_roles'].split('|');coll=any((x['domain'],x['split'],x['view'],r) in collision_roles for r in rs);newstatus.append(dict(**x,v3_local_conflict=coll,proposed_extra_weight_status='hold_local_input_conflict' if coll else x['proposed_status']))
 dump('candidate_v3_review.csv',newstatus);candidates={(x['domain'],int(x['row'])):x for x in newstatus if x['split']=='train'};matched=[]
 for x in rows(B/'train_pairs.csv'):
  dm=x['domain'];a=data[dm+'_train'];i,j=int(x['C']),int(x['H']);assert (a['y'][[i,j]]==0).all() and a['trusted'][[i,j]].all();assert np.array_equal(a['x39'][i,:25],a['x39'][j,:25]);distance=float(np.sqrt(np.mean((a['x'][i,25:]-a['x'][j,25:])**2)));s=candidates[(dm,i)]['proposed_extra_weight_status'];status=s if s!='structurally_supported_unproved' else 'needs_H_rematch' if distance>2 else 'structural_and_local_checks_passed_function_unproved'
  matched.append(dict(**x,v3_topology_rms_z=distance,v3_same_gate=True,qualification_status=s,proposed_matching_status=status,labels_modified=False,old_sampling_modified=False))
 dump('C_H_pairs_v3_review.csv',matched);summary=[]
 for dm in ['orig','trans']:
  aa=[x for x in matched if x['domain']==dm];supported=[x for x in aa if x['proposed_matching_status']=='structural_and_local_checks_passed_function_unproved'];summary.append(dict(domain=dm,current_pairs=len(aa),provisional_supported_pairs=len(supported),supported_sources=len({x['source'] for x in supported}),supported_views=len({x['view'] for x in supported}),hold_boundary_or_collision=sum(x['qualification_status']!='structurally_supported_unproved' for x in aa),needs_H_rematch=sum(x['proposed_matching_status']=='needs_H_rematch' for x in aa),functional_verified=0))
 dump('preflight_checks.csv',checks);dump('provisional_pool_summary.csv',summary)
 for p,h in old['files'].items():assert sha(R/p)==h,p
 for p,h in c['files'].items():assert sha(R/p)==h,p
 for p,h in read(B/'manifest.json')['files'].items():assert sha(B/p)==h,p
 for p,h in read(R/'_p0pilot/control_roles_20261104/analysis.json')['score_bindings'].items():assert sha(R/p)==h,p
 result=dict(training=0,SAT=0,model_forward=0,labels_modified=False,old_inputs_predictions_masks_unchanged=True,new_loader_passed=True,all_six_splits_verified=True,normalization_fit_count=int(norm['fit_count']),equal3_pairs_v2=sum(x['old_equal3_pairs'] for x in context),equal3_pairs_v3=sum(x['v3_equal3_pairs'] for x in context),local_conflict_role_records_v3=len(collision_roles),summary=summary,features_contract_sha=sha(O/'input_contract.json'))
 (O/'PREFLIGHT_COMPLETE.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(result)
if __name__=='__main__':main()
