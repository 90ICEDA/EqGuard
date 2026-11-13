"""Independent provenance/budget/metric checks; cached data only."""
from pathlib import Path
import collections,csv,hashlib,json,re
import numpy as np
from sklearn.metrics import roc_auc_score
O=Path(__file__).resolve().parent;R=O.parents[1];J=R/'_p0pilot/cec_joint_expand_20261105'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def table(n,x):
 if not x:return
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(x[0]));w.writeheader();w.writerows(x)
def main():
 panel=read(O/'panel_certificates.json');proofs=read(J/'proofs.json');pairs={p['pair_id']:p for p in read(J/'final_pairs.json')};cones={c['cone_id']:c for c in read(J/'final_cones.json')};depth=read(O/'panel_cone_depths.json');frozen={}
 gdone=read(O/'GRADIENT_COMPLETE.json');contract=read(O/'DIAGNOSTIC_CONTRACT.json')
 for p,h in contract['frozen_files'].items():assert sha(R/p)==h,p
 qids={q for c in panel for q in c['proof_ids']};qrows=[];cache={}
 for qid in sorted(qids):
  q=proofs[qid];folder=R/q['folder'];script=(folder/'run.ys').read_text(encoding='utf-8');log=(folder/'run.log').read_text(encoding='utf-8')
  assert sha(folder/'model.v')==q['model_sha'] and sha(folder/'run.log')==q['log_sha'] and hashlib.sha256(script.encode()).hexdigest()==q['script_sha']
  command=[s for s in script.splitlines() if s.startswith('sat ')][int(q['query_id'])]
  assert re.fullmatch(r'sat '+re.escape(q['args'])+r' -timeout \d+ -show-inputs -show-outputs -dump_json "[^"]+"',command)
  blocks=re.split(r'^(?:Q|QUERY)\d{4}\s*$',log,flags=re.M);block=blocks[int(q['query_id'])+1]
  assert 'no model found: SUCCESS' in block and 'TIMEOUT' not in block and 'ERROR:' not in log
  for n in ['run.ys','run.log','model.v']:frozen[str((folder/n).relative_to(R))]=sha(folder/n)
  qrows.append(dict(proof_id=qid,folder=q['folder'],query_id=q['query_id'],success=True))
 table('proof_query_recheck.csv',qrows)
 for c in panel:
  a,b=[pairs[c[k]] for k in ['pair_a','pair_b']]
  assert a['source_object']==b['source_object']==c['source'] and a['context_id']==b['context_id']==c['context_id']
  assert a['split']==b['split']==c['split'] and c['split'] in ['train','val']
  assert cones[a['left_cone']]['view']==cones[b['left_cone']]['view'] and cones[a['right_cone']]['view']==cones[b['right_cone']]['view']
  assert max(len(cones[k]['members']) for k in c['cones'])<=16
  assert (max(depth[k]['gate_depth'] for k in c['cones'])<=4)==(c['tier']=='shallow_small')
 for split in ['train','val']:
  for tier in ['shallow_small','small_depth_control']:
   cc=[c for c in panel if c['split']==split and c['tier']==tier];counts=collections.Counter(k for c in cc for k in c['cones']);assert max(counts.values())<=2
   assert max(collections.Counter(c['source'] for c in cc).values())<=16
   assert len({tuple(sorted(c['cones'])) for c in cc})==len(cc)
 # Coverage denominator, including sources not able to form any different-function block.
 contexts=read(R/'_p0pilot/cec_pretrain_ready_20261105/witness_contexts.json');contexts.update(read(R/'_p0pilot/cec_cert_expand_20261105/validation_witness_contexts.json'))
 # Inspect endpoint-only structural shortcuts; no candidate changes.
 raw={};struct=[]
 def m(c):
  if c['view'] not in raw:raw[c['view']]=next(iter(read(R/c['raw_path'])['modules'].values()))
  return raw[c['view']]
 for c in panel:
  co=[cones[k] for k in c['cones']];g=[m(z)['cells'][z['output_cell']]['type'] for z in co];leaves=[sorted({tuple(x[:3]) for x in z['leaves']}) for z in co];sizes=[(len(z['members'])-1).bit_length() for z in co]
  flags=dict(gates_matched=g[0]==g[2] and g[1]==g[3],cut_counts_matched=len(leaves[0])==len(leaves[2]) and len(leaves[1])==len(leaves[3]),boundary_sets_matched=leaves[0]==leaves[2] and leaves[1]==leaves[3],size_bins_matched=sizes[0]==sizes[2] and sizes[1]==sizes[3])
  struct.append(dict(certificate=c['certificate_id'],split=c['split'],tier=c['tier'],source=c['source'],**flags,strict_matched=all(flags.values())))
 table('panel_structural_matching.csv',struct)
 ss={x['certificate']:x for x in struct};metric=[];published=rows(O/'panel_evaluation_summary.csv')
 for split in ['train','val']:
  for arm in ['Z','R','P']:
   with np.load(O/f'panel_{split}_{arm}.npz') as z:
    ix={k:i for i,k in enumerate(z['cone_ids'].tolist())}
    for tier in ['shallow_small','small_depth_control']:
     for subset in ['all','strict_matched']:
      cc=[c for c in panel if c['split']==split and c['tier']==tier and (subset=='all' or ss[c['certificate_id']]['strict_matched'])]
      if not cc:continue
      for space,x in [('root64',z['concat128'][:,:64]),('mean64',z['concat128'][:,64:]),('concat128',z['concat128']),('projection32',z['projection32'])]:
       real=[];wrong=[]
       for c in cc:
        a,b,d,e=[x[ix[k]].astype(np.float64) for k in c['cones']];dist=lambda a,b:float(np.sqrt(np.mean((a-b)**2)))
        real += [dist(a,b),dist(d,e)];wrong += [dist(a,e),dist(d,b)]
       auc=float(roc_auc_score([1]*len(real)+[0]*len(wrong),-np.array(real+wrong)))
       metric.append(dict(split=split,arm=arm,tier=tier,subset=subset,space=space,blocks=len(cc),sources=len({c['source'] for c in cc}),auc=auc))
       if subset=='all':
        old=next(r for r in published if r['split']==split and r['arm']==arm and r['tier']==tier and r['space']==space);assert abs(auc-float(old['cross_auc']))<1e-12
 table('panel_independent_metrics.csv',metric)
 assert gdone['optimizer_steps']==gdone['SAT']==gdone['test_reads']==0 and all(x['all_parameters_and_buffers_unchanged'] for x in gdone['states'])
 angles=rows(O/'gradient_angles.csv');norms=rows(O/'gradient_norms.csv')
 assert len(norms)==14*4*6 and len(angles)==14*6*4
 assert all(np.isfinite(float(r['grad_norm'])) for r in norms)
 gs=[]
 for arm in ['Z','R','P']:
  for group in ['backbone','shared_boundary','pin_boundary','pin_internal','projection','all']:
   aa=[x for x in angles if x['checkpoint']==arm and x['group']==group and x['dropout']=='False'];nn=[x for x in norms if x['checkpoint']==arm and x['group']==group and x['dropout']=='False']
   gs.append(dict(checkpoint=arm,group=group,real_permuted_cosine_mean=np.mean([float(x['cosine']) for x in aa if x['left']=='real' and x['right']=='permuted']),real_different_cosine_mean=np.mean([float(x['cosine']) for x in aa if x['left']=='real' and x['right']=='different']),R_P_total_cosine_mean=np.mean([float(x['cosine']) for x in aa if x['left']=='R_total']),**{t+'_norm_mean':np.mean([float(x['grad_norm']) for x in nn if x['term']==t]) for t in ['real','permuted','different','variance_weighted']}))
 table('gradient_summary.csv',gs)
 allsrc=sorted({(p['split'],p['source_object']) for p in pairs.values()});missing=[]
 for split,source in allsrc:
  pp=[p for p in pairs.values() if p['split']==split and p['source_object']==source];small=[p for p in pp if max(len(cones[p[k]]['members']) for k in ['left_cone','right_cone'])<=16];shallow=[p for p in small if max(depth[p[k]]['gate_depth'] for k in ['left_cone','right_cone'])<=4]
  missing.append(dict(split=split,source=source,existing_pairs=len(pp),small_pairs=len(small),shallow_pairs=len(shallow),selected_shallow_blocks=sum(c['source']==source and c['tier']=='shallow_small' for c in panel),selected_deeper_blocks=sum(c['source']==source and c['tier']=='small_depth_control' for c in panel)))
 table('panel_coverage_denominators.csv',missing)
 for p,h in frozen.items():assert sha(R/p)==h
 write('DIAGNOSTIC_VERIFIED.json',dict(independent_AUC_exact_match=True,proof_queries_rechecked=len(qrows),query_files_sha=frozen,old_manifest_and_checkpoints_unchanged=True,panel_certificates=250,per_source_per_tier_cap=16,per_endpoint_per_tier_cap=2,model_forwards=gdone['model_forwards'],loss_vector_jacobian_products=gdone['loss_vector_jacobian_products'],optimizer_steps=0,SAT=0,test_reads=0,notes='Masks are saved existence witnesses;equivalence reused from existing query/enumeration evidence.Gradient summaries are local raw gradients,not Adam/clipped updates.Independent sources not equal independent hosts.'))
 print(json.dumps(dict(proof_queries_rechecked=len(qrows),strict_counts=collections.Counter((x['split'],x['tier']) for x in struct if x['strict_matched']).__str__(),verified=True)),flush=True)
if __name__=='__main__':main()
