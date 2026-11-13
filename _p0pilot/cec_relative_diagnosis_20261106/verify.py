"""Independent SVD/metric/history checks for the posthoc geometry audit."""
from pathlib import Path
import collections,csv,hashlib,json
import numpy as np
from sklearn.metrics import roc_auc_score
O=Path(__file__).resolve().parent;R=O.parents[1];OLD=R/'_p0pilot/cec_relative_seed42_20261106'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(n):
 with (O/n).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def main():
 done=read(O/'EXTRACTION_COMPLETE.json');contract=read(O/'ANALYSIS_CONTRACT.json');assert done['model_forwards']==7 and done['backwards']==done['optimizer_updates']==done['SAT']==done['test_reads']==0 and all(s['weights_and_BN_unchanged'] for s in done['states'])
 for p,h in contract['frozen_files'].items():assert sha(R/p)==h,p
 panels=read(O/'panels.json');primary=read(OLD/'PRIMARY_RESULT.json')['primary_sources'];panels['val_primary']=[t for t in panels['val'] if t['source'] in primary];unusedsrc={t['source'] for t in panels['train_unused_same_source']};panels['train_used_matched3']=[t for t in panels['train_used'] if t['source'] in unusedsrc]
 trained={t['triple_id'] for t in panels['train_used']};assert len(trained)==143 and len(panels['train_unused_same_source'])==75 and len(unusedsrc)==3
 assert not trained&{t['triple_id'] for t in panels['train_unused_same_source']}
 roles=lambda ts:{(t['source'],s) for t in ts for s in t['function_signatures']}
 assert not roles(panels['train_used'])&roles(panels['train_unused_same_source'])
 m={x['cone_id']:x for x in rows('cone_metadata.csv')};geos=rows('geometry.csv');met=rows('function_metrics.csv');ref=read(OLD/'PRIMARY_RESULT.json');checks=[]
 for panel in ['train_used','train_used_matched3','train_unused_same_source','val_primary']:
  tt=panels[panel];ids=sorted({c for t in tt for c in t['cones']});cnt=collections.Counter(m[c]['source'] for c in ids);w=np.array([1/(len(cnt)*cnt[m[c]['source']]) for c in ids]);ix={c:j for j,c in enumerate(ids)}
  for arm in ['INIT','Z','A_R','A_P','S_R','S_P']:
   domain='train' if panel.startswith('train') else 'val';path=O/f'{domain}_{arm}_remap9000.npz' if domain=='train' or arm=='INIT' else OLD/f'val_{arm}_remap9000.npz'
   with np.load(path) as f:
    addr={c:j for j,c in enumerate(f['cone_ids'].tolist())};index=[addr[c] for c in ids];xx=f['concat128'][index].astype(np.float64);zz=f['projection32'][index].astype(np.float64)
   for space,x in [('root64',xx[:,:64]),('projection32',zz)]:
    xc=x-(w[:,None]*x).sum(0);sv=np.linalg.svd(xc*np.sqrt(w[:,None]),compute_uv=False);energy=sv**2;p=energy/energy.sum();rank=float(np.exp(-np.sum(p[p>0]*np.log(p[p>0]))));pc=float(p[0]);g=next(r for r in geos if r['panel']==panel and r['arm']==arm and r['space']==space)
    assert abs(rank-float(g['effective_rank']))<1e-8 and abs(pc-float(g['pc1_energy']))<1e-10
    grouped=collections.defaultdict(list)
    for t in tt:
     vv=[x[ix[c]] for c in t['cones']]
     for a,r,p in [(0,1,3),(2,3,1),(1,0,2),(3,2,0)]:
      d=lambda j,k:float(np.sqrt(np.mean((vv[j]-vv[k])**2)));grouped[t['source']].append((d(a,r),d(a,p)))
    wins=[];aucs=[]
    for source,values in grouped.items():
     r,p=np.array(values).T;wins.append(np.mean((r<p)+.5*(r==p)));aucs.append(roc_auc_score([1]*len(r)+[0]*len(p),-np.r_[r,p]))
    win=float(np.mean(wins));auc=float(np.mean(aucs));published=next(r for r in met if r['panel']==panel and r['arm']==arm and r['space']==space and r['variant']=='raw');assert abs(win-float(published['source_macro_win']))<1e-12 and abs(auc-float(published['source_macro_auc']))<1e-12
    if panel=='val_primary' and arm!='INIT' and space=='root64':assert abs(win-ref['root64'][arm]['source_macro_win'])<1e-12 and abs(auc-ref['root64'][arm]['source_macro_auc'])<1e-12
    checks.append((panel,arm,space))
 # Verify host/source constant cannot discriminate any within-source triple.
 controls=[r for r in met if r['arm']=='METADATA' and r['space']=='source_constant_negative_control'];assert all(float(r['source_macro_win'])==float(r['source_macro_auc'])==.5 for r in controls)
 cent=rows('source_centering_invariance.csv');assert all(abs(float(r['source_center_win_change']))<1e-12 and abs(float(r['source_center_auc_change']))<1e-12 for r in cent)
 # Gate-group eta2 recomputed with independent weighted SVD scores (sign arbitrary).
 for panel in ['train_used','val_primary']:
  tt=panels[panel];ids=sorted({c for t in tt for c in t['cones']});cnt=collections.Counter(m[c]['source'] for c in ids);w=np.array([1/(len(cnt)*cnt[m[c]['source']]) for c in ids]);domain='train' if panel=='train_used' else 'val';path=O/'train_S_R_remap9000.npz' if domain=='train' else OLD/'val_S_R_remap9000.npz'
  with np.load(path) as f:ii={c:j for j,c in enumerate(f['cone_ids'].tolist())};x=f['concat128'][[ii[c] for c in ids],:64].astype(np.float64)
  xc=x-(w[:,None]*x).sum(0);u,s,vh=np.linalg.svd(xc*np.sqrt(w[:,None]),full_matrices=False);score=xc@vh[0];den=np.dot(w,score**2);between=0
  for gate in sorted({m[c]['gate'] for c in ids}):
   jj=np.array([m[c]['gate']==gate for c in ids]);mass=w[jj].sum();between+=mass*(np.dot(w[jj],score[jj])/mass)**2
  row=next(r for r in rows('PC1_associations.csv') if r['panel']==panel and r['arm']=='S_R' and r['space']=='root64');assert abs(between/den-float(row['pc1_gate_eta2']))<1e-10
 # Paired CE gaps come from real training batches, not a fresh model fit.
 for r in rows('training_target_fit.csv'):
  hist=read(OLD/r['arm']/'history.json');hh=hist[:10] if r['window']=='first10' else hist[-10:];cr=np.mean([x['S_R'] for x in hh]);cp=np.mean([x['S_P'] for x in hh]);assert abs(cr-float(r['CE_real']))<1e-12 and abs(cp-float(r['CE_permuted']))<1e-12
 # Train-only basis controls: independently reconstruct their held-out metrics.
 transfer=rows('train_basis_transfer_metrics.csv');transfer_checks=0
 ti=sorted({c for t in panels['train_used'] for c in t['cones']});vi=sorted({c for t in panels['val_primary'] for c in t['cones']});cnt=collections.Counter(m[c]['source'] for c in ti);tw=np.array([1/(len(cnt)*cnt[m[c]['source']]) for c in ti]);cats=sorted({m[c]['gate'] for c in ti});scales={}
 for key in ['members','depth','cut']:
  values=np.log1p([int(m[c][key]) for c in ti]);mu=tw@values;scales[key]=(mu,max(np.sqrt(tw@((values-mu)**2)),1e-12))
 design=[np.ones((len(vi),1))]
 for key in ['members','depth','cut']:
  mu,sd=scales[key];design.append(((np.log1p([int(m[c][key]) for c in vi])-mu)/sd)[:,None])
 design.append(np.array([[float(m[c]['gate']==gate) for gate in cats[1:]] for c in vi]));vd=np.concatenate(design,1);vix={c:j for j,c in enumerate(vi)}
 for arm in ['INIT','Z','A_R','A_P','S_R','S_P']:
  with np.load(O/f'train_projection_{arm}.npz') as f:basis=f['basis'];coef=f['coef'];assert np.allclose(basis.T@basis,np.eye(64),atol=1e-10)
  path=O/'val_INIT_remap9000.npz' if arm=='INIT' else OLD/f'val_{arm}_remap9000.npz'
  with np.load(path) as f:ii={c:j for j,c in enumerate(f['cone_ids'].tolist())};x=f['concat128'][[ii[c] for c in vi],:64].astype(np.float64)
  for variant,xx in [('raw',x),('train_PC1_removed',x@basis[:,1:]),('train_top2_removed',x@basis[:,2:]),('train_structure_residual',x-vd@coef)]:
   observed=collections.defaultdict(list)
   for t in panels['val_primary']:
    vv=[xx[vix[c]] for c in t['cones']]
    for a,r,p in [(0,1,3),(2,3,1),(1,0,2),(3,2,0)]:
     distance=lambda j,k:float(np.sqrt(np.mean((vv[j]-vv[k])**2)));observed[t['source']].append((distance(a,r),distance(a,p)))
   stats=[]
   for source,values in observed.items():
    rr,pp=np.array(values).T;stats.append((np.mean((rr<pp)+.5*(rr==pp)),roc_auc_score([1]*len(rr)+[0]*len(pp),-np.r_[rr,pp])))
   pub=next(v for v in transfer if v['arm']==arm and v['panel']=='val_primary' and v['variant']==variant);assert abs(np.mean([v[0] for v in stats])-float(pub['source_macro_win']))<1e-12 and abs(np.mean([v[1] for v in stats])-float(pub['source_macro_auc']))<1e-12;transfer_checks+=1
 # Independently reproduce the boundary flags via shortest-distance decomposition,
 # rather than the original (node,crossed_boundary) state traversal.
 from scipy.sparse import csr_matrix
 inp=read(R/'_p0pilot/control_boundary_v3_20261104/input_contract.json');cones={c['cone_id']:c for c in read(R/'_p0pilot/cec_joint_expand_20261105/final_cones.json')};br=rows('boundary_reach_cones.csv');wanted=collections.defaultdict(set)
 for row in br:
  c=cones[row['cone_id']];wanted[c['view']].update(t[1].strip().lstrip('\\') for t in c['leaves'] if t[0]=='Q')
 names=(R/'generate_trans/folds/hosts_bt31/data/processed/node_names_trans.txt').read_text(encoding='utf-8').splitlines();qmap={}
 for domain in ['train','val']:
  for view in inp['shared_inputs']['trans_'+domain]['views']:
   if view['view'] in wanted:qmap[view['view']]={name.strip().lstrip('\\'):view['start']+j for j,name in enumerate(names[view['old_start']:view['old_stop']]) if name.strip().lstrip('\\') in wanted[view['view']]}
 del names
 for domain in ['train','val']:
  conf=inp['shared_inputs']['trans_'+domain];path=R/conf['folder']/'edge_index.npy';assert sha(path)==inp['files'][str(path.relative_to(R))];ee=np.load(path,mmap_mode='r');mat=csr_matrix((np.ones(ee.shape[1],np.int8),(ee[1],ee[0])),shape=(conf['nodes'],conf['nodes']))
  for row in br:
   if row['split']!=domain:continue
   c=cones[row['cone_id']];boundary={qmap[c['view']][t[1].strip().lstrip('\\')] for t in c['leaves'] if t[0]=='Q'};dist={c['root_row']:0};front={c['root_row']}
   for depth in range(1,4):
    nxt=set()
    for node in front:
     for par in mat.indices[mat.indptr[node]:mat.indptr[node+1]]:
      par=int(par)
      if par not in dist:dist[par]=depth;nxt.add(par)
    front=nxt
   beyond=set()
   for q in boundary&dist.keys():
    layer={q}
    for _ in range(3-dist[q]):
     layer={int(p) for node in layer for p in mat.indices[mat.indptr[node]:mat.indptr[node+1]]};beyond.update(layer)
   assert bool(beyond)==(row['has_messages_beyond_freeQ']=='True') and len(beyond)==int(row['nodes_beyond_freeQ']) and len(set(c['graph_rows'])-dist.keys())==int(row['cone_members_missing_from_full3hop'])
  del mat,ee
 for p,h in contract['frozen_files'].items():assert sha(R/p)==h,p
 result=dict(passed=True,new_model_forwards=7,new_backwards=0,new_optimizer_updates=0,SAT=0,test_reads=0,old_files_and_checkpoints_unchanged=True,independent_weighted_SVD_and_metrics_checks=len(checks),independent_train_basis_transfer_checks=transfer_checks,independent_boundary_reach_cones=len(br),old_primary_metrics_reproduced=True,independent_gate_eta2_verified=True,source_center_invariance_verified=True,unused_functions_disjoint=True,statistics='posthoc source-weighted descriptive projections;no new GNN/detector training;not causal attribution',files_SHA={p.name:sha(p) for p in O.iterdir() if p.is_file() and p.suffix in ['.csv','.npz']})
 (O/'VERIFIED.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print('VERIFIED',len(checks))
if __name__=='__main__':main()
