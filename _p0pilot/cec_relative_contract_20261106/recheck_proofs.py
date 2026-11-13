"""Recheck saved proof provenance and finite witness records; no solver execution."""
from pathlib import Path
import csv,hashlib,json,re
O=Path(__file__).resolve().parent;R=O.parents[1];J=R/'_p0pilot/cec_joint_expand_20261105'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 prep=read(O/'PREPARED.json');v=read(O/'VERIFIED.json')
 for p,h in prep['protected_files'].items():assert sha(R/p)==h,p
 for n,h in v['indices_sha'].items():assert sha(O/n)==h,n
 ts={t['triple_id']:t for t in read(O/'triple_pool.json')};ids={r['triple_id'] for r in read(O/'schedule_seed42.json')}|{t['triple_id'] for t in read(O/'evaluation_panel.json')};pairs={p['pair_id']:p for p in read(J/'final_pairs.json')};cones={c['cone_id']:c for c in read(J/'final_cones.json')};proofs=read(J/'proofs.json');pids={ts[t][k] for t in ids for k in ['pair_A','pair_B','pair_C']};qids={q for pid in pids for q in pairs[pid]['proof_ids']};bound={b['pair_id']:b for b in read(J/'bounded_certificates.json')};checked=[];frozen={}
 for qid in sorted(qids):
  q=proofs[qid];folder=R/q['folder'];script=(folder/'run.ys').read_text(encoding='utf-8');log=(folder/'run.log').read_text(encoding='utf-8')
  assert sha(folder/'model.v')==q['model_sha'] and sha(folder/'run.log')==q['log_sha'] and hashlib.sha256(script.encode()).hexdigest()==q['script_sha']
  command=[s for s in script.splitlines() if s.startswith('sat ')][int(q['query_id'])]
  assert re.fullmatch(r'sat '+re.escape(q['args'])+r' -timeout \d+ -show-inputs -show-outputs -dump_json "[^"]+"',command)
  blocks=re.split(r'^(?:Q|QUERY)\d{4}\s*$',log,flags=re.M);block=blocks[int(q['query_id'])+1]
  assert 'no model found: SUCCESS' in block and 'TIMEOUT' not in block and 'ERROR:' not in log
  for n in ['model.v','run.ys','run.log']:frozen[str((folder/n).relative_to(R))]=sha(folder/n)
  checked.append(dict(kind='saved_CEC_query',id=qid,folder=q['folder'],passed=True))
 legacy=R/'_p0pilot/cec_coverage_pretrain_20261105';lp=read(legacy/'PUBLISHED.json')
 for name in ['ENUM_CERTIFICATES.json','bounded_positive_pairs.json','bounded_positive_cones.json']:
  path=legacy/name;rel=str(path.relative_to(R));assert sha(path)==lp['files'][rel];frozen[rel]=sha(path)
 bound.update({b['pair_id']:b for b in read(legacy/'ENUM_CERTIFICATES.json')})
 for pid in sorted(pids):
  p=pairs[pid]
  if p['proof_ids']:continue
  b=bound[pid];cs=[cones[p[k]] for k in ['left_cone','right_cone']]
  assert (b.get('status')=='proved' or b.get('method')=='independent_scalar_complete_PI_Q_enumeration') and b['raw_shas']==[c['raw_sha'] for c in cs] and b['root_bits']==[c['root_bit'] for c in cs]
  assert b['truth_sha']==p['enum']['truth_sha'] and b['patterns']==p['enum']['patterns'] and hashlib.sha256(bytes.fromhex(b['packed_truth_hex'])).hexdigest()==b['truth_sha']
  checked.append(dict(kind='saved_complete_enumeration',id=pid,folder=str(J.relative_to(R)),passed=True))
 with (O/'proof_recheck.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(checked[0]));w.writeheader();w.writerows(checked)
 (O/'PROVENANCE_VERIFIED.json').write_text(json.dumps(dict(existing_CEC_queries_rechecked=len(qids),complete_enumeration_certificates_checked=len(checked)-len(qids),selected_equivalence_pairs=len(pids),selected_different_function_witnesses=prep['selected_scalar_witnesses'],query_files_sha=frozen,old_files_unchanged=True,SAT=0,training=0,model_forwards=0),ensure_ascii=False,indent=2),encoding='utf-8')
 print('PROVENANCE_VERIFIED',len(qids),len(checked)-len(qids),flush=True)
if __name__=='__main__':main()
