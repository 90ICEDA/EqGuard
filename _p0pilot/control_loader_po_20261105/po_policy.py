"""Frozen PO bins and score-only summaries. No fitting, models or threshold tuning."""
import numpy as np
BIN_NAMES=['unreachable','PO0','PO1_2','PO3_5','PO6plus']
def bin_distance(raw):
 d=np.asarray(raw)
 if not np.isfinite(d).all() or not np.equal(d,np.rint(d)).all() or (d< -1).any():raise ValueError('PO distance must be finite integer>=-1')
 return np.select([d==-1,d==0,(d>=1)&(d<=2),(d>=3)&(d<=5),d>=6],[0,1,2,3,4],default=-9).astype(np.int8)
def score_counts(y,scores,threshold):
 y=np.asarray(y);scores=np.asarray(scores)
 if y.shape!=scores.shape or not np.isin(y,[0,1]).all() or not np.isfinite(scores).all() or ((scores<0)|(scores>1)).any() or not np.isfinite(threshold):raise ValueError('Invalid labels/scores/threshold')
 positive=y==1;negative=y==0;p=int(positive.sum());n=int(negative.sum());hit=scores>=threshold
 out=dict(nodes=len(y),positive=p,negative=n,FP=int(hit[negative].sum()),TP=int(hit[positive].sum()),FPR=float(hit[negative].mean()) if n else None,recall=float(hit[positive].mean()) if p else None,normal_alarm=bool(hit[negative].any()) if n else None)
 if p and n:
  from sklearn.metrics import average_precision_score,roc_auc_score
  out.update(AP=float(average_precision_score(y,scores)),AUC=float(roc_auc_score(y,scores)))
 else:out.update(AP=None,AUC=None)
 return out
def worst_rank_fraction(all_physical_scores,region_scores):
 allp=np.asarray(all_physical_scores);p=np.asarray(region_scores)
 if not len(allp) or not len(p):return None
 return (len(allp)-np.searchsorted(np.sort(allp),p,side='left'))/len(allp)
def standardized(values,weights):
 # Missing supported strata invalidate the total; never silently renormalize.
 if len(values)!=len(weights):raise ValueError('Bin shape mismatch')
 if any(w>0 and (v is None or not np.isfinite(v)) for v,w in zip(values,weights)):return None
 return float(sum(v*w for v,w in zip(values,weights) if w>0))
def boundary_checks():
 assert np.array_equal(bin_distance(np.array([-1,0,1,2,3,5,6,100])),[0,1,2,2,3,3,4,4])
 for x in [[-2],[np.nan],[.5],[np.inf]]:
  try:bin_distance(x)
  except ValueError:pass
  else:raise AssertionError(x)
 z=score_counts(np.array([0,0,1]),np.array([.5,.49,.5]),.5);assert z['FP']==1 and z['TP']==1 and z['FPR']==.5
 assert score_counts(np.zeros(2),np.array([.1,.2]),.5)['AP'] is None
 assert score_counts(np.array([],int),np.array([]),.5)['FPR'] is None
 assert standardized([None,.5],[.2,.8]) is None and standardized([None,.5],[0,1])==.5
 assert worst_rank_fraction([.5,.5,.1],[.5])[0]==2/3
