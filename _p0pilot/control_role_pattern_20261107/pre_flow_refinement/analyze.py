"""Reuse predictions only; match features before reading scores; train/val only."""
import build as C
import numpy as np,collections,json
R=C.R;O=C.O;SEEDS=[42,1,2];ARMS=['G0','GB','GM','GBM','GAll'];CONTRASTS=[('GM','G0'),('GBM','GB'),('GBM','G0'),('GB','G0')]
def parts(y,p):
 order=np.argsort(-p,kind='stable');s=p[order];t=np.cumsum(y[order]==1);end=np.r_[np.flatnonzero(s[:-1]!=s[1:]),len(s)-1];g=np.searchsorted(end,np.arange(len(s)));q=np.zeros(len(y));q[order]=t[end[g]]/(end[g]+1)*(y[order]==1)/sum(y==1);return q
def boolv(s):return s=='True' or s is True
def f(s):return float(s) if s not in ['',None] else None
def average(rr,cols):return {k:float(np.mean([r[k] for r in rr if r[k] is not None])) if any(r[k] is not None for r in rr) else None for k in cols}
def group(rr,keys,cols,method='mean'):
 gg=collections.defaultdict(list)
 for r in rr:gg[tuple(r[k] for k in keys)].append(r)
 return [dict(zip(keys,k),records=len(v),**(average(v,cols) if method=='mean' else {c:sum(r[c] for r in v) for c in cols})) for k,v in sorted(gg.items())]
def main():
 assert C.read(O/'BUILD_COMPLETE.json')['passed'];lineage=C.rows(O/'NODE_LINEAGE.csv');ld={(r['key'],int(r['row'])):r for r in lineage};desc={(r['key'],int(r['row'])):r for r in C.rows(O/'LOCAL_DESCRIPTORS.csv')};links=C.rows(O/'FEATURE_NEAREST_LINKS.csv');views=[r for r in C.rows(R/'_p0pilot/control_loader_po_20261105/view_dictionary.csv') if r['key'] in C.KEYS];fc=C.read(C.V/'input_contract.json');data={k:{n:np.load(R/fc['shared_inputs'][k]['folder']/(n+'.npy'),mmap_mode='r') for n in ['y','trusted','physical']} for k in C.KEYS};protected={};scores=[];reproduce=0
 for protocol in ['selected','last200']:
  for seed in SEEDS:
   folder=R/f'_p0pilot/control_five_seed{seed}_20261107' if protocol=='selected' else R/f'_p0pilot/control_last200_20261107/seed{seed}';assert C.read(folder/'ANALYSIS_COMPLETE.json')['SAT']==0;refs={(r['arm'],r['key'],r['view']):r for r in C.rows(folder/'per_view_scope_PO.csv') if r['operation']=='val_recall80' and r['scope']=='trusted_all' and r['PO_bin']=='all' and r['kind']=='trojan'}
   for arm in ARMS:
    ev=C.read(folder/arm/'EVALUATED.json');protected[str((folder/arm/'EVALUATED.json').relative_to(R))]=C.sha(folder/arm/'EVALUATED.json');tau=ev['thresholds']['val_recall80'];t0=C.read(folder/'G0/EVALUATED.json')['thresholds']['val_recall80']
    for key,a in data.items():
     path=folder/arm/(key+'_scores.npy');assert C.sha(path)==ev['prediction_sha'][key];protected[str(path.relative_to(R))]=ev['prediction_sha'][key];p=np.load(path,mmap_mode='r')
     for v in [v for v in views if v['key']==key]:
      roots=[r for r in lineage if r['key']==key and r['view']==v['view']]
      if not roots:continue
      ids=np.arange(int(v['start']),int(v['physical_stop']));ids=ids[a['trusted'][ids]&a['physical'][ids]];local={int(i):j for j,i in enumerate(ids)};y=a['y'][ids];pv=p[ids];posparts=parts(y,pv) if (y==1).any() else np.zeros(len(ids));neg=np.sort(pv[y==0]);allp=np.sort(pv)
      if v['kind']=='trojan':assert abs(float(posparts.sum())-float(refs[arm,key,v['view']]['AP']))<1e-12;reproduce+=1
      for r in roots:
       i=int(r['row']);j=local[i];positive=r['side']=='positive';scores.append(dict(protocol=protocol,seed=seed,arm=arm,key=key,row=i,source=r['source'],view=r['view'],side=r['side'],role=r['role'],parents=r['parents'],score=float(p[i]),threshold=tau,hit=int(p[i]>=tau),hit_at_G0_threshold=int(p[i]>=t0),negative_above=int(len(neg)-np.searchsorted(neg,p[i],side='left')) if positive else None,AP_contribution=float(posparts[j]) if positive else None,risk_rank_fraction=float((len(allp)-np.searchsorted(allp,p[i],side='left'))/len(allp)),checkpoint_update=ev['selected']['epoch']))
   print('REUSED',protocol,seed,flush=True)
 C.table('NODE_PREDICTIONS.csv',scores);sl={(r['protocol'],r['seed'],r['arm'],r['key'],r['row']):r for r in scores};deltas=[]
 for r in scores:
  for arm,base in CONTRASTS:
   if r['arm']!=arm:continue
   b=sl[r['protocol'],r['seed'],base,r['key'],r['row']];meta=ld[r['key'],r['row']];d=desc[r['key'],r['row']];deltas.append(dict(protocol=r['protocol'],seed=r['seed'],comparison=arm+'-'+base,key=r['key'],row=r['row'],source=r['source'],view=r['view'],parents=r['parents'],side=r['side'],role=r['role'],gate=d['gate'],nature=meta['nature'],score_delta=r['score']-b['score'],hit_delta=r['hit']-b['hit'],hit_common_G0_tau_delta=r['hit_at_G0_threshold']-b['hit_at_G0_threshold'],negative_above_delta=None if r['negative_above'] is None else r['negative_above']-b['negative_above'],AP_contribution_delta=None if r['AP_contribution'] is None else r['AP_contribution']-b['AP_contribution'],score_decreased=int(r['score']-b['score']<-.001),rank_harmed=int(r['AP_contribution'] is not None and r['AP_contribution']-b['AP_contribution']< -1e-6),M_exposure_200=int(meta['M_exposure_200'])))
 C.table('NODE_DELTAS.csv',deltas);dl={(r['protocol'],r['seed'],r['comparison'],r['key'],r['row']):r for r in deltas};cols=['score_delta','hit_delta','hit_common_G0_tau_delta','negative_above_delta','AP_contribution_delta','score_decreased','rank_harmed']
 # Mean node scores/rates through view then source. AP contributions SUM within role/view.
 source=group(group(deltas,['protocol','seed','comparison','key','source','view','side','role'],cols),['protocol','seed','comparison','key','source','side','role'],cols);C.table('SOURCE_ROLE_CHANGES.csv',source)
 av=group([r for r in deltas if r['side']=='positive'],['protocol','seed','comparison','key','source','view','role'],['AP_contribution_delta'],'sum');aps=group(av,['protocol','seed','comparison','key','source','role'],['AP_contribution_delta']);C.table('SOURCE_ROLE_AP_CONTRIBUTIONS.csv',aps)
 # Pair nearest choices were fixed by features and exact coordinates before score loading.
 pairs=[];pairfeature=[];xf={k:dict(np.load(O/(k+'_features.npz'))) for k in C.KEYS};xi={k:{int(i):j for j,i in enumerate(z['rows'])} for k,z in xf.items()}
 for link in links:
  if not boolv(link['matched']):continue
  key=link['key'];i,j=int(link['positive_row']),int(link['normal_row']);pr,nr=ld[key,i],ld[key,j];a,b=desc[key,i],desc[key,j];x=xf[key]['normalized'];raw=xf[key]['raw'];ii,jj=xi[key][i],xi[key][j];difference=np.abs(x[ii]-x[jj]);top=np.argsort(-difference,kind='stable')[:5];pairfeature.append(dict(key=key,route=link['route'],positive_row=i,normal_row=j,positive_source=pr['source'],normal_source=nr['source'],positive_gate=pr['parents'],normal_gate=nr['parents'],positive_role=pr['role'],normal_role=nr['role'],recipe=pr['recipe'],gate=a['gate'],rms_z14=f(link['rms_z14']),feature_equal=link['feature_equal'],incoming_feature3_equal=link['incoming_feature3_equal'],top_feature_differences='|'.join(f"{fc['columns39'][t]}:{difference[t]:.5g}" for t in top if difference[t]>0),positive_PO=float(raw[ii,30]),normal_PO=float(raw[jj,30]),positive_fanout=a['fanout'],normal_fanout=b['fanout'],normal_exposure_200=int(nr['M_exposure_200']),nearest_ties=int(link['ties'])))
  for protocol in ['selected','last200']:
   for seed in SEEDS:
    for arm,base in CONTRASTS:
     comparison=arm+'-'+base;p=dl[protocol,seed,comparison,key,i];n=dl[protocol,seed,comparison,key,j];pairs.append(dict(protocol=protocol,seed=seed,comparison=comparison,key=key,route=link['route'],positive_row=i,normal_row=j,positive_source=pr['source'],normal_source=nr['source'],positive_parents=pr['parents'],normal_parents=nr['parents'],view=pr['view'],normal_view=nr['view'],recipe=pr['recipe'],gate=a['gate'],positive_role=pr['role'],normal_role=nr['role'],feature_equal=boolv(link['feature_equal']),feature_close=f(link['rms_z14'])<=.5,rms_z14=f(link['rms_z14']),gate_context2_equal=boolv(link['gate_context2_equal']),incoming_feature3_equal=boolv(link['incoming_feature3_equal']),normal_exposure_200=int(nr['M_exposure_200']),normal_score_delta=n['score_delta'],normal_hit_delta=n['hit_delta'],normal_hit_common_G0_tau_delta=n['hit_common_G0_tau_delta'],positive_score_delta=p['score_delta'],positive_negative_above_delta=p['negative_above_delta'],positive_AP_contribution_delta=p['AP_contribution_delta'],normal_score_decreased=n['score_decreased'],positive_rank_harmed=p['rank_harmed'],coupled=int(n['score_decreased'] and p['rank_harmed']),both_scores_decreased=int(n['score_decreased'] and p['score_decreased'])))
 C.table('PAIR_FEATURE_DETAILS.csv',pairfeature);C.table('PAIR_PREDICTION_CHANGES.csv',pairs)
 pc=['normal_score_delta','normal_hit_delta','normal_hit_common_G0_tau_delta','positive_score_delta','positive_negative_above_delta','positive_AP_contribution_delta','normal_score_decreased','positive_rank_harmed','coupled','both_scores_decreased'];basekeys=['protocol','seed','comparison','key','route','positive_source','normal_source','positive_role','normal_role','gate','feature_equal','gate_context2_equal'];ps=group(group(pairs,basekeys+['positive_parents','recipe'],pc),basekeys,pc);C.table('PAIR_OBJECT_THEN_SOURCE.csv',ps)
 # Stable node-patterns: same root/link/contrast, three paired seeds, never count views as seeds.
 g=collections.defaultdict(list)
 for r in pairs:g[tuple(r[k] for k in ['protocol','comparison','key','route','positive_row','normal_row'])].append(r)
 stable=[]
 for k,v in sorted(g.items()):
  assert len(v)==3 and {r['seed'] for r in v}==set(SEEDS);r=v[0];stable.append(dict(zip(['protocol','comparison','key','route','positive_row','normal_row'],k),**{z:r[z] for z in ['positive_source','normal_source','positive_parents','normal_parents','view','normal_view','recipe','gate','positive_role','normal_role','feature_equal','feature_close','rms_z14','gate_context2_equal','incoming_feature3_equal','normal_exposure_200']},normal_decreased_seeds=sum(x['normal_score_decreased'] for x in v),positive_rank_harmed_seeds=sum(x['positive_rank_harmed'] for x in v),coupled_seeds=sum(x['coupled'] for x in v),**{c+'_mean':float(np.mean([x[c] for x in v])) for c in pc[:6]}))
 C.table('PAIR_THREE_SEED_STABILITY.csv',stable)
 coverage=[]
 for key in C.KEYS:
  for route in ['all_M','exposed_M_only','manufacturing_counterpart']:
   z=[r for r in links if r['key']==key and r['route']==route];m=[r for r in z if boolv(r['matched'])];coverage.append(dict(key=key,route=route,eligible_positive_roots=len(z),matched=len(m),positive_sources=len({ld[key,int(r['positive_row'])]['source'] for r in m}),normal_sources=len({ld[key,int(r['normal_row'])]['source'] for r in m}),feature_equal=sum(boolv(r['feature_equal']) for r in m),feature_close=sum(f(r['rms_z14'])<=.5 for r in m),gate_context2_equal=sum(boolv(r['gate_context2_equal']) for r in m),incoming_feature3_equal=sum(boolv(r['incoming_feature3_equal']) for r in m)))
 C.table('MATCH_COVERAGE.csv',coverage)
 for p,h in protected.items():assert C.sha(R/p)==h,p
 for p,h in C.read(O/'BUILD_COMPLETE.json')['protected_inputs'].items():assert C.sha(R/p)==h,p
 (O/'ANALYSIS_COMPLETE.json').write_text(json.dumps(dict(passed=True,scope=C.KEYS,model_forwards=0,training=0,SAT=0,labels_changed=False,AP_view_reproductions=reproduce,match_score_independent=True,noise_guard='score decrease<-0.001;AP-contribution harm<-1e-6;descriptive only',protected_predictions=protected),indent=2),encoding='utf-8');print('ANALYSIS_COMPLETE',len(scores),len(pairs),flush=True)
if __name__=='__main__':main()
