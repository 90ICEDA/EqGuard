"""Descriptive geometry/statistical audit; cached arrays, no GNN training or SAT."""
import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import collections,csv,json
import numpy as np
from scipy.stats import rankdata
from sklearn.metrics import roc_auc_score
O=Path(__file__).resolve().parent;R=O.parents[1];OLD=R/'_p0pilot/cec_relative_seed42_20261106'
ARMS=['INIT','Z','A_R','A_P','S_R','S_P']
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def rows(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def table(n,rr):
 if not rr:return
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def weights(meta):
 counts=collections.Counter(m['source'] for m in meta);return np.array([1/(len(counts)*counts[m['source']]) for m in meta])
def corr(a,b,w):
 a=a-(a*w).sum();b=b-(b*w).sum();den=np.sqrt((w*a*a).sum()*(w*b*b).sum());return float((w*a*b).sum()/den) if den>1e-20 else None
def spear(a,b,w):return corr(rankdata(a),rankdata(b),w)
def eta(y,c,w):
 if len(set(c))<2:return None
 mean=(y*w).sum();den=(w*(y-mean)**2).sum();val=0
 for k in sorted(set(c)):
  ix=np.array([v==k for v in c]);mass=w[ix].sum();mu=(w[ix]*y[ix]).sum()/mass;val+=mass*(mu-mean)**2
 return float(val/den) if den>0 else None
def center_source(x,meta,w):
 out=x.copy()
 for source in sorted({m['source'] for m in meta}):
  ix=np.array([m['source']==source for m in meta]);out[ix]-=(x[ix]*w[ix,None]).sum(0)/w[ix].sum()
 return out
def pca(x,w):
 xc=x-(x*w[:,None]).sum(0);cov=(xc*w[:,None]).T@xc;ev,v=np.linalg.eigh(cov);order=np.argsort(ev)[::-1];ev=np.maximum(0,ev[order]);v=v[:,order];probs=ev/ev.sum() if ev.sum() else ev
 rank=float(np.exp(-np.sum(probs[probs>0]*np.log(probs[probs>0])))) if ev.sum() else 0
 return xc@v,v,dict(effective_rank=rank,pc1_energy=float(probs[0]),top2_energy=float(probs[:2].sum()),top4_energy=float(probs[:4].sum()),weighted_mean_std=float(np.sqrt(np.maximum(0,np.diag(cov))).mean()))
def design(meta,w,groups):
 xx=[np.ones((len(meta),1))]
 for g in groups:
  if g in ['members','depth','cut']:
   v=np.log1p(np.array([float(m[g]) for m in meta]));v-=np.dot(w,v);sd=np.sqrt(np.dot(w,v*v));xx.append((v/max(sd,1e-12))[:,None])
  else:
   cc=[m[g] for m in meta];keys=sorted(set(cc));xx.append(np.array([[float(c==k) for k in keys[1:]] for c in cc]).reshape(len(meta),-1))
 return np.concatenate(xx,1)
def residual(x,meta,w,groups):
 xx=design(meta,w,groups);sw=np.sqrt(w);coef,_,rank,_=np.linalg.lstsq(xx*sw[:,None],x*sw[:,None],rcond=1e-10);res=x-xx@coef;den=(w[:,None]*(x-(w[:,None]*x).sum(0))**2).sum();r2=1-(w[:,None]*res**2).sum()/den if den>0 else 0
 return res,float(r2),int(rank)
def metrics(x,ids,triples):
 ix={c:j for j,c in enumerate(ids)};per=[];ed=[]
 for t in triples:
  vv=[x[ix[c]] for c in t['cones']];real=[];wrong=[];third=[]
  for a,r,p,c in [(0,1,3,5),(2,3,1,5),(1,0,2,4),(3,2,0,4)]:
   distance=lambda j,k:float(np.sqrt(np.mean((vv[j]-vv[k])**2)))
   real.append(distance(a,r));wrong.append(distance(a,p));third.append(distance(a,c))
  per.append(dict(source=t['source'],triple_id=t['triple_id'],real=real,wrong=wrong,third=third))
 def stat(rr):
  a=np.array([d for r in rr for d in r['real']]);b=np.array([d for r in rr for d in r['wrong']]);c=np.array([d for r in rr for d in r['third']]);wins=np.mean((a<b)+.5*(a==b));three=np.mean([float(v==min(v,p,n))/sum(d==min(v,p,n) for d in [v,p,n]) for v,p,n in zip(a,b,c)])
  return float(wins),float(roc_auc_score([1]*len(a)+[0]*len(b),-np.r_[a,b])),float(three)
 ss=[stat([r for r in per if r['source']==source]) for source in sorted({r['source'] for r in per})];win,auc,three=stat(per)
 return dict(triples=len(triples),sources=len(ss),anchor_win=win,cross_auc=auc,source_macro_win=float(np.mean([s[0] for s in ss])),source_macro_auc=float(np.mean([s[1] for s in ss])),source_macro_threeway=float(np.mean([s[2] for s in ss])))
def main():
 assert read(O/'EXTRACTION_COMPLETE.json')['optimizer_updates']==0;panels=read(O/'panels.json');meta_by={m['cone_id']:m for m in rows(O/'cone_metadata.csv')}
 for m in meta_by.values():
  for k in ['members','depth','cut','mux','root_row']:m[k]=int(m[k])
 primary=read(OLD/'PRIMARY_RESULT.json')['primary_sources'];panels['val_primary']=[t for t in panels['val'] if t['source'] in primary];us={t['source'] for t in panels['train_unused_same_source']};panels['train_used_matched3']=[t for t in panels['train_used'] if t['source'] in us]
 # The selections are fixed, posthoc diagnostic panels, not revised primary trials.
 write('STATISTICS_PLAN.json',dict(pca='source-equal centered covariance,not per-dimension whitening;train/val separate;within-source PCA also',controls=['members','depth','cut','gate','host','source'],removals=['source_center','pc1_only','remove_pc1','remove_top2','structure_residual'],baselines=['logsize','logdepth','gate','joint_structure','source_constant_negative_control'],training_history='actual logged real/permuted CE on same batch;first10,last10,not a fixed-batch convergence test',inference_new=7,optimizer_updates=0,SAT=0,scope='posthoc mechanism analysis;descriptive WLS projection not a new detector;residualization not causal proof or replacement evaluation'))
 geometry=[];association=[];r2rows=[];metricrows=[];distancecorr=[];centering=[];conditions=[];metadist=[]
 for panel in ['train_used','train_used_matched3','train_unused_same_source','val_primary']:
  tt=panels[panel];ids=sorted({c for t in tt for c in t['cones']});meta=[meta_by[c] for c in ids];w=weights(meta);domain='train' if panel.startswith('train') else 'val';cnt=collections.Counter(m['source'] for m in meta)
  for field in ['members','depth','cut']:
   v=np.array([m[field] for m in meta],float);metadist.append(dict(panel=panel,field=field,weighted_mean=float(w@v),minimum=float(v.min()),maximum=float(v.max()),source_count=len(cnt),host_count=len({m['host'] for m in meta})))
  # Compare exactly the same anchors under fixed nonlearned structural distances.
  baselines={'logsize':np.log1p(np.array([m['members'] for m in meta]))[:,None],'logdepth':np.log1p(np.array([m['depth'] for m in meta]))[:,None],'gate':np.array([[float(m['gate']==k) for k in sorted({q['gate'] for q in meta})] for m in meta]),'joint_structure':design(meta,w,['members','depth','cut','gate'])[:,1:],'source_constant_negative_control':np.array([[float(m['source']==k) for k in sorted(cnt)] for m in meta])}
  for baseline,x in baselines.items():
   metricrows.append(dict(panel=panel,arm='METADATA',space=baseline,variant='fixed_baseline',**metrics(x,ids,tt)))
  flags={}
  for t in tt:
   a,b,c,d,e,f=[meta_by[k] for k in t['cones']];gates=a['gate']==c['gate'] and b['gate']==d['gate'];cut=a['cut']==c['cut'] and b['cut']==d['cut'];sb=lambda m:(m['members']-1).bit_length();sizebin=sb(a)==sb(c) and sb(b)==sb(d);boundary=a['leaf_tokens']==c['leaf_tokens'] and b['leaf_tokens']==d['leaf_tokens'];flags[t['triple_id']]=dict(gate=gates,gate_cut_size=gates and cut and sizebin,strict=gates and cut and sizebin and boundary)
  for arm in ARMS:
   path=O/f'{domain}_{arm}_remap9000.npz' if domain=='train' or arm=='INIT' else OLD/f'val_{arm}_remap9000.npz'
   with np.load(path) as cache:
    ix={c:j for j,c in enumerate(cache['cone_ids'].tolist())};index=[ix[c] for c in ids];cc=cache['concat128'][index].astype(np.float64);pp=cache['projection32'][index].astype(np.float64)
   for space,x in [('root64',cc[:,:64]),('mean64',cc[:,64:]),('concat128',cc),('projection32',pp)]:
    metricrows.append(dict(panel=panel,arm=arm,space=space,variant='raw',**metrics(x,ids,tt)))
    if space not in ['root64','projection32']:continue
    pc,v,info=pca(x,w);within=center_source(x,meta,w);_,_,wi=pca(within,w)
    geometry.append(dict(panel=panel,arm=arm,space=space,**info,within_source_effective_rank=wi['effective_rank'],within_source_pc1_energy=wi['pc1_energy'],between_source_energy_share=float(1-np.sum(w[:,None]*within**2)/np.sum(w[:,None]*(x-np.sum(w[:,None]*x,0))**2))))
    y=pc[:,0];row=dict(panel=panel,arm=arm,space=space,pc1_rho_logmembers=spear(y,np.log1p([m['members'] for m in meta]),w),pc1_rho_logdepth=spear(y,np.log1p([m['depth'] for m in meta]),w),pc1_rho_logcut=spear(y,np.log1p([m['cut'] for m in meta]),w),pc1_gate_eta2=eta(y,[m['gate'] for m in meta],w),pc1_host_eta2=eta(y,[m['host'] for m in meta],w),pc1_source_eta2=eta(y,[m['source'] for m in meta],w),pc1_recipe_eta2=eta(y,[m['recipe'] for m in meta],w));association.append(row)
    for target,yy in [('PC1',y[:,None]),('embedding',x)]:
     fits={}
     for name,gg in [('structure',['members','depth','cut','gate']),('structure_host',['members','depth','cut','gate','host']),('structure_host_source',['members','depth','cut','gate','host','source'])]:
      rr,r2,rank=residual(yy,meta,w,gg);fits[name]=r2;r2rows.append(dict(panel=panel,arm=arm,space=space,target=target,controls=name,R2=r2,design_rank=rank,observations=len(ids)))
    cen=metrics(within,ids,tt);rawm=metrics(x,ids,tt);assert abs(cen['source_macro_win']-rawm['source_macro_win'])<1e-12 and abs(cen['source_macro_auc']-rawm['source_macro_auc'])<1e-12
    centering.append(dict(panel=panel,arm=arm,space=space,source_center_win_change=cen['source_macro_win']-rawm['source_macro_win'],source_center_auc_change=cen['source_macro_auc']-rawm['source_macro_auc']))
    if space=='root64':
     residual_struct,_,_=residual(x,meta,w,['members','depth','cut','gate']);variants={'pc1_only':pc[:,:1],'remove_pc1':pc[:,1:],'remove_top2':pc[:,2:],'structure_residual':residual_struct,'source_center':within}
     for name,xx in variants.items():metricrows.append(dict(panel=panel,arm=arm,space=space,variant=name,**metrics(xx,ids,tt)))
     # Four distinct undirected true/wrong edges per triple, no reciprocal duplication.
     dist=[];size=[];depthdif=[];gate=[];src=[]
     jx={c:j for j,c in enumerate(ids)}
     for t in tt:
      for a,b in [(0,1),(2,3),(0,3),(2,1)]:
       ca,cb=t['cones'][a],t['cones'][b];ma,mb=meta_by[ca],meta_by[cb];dist.append(float(np.sqrt(np.mean((x[jx[ca]]-x[jx[cb]])**2))));size.append(abs(np.log1p(ma['members'])-np.log1p(mb['members'])));depthdif.append(abs(np.log1p(ma['depth'])-np.log1p(mb['depth'])));gate.append(float(ma['gate']!=mb['gate']));src.append(t['source'])
     counts=collections.Counter(src);ew=np.array([1/(len(counts)*counts[s]) for s in src]);distancecorr.append(dict(panel=panel,arm=arm,size_difference_rho=spear(dist,size,ew),depth_difference_rho=spear(dist,depthdif,ew),gate_mismatch_rho=spear(dist,gate,ew),distinct_undirected_edges=len(dist)))
     for condition in ['gate','gate_cut_size','strict']:
      ss=[t for t in tt if flags[t['triple_id']][condition]]
      if ss:conditions.append(dict(panel=panel,arm=arm,condition=condition,**metrics(x,ids,ss)))
 # Use paired loss logs from actual training to distinguish target fit from eval shift.
 histories=[]
 for arm in ARMS[1:]:
  hh=read(OLD/arm/'history.json')
  for window,h in [('first10',hh[:10]),('last10',hh[-10:])]:
   ce_r=float(np.mean([r['S_R'] for r in h]));ce_p=float(np.mean([r['S_P'] for r in h]));histories.append(dict(arm=arm,window=window,CE_real=ce_r,CE_permuted=ce_p,true_minus_wrong_distance_margin=ce_p-ce_r,selected_target_margin=(ce_r-ce_p) if arm.endswith('_P') else ce_p-ce_r,mean_common_negative=float(np.mean([r['different'] for r in h])),projection_std=float(np.mean([r['projection_std'] for r in h]))))
 for n,rr in [('geometry.csv',geometry),('PC1_associations.csv',association),('metadata_variance_accounting.csv',r2rows),('function_metrics.csv',metricrows),('pair_distance_correlations.csv',distancecorr),('source_centering_invariance.csv',centering),('conditional_metrics.csv',conditions),('training_target_fit.csv',histories),('panel_metadata_distribution.csv',metadist)]:table(n,rr)
 write('ANALYSIS_COMPLETE.json',dict(model_forwards_added=0,optimizer_updates=0,SAT=0,statistical_projections_only=True,source_centering_same_source_distance_invariance_verified=True,panels={k:dict(triples=len(v),sources=len({t['source'] for t in v})) for k,v in panels.items()},posthoc_diagnostic=True))
 print('ANALYSIS_COMPLETE',flush=True)
if __name__=='__main__':main()
