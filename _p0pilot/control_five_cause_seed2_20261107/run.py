"""Cached-only symmetric threshold/score and AP decomposition,no torch/training/SAT."""
import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import collections,csv,hashlib,json,re
import numpy as np
from sklearn.metrics import average_precision_score
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;OLD=R/'_p0pilot/control_five_seed2_20261107';L=R/'_p0pilot/control_loader_po_20261105';C=R/'_p0pilot/control_boundary_v3_20261104'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def write(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def table(n,rr):
 if rr:
  with (O/n).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def avg(rr,keys,cols):
 gg=collections.defaultdict(list)
 for r in rr:gg[tuple(r[k] for k in keys)].append(r)
 return [dict(zip(keys,k),records=len(v),**{c:float(np.mean([r[c] for r in v])) for c in cols}) for k,v in sorted(gg.items())]
def decompose(p0,p1,t0,t1):
 a=float(np.mean(p0>=t0));b=float(np.mean(p1>=t0));c=float(np.mean(p0>=t1));d=float(np.mean(p1>=t1));return dict(baseline=a,new_scores_old_threshold=b,old_scores_new_threshold=c,new=d,delta=d-a,score_effect=.5*((b-a)+(d-c)),threshold_effect=.5*((c-a)+(d-b)),mean_score0=float(np.mean(p0)),mean_score1=float(np.mean(p1)),score_delta=float(np.mean(p1-p0)),threshold0=t0,threshold1=t1)
def roleclass(s):
 if re.fullmatch(r'T(?:N|I|M|X|Y)?\d+',s):return 'trigger'
 if re.fullmatch(r'P\d+',s):return 'payload'
 if re.fullmatch(r'S\d+',s):return 'payload_select'
 if s=='HJ':return 'output_hijack'
 return 'unclassified'
def main():
 assert not (O/'COMPLETE.json').exists() and read(OLD/'VERIFIED.json')['passed'];protected=dict(read(OLD/'EXECUTION_CONTRACT.json')['protected_files'])
 for n,h in read(OLD/'OUTPUT_MANIFEST.json').items():assert sha(OLD/n)==h,n;protected[str((OLD/n).relative_to(R))]=h
 for p in [OLD/'VERIFIED.json',R/'_p0pilot/control_five_multiseed_20261107/PUBLISHED.json',Path(__file__)]:protected[str(p.relative_to(R))]=sha(p)
 write('AUDIT_CONTRACT.json',dict(scope='all5cached predictions;GM/GBM primary pairedG0 contrasts,B/U secondary;all6splits/3frozen operatingrules',decomposition='2x2 saved scores and validation-only thresholds;symmetric order-average contributions,descriptive not training-causal',AP='threshold independent;positive-only/negative-only score replacement counterfactuals plus per-positive precision contribution;all fixedtrusted populations',role_scope='frozen known manufacturing roles plus explicit unclassified;no relabeling/protection',training=0,SAT=0,new_model_forwards=0,protected_files=protected))
 fc=read(C/'input_contract.json');views=rows(L/'view_dictionary.csv');vm={(v['key'],v['view']):v for v in views};arms=['G0','GB','GM','GBM','GAll'];ev={a:read(OLD/a/'EVALUATED.json') for a in arms};data={};mem={};pred={};roles={};normalization=np.load(C/'normalization.npz');decomp=[];AProws=[];positive_rows=[];coverage=[];flips=[]
 for key,q in fc['shared_inputs'].items():
  folder=R/q['folder'];a={n:np.load(folder/(n+'.npy'),mmap_mode='r') for n in ['x39','y','trusted','physical']};data[key]=a;roles[key]={}
  with np.load(L/f'PO_membership_{key}.npz') as z:mem[key]={k:z[k] for k in z.files}
  for arm in arms:pred[arm,key]=np.load(OLD/arm/(key+'_scores.npy'),mmap_mode='r')
 for r in rows(OLD/'frozen_role_assignments.csv'):roles[r['key']][int(r['row'])]=r['role_class']
 # Exact metrics for unchanged per-view populations;empty scopes not fabricated.
 for key,a in data.items():
  vv=[v for v in views if v['key']==key]
  for v in vv:
   lo,hi=int(v['start']),int(v['physical_stop']);ids=np.arange(lo,hi);trusted=a['trusted'][lo:hi]&a['physical'][lo:hi];scopeids={}
   for scope in ['normal_primary_added','normal_all','trojan_positive']:
    ii=ids[mem[key][scope][lo:hi]]
    if len(ii):scopeids[scope]=ii
   if v['kind']=='trojan':
    for cl in sorted({roles[key].get(int(i),'unclassified') for i in ids[trusted&(a['y'][lo:hi]==1)]}):scopeids['role/'+cl]=np.array([i for i in ids[trusted&(a['y'][lo:hi]==1)] if roles[key].get(int(i),'unclassified')==cl],np.int64)
   for arm in arms[1:]:
    p0=pred['G0',key];p1=pred[arm,key]
    for mode in ['historical_fpr5','val_recall80','val_recall90']:
     t0,t1=ev['G0']['thresholds'][mode],ev[arm]['thresholds'][mode]
     for scope,ii in scopeids.items():
      out=decompose(p0[ii],p1[ii],t0,t1);decomp.append(dict(arm=arm,key=key,operation=mode,source=v['source'],view=v['view'],scope=scope,nodes=len(ii),**out))
      if arm in ['GM','GBM'] and scope.startswith('role/'):
       for i in ii:
        hit0=bool(p0[i]>=t0);hit1=bool(p1[i]>=t1)
        if hit0!=hit1:flips.append(dict(arm=arm,key=key,operation=mode,source=v['source'],view=v['view'],row=int(i),role_class=scope[5:],score0=float(p0[i]),score1=float(p1[i]),threshold0=t0,threshold1=t1,baseline_hit=hit0,new_hit=hit1,new_score_old_threshold=bool(p1[i]>=t0),old_score_new_threshold=bool(p0[i]>=t1),PO_distance=float(a['x39'][i,30])))
    if v['kind']!='trojan':continue
    ii=ids[trusted];y=a['y'][ii];pos=y==1;neg=y==0
    if not (pos.any() and neg.any()):continue
    s0=p0[ii].astype(float);s1=p1[ii].astype(float);onlypos=np.where(pos,s1,s0);onlyneg=np.where(pos,s0,s1);ap0=average_precision_score(y,s0);ap1=average_precision_score(y,s1);apP=average_precision_score(y,onlypos);apN=average_precision_score(y,onlyneg);AProws.append(dict(arm=arm,key=key,source=v['source'],view=v['view'],positive=int(pos.sum()),negative=int(neg.sum()),AP0=float(ap0),AP1=float(ap1),AP_delta=float(ap1-ap0),new_positive_old_negative_AP=float(apP),old_positive_new_negative_AP=float(apN),positive_score_effect=float(.5*((apP-ap0)+(ap1-apN))),negative_score_effect=float(.5*((apN-ap0)+(ap1-apP)))))
    sorted0=np.sort(s0);sorted1=np.sort(s1);ps0=np.sort(s0[pos]);ps1=np.sort(s1[pos]);ns0=np.sort(s0[neg]);ns1=np.sort(s1[neg]);parts=[]
    for j in np.flatnonzero(pos):
     score0,score1=s0[j],s1[j];allabove0=len(s0)-int(np.searchsorted(sorted0,score0,'left'));allabove1=len(s1)-int(np.searchsorted(sorted1,score1,'left'));pa0=len(ps0)-int(np.searchsorted(ps0,score0,'left'));pa1=len(ps1)-int(np.searchsorted(ps1,score1,'left'));precision0=pa0/allabove0;precision1=pa1/allabove1;i=int(ii[j]);parts.append((precision0,precision1));positive_rows.append(dict(arm=arm,key=key,source=v['source'],view=v['view'],row=i,role_class=roles[key].get(i,'unclassified'),score0=score0,score1=score1,score_delta=score1-score0,precision_at_score0=precision0,precision_at_score1=precision1,view_AP_contribution_delta=(precision1-precision0)/int(pos.sum()),trusted_rank_fraction0=allabove0/len(s0),trusted_rank_fraction1=allabove1/len(s1),negative_above0=len(ns0)-int(np.searchsorted(ns0,score0,'left')),negative_above1=len(ns1)-int(np.searchsorted(ns1,score1,'left')),PO_distance=float(a['x39'][i,30])))
    assert abs(np.mean([x[0] for x in parts])-ap0)<1e-12 and abs(np.mean([x[1] for x in parts])-ap1)<1e-12
 table('threshold_score_per_view.csv',decomp);table('AP_decomposition_per_view.csv',AProws);table('positive_rank_contributions.csv',positive_rows);table('role_hit_flips.csv',flips)
 dc=['baseline','new_scores_old_threshold','old_scores_new_threshold','new','delta','score_effect','threshold_effect','mean_score0','mean_score1','score_delta','threshold0','threshold1'];ds=avg(decomp,['arm','key','operation','source','scope'],dc);table('threshold_score_per_source.csv',ds);dm=avg(ds,['arm','key','operation','scope'],dc);table('threshold_score_macro.csv',dm)
 ac=['AP0','AP1','AP_delta','new_positive_old_negative_AP','old_positive_new_negative_AP','positive_score_effect','negative_score_effect'];aps=avg(AProws,['arm','key','source'],ac);table('AP_decomposition_per_source.csv',aps);table('AP_decomposition_macro.csv',avg(aps,['arm','key'],ac))
 # Sum contribution byrole BEFORE source averaging;these are additive AP contributions,not role-subset AP.
 ap_role=[]
 group=collections.defaultdict(list)
 for r in positive_rows:group[tuple(r[k] for k in ['arm','key','source','view','role_class'])].append(r)
 for k,rr in sorted(group.items()):ap_role.append(dict(zip(['arm','key','source','view','role_class'],k),AP_contribution_delta=sum(r['view_AP_contribution_delta'] for r in rr),score_delta=float(np.mean([r['score_delta'] for r in rr])),positive_nodes=len(rr)))
 # Missing roles contribute0 within a fixed source/view when summingAP;do not drop absent roles.
 aligned=[]
 for r in AProws:
  for cl in ['trigger','payload','payload_select','output_hijack','mixed_lineage','unclassified']:
   rr=[x for x in ap_role if all(x[k]==r[k] for k in ['arm','key','source','view']) and x['role_class']==cl];aligned.append(dict(arm=r['arm'],key=r['key'],source=r['source'],view=r['view'],role_class=cl,AP_contribution_delta=rr[0]['AP_contribution_delta'] if rr else 0.))
 ar=avg(aligned,['arm','key','source','role_class'],['AP_contribution_delta']);table('AP_role_contribution_per_source.csv',ar)
 # Manufacturing rolecoupling;existing descendants only,no new graph correspondence or functions.
 specs=read(L/'ROLE_PO_PAIRS.json');pairs=rows(R/'_p0pilot/control_risk_20261104/source_node_pairs.csv');suffix={(r['control_source'],r['control_instance']):r['role_suffix'] for r in pairs if r['role_pair']=='True'};needs=collections.defaultdict(set)
 for r in pairs:
  if r['role_pair']!='True':continue
  key='orig_'+r['split']
  for view,name in [(r['control_source'],r['control_instance']),(r['trojan_source'],r['trojan_instance'])]:
   if (key,view) in vm:needs[key,view].add(name)
 spans=sorted((int(vm[k]['old_start']),int(vm[k]['old_stop']),k) for k in needs);resolved={};j=0;namepath=R/'_p0pilot/round32_20261029/orig_names/node_names_orig.txt'
 with namepath.open(encoding='utf-8') as f:
  for gid,line in enumerate(f):
   while j<len(spans) and gid>=spans[j][1]:j+=1
   if j==len(spans):break
   lo,hi,k=spans[j];name=line.strip().lstrip('\\')
   if gid>=lo and name in needs[k]:resolved[k,name]=int(vm[k]['start'])+gid-lo
 excluded=[]
 for r in pairs:
  if r['role_pair']!='True':continue
  key='orig_'+r['split'];ni=resolved.get(((key,r['control_source']),r['control_instance']));ti=resolved.get(((key,r['trojan_source']),r['trojan_instance']))
  if ni is None or ti is None:excluded.append(dict(key=key,source=r['control_source'],gate=r['control_instance'],reason='source_or_name_not_in_fixedsplit'));continue
  if not mem[key]['normal_primary_added'][ni]:excluded.append(dict(key=key,source=r['control_source'],gate=r['control_instance'],reason='outside_frozen_primary_region'));continue
  specs.append(dict(key=key,normal_source=r['control_source'],trojan_source=r['trojan_source'],normal_view=r['control_source'],trojan_view=r['trojan_source'],normal_source_gate=r['control_instance'],normal_rows=[ni],trojan_rows=[ti]))
 coupling=[];featurecache={}
 for spec in specs:
  key=spec['key'];a=data[key];ni=np.array(spec['normal_rows'],np.int64);ti=np.array(spec['trojan_rows'],np.int64);assert (a['trusted'][ni]&a['physical'][ni]).all() and (a['trusted'][ti]&a['physical'][ti]).all() and (a['y'][ni]==0).all() and (a['y'][ti]==1).all();cl=roleclass(suffix.get((spec['normal_source'],spec['normal_source_gate']),''))
  def norm(ii):
   x=np.array(a['x39'][ii],copy=True,dtype=np.float32);x[:,25:]=np.clip((x[:,25:]-normalization['mean'][25:])/normalization['std'][25:],-10,10);return x
  xn,xt=norm(ni),norm(ti);distance=np.sqrt(np.mean((xn[:,None,:]-xt[None,:,:])**2,2));minrms=float(distance.min());exact=bool(np.any(np.all(xn[:,None,:]==xt[None,:,:],axis=2)))
  for arm in ['GM','GBM']:
   p0,p1=pred['G0',key],pred[arm,key];ns=float(np.mean(p1[ni]-p0[ni]));ts=float(np.mean(p1[ti]-p0[ti]))
   for mode in ['historical_fpr5','val_recall80','val_recall90']:
    t0,t1=ev['G0']['thresholds'][mode],ev[arm]['thresholds'][mode];n=decompose(p0[ni],p1[ni],t0,t1);t=decompose(p0[ti],p1[ti],t0,t1);coupling.append(dict(arm=arm,key=key,operation=mode,normal_source=spec['normal_source'],trojan_source=spec['trojan_source'],view=spec['normal_view'],gate=spec['normal_source_gate'],role_class=cl,normal_nodes=len(ni),trojan_nodes=len(ti),normal_score_delta=ns,trojan_score_delta=ts,both_scores_fall=int(ns<-1e-6 and ts<-1e-6),normal_FPR_delta=n['delta'],trojan_recall_delta=t['delta'],normal_score_effect=n['score_effect'],normal_threshold_effect=n['threshold_effect'],trojan_score_effect=t['score_effect'],trojan_threshold_effect=t['threshold_effect'],normal_FPR0=n['baseline'],normal_FPR1=n['new'],trojan_recall0=t['baseline'],trojan_recall1=t['new'],new_normal_better_T_lost=int(n['delta']<0 and t['delta']<0),normal_PO_mean=float(np.mean(a['x39'][ni,30])),trojan_PO_mean=float(np.mean(a['x39'][ti,30])),minimum_normalized39_RMS=minrms,exact39_any=exact))
 table('manufacturing_coupling_per_view.csv',coupling);table('manufacturing_excluded.csv',excluded)
 cc=['normal_score_delta','trojan_score_delta','both_scores_fall','normal_FPR_delta','trojan_recall_delta','normal_score_effect','normal_threshold_effect','trojan_score_effect','trojan_threshold_effect','normal_FPR0','normal_FPR1','trojan_recall0','trojan_recall1','new_normal_better_T_lost','minimum_normalized39_RMS']
 cr=avg(coupling,['arm','key','operation','normal_source','trojan_source','gate','role_class'],cc);table('manufacturing_coupling_source_role.csv',cr);cs=avg(cr,['arm','key','operation','normal_source','trojan_source','role_class'],cc);table('manufacturing_coupling_source_class.csv',cs)
 for p in [L/'ROLE_PO_PAIRS.json',R/'_p0pilot/control_risk_20261104/source_node_pairs.csv',namepath]:protected[str(p.relative_to(R))]=sha(p)
 for p,h in protected.items():assert sha(R/p)==h,p
 write('PROTECTED_INPUTS.json',protected);write('COMPLETE.json',dict(passed=True,model_forwards=0,autograd_calls=0,training=0,SAT=0,roles_reused=True,AP_view_rows=len(AProws),threshold_view_rows=len(decomp),positive_rank_rows=len(positive_rows),manufacturing_view_rows=len(coupling),claim='descriptive fixedprediction decomposition;not causal attribution of training gradients;single seed'))
 print('FIVE_GROUP_CACHED_CAUSE_AUDIT_COMPLETE',flush=True)
if __name__=='__main__':main()
