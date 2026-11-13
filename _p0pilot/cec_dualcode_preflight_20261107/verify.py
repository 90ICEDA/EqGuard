"""Independent CPU reconstruction of inputs,targets,budgets,JS and VJPs."""
from pathlib import Path
import collections,csv,hashlib,importlib.util,json
import numpy as np
import dual_interface as D
M=D.M;torch=M.torch;R=D.R;O=Path(__file__).resolve().parent;C=R/'_p0pilot/cec_repaired_contract_20261107'
def read(p):return M.read(p)
def rows(n):
 with (O/n).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def sha(p):return M.sha(p)
def arrsha(a):return hashlib.sha256(str(a.dtype).encode()+str(a.shape).encode()+a.tobytes()).hexdigest()
s=importlib.util.spec_from_file_location('independent_numpy_losses',R/'_p0pilot/cec_freeq_preflight_20261106/verify.py');V=importlib.util.module_from_spec(s);s.loader.exec_module(V)
def numpy_js(za,zb,b):
 def probability(z):
  x=z.astype(float);logits=-np.sqrt(np.mean((x[b['anchors']][:,None,:]-x[b['candidates']])**2,axis=2)+1e-12);p=np.exp(logits-logits.max(1,keepdims=True));return p/p.sum(1,keepdims=True)
 p,q=probability(za),probability(zb);m=(p+q)*.5
 return float(.5*np.dot(b['query_weight'],(p*np.log(p/m)).sum(1)+(q*np.log(q/m)).sum(1)))
def main():
 complete=read(O/'COMPLETE.json');assert complete['passed'] and complete['training']==complete['SAT']==complete['optimizer_objects']==0
 schedule=read(C/'SCHEDULE_SEED42.json');loader=D.pf.Loader();led=rows('six_arm_budget_ledger.csv');stats=rows('loaded_batches.csv');assert len(led)==192 and len(stats)==len(schedule)==32;coefficient=read(O/'FROZEN_COEFFICIENT.json')['coefficient'];maxerr=0.;maxJSerr=0.;budgets={a:collections.Counter() for a in D.ARMS}
 for u,row in zip(schedule,stats):
  step=u['update'];ids=sorted({c for r in u['units'] for c in r['cone_ids']});ix={c:i for i,c in enumerate(ids)};expected=collections.defaultdict(list)
  for r in u['units']:
   expected['anchors'] +=[ix[c] for c in r['anchors']];expected['candidates'] +=[[ix[c] for c in cc] for cc in r['candidates']];expected['real']+=r['real_targets'];expected['permuted']+=r['permuted_targets'];expected['negative_edges'] +=[[ix[a],ix[b]] for a,b in r['negative_edges']];expected['query_weight'] +=[r['query_weight']]*len(r['anchors']);expected['negative_weight'] +=[r['negative_weight']]*len(r['negative_edges'])
   for key in ['real_targets','permuted_targets']:
    pairs={(a,cc[t]) for a,cc,t in zip(r['anchors'],r['candidates'],r[key])};assert pairs=={(b,a) for a,b in pairs}
   assert all(a!=b for a,b in zip(r['real_targets'],r['permuted_targets']))
  with np.load(O/f'preview{step:02}.npz') as z:
   assert z['cone_ids'].tolist()==ids
   for k,v in expected.items():assert np.array_equal(z[k],np.asarray(v,dtype=z[k].dtype)),(step,k)
   b={k:z[k].copy() for k in expected};ra=z['root_a'].copy();rb=z['root_b'].copy();aa=V.cpu_losses(ra,b);bb=V.cpu_losses(rb,b);js=numpy_js(ra,rb,b)
   for k in ['CE_R','CE_P','different','variance_weighted','loss_Z','loss_R','loss_P']:
    col='base_'+k[-1] if k.startswith('loss_') else k;err=abs((aa[k]+bb[k])*.5-float(row[col]));maxerr=max(maxerr,err);assert err<1e-6
   maxJSerr=max(maxJSerr,abs(js-float(row['JS'])));assert abs(js-float(row['JS']))<2e-7
   # Changing labels cannot change JS; both actual roots remain separate functions.
   t={k:torch.tensor(v) for k,v in b.items()};parts,base,j,totals,_,_=D.objective(torch.tensor(ra),torch.tensor(rb),t,coefficient);alter=dict(t,real=t['permuted'],permuted=t['real']);j2=D.objective(torch.tensor(ra),torch.tensor(rb),alter,coefficient)[2];assert j.item()==j2.item()
   for arm in D.ARMS:assert abs(totals[arm].item()-(.5*(aa['loss_'+arm[0]]+bb['loss_'+arm[0]])+(coefficient if arm[1]=='1' else 0.)*js))<5e-6
  arrays=[loader.arrays(ids,tag) for tag in [step,10000+step]]
  hashes=[arrsha(a['x']) for a in arrays]
  for arm in D.ARMS:
   rr=next(r for r in led if r['arm']==arm and int(r['step'])==step);assert [rr['features_a_sha'],rr['features_b_sha']]==hashes
   budgets[arm].update({k:int(rr[k]) for k in ['logical_units','logical_queries','encoded_units','encoded_queries','candidate_distances','common_negatives','JS_queries']})
 wanted=dict(logical_units=64,logical_queries=384,encoded_units=128,encoded_queries=768,candidate_distances=2304,common_negatives=768,JS_queries=384)
 assert all(dict(b)==wanted for b in budgets.values())
 with np.load(O/'gradient_vectors.npz') as z:
  ratios=[];maxgrad=0
  for step in [1,2,16,32]:
   v={k:z[f'step{step}_{k}'].astype(float) for k in ['CE_R','CE_P','different','variance_weighted','JS','base_Z','base_R','base_P']}
   ratios.append(np.linalg.norm(v['JS'])/np.linalg.norm(v['base_R']))
   for arm in D.ARMS:
    actual=z[f'step{step}_total_{arm}'].astype(float);expected=v['base_'+arm[0]]+(coefficient if arm[1]=='1' else 0.)*v['JS'];err=np.linalg.norm(actual-expected)/np.linalg.norm(actual);maxgrad=max(maxgrad,err);assert err<2e-5
    expectedbase=v['different']+v['variance_weighted']+(v['CE_R'] if arm[0]=='R' else v['CE_P'] if arm[0]=='P' else 0);assert np.linalg.norm(v['base_'+arm[0]]-expectedbase)/np.linalg.norm(v['base_'+arm[0]])<2e-5
  independent=.25/float(np.median(ratios));assert abs(independent-coefficient)/coefficient<1e-6
 for p,h in read(O/'PREFLIGHT_CONTRACT.json')['protected_files'].items():assert sha(R/p)==h,p
 result=dict(passed=True,independently_rebuilt_dual_batches=32,independent_CPU_base_losses=224,six_arm_loss_checks=192,independent_JS_checks=32,labels_do_not_enter_JS_checks=32,gradient_total_vectors_checked=24,max_base_loss_error=maxerr,max_JS_error=maxJSerr,max_gradient_additivity_error=maxgrad,independent_coefficient=independent,coefficient_relative_error=abs(independent-coefficient)/coefficient,per_arm_budget=wanted,protected_files_unchanged=True,extra_model_forwards=0,training=0,SAT=0,ready_for_exploratory_training=True,not_performance_evidence=True)
 (O/'VERIFIED.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
if __name__=='__main__':main()
