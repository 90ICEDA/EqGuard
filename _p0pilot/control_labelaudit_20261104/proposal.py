"""Reviewable eligibility proposal only; never changes masks, schedules or labels."""
from pathlib import Path
import json,csv,collections,sys
import numpy as np
O=Path(__file__).resolve().parent;R=O.parents[1];sys.path.insert(0,str(O))
from audit import raw_network,read,rows,dump,NL,F
def main():
 collisions=rows(O/'collision_node_pairs.csv');groups={x['normal_view']:x for x in collisions};lib=NL.load_library(F/'verilog_lib.v');result=[]
 for view,r in groups.items():
  rec=dict(normal_view=view,trojan_view=r['trojan_view'],source=r['source'],role=r['role'])
  for side in ['normal','trojan']:
   g=raw_network(F/'trans'/(r[side+'_view']+'.v'),lib);mp=read(F/'mappings'/(r[side+'_view']+'.json'));targets=mp['node_alignment'][r[side+'_source_gate']];rec[side+'_targets']='|'.join(targets);rec[side+'_target_count']=len(targets);rec[side+'_live_targets']=sum(x in g['reachable'] for x in targets)
  assert rec['normal_live_targets']==rec['trojan_live_targets']==0;result.append(rec)
 dump('collision_role_sets.csv',result)
 coords=rows(R/'_p0pilot/control_roles_20261104/coordinate_manifest.csv');bad={int(i) for x in coords if x['view'] in groups and x['role']=='TM1' for i in x['normal_ids'].split('|')};checks=rows(O/'label_chain_checks.csv');exact={int(x['split_row']) for x in checks if x['kind']=='collision' and x['expected_label']=='0'}
 b=R/'_p0pilot/control_fair200_20261104';pairs=[x for x in rows(b/'train_pairs.csv') if x['domain']=='trans'];slots=np.load(b/'trans_C_slots.npy');proposal=[]
 for x in pairs:proposal.append(dict(**x,proposed_extra_weight_status='hold_anchor_only_role' if int(x['C']) in bad else 'pending_same_rule_audit',original_base_label_unchanged=True,extra_H_pair_same_status=True,current_training_artifact_modified=False))
 dump('proposed_extra_role_eligibility.csv',proposal)
 (O/'proposal.json').write_text(json.dumps(dict(proposal_only=True,labels_modified=False,masks_modified=False,slots_modified=False,training=0,SAT=0,current_trans_unique_C=294,known_anchor_role_C=6,exact_collision_C=4,known_anchor_role_exposures=int(np.isin(slots,list(bad)).sum()),exact_collision_exposures=int(np.isin(slots,list(exact)).sum()),remaining_candidate_upper_bound=288,remaining_source_objects=len({x['source'] for x in pairs if int(x['C']) not in bad}),remaining_views=len({x['view'] for x in pairs if int(x['C']) not in bad}),note='288 is not fully audited functional eligibility; mirror all future exclusions/weights in H and C; derive rules from train only; keep original whole-test metrics'),ensure_ascii=False,indent=2),encoding='utf-8');print(read(O/'proposal.json'))
if __name__=='__main__':main()
