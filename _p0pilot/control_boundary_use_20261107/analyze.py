"""Describe frozen boundary-use contrasts; no fitting or candidate selection."""
import audit as C
import numpy as np,collections,json
O=C.O;P=C.P
def b(v):return v is True or v=='True'
def main():
 assert C.read(O/'AUDIT_COMPLETE.json')['passed'];rr=C.rows(O/'NODE_BOUNDARIES.csv');lm={(r['key'],r['row']):r for r in rr};summary=[];sources=[]
 flags=['root_is_terminal_load','no_output_or_register_boundary','D','SI','scan_only','PO_before_register','PO_Donly_structural_path']
 for key in ['orig_train','orig_val','trans_train','trans_val']:
  for scope in ['M_all','M_exposed','positive_payload','positive_hijack','positive_trigger','positive_pure_all']:
   z=[r for r in rr if r['key']==key and not b(r['root_is_register']) and (r['side']=='M' if scope.startswith('M') else r['side']=='positive')]
   if scope=='M_exposed':z=[r for r in z if int(r['M_exposure_200'])>0]
   if scope.startswith('positive_'):
    cl=scope.removeprefix('positive_');z=[r for r in z if r['role']==('output_hijack' if cl=='hijack' else cl)] if cl!='pure_all' else [r for r in z if r['role']!='mixed_source']
   if not z:continue
   row=dict(key=key,scope=scope,nodes=len(z),sources=len({r['source'] for r in z}),D_or_PO=sum(b(r['D']) or b(r['PO_before_register']) for r in z),**{f:sum(b(r[f]) for r in z) for f in flags});summary.append(row)
   for src in sorted({r['source'] for r in z}):
    ss=[r for r in z if r['source']==src];sources.append(dict(key=key,scope=scope,source=src,nodes=len(ss),**{f:float(np.mean([b(r[f]) for r in ss])) for f in flags},D_or_PO=float(np.mean([b(r['D']) or b(r['PO_before_register']) for r in ss]))))
 C.table('BOUNDARY_GROUP_COUNTS.csv',summary);C.table('BOUNDARY_PER_SOURCE.csv',sources)
 links=C.rows(P/'FEATURE_NEAREST_LINKS.csv');stable=C.rows(P/'PAIR_TIE_ROBUSTNESS.csv');sl={(r['protocol'],r['comparison'],r['key'],r['route'],r['positive_row']):r for r in stable};pair=[]
 for link in links:
  if not b(link['matched']):continue
  key=link['key'];p,n=lm[key,link['positive_row']],lm[key,link['normal_row']];assert not b(p['root_is_register']) and not b(n['root_is_register']);s=sl['last200','GM-G0',key,link['route'],link['positive_row']];pair.append(dict(key=key,route=link['route'],positive_row=p['row'],normal_row=n['row'],positive_source=p['source'],normal_source=n['source'],positive_parents=p['parents'],normal_parents=n['parents'],positive_role=p['role'],normal_role=n['role'],flow_full=p['flow_full'],rms_z14=link['rms_z14'],feature_equal=b(link['feature_equal']),feature_close=float(link['rms_z14'])<=.5,positive_signature=p['boundary_signature'],normal_signature=n['boundary_signature'],signature_diff=p['boundary_signature']!=n['boundary_signature'],D_SI_PO_diff=any(b(p[f])!=b(n[f]) for f in ['D','SI','PO_before_register']),distance_diff=any(p[f]!=n[f] for f in ['D_distance','SI_distance','PO_before_register_distance']),positive_D_or_PO=b(p['D']) or b(p['PO_before_register']),normal_D_or_PO=b(n['D']) or b(n['PO_before_register']),positive_DonlyPO=b(p['PO_Donly_structural_path']),normal_DonlyPO=b(n['PO_Donly_structural_path']),GM_coupled3=int(s['all_ties_coupled_seeds'])==3,GM_actual_alarm_and_rank_seeds=s['alarm_removed_and_rank_harmed_seeds'],normal_score_delta_mean=s['normal_score_delta_mean'],positive_score_delta_mean=s['positive_score_delta_mean'],positive_AP_contribution_delta_mean=s['positive_AP_contribution_delta_mean']))
 C.table('FROZEN_PAIR_BOUNDARY_CONTRASTS.csv',pair);pc=[]
 for key in ['orig_train','orig_val','trans_train','trans_val']:
  for route in ['all_M','exposed_M_only','manufacturing_counterpart']:
   for scope in ['all_matched','feature_close','feature_equal','close_coupled3']:
    z=[r for r in pair if r['key']==key and r['route']==route]
    if scope=='feature_close':z=[r for r in z if r['feature_close']]
    if scope=='feature_equal':z=[r for r in z if r['feature_equal']]
    if scope=='close_coupled3':z=[r for r in z if r['feature_close'] and r['GM_coupled3']]
    pc.append(dict(key=key,route=route,scope=scope,pairs=len(z),source_gate_objects=len({(r['positive_source'],r['positive_parents']) for r in z}),sources=len({r['positive_source'] for r in z}),signature_diff=sum(r['signature_diff'] for r in z),D_SI_PO_diff=sum(r['D_SI_PO_diff'] for r in z),distance_diff=sum(r['distance_diff'] for r in z),positive_D_or_PO_normal_not=sum(r['positive_D_or_PO'] and not r['normal_D_or_PO'] for r in z),both_D_or_PO=sum(r['positive_D_or_PO'] and r['normal_D_or_PO'] for r in z),both_no_D_or_PO=sum(not r['positive_D_or_PO'] and not r['normal_D_or_PO'] for r in z),positive_DonlyPO_normal_not=sum(r['positive_DonlyPO'] and not r['normal_DonlyPO'] for r in z)))
 C.table('PAIR_SEPARATION_COUNTS.csv',pc)
 # Invariance is audited source-gate descendant-set UNION, not pointwise safety-role transfer.
 native={(r['key'].split('_')[1],r['source'],r['parents']):r for r in rr if r['key'].startswith('orig') and r['role'] not in ['mixed_source','unresolved']};gg=collections.defaultdict(list)
 for r in rr:
  if r['key'].startswith('trans') and r['role'] not in ['mixed_source','unresolved'] and '|' not in r['parents'] and not b(r['root_is_register']):gg[r['key'],r['source'],r['parents'],r['view']].append(r)
 inv=[]
 for (key,src,parent,view),z in sorted(gg.items()):
  ref=native.get((key.split('_')[1],src,parent))
  if ref is None:continue
  union={f:any(b(r[f]) for r in z) for f in ['D','SI','PO_before_register','PO_Donly_structural_path']};same=all(union[f]==b(ref[f]) for f in ['D','SI','PO_before_register']);inv.append(dict(key=key,side=z[0]['side'],source=src,parent=parent,role=z[0]['role'],view=view,audited_descendants=len(z),first_boundary_union_same=same,Donly_PO_same=union['PO_Donly_structural_path']==b(ref['PO_Donly_structural_path']),native_signature=ref['boundary_signature'],union_signature='|'.join(f for f in ['D','SI','PO_before_register'] if union[f]),interpretation='union over frozen trusted audited descendants,not guaranteed complete source-cone mapping'))
 C.table('CROSS_IMPLEMENTATION_BOUNDARY_UNION.csv',inv)
 # Export the fixed primary near/rank-loss cases and a fixed ambiguity (no new nearest search).
 cases=[r for r in pair if r['route']==('exposed_M_only' if r['key'].endswith('train') else 'all_M') and r['feature_close'] and r['GM_coupled3']]
 C.table('FIXED_CASES_BOUNDARY_RESULT.csv',cases)
 (O/'ANALYSIS_COMPLETE.json').write_text(json.dumps(dict(passed=True,pairs=len(pair),fixed_GM_cases=len(cases),invariance_rows=len(inv),training=0,SAT=0,model_forward=0,labels_changed=False,no_new_matching=True,no_classifier_fitted=True),indent=2),encoding='utf-8');print('ANALYSIS_COMPLETE',len(pair),len(cases),len(inv))
if __name__=='__main__':main()
