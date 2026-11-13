"""Include unpaired normal terminals/deep-XOR, without inventing Trojan counterparts."""
from pathlib import Path
import csv,collections,sys,json
import numpy as np
O=Path(__file__).resolve().parent;R=O.parents[1]
sys.path.insert(0,str(O));from analyze import roleclass,dump,rows
def main():
 source=rows(R/'_p0pilot/control_risk_20261104/source_node_pairs.csv');sr={(x['control_source'],x['control_instance']):x for x in source};mapping=collections.defaultdict(set)
 for r in rows(R/'_p0pilot/control_retention_20261104/per_source_node.csv'):
  if not r['all_trace_targets']:continue
  for n in r['all_trace_targets'].split('|'):mapping[(r['view'],n)].add((r['source_view'],r['source_gate']))
 base=rows(O/'normal_node_deltas.csv');annotated=[]
 for r in base:
  lineage={(r['source'],r['instance'])} if r['domain']=='orig' else mapping[(r['view'],r['instance'])]
  assert lineage,(r['view'],r['instance'])
  specs=[sr[k] for k in sorted(lineage)];classes={roleclass(x['role_suffix']) for x in specs};cl=next(iter(classes)) if len(classes)==1 else 'mixed_lineage'
  annotated.append(dict(**r,role_class=cl,source_roles='|'.join(sorted({x['role_suffix'] for x in specs})),lineage_source_gates='|'.join(sorted({x['control_instance'] for x in specs})),manufacturing_partner_all=all(x['role_pair']=='True' for x in specs),lineage_multiplicity=len(lineage)))
 dump('normal_nodes_with_roles.csv',annotated)
 numeric=['score_H','score_C','score_delta','fpr_H','fpr_C','Hscores_Cthreshold','Cscores_Hthreshold','relative_delta']
 def agg(a,keys):
  g=collections.defaultdict(list)
  for x in a:g[tuple(x[k] for k in keys)].append(x)
  return [dict(zip(keys,k),records=len(aa),**{n:float(np.mean([float(x[n]) for x in aa])) for n in numeric}) for k,aa in sorted(g.items())]
 perview=agg(annotated,['seed','operation','domain','split','source','view','role_class']);per_source=agg(perview,['seed','operation','domain','split','source','role_class']);av=agg(per_source,['operation','domain','split','source','role_class']);summary=agg(per_source,['operation','domain','split','role_class'])
 dump('normal_roleclass_source_seed.csv',per_source);dump('normal_roleclass_source_average.csv',av);dump('normal_roleclass_summary.csv',summary)
 (O/'normal_roles.json').write_text(json.dumps(dict(training=0,SAT=0,forward=0,node_rows=len(annotated),classes=sorted({x['role_class'] for x in annotated}),ambiguous_rule='one physical node one class; cross-class lineage marked mixed_lineage; no invented Trojan partner',source_role_summary_rows=len(av)),ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
