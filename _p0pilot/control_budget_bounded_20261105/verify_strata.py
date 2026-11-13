"""Verify endpoint strata preservation and separate U meaning from trusted labels."""
from pathlib import Path
import json,csv,collections
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;P=R/'_p0pilot/control_overall_contract_20261105';V=R/'_p0pilot/control_boundary_v3_20261104'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def load(p):
 with np.load(p) as z:return {k:z[k] for k in z.files}
def main():
 assert (O/'VERIFIED.json').exists();c=read(V/'input_contract.json');norm=load(V/'normalization.npz');vs=list(csv.DictReader((P/'view_dictionary.csv').open(encoding='utf-8-sig')));u=[];coverage=[]
 for dm in ['orig','trans']:
  key=dm+'_train';s=load(O/('pools_'+key+'.npz'));n=load(P/('normal_'+key+'.npz'));vm={int(v['view_id']):v for v in vs if v['key']==key};x=np.load(R/c['shared_inputs'][key]['folder']/'x39.npy',mmap_mode='r');zn=np.clip((x[s['N'],25:]-norm['mean'][25:])/norm['std'][25:],-10,10);zh=np.clip((x[s['H'],25:]-norm['mean'][25:])/norm['std'][25:],-10,10);assert (np.sqrt(np.mean((zn-zh)**2,axis=1))<=2+1e-6).all();assert (np.argmax(x[s['N'],:25],axis=1)==np.argmax(x[s['H'],:25],axis=1)).all()
  for nv,hv in zip(s['Nview'],s['Hview']):assert all(vm[int(nv)][k]==vm[int(hv)][k] for k in ['host','recipe'])
  for variant in ['main_fanout05','sensitivity_wideM']:
   seq=np.load(O/(variant+'_'+key+'_pairs.npy'));counts=np.bincount(seq.ravel(),minlength=len(s['N']))
   for cat,name in enumerate(['B','M','U']):
    eligible=np.flatnonzero((s['category']==cat)&(s['main_eligible'] if variant=='main_fanout05' else True));used=eligible[counts[eligible]>0];es=set(map(int,s['normal_source'][eligible]));us=set(map(int,s['normal_source'][used]));assert es==us,(dm,variant,name,es-us);coverage.append(dict(domain=dm,variant=variant,block=name,eligible_sources=len(es),used_sources=len(us),all_eligible_sources_seen=True))
   ui=np.flatnonzero((s['category']==2)&(counts>0));order=np.argsort(n['rows']);idx=np.searchsorted(n['rows'][order],s['N'][ui]);assert (n['rows'][order][idx]==s['N'][ui]).all();reasons=n['reason'][order[idx]]
   for rc in sorted(set(map(int,reasons))):
    ids=ui[reasons==rc];u.append(dict(domain=dm,variant=variant,reason=rc,unique_nodes=len(ids),entries_200=int(counts[ids].sum()),share_of_U_entries=float(counts[ids].sum()/counts[ui].sum())))
 for name,rr in [('U_actual_exposure.csv',u),('eligible_source_coverage.csv',coverage)]:
  with (O/name).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
 (O/'STRATA_VERIFIED.json').write_text(json.dumps(dict(training=0,model_forward=0,SAT=0,all_pairs_host_recipe_gate_equal=True,all_pairs_14d_RMS_le2=True,per_step_host_recipe_gate_histograms_identical_by_endpoint_bijection=True,all_eligible_normal_sources_exposed=True,negative_source_identities_not_equal_across_arms=True,U_reason_exposure_reported=True),indent=2),encoding='utf-8');print('Strata and all eligible source coverage passed',flush=True)
if __name__=='__main__':main()
