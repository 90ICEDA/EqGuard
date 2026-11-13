"""Cached root64 metrics stratified by existing internal cone 3-hop inventory."""
from pathlib import Path
import csv,json,collections
import numpy as np
from sklearn.metrics import roc_auc_score
O=Path(__file__).resolve().parent;R=O.parents[1]
def rows(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def main():
 inv={r['cone_id']:r for r in rows(R/'_p0pilot/cec_fair_audit_20261105/boundary_cone_inventory.csv')};certs=json.loads((R/'_p0pilot/cec_cert_expand_20261105/validation_negative_certificates.json').read_text(encoding='utf-8-sig'));flags={c['certificate_id']:all(int(inv[k]['members_outside_3hop'])==0 for k in c['cones']) for c in certs};blocks=rows(O/'evaluation_blocks.csv');result=[]
 for condition in ['shared','viewshuffle']:
  for arm in ['Z','R','P']:
   for remap in ['9000','9001']:
    rr=[r for r in blocks if r['space']=='root64' and r['alignment']==condition and r['arm']==arm and r['remap']==remap]
    for complete in [True,False]:
     gg=[r for r in rr if flags[r['certificate']]==complete]
     if not gg:continue
     a=[float(r[k]) for r in gg for k in ['real0','real1']];b=[float(r[k]) for r in gg for k in ['wrong0','wrong1']];result.append(dict(condition=condition,arm=arm,remap=remap,all_four_internal_cones_within_root3hop=complete,blocks=len(gg),sources=len({r['source'] for r in gg}),auc=float(roc_auc_score([1]*len(a)+[0]*len(b),-np.array(a+b))),anchor_win=float(np.mean([float(r['anchor_win']) for r in gg]))))
 with (O/'root3hop_strata.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(result[0]));w.writeheader();w.writerows(result)
 summary=dict(blocks=68,all_four_internal_cones_within_root3hop=sum(flags.values()),some_internal_cone_beyond_root3hop=sum(not v for v in flags.values()),interpretation='Internal combinational cone membership only;not full model receptive field;mean pooling includes every cone member;BN may couple whole graph in training;not proof large cones are unlearnable',new_forwards=0,new_training=0,SAT=0)
 (O/'ROOT3HOP_COVERAGE.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(summary))
if __name__=='__main__':main()
