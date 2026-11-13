"""Exploratory fixed train-basis projections, no GNN updates or val fitting."""
from pathlib import Path
import csv,json
import numpy as np
from analyze import read,rows,table,weights,pca,metrics
O=Path(__file__).resolve().parent;R=O.parents[1];OLD=R/'_p0pilot/cec_relative_seed42_20261106'
def main():
 panels=read(O/'panels.json');val_sources=read(OLD/'PRIMARY_RESULT.json')['primary_sources'];train=panels['train_used'];val=[t for t in panels['val'] if t['source'] in val_sources];metadata={m['cone_id']:m for m in rows(O/'cone_metadata.csv')}
 for m in metadata.values():
  for k in ['members','depth','cut']:m[k]=int(m[k])
 ti=sorted({c for t in train for c in t['cones']});vi=sorted({c for t in val for c in t['cones']});tm=[metadata[c] for c in ti];vm=[metadata[c] for c in vi];w=weights(tm)
 # All coefficients/normalization/category vocabulary come only from train.
 stats={}
 for k in ['members','depth','cut']:
  x=np.log1p([m[k] for m in tm]);mu=w@x;sd=np.sqrt(w@((x-mu)**2));stats[k]=(mu,max(sd,1e-12))
 cats=sorted({m['gate'] for m in tm})
 def design(mm):
  cols=[np.ones((len(mm),1))]
  for k in ['members','depth','cut']:
   mu,sd=stats[k];cols.append(((np.log1p([m[k] for m in mm])-mu)/sd)[:,None])
  cols.append(np.array([[float(m['gate']==c) for c in cats[1:]] for m in mm]));return np.concatenate(cols,1)
 xt,xv=design(tm),design(vm);out=[];models={}
 for arm in ['INIT','Z','A_R','A_P','S_R','S_P']:
  with np.load(O/f'train_{arm}_remap9000.npz') as f:
   ix={c:j for j,c in enumerate(f['cone_ids'].tolist())};tx=f['concat128'][[ix[c] for c in ti],:64].astype(np.float64)
  path=O/'val_INIT_remap9000.npz' if arm=='INIT' else OLD/f'val_{arm}_remap9000.npz'
  with np.load(path) as f:
   ix={c:j for j,c in enumerate(f['cone_ids'].tolist())};vx=f['concat128'][[ix[c] for c in vi],:64].astype(np.float64)
  _,basis,_=pca(tx,w);coef=np.linalg.lstsq(xt*np.sqrt(w[:,None]),tx*np.sqrt(w[:,None]),rcond=1e-10)[0]
  for domain,x,ids,tt,dd in [('train_used',tx,ti,train,xt),('val_primary',vx,vi,val,xv)]:
   for name,y in [('raw',x),('train_PC1_removed',x@basis[:,1:]),('train_top2_removed',x@basis[:,2:]),('train_structure_residual',x-dd@coef)]:out.append(dict(arm=arm,panel=domain,variant=name,**metrics(y,ids,tt)))
  models[arm]=dict(basis=basis,coef=coef)
  np.savez_compressed(O/f'train_projection_{arm}.npz',basis=basis,coef=coef)
 table('train_basis_transfer_metrics.csv',out)
 (O/'TRANSFER_DIAGNOSTIC.json').write_text(json.dumps(dict(posthoc_supplement=True,projection_estimation='train_used858 endpoints;source-equal;no paired targets or val used in coefficient estimation',fixed_removals=[1,2],unknown_val_gate_categories=sorted({m['gate'] for m in vm}-set(cats)),optimizer_updates=0,model_forwards=0,SAT=0,note='descriptive projections,not a new validated detector or replacement of frozen metric'),ensure_ascii=False,indent=2),encoding='utf-8');print('TRANSFER_DIAGNOSTIC_COMPLETE')
if __name__=='__main__':main()
