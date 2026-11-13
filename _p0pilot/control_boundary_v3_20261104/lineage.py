"""Full source/split/global-label lineage verification for audited train/val candidates."""
from pathlib import Path
import csv,json,collections,hashlib
O=Path(__file__).resolve().parent;R=O.parents[1];P=R/'_p0pilot/round32_20261029';F=R/'generate_trans/folds/hosts_bt31'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def main():
 c=read(P/'input_contract.json');vv={(key,v['view']):v for key,q in c['shared_inputs'].items() for v in q['views']};target=rows(O/'target_activity.csv');source={(x['control_source'],x['role_suffix']):x for x in rows(R/'_p0pilot/control_risk_20261104/source_node_pairs.csv') if x['role_pair']=='True'};qr=rows(O/'role_boundary_qualification.csv');logical={}
 for x in qr:
  logical[(x['domain'],x['split'],x['view'],x['role'],'normal')]=x;logical[(x['domain'],x['split'],x['trojan_view'],x['role'],'trojan')]=x
 orig_names=(P/'orig_names/node_names_orig.txt').read_text(encoding='utf-8').splitlines();onorm=lambda s:s.strip().lstrip('\\');om=read(F/'data/for_train/class_map_orig.json');cm=read(F/'data/for_train/class_map_trans_transported.json');wanted={}
 for x in target:
  if x['domain']=='trans':
   v=vv[('trans_'+x['split'],x['view'])];wanted[v['old_start']+int(x['row'])-v['start']]=x
 parents=collections.defaultdict(set)
 for oi,ti in read(F/'data/for_train/alignment.json'):
  if ti in wanted:parents[ti].add(oi)
 out=[]
 for x in target:
  q=logical[(x['domain'],x['split'],x['view'],x['role'],x['side'])];s=source[(q['source'],x['role'])];expected=s['control_instance'] if x['side']=='normal' else s['trojan_instance'];label=int(x['label']);key=x['domain']+'_'+x['split'];v=vv[(key,x['view'])];gid=v['old_start']+int(x['row'])-v['start'];ov=vv[('orig_'+x['split'],x['source'])]
  if x['domain']=='orig':
   assert onorm(orig_names[gid])==expected and om[str(gid)]==label;pp={gid}
  else:
   pp=parents[gid];assert pp and cm[str(gid)]==label;assert {onorm(orig_names[i]) for i in pp}=={expected},(x,expected,pp)
  assert all(ov['old_start']<=i<ov['old_stop'] and om[str(i)]==label for i in pp),(x,pp)
  out.append(dict(domain=x['domain'],split=x['split'],view=x['view'],side=x['side'],role=x['role'],instance=x['instance'],global_id=gid,source_gate=expected,source_label=label,source_split_matches=True,transport_matches=True))
 with (O/'lineage_checks.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
 files=[F/'data/for_train/alignment.json',F/'data/for_train/class_map_orig.json',F/'data/for_train/class_map_trans_transported.json']
 (O/'lineage.json').write_text(json.dumps(dict(training=0,SAT=0,forward=0,passed=True,role_target_records=len(out),trans_unique_nodes=len(wanted),source_split_and_label_chain_consistent=True,inputs={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}),ensure_ascii=False,indent=2),encoding='utf-8');print('lineage records',len(out),'trans unique',len(wanted))
if __name__=='__main__':main()
