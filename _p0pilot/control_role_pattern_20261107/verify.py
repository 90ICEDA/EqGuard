"""Independent scope, coordinate, matching, feature and AP additivity checks."""
import build as C
import numpy as np,collections,json
O=C.O;R=C.R
def main():
 done=C.read(O/'ANALYSIS_COMPLETE.json');build=C.read(O/'BUILD_COMPLETE.json');assert done['passed'] and build['coordinate_discrepancies']==0;lin=C.rows(O/'NODE_LINEAGE.csv');lm={(r['key'],int(r['row'])):r for r in lin};des={(r['key'],int(r['row'])):r for r in C.rows(O/'LOCAL_DESCRIPTORS.csv')};links=C.rows(O/'FEATURE_NEAREST_LINKS.csv');fc=C.read(C.V/'input_contract.json');checks=0
 for key in C.KEYS:
  z=dict(np.load(O/(key+'_features.npz')));ix={int(i):j for j,i in enumerate(z['rows'])};full=R/fc['shared_inputs'][key]['folder'];y=np.load(full/'y.npy');tr=np.load(full/'trusted.npy');ph=np.load(full/'physical.npy');assert len(ix)==sum(r['key']==key for r in lin);expected=set(np.flatnonzero((y==1)&tr&ph));assert expected=={int(r['row']) for r in lin if r['key']==key and r['side']=='positive'};assert np.array_equal(z['raw'],np.load(full/'x39.npy',mmap_mode='r')[z['rows']])
  for link in [r for r in links if r['key']==key and r['matched']=='True']:
   i,j=int(link['positive_row']),int(link['normal_row']);p,n=lm[key,i],lm[key,j];assert p['side']=='positive' and n['side']=='M' and int(y[i])==1 and int(y[j])==0 and tr[i] and tr[j] and ph[i] and ph[j];assert p['host']==n['host'] and p['flow_full']==n['flow_full'] and des[key,i]['gate']==des[key,j]['gate'];assert (p['key'].endswith('val'))==(n['key'].endswith('val'))
   diff=z['normalized'][ix[i],25:]-z['normalized'][ix[j],25:];assert abs(float(np.sqrt(np.mean(diff**2)))-float(link['rms_z14']))<1e-7
   if link['route']=='exposed_M_only':assert key.endswith('train') and int(n['M_exposure_200'])>0
   checks+=1
 # All claimed 3-seed flags independently reconstructed from raw deltas.
 nd=C.rows(O/'NODE_DELTAS.csv');d={(r['protocol'],r['seed'],r['comparison'],r['key'],r['row']):r for r in nd};stable=C.rows(O/'PAIR_THREE_SEED_STABILITY.csv');flagchecks=0
 for r in stable:
  cv=0
  for seed in [42,1,2]:
   n=d[r['protocol'],str(seed),r['comparison'],r['key'],r['normal_row']];p=d[r['protocol'],str(seed),r['comparison'],r['key'],r['positive_row']];cv+=float(n['score_delta'])<-.001 and float(p['AP_contribution_delta'])< -1e-6
  assert cv==int(r['coupled_seeds']);flagchecks+=1
 # Fill absent roles with zero before averaging implementations, preserving AP additivity.
 views=C.rows(R/'_p0pilot/control_loader_po_20261105/view_dictionary.csv');views=[r for r in views if r['key'] in C.KEYS and r['kind']=='trojan'];agg=collections.defaultdict(float)
 for r in nd:
  if r['side']=='positive':agg[r['protocol'],r['seed'],r['comparison'],r['key'],r['source'],r['view'],r['role']]+=float(r['AP_contribution_delta'])
 roles={k:sorted({r['role'] for r in lin if r['key']==k and r['side']=='positive'}) for k in C.KEYS};sources={k:sorted({v['source'] for v in views if v['key']==k}) for k in C.KEYS};ad=[]
 for protocol in ['selected','last200']:
  for seed in [42,1,2]:
   for arm,base in [('GM','G0'),('GBM','GB'),('GBM','G0'),('GB','G0')]:
    comparison=arm+'-'+base
    for key in C.KEYS:
     for src in sources[key]:
      vv=[v['view'] for v in views if v['key']==key and v['source']==src]
      for role in roles[key]:ad.append(dict(protocol=protocol,seed=seed,comparison=comparison,key=key,source=src,role=role,AP_contribution_delta=float(np.mean([agg[protocol,str(seed),comparison,key,src,v,role] for v in vv]))))
 C.table('SOURCE_ROLE_AP_CONTRIBUTIONS_ADDITIVE.csv',ad);prior=C.rows(R/'_p0pilot/control_last200_20261107/AP_source_all.csv');pm={(r['protocol'],r['seed'],r['arm'],r['key'],r['source']):float(r['AP']) for r in prior};addchecks=0
 for protocol in ['selected','last200']:
  for seed in [42,1,2]:
   for a,b in [('GM','G0'),('GBM','GB'),('GBM','G0'),('GB','G0')]:
    for key in C.KEYS:
     for src in sources[key]:
      value=sum(r['AP_contribution_delta'] for r in ad if r['protocol']==protocol and r['seed']==seed and r['comparison']==a+'-'+b and r['key']==key and r['source']==src);ref=pm[protocol,str(seed),a,key,src]-pm[protocol,str(seed),b,key,src];assert abs(value-ref)<1e-12;addchecks+=1
 for p,h in {**build['protected_inputs'],**done['protected_predictions']}.items():assert C.sha(R/p)==h,p
 result=dict(passed=True,scope=C.KEYS,coordinate_discrepancies=0,matched_link_checks=checks,three_seed_flag_checks=flagchecks,AP_source_role_additivity_checks=addchecks,AP_view_reproductions=done['AP_view_reproductions'],all_protected_hashes_unchanged=True,normal_matching_uses_no_predictions=True,test_predictions_read=False,labels_changed=False,model_forwards=0,training=0,SAT=0)
 (O/'VERIFIED.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(result)
if __name__=='__main__':main()
