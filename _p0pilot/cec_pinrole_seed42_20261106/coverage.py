"""Describe actual MUX exposure in frozen train/evaluation cones; no model/SAT."""
from pathlib import Path
import json,gzip,csv,collections
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def table(name,rr):
 with (O/name).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def main():
 cones={c['cone_id']:c for c in read(R/'_p0pilot/cec_joint_expand_20261105/final_cones.json')}
 with (O/'pin_loading_audit.csv').open(encoding='utf-8-sig') as f:views={r['view']:r for r in csv.DictReader(f)}
 stats={}
 with gzip.open(R/'_p0pilot/cec_interface_minimal_20261105/cone_pin_incidence.jsonl.gz','rt',encoding='utf-8') as f:
  for line in f:
   p=json.loads(line);c=cones[p['cone_id']];mux=sum(op=='MUX' for op in p['op']);changed=int(views[c['view']]['rank'])>0 and mux>0
   stats[c['cone_id']]=dict(mux=mux,changed=changed)
 inventory={r['pair_id']:r for r in read(R/'_p0pilot/cec_pretrain_ready_20261105/function_inventory.json')}
 schedule=[r for r in read(R/'_p0pilot/cec_pretrain_ready_20261105/schedule.json') if r['mode']=='main' and r['seed']==42]
 ids=[r[k] for r in schedule for k in ['pair_a','pair_b']];rr=[]
 for pid in sorted(set(ids)):
  p=inventory[pid];aa=[stats[p[k]] for k in ['left_cone','right_cone']]
  rr.append(dict(pair_id=pid,source=p['source'],exposures=ids.count(pid),contains_mux=any(s['mux'] for s in aa),contains_changed_mux=any(s['changed'] for s in aa),mux_member_occurrences=sum(s['mux'] for s in aa)))
 table('train_mux_exposure.csv',rr)
 certs=read(R/'_p0pilot/cec_cert_expand_20261105/validation_negative_certificates.json');vv=[]
 for c in certs:
  aa=[stats[k] for k in c['cones']];vv.append(dict(certificate_id=c['certificate_id'],source=c['source'],contains_mux=any(s['mux'] for s in aa),contains_changed_mux=any(s['changed'] for s in aa),mux_member_occurrences=sum(s['mux'] for s in aa)))
 table('validation_mux_blocks.csv',vv)
 summary=dict(training_unique_pairs=len(rr),training_unique_pairs_with_mux=sum(r['contains_mux'] for r in rr),training_unique_pairs_with_changed_mux=sum(r['contains_changed_mux'] for r in rr),training_slots=500,training_slots_with_mux=sum(r['exposures'] for r in rr if r['contains_mux']),training_slots_with_changed_mux=sum(r['exposures'] for r in rr if r['contains_changed_mux']),validation_blocks=68,validation_blocks_with_mux=sum(r['contains_mux'] for r in vv),validation_blocks_with_changed_mux=sum(r['contains_changed_mux'] for r in vv),interpretation='exact cone members only;does not count MUX elsewhere in GNN/BN graph context',source_train={s:dict(pairs=sum(r['source']==s for r in rr),mux=sum(r['source']==s and r['contains_mux'] for r in rr),changed=sum(r['source']==s and r['contains_changed_mux'] for r in rr)) for s in sorted({r['source'] for r in rr})})
 (O/'MUX_COVERAGE.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
