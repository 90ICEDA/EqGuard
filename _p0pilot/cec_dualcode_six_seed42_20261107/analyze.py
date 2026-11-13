"""Saved-root ranking,source/MUX and flat-distribution checks. No model calls."""
from pathlib import Path
import csv,importlib.util,json
import numpy as np
O=Path(__file__).resolve().parent;R=O.parents[1]
def load(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
A=load('retained_metrics',R/'_p0pilot/cec_repaired_zrp_seed42_20261107/analyze.py')
def read(n):return json.loads((O/n).read_text(encoding='utf-8-sig'))
def table(n,rr):
 if rr:
  with (O/n).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def cached(domain,arm,tag):
 with np.load(O/f'{domain}_{arm}_tag{tag}.npz') as z:return z['cone_ids'].tolist(),z['root64'].astype(float)
def queries(units,ids,x):
 ix={c:i for i,c in enumerate(ids)};result={}
 for u in units:
  v=x[[ix[c] for c in u['cones']]];n=u['functions']
  for f in range(n):
   for side in [0,1]:
    ds=np.sqrt(np.mean((v[2*f+side]-v[[2*j+1-side for j in range(n)]])**2,1)+1e-12);p=np.exp(-ds+ds.min());p/=p.sum();other=np.array([j for j in range(n) if j!=f]);margin=ds[other]-ds[f];sd=float(ds.std());result[u['unit_id'],f,side]=dict(p=p,d=ds,win=(margin>0).astype(float)+.5*(margin==0),normalized_margin=margin/max(sd,1e-8),source=u['source'],has_mux=u.get('has_mux',False),entropy=float(-np.sum(p*np.log(p))/np.log(n)),candidate_distance_std=sd,pmax=float(p.max()),distance_mean=float(ds.mean()),weight=1/(len(units)*2*n))
 return result
def groups(pp):
 gg=dict(pp)
 for domain,name in [('train','train_frozen_pool'),('val','val_H3_primary')]:
  us=pp[name]
  for mux in [False,True]:gg[domain+('_MUX' if mux else '_nonMUX')]=[u for u in us if bool(u['has_mux'])==mux]
  for n in [2,3]:gg[domain+f'_candidates{n}']=[u for u in us if u['functions']==n]
  for source in sorted({u['source'] for u in us}):
   gg[domain+'_source/'+source]=[u for u in us if u['source']==source]
   for mux in [False,True]:gg[domain+'_source/'+source+('/MUX' if mux else '/nonMUX')]=[u for u in us if u['source']==source and bool(u['has_mux'])==mux]
 return {k:v for k,v in gg.items() if v}
def main():
 assert read('COMPLETE.json')['actual_optimizer_updates']==192;pp=read('EVALUATION_PANELS.json');gg=groups(pp);arms=['INIT','Z0','Z1','R0','R1','P0','P1'];metrics=[];units=[];pairs=[];geometry=[]
 for tag in range(9000,9012):
  for arm in arms:
   for domain in ['train','val']:
    ids,x=cached(domain,arm,tag)
    for group,uu in gg.items():
     if not group.startswith(domain+'_'):continue
     rr=A.unit_records(uu,ids,x);summary,_,_=A.stats(rr);qq=queries(uu,ids,x);mean=lambda key:float(sum(q['weight']*q[key] for q in qq.values()))
     metrics.append(dict(tag=tag,arm=arm,group=group,**summary,normalized_candidate_entropy=mean('entropy'),candidate_distance_std=mean('candidate_distance_std'),max_candidate_probability=mean('pmax'),candidate_distance_mean=mean('distance_mean'),normalized_pair_margin=float(sum(q['weight']*q['normalized_margin'].mean() for q in qq.values()))))
     if group in ['train_frozen_pool','val_H3_primary']:
      units.extend(dict(tag=tag,arm=arm,group=group,**{k:v for k,v in r.items() if k not in ['real_distances','wrong_distances']}) for r in rr);ix={c:i for i,c in enumerate(ids)};sub=sorted({c for u in uu for c in u['cones']});geometry.append(dict(tag=tag,arm=arm,group=group,**A.geometry(x[[ix[c] for c in sub]])))
 table('evaluation_metrics.csv',metrics);table('unit_metrics.csv',units);table('representation_geometry.csv',geometry)
 # Disjoint paired evaluation maps,all reported,unit weighting preserved.
 for domain,uu in [('train',pp['train_frozen_pool']),('val',pp['val_H3_primary'])]:
  for arm in arms:
   for ta in [9000,9002,9004,9006,9008,9010]:
    ia,xa=cached(domain,arm,ta);ib,xb=cached(domain,arm,ta+1)
    for group,us in gg.items():
     if not group.startswith(domain+'_') or group in ['val_old_PO','val_new_PO']:continue
     qa,qb=queries(us,ia,xa),queries(us,ib,xb);js=flip=0
     for key,a in qa.items():
      b=qb[key];p,q=a['p'],b['p'];m=(p+q)/2;js+=a['weight']*.5*(p@np.log(p/m)+q@np.log(q/m));flip+=a['weight']*float(np.mean(a['win']!=b['win']))
     pairs.append(dict(domain=domain,arm=arm,group=group,tag_a=ta,tag_b=ta+1,weighted_JS=float(js),pairwise_rank_flip_rate=float(flip)))
 table('encoding_stability.csv',pairs)
 comparisons=[]
 for tag in range(9000,9012):
  for group in gg:
   rows={r['arm']:r for r in metrics if r['tag']==tag and r['group']==group}
   for a,b in [('R1','R0'),('R1','P1'),('R1','Z1'),('R0','P0'),('Z1','Z0'),('P1','P0'),('R1','INIT')]:
    comparisons.append(dict(tag=tag,group=group,comparison=a+'-'+b,units=rows[a]['units'],win_difference=rows[a]['family_macro_win']-rows[b]['family_macro_win'],entropy_difference=rows[a]['normalized_candidate_entropy']-rows[b]['normalized_candidate_entropy'],distance_std_ratio=rows[a]['candidate_distance_std']/max(rows[b]['candidate_distance_std'],1e-12),normalized_margin_difference=rows[a]['normalized_pair_margin']-rows[b]['normalized_pair_margin']))
 table('comparisons.csv',comparisons)
 primary=[r for r in metrics if r['group']=='val_H3_primary'];table('PRIMARY_METRICS.csv',primary)
 result=dict(primary_tag=9000,primary='73H3 root64 familymacro pairwise win;fixedlast32;no detectorAP claim',main={r['arm']:r for r in primary if r['tag']==9000},mean_new6={a:float(np.mean([r['family_macro_win'] for r in primary if r['arm']==a and r['tag']>=9006])) for a in arms},mean_all12={a:float(np.mean([r['family_macro_win'] for r in primary if r['arm']==a])) for a in arms},training_updates=192,SAT=0,finetune=0,test_reads=0)
 (O/'PRIMARY_RESULT.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps({k:result[k] for k in ['mean_new6','mean_all12']}))
if __name__=='__main__':main()
