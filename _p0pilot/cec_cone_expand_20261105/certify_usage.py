"""Verify whole-proof entailment per large cone; separate CEC and enum-only pools."""
from pathlib import Path
import sys,json,csv,re,collections
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent
sys.path.insert(0,str(R/'_p0pilot/cec_cone_audit_20261105'));from audit import read,rows,sha,module,ident
def main():
 assert not (O/'CEC_POOL_CONTRACT.json').exists();pairs=read(O/'pairs.json');cones={z['cone_id']:z for z in read(O/'cones.json')};proofs=read(O/'reused_proofs.json');globals=rows(O/'whole_proof_observation_sources.csv');byproof={g['proof_id']:g for g in globals};out=[]
 for p in pairs:
  if p['enum']['method']!='not_enumerated_width_cap':continue
  available=[q for q in p['proof_ids'] if q in byproof];pid=available[0] if available else p['proof_ids'][0];q=proofs[pid];a,b=cones[p['left_cone']],cones[p['right_cone']];g=byproof[pid] if available else next(g for g in globals if a['view']==g['view_a'] and b['view']==g['view_b']);assert q['model_sha']==proofs[g['proof_id']]['model_sha'];text=(R/q['folder']/'model.v').read_text(encoding='utf-8');assert a['view']==g['view_a'] and b['view']==g['view_b'];names=['left_design','right_design'] if q['args']=='-prove observation_diff 0' else ['design_ys_id','design_ys_abc'];terms=[];direct=re.fullmatch(r'-prove delta\[(\d+)\] 0',q['args'])
  for name in names:
   code=module(text,name);mm=re.search(r'assign '+('p' if direct else 'obs')+r'\s*=\s*\{(.*?)\};',code);assert mm;terms.append([x.strip() for x in mm[1].split(',')][::-1])
  indices=[i for i,(x,y) in enumerate(zip(*terms)) if x=='b'+str(a['root_bit']) and y=='b'+str(b['root_bit'])];assert indices,(p['pair_id'],'whole proof is not an internal-signal proof')
  if direct:assert int(direct[1]) in indices
  out.append(dict(pair_id=p['pair_id'],proof_id=pid,source_object=p['source_object'],split=p['split'],root_a=a['root_bit'],root_b=b['root_bit'],certified_observation_indices='|'.join(map(str,indices)),boundary_inputs=p['enum']['inputs'],proof_args=q['args'],entailment='direct exact probe proof' if direct else 'proved OR of all paired observation XORs is0, hence each indexed XOR is0; acyclic total PI/Q model verified'))
 with (O/'large_cone_proof_projection.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
 primary=[p for p in pairs if p['proof_ids']];supp=[p for p in pairs if not p['proof_ids']];by={s:[p for p in primary if p['split']==s] for s in ['train','val','test']};plan=dict(status='EVIDENCE_DATA_ONLY_NO_TRAINING',training=0,SAT=0,primary=dict(train=[p['pair_id'] for p in by['train']],val=[p['pair_id'] for p in by['val']],test=[]),enum_only_supplement=[p['pair_id'] for p in supp],selection='blind and label-assisted all admitted when same source+explicit boundary+source-bound proof pass; origin stays tagged',training_scope='dedicated functional-cone representation/output auxiliary only; train split only; no wholesale node embedding/risk consistency or safety-label transfer',stability_scope='functional object stability all primary; point prediction drift when root labels independently trusted/equal, descriptive only; full-cone detection risk pooling not certified',source_component_weights='source_component_weights.csv; primary renormalize per source/component after excluding enum-only supplement',auxiliary_head_not_implemented=True,anti_collapse_and_budget_protocol_not_implemented=True,new_training_not_authorized=True)
 # Exact main-pool source/component weights; no label-driven weight changes.
 parent={}
 def find(x):
  parent.setdefault(x,x)
  if parent[x]!=x:parent[x]=find(parent[x])
  return parent[x]
 for p in primary:
  a,b=find(p['left_cone']),find(p['right_cone']);parent[max(a,b)]=min(a,b)
 groups=collections.defaultdict(list)
 for p in primary:groups[p['split'],p['source_object'],find(p['left_cone'])].append(p)
 weightrows=[]
 for (split,source,component),pp in groups.items():
  ns=len({s for sp,s,_ in groups if sp==split});nc=sum(sp==split and s==source for sp,s,_ in groups)
  for p in pp:weightrows.append(dict(pair_id=p['pair_id'],split=split,source_object=source,component=component,weight=1/ns/nc/len(pp)))
 for split in ['train','val']:assert np.isclose(sum(r['weight'] for r in weightrows if r['split']==split),1)
 with (O/'primary_source_weights.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(weightrows[0]));w.writeheader();w.writerows(weightrows)
 (O/'CEC_POOL_CONTRACT.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8');(O/'CEC_POOL_VERIFIED.json').write_text(json.dumps(dict(training=0,model_forward=0,SAT=0,primary_pairs=len(primary),primary_splits={s:len(pp) for s,pp in by.items()},primary_components=len(groups),primary_components_splits=dict(collections.Counter(k[0] for k in groups)),sources_by_split={s:len({p['source_object'] for p in pp}) for s,pp in by.items()},enum_only_supplement=len(supp),large_projection_checks=len(out),primary_positive_roots={s:sum(p['root_endpoints'][0]['label']==1 for p in pp) for s,pp in by.items()},all_primary_prediction_diagnostics_eligible=all(p['detection_stability_diagnostic_eligible'] for p in primary)),ensure_ascii=False,indent=2),encoding='utf-8');print('Primary source-bound CEC:',{s:len(pp) for s,pp in by.items()},'enum-only supplement',len(supp),flush=True)
if __name__=='__main__':main()
