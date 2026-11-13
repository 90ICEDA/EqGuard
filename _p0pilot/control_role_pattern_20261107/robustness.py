"""Check every nearest-feature tie, not just a favorable chosen normal node."""
import build as C
import numpy as np,collections,json
O=C.O;R=C.R
def main():
 lin=C.rows(O/'NODE_LINEAGE.csv');lm={(r['key'],int(r['row'])):r for r in lin};desc={(r['key'],int(r['row'])):r for r in C.rows(O/'LOCAL_DESCRIPTORS.csv')};links=C.rows(O/'FEATURE_NEAREST_LINKS.csv');stable=C.rows(O/'PAIR_THREE_SEED_STABILITY.csv');d={(r['protocol'],r['seed'],r['comparison'],r['key'],r['row']):r for r in C.rows(O/'NODE_DELTAS.csv')};sp={(r['control_source'],r['control_instance'],r['trojan_source'],r['trojan_instance']) for r in C.rows(R/'_p0pilot/control_risk_20261104/source_node_pairs.csv') if r['role_pair']=='True'};ties={};checks=0
 for key in C.KEYS:
  z=dict(np.load(O/(key+'_features.npz')));ix={int(i):j for j,i in enumerate(z['rows'])};x=z['normalized'];ms=[r for r in lin if r['key']==key and r['side']=='M' and r['coordinate_verified']=='True' and r['role'] not in ['mixed_source','unresolved'] and r['nature']!='sequential_descendant']
  for link in [r for r in links if r['key']==key]:
   i=int(link['positive_row']);pr=lm[key,i];valid=[r for r in ms if r['host']==pr['host'] and r['flow_full']==pr['flow_full'] and desc[key,int(r['row'])]['gate']==desc[key,i]['gate']];route=link['route']
   if route=='exposed_M_only':valid=[r for r in valid if int(r['M_exposure_200'])>0]
   if route=='manufacturing_counterpart':valid=[r for r in valid if any((r['source'],mp,pr['source'],tp) in sp for mp in r['parents'].split('|') for tp in pr['parents'].split('|'))]
   assert len(valid)==int(link['candidates'])
   if not valid:assert link['matched']=='False';continue
   ids=np.array([int(r['row']) for r in valid]);dd=np.sqrt(np.mean((x[[ix[j] for j in ids],25:]-x[ix[i],25:])**2,axis=1));ts=sorted(map(int,ids[dd==dd.min()]));assert int(link['normal_row'])==ts[0] and len(ts)==int(link['ties']);assert abs(float(dd.min())-float(link['rms_z14']))<1e-7;ties[key,route,i]=ts;checks+=1
 out=[]
 for r in stable:
  key=r['key'];i=int(r['positive_row']);ts=ties[key,r['route'],i];allseed=0;anyseed=0;alarm_removed=0;common_removed=0
  for seed in [42,1,2]:
   harmed=float(d[r['protocol'],str(seed),r['comparison'],key,str(i)]['AP_contribution_delta'])< -1e-6;drop=[float(d[r['protocol'],str(seed),r['comparison'],key,str(j)]['score_delta'])<-.001 for j in ts];allseed+=harmed and all(drop);anyseed+=harmed and any(drop);chosen=d[r['protocol'],str(seed),r['comparison'],key,r['normal_row']];alarm_removed+=harmed and float(chosen['hit_delta'])<0;common_removed+=harmed and float(chosen['hit_common_G0_tau_delta'])<0
  out.append(dict(**r,nearest_ties=len(ts),all_ties_coupled_seeds=allseed,any_ties_coupled_seeds=anyseed,alarm_removed_and_rank_harmed_seeds=alarm_removed,common_tau_alarm_removed_and_rank_harmed_seeds=common_removed))
 C.table('PAIR_TIE_ROBUSTNESS.csv',out)
 summary=[]
 for key in C.KEYS:
  route='exposed_M_only' if key.endswith('train') else 'all_M'
  for comparison in ['GM-G0','GBM-GB','GBM-G0','GB-G0']:
   for protocol in ['selected','last200']:
    z=[r for r in out if r['key']==key and r['route']==route and r['comparison']==comparison and r['protocol']==protocol]
    for radius in [.25,.5,1.0]:
     close=[r for r in z if float(r['rms_z14'])<=radius];strict=[r for r in close if r['all_ties_coupled_seeds']==3];summary.append(dict(key=key,route=route,comparison=comparison,protocol=protocol,radius_rms_z14=radius,matched=len(z),close=len(close),chosen_coupled3=sum(int(r['coupled_seeds'])==3 for r in close),all_ties_coupled3=len(strict),sources=len({r['positive_source'] for r in strict}),source_gate_objects=len({(r['positive_source'],r['positive_parents']) for r in strict}),normal_sources=len({r['normal_source'] for r in strict}),exact_features=sum(r['feature_equal']=='True' for r in strict),same_gate_context2=sum(r['gate_context2_equal']=='True' for r in strict),chosen_actual_alarm_rank_cooccurrence_ge1=sum(r['alarm_removed_and_rank_harmed_seeds']>=1 for r in close),chosen_actual_alarm_rank_cooccurrence3=sum(r['alarm_removed_and_rank_harmed_seeds']==3 for r in close),common_tau_actual_alarm_rank_cooccurrence_ge1=sum(r['common_tau_alarm_removed_and_rank_harmed_seeds']>=1 for r in close)))
 C.table('ROBUST_PATTERN_COUNTS.csv',summary)
 # Feature deltas are annotation only; no model fit or predictive candidate selection.
 for p,h in C.read(O/'BUILD_COMPLETE.json')['protected_inputs'].items():assert C.sha(R/p)==h
 v=C.read(O/'VERIFIED.json');v.update(nearest_minimum_and_tie_checks=checks,nearest_tie_robustness=True,feature_radii=[.25,.5,1.0]);(O/'VERIFIED.json').write_text(json.dumps(v,indent=2),encoding='utf-8');print('ROBUSTNESS_VERIFIED',checks)
if __name__=='__main__':main()
