"""Reviewable training/validation-only positive guard proposal; no mask/loss/model mutation."""
from pathlib import Path
import csv,json,collections
O=Path(__file__).resolve().parent
def rows(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def main():
 a=rows(O/'positive_coordinates_and_roles.csv');out=[]
 for x in a:
  if x['key'] not in ['orig_train','trans_train','trans_val']:continue
  status=x['proposed_positive_aux_eligibility'];eligible=status=='structural_positive_unproved' and x['role_class'] in ['trigger','payload']
  out.append(dict(**x,stage1_positive_role_guard_candidate=eligible,training_gradient_eligible=eligible and x['key'].endswith('_train'),validation_audit_only=x['key']=='trans_val',loss_group=x['source']+'::'+x['role_class'] if eligible else '',original_label=1,original_global_supervision_retained=True,actual_training_mask_modified=False,proposal_only=True))
 with (O/'positive_guard_proposal.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
 groups=collections.defaultdict(list)
 for x in out:groups[(x['key'],str(x['stage1_positive_role_guard_candidate']))].append(x)
 counts=[dict(key=k[0],stage1_guard_candidate=k[1],unique_positive_nodes=len(v),source_objects=len({x['source'] for x in v}),role_classes='|'.join(sorted({x['role_class'] for x in v}))) for k,v in sorted(groups.items())]
 with (O/'guard_proposal_counts.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(counts[0]));w.writeheader();w.writerows(counts)
 plan=dict(date='2026-11-05',training=0,model_forward=0,SAT=0,labels_or_masks_modified=False,feature_and_negative_pool='same frozen v3; orig116/trans233 C-H pairs',current_primary_labels='all original trusted positives retained in ASL/global metrics including dead or mixed descendants',first_guard_groups=['trigger','payload'],auxiliary_scope='train only, trusted positive, PO-driver reachable, no mixed positive/negative source parents; not SAT-certified',validation_rows_audit_only=True,test_rows_not_used_to_choose_auxiliary_pool=True,loss_proposal='L_ASL +1.4*((1-eta)*L_global_softmiss +eta*L_source_role_softmiss); role loss mean over sources then present trigger/payload groups; same unique node enters once',eta_example=0.25,eta_example_not_validated=True,total_softmiss_coefficient=1.4,no_equal_gradient_norm_claim=True,comparison='reuse existing eta0 H/C; if authorized, eta>0 in both H and C with same init/200 updates/positive exposure/negative budget, not C-only extra loss',checkpoint_rule='same validation AP every5; role recall used to accept/reject configuration, not posthoc choose favorable checkpoint',calibration='freeze a validation-only single global threshold rule for all conditions before future comparison; no inference role/name inputs',counts=counts)
 (O/'POSITIVE_GUARD_PROPOSAL.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8');print(counts)
if __name__=='__main__':main()
