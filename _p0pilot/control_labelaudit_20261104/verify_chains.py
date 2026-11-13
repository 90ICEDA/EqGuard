from pathlib import Path
import csv,json,collections,hashlib
import numpy as np
O=Path(__file__).resolve().parent;R=O.parents[1];F=R/'generate_trans/folds/hosts_bt31';P=R/'_p0pilot/round32_20261029'
def rows(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def dump(n,a):
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(a[0]));w.writeheader();w.writerows(a)
def main():
 c=read(P/'input_contract.json');vv={v['view']:(key,v) for key,q in c['shared_inputs'].items() if key.startswith('trans_') for v in q['views']};wanted={};pending=[]
 for x in rows(O/'unreachable34.csv'):pending.append(dict(view=x['view'],node=x['name'],source=x['source'],source_gate=x['source_gate'],expected_label=1,kind='unreachable34'))
 for x in rows(O/'collision_node_pairs.csv'):
  for side,label in [('normal',0),('trojan',1)]:pending.append(dict(view=x[side+'_view'],node=x[side+'_node'],source=x['source'] if side=='normal' else x['trojan_view'].split('__ys_')[0],source_gate=x[side+'_source_gate'],expected_label=label,kind='collision'))
 need={x['view'] for x in pending};allnames={};spans=sorted((vv[v][1]['old_start'],vv[v][1]['old_stop'],v) for v in need);j=0
 with (F/'data/processed/node_names_trans.txt').open(encoding='utf-8') as f:
  for gid,line in enumerate(f):
   while j<len(spans) and gid>=spans[j][1]:j+=1
   if j==len(spans):break
   lo,hi,v=spans[j]
   if gid>=lo:allnames[(v,line.strip().lstrip('\\'))]=gid
 for x in pending:wanted[allnames[(x['view'],x['node'])]]=x
 ap=collections.defaultdict(list)
 for oi,ti in read(F/'data/for_train/alignment.json'):
  if ti in wanted:ap[ti].append(oi)
 onames=(P/'orig_names/node_names_orig.txt').read_text(encoding='utf-8').splitlines();cm=read(F/'data/for_train/class_map_trans_transported.json');om=read(F/'data/for_train/class_map_orig.json');cache={};checks=[]
 for gid,x in wanted.items():
  key,v=vv[x['view']];folder=R/c['shared_inputs'][key]['folder']
  if key not in cache:cache[key]=(np.load(folder/'y.npy'),np.load(folder/'trusted.npy'))
  row=v['start']+gid-v['old_start'];lab=x['expected_label'];assert int(cache[key][0][row])==cm[str(gid)]==lab and cache[key][1][row];assert ap[gid] and {onames[i].strip().lstrip('\\') for i in ap[gid]}=={x['source_gate']} and all(om[str(i)]==lab for i in ap[gid])
  oq=c['shared_inputs']['orig_'+key.split('_')[1]];ov=next(v for v in oq['views'] if v['view']==x['source']);assert all(ov['old_start']<=i<ov['old_stop'] for i in ap[gid])
  checks.append(dict(**x,global_trans_id=gid,split_row=row,global_orig_ids='|'.join(map(str,ap[gid])),split_and_source_coordinates_match=True,source_class_label=lab,transported_label=lab,current_label=lab,current_trusted=True,ambiguous_or_mixed_labels=False))
 dump('label_chain_checks.csv',checks);assert len(checks)==42
 # Data and predictions are immutable through the offline audit.
 for p,h in read(R/'_p0pilot/control_fair200_20261104/manifest.json')['inputs'].items():assert hashlib.sha256((R/p).read_bytes()).hexdigest()==h,p
 for p,h in read(R/'_p0pilot/control_roles_20261104/analysis.json')['score_bindings'].items():assert hashlib.sha256((R/p).read_bytes()).hexdigest()==h,p
 (O/'verification.json').write_text(json.dumps(dict(checked_physical_nodes=len(checks),unreachable34=34,collision_nodes=8,all_label_chains_match=True,all_source_split_coordinates_match=True,all_training_inputs_unchanged=True,all_predictions_unchanged=True,training=0,SAT=0,model_forward=0,labels_modified=False),ensure_ascii=False,indent=2),encoding='utf-8');print('42 complete label chains and frozen inputs/predictions verified')
if __name__=='__main__':main()
