"""Independent materialization of every arm/step, counts and lineage checks. CPU only."""
from pathlib import Path
import numpy as np
import json,csv,collections,hashlib
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;P=R/'_p0pilot/control_overall_contract_20261105';V=R/'_p0pilot/control_boundary_v3_20261104'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def load(p):
 with np.load(p) as z:return {k:z[k] for k in z.files}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(name,rr):
 with (O/name).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def stats(dm,variant,scope,cat,ids,weights,s,x,norm):
 assert len(ids)>0;nn=np.clip((x[s['N'][ids],25:]-norm['mean'][25:])/norm['std'][25:],-10,10);hh=np.clip((x[s['H'][ids],25:]-norm['mean'][25:])/norm['std'][25:],-10,10);delta=nn-hh;gap=np.average(delta,axis=0,weights=weights);rawdiff=(x[s['N'][ids],32]-x[s['H'][ids],32])/norm['std'][32]
 return dict(domain=dm,variant=variant,scope=scope,block=cat,pairs=len(ids),weighted_entries=int(weights.sum()),fanout_signed_train_z=float(np.average(rawdiff,weights=weights)),fanout_abs_train_z=float(np.average(np.abs(rawdiff),weights=weights)),fanout_max_abs_train_z=float(np.abs(rawdiff).max()),twohop_count_normal_mean=float(np.average(np.rint(np.expm1(x[s['N'][ids],32])),weights=weights)),twohop_count_H_mean=float(np.average(np.rint(np.expm1(x[s['H'][ids],32])),weights=weights)),largest_14d_mean_gap=float(np.abs(gap).max()),largest_gap_column=int(25+np.abs(gap).argmax()),pair_weight_concentration_equivalent=float(weights.sum()**2/np.square(weights.astype(float)).sum()))
def main():
 assert (O/'PREPARED.json').exists();assert not (O/'VERIFIED.json').exists();c=read(O/'CONTRACT.json');base=read(V/'input_contract.json');norm=load(V/'normalization.npz');vs=list(csv.DictReader((P/'view_dictionary.csv').open(encoding='utf-8-sig')));step_rows=[];group_rows=[];node_rows=[];source_rows=[];balance=[];msource=[];strata=[];global_sources=collections.defaultdict(collections.Counter);global_source_steps=collections.defaultdict(lambda:collections.defaultdict(lambda:np.zeros(200,np.int64)));sourcekinds={v['source']:v['kind'] for v in vs};fanout_audit=list(csv.DictReader((O/'M_fanout_pair_audit.csv').open(encoding='utf-8-sig')))
 for dm in ['orig','trans']:
  key=dm+'_train';s=load(O/('pools_'+key+'.npz'));sources=read(O/('sources_'+key+'.json'));d=R/base['shared_inputs'][key]['folder'];x=np.load(d/'x39.npy',mmap_mode='r');y=np.load(d/'y.npy',mmap_mode='r');trusted=np.load(d/'trusted.npy',mmap_mode='r');physical=np.load(d/'physical.npy',mmap_mode='r');common=np.load(O/('common_'+key+'.npy'));vm={int(v['view_id']):v for v in vs if v['key']==key};row_source=np.full(len(y),-1,np.int16);row_control=np.zeros(len(y),bool)
  for v in vm.values():row_source[int(v['start']):int(v['physical_stop'])]=sources.index(v['source']);row_control[int(v['start']):int(v['physical_stop'])]=v['kind']=='control'
  pos=s['positive'];assert len(pos)==c['domains'][dm]['positive'];assert (physical[pos]&trusted[pos]&(y[pos]==1)&~row_control[pos]).all();assert not np.intersect1d(s['common_negative'],np.r_[s['N'],s['H']]).size;assert len(np.unique(s['N']))==len(s['N'])==len(np.unique(s['H']));assert not np.intersect1d(s['N'],s['H']).size
  for ii in [s['N'],s['H']]:assert (physical[ii]&trusted[ii]&(y[ii]==0)).all()
  assert row_control[s['N']].all() and not row_control[s['H']].any();assert np.array_equal(row_source[s['N']],s['normal_source']) and np.array_equal(row_source[s['H']],s['H_source'])
  assert np.isin(common,s['common_negative']).all() and common.shape==(200,8192);cc=np.bincount(common.ravel(),minlength=len(y));assert cc.max()<=128
  cq=np.bincount(row_source[common.ravel()],minlength=len(sources));assert cq.max()<=160000
  mainseq=np.load(O/('main_fanout05_'+key+'_pairs.npy'));wideseq=np.load(O/('sensitivity_wideM_'+key+'_pairs.npy'));assert np.array_equal(mainseq[:,:48],wideseq[:,:48]) and np.array_equal(mainseq[:,96:],wideseq[:,96:])
  allmi=np.flatnonzero(s['category']==1)
  for variant in c['variants']:
   seq=np.load(O/(variant+'_'+key+'_pairs.npy'));assert seq.shape==(200,sum(c['domains'][dm]['block_entries'].values()));counts=np.bincount(seq.ravel(),minlength=len(s['N']));assert counts.max()<=128
   if variant=='main_fanout05':assert s['main_eligible'][seq].all()
   for col,cat in [(slice(0,48),0),(slice(48,96),1),(slice(96,None),2)]:assert (s['category'][seq[:,col]]==cat).all()
   for name,ii in [('B',np.flatnonzero(s['category']==0)),('M',allmi if variant=='sensitivity_wideM' else allmi[s['main_eligible'][allmi]]),('U',np.flatnonzero(s['category']==2))]:
    balance.append(stats(dm,variant,'eligible_pool',name,ii,np.ones(len(ii),np.int64),s,x,norm));used=ii[counts[ii]>0];balance.append(stats(dm,variant,'actual_200_exposure',name,used,counts[used],s,x,norm))
   for nsource in sorted(set(s['normal_source'][allmi])):
    ii=allmi[s['normal_source'][allmi]==nsource];jj=ii[s['main_eligible'][ii]];msource.append(dict(domain=dm,variant=variant,source=sources[int(nsource)],old_M_pairs=len(ii),strict_M_pairs=len(jj),fanout_held=len(ii)-len(jj),used_M_pairs=int((counts[ii]>0).sum()),M_entries_200=int(counts[ii].sum()),source_status='fully_held_fanout' if not len(jj) else 'partially_held_fanout' if len(jj)<len(ii) else 'all_eligible'))
   for host,recipe,gate in sorted({(vm[int(s['Nview'][i])]['host'],vm[int(s['Nview'][i])]['recipe'],int(np.argmax(x[s['N'][i],:25]))) for i in allmi}):
    ii=np.array([i for i in allmi if vm[int(s['Nview'][i])]['host']==host and vm[int(s['Nview'][i])]['recipe']==recipe and int(np.argmax(x[s['N'][i],:25]))==gate]);ee=ii[s['main_eligible'][ii]] if variant=='main_fanout05' else ii;uu=ii[counts[ii]>0];strata.append(dict(domain=dm,variant=variant,host=host,recipe=recipe,gate=base['columns39'][gate],old_M_pairs=len(ii),eligible_M_pairs=len(ee),used_M_pairs=len(uu),M_entries_200=int(counts[ii].sum()),weighted_signed_fanout_z=float(np.average((x[s['N'][uu],32]-x[s['H'][uu],32])/norm['std'][32],weights=counts[uu])) if len(uu) else None))
   for arm,modes in c['arms'].items():
    chooseN=np.array([modes[int(k)]=='N' for k in s['category']]);endpoint=np.where(chooseN,s['N'],s['H']);cum=np.zeros(len(y),np.int64);source_cum=np.zeros(len(sources),np.int64);extra_cum=np.zeros(len(sources),np.int64)
    for step in range(200):
     extras=endpoint[seq[step]];negative=np.r_[common[step],extras];assert len(np.unique(negative))==len(negative)==c['domains'][dm]['negative_per_update'];assert (trusted[negative]&physical[negative]&(y[negative]==0)).all();assert not np.intersect1d(pos,negative).size
     ncontrols=int(row_control[negative].sum());expected=sum(n for (cat,n) in c['domains'][dm]['block_entries'].items() if modes[['B','M','U'].index(cat)]=='N');assert ncontrols==expected;assert arm!='G0' or ncontrols==0
     cum[negative]+=1;sc=np.bincount(row_source[negative],minlength=len(sources));ec=np.bincount(row_source[extras],minlength=len(sources));common_sc=np.bincount(row_source[common[step]],minlength=len(sources));assert common_sc.max()<=1024 and ec.max()<=32 and sc.max()<=1056;source_cum+=sc;extra_cum+=ec
     for j in np.flatnonzero(sc):global_source_steps[(variant,arm)][sources[j]][step]+=sc[j]
     step_rows.append(dict(domain=dm,variant=variant,arm=arm,update=step+1,positive=len(pos),negative=len(negative),unique_negative=len(negative),duplicate_negative=0,normal_control_entries=ncontrols,max_common_source_entries=int(common_sc.max()),max_extra_source_entries=int(ec.max())))
    assert cum.max()<=128 and extra_cum.max()<=3200 and source_cum.max()<=163200
    expected_hist=np.sort(np.r_[cc[cc>0],counts[counts>0]]);assert np.array_equal(np.sort(cum[cum>0]),expected_hist)
    for j in np.flatnonzero(source_cum):
     source=sources[j];global_sources[(variant,arm)][source]+=int(source_cum[j]);source_rows.append(dict(domain=dm,variant=variant,arm=arm,source=source,kind=sourcekinds[source],common_entries_200=int(cq[j]),extra_entries_200=int(extra_cum[j]),total_negative_entries_200=int(source_cum[j])))
    for label,ccnt in [('common',cc),('all_negative',cum)]:
     weights=ccnt[ccnt>0];node_rows.append(dict(domain=dm,variant=variant,arm=arm,scope=label,unique_nodes=len(weights),entries_200=int(weights.sum()),minimum_exposure=int(weights.min()),maximum_exposure=int(weights.max()),weight_concentration_equivalent=float(weights.sum()**2/np.square(weights.astype(float)).sum())))
    group_rows.append(dict(domain=dm,variant=variant,arm=arm,positive_per_update=len(pos),common_negative_per_update=8192,negative_per_update=c['domains'][dm]['negative_per_update'],normal_control_per_update=expected,negative_unique_200=int((cum>0).sum()),negative_entries_200=int(cum.sum()),max_negative_node_exposure=int(cum.max()),max_source_negative_round=int(source_cum.max())))
   print('verified',dm,variant,flush=True)
  del x,y,trusted,physical
 combined=[]
 for (variant,arm),counter in global_sources.items():
  assert max(counter.values())<=326400
  for source,q in counter.items():
   ss=global_source_steps[(variant,arm)][source];assert int(ss.sum())==q and ss.max()<=2112;combined.append(dict(variant=variant,arm=arm,source=source,kind=sourcekinds[source],negative_entries_two_domains_200=q,max_entries_two_domains_per_update=int(ss.max())))
 for name,rr in [('step_fairness.csv',step_rows),('group_budgets.csv',group_rows),('node_exposure.csv',node_rows),('source_exposure_actual.csv',source_rows),('source_exposure_two_domains.csv',combined),('balance.csv',balance),('M_source_coverage.csv',msource),('M_host_recipe_gate.csv',strata)]:dump(name,rr)
 for name,hh in c['inputs'].items():assert sha(R/name)==hh,name
 previous=read(P/'COMPLETE.json')
 for name,hh in previous['files'].items():assert sha(R/name)==hh,name
 verified=dict(status='OFFLINE_CHECKS_PASSED_NO_TRAINING_AUTHORIZATION',training=0,model_forward=0,SAT=0,old_results_and_v3_inputs_unchanged=True,labels_changed=False,all_five_per_step_P_N_unique_repeat_budgets_identical=True,common_and_B_U_shared_between_variants=True,negative_same_step_duplicates=0,negative_node_max128_all_round=True,negative_source_caps_all_arms_both_domains_verified=True,steps_materialized=len(step_rows),M_raw_twohop_feature_independently_checked=len(fanout_audit)*2,main_fanout_raw_train_z_pair_caliper=.5,U_untrusted_promoted=0,contract_sha=sha(O/'CONTRACT.json'),limitations=['Budgets differ from historical H/C; cannot reuse old G0','MainM fanout filtering changes coverage and estimand; report wide-pool offline sensitivity and held sources','Only fanout and previous matching conditions controlled; other structural/context residuals remain','U is residual trusted normal negatives, not a coherent functional category','Caps apply to negative supervision. All original positives remain once/update200; no role weighting/protection.','No independent-test performance claim; zero models run'])
 (O/'VERIFIED.json').write_text(json.dumps(verified,ensure_ascii=False,indent=2),encoding='utf-8');print('All checks passed',len(step_rows),'step-arm-domain records',flush=True)
if __name__=='__main__':main()
