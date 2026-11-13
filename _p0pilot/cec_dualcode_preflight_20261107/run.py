"""Actual two-code loading,train-only calibration and no-update six-arm VJPs."""
import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import collections,csv,gc,hashlib,json,time,traceback,sys
import numpy as np
import dual_interface as D
M=D.M;torch=M.torch;R=D.R;O=Path(__file__).resolve().parent;C=R/'_p0pilot/cec_repaired_contract_20261107';PRE=R/'_p0pilot/cec_freeq_preflight_20261106';OLD=R/'_p0pilot/cec_repaired_transfer_audit_20261107'
def read(p):return M.read(p)
def sha(p):return M.sha(p)
def write(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def table(n,rr):
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def arrsha(a):return hashlib.sha256(str(a.dtype).encode()+str(a.shape).encode()+a.tobytes()).hexdigest()
def cosine(a,b):return float(a@b/(np.linalg.norm(a)*np.linalg.norm(b)))
def main():
 assert not (O/'COMPLETE.json').exists() and 'ginvenv_gpu' in sys.executable and torch.cuda.is_available();torch.set_num_threads(1);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
 assert read(OLD/'VERIFIED.json')['passed'];protected=dict(read(OLD/'AUDIT_CONTRACT.json')['protected_files'])
 for n,h in read(OLD/'OUTPUT_MANIFEST.json').items():assert sha(OLD/n)==h,n;protected[str((OLD/n).relative_to(R))]=h
 for p in [Path(__file__),O/'dual_interface.py',OLD/'VERIFIED.json',OLD/'PUBLISHED.json',C/'SCHEDULE_SEED42.json',PRE/'INITIAL_STATE.pt']:protected[str(p.relative_to(R))]=sha(p)
 for p,h in protected.items():assert sha(R/p)==h,p
 contract=dict(scope='authorized loader/calibration/no-update gradient preflight only',arms=D.ARMS,seed=42,updates_planned_each=32,actual_updates=0,base='average original Z/R/P losses over tag=t and10000+t;identical two encodings in all6arms',consistency='weightedJS(softmax(-RMSdistance/1)) across same ordered3candidates;no labels/stopgrad inJS',coefficient_rule='lambda=0.25/median_train_steps1,2,16,32(norm(gradJS)/norm(grad_base_R));same lambda all onarms;abort if normJS<1e-8 orlambda>1e4',checkpoint='common saved oldINITIAL_STATE,not trained final32',calibration_consumes='training units only;no validation scoring or coefficient tuning',budget_each=dict(logical_unit_slots=64,logical_queries=384,encoded_unit_slots=128,encoded_queries=768,candidate_distances=2304,common_negative_computations=768,consistency_queries=384),training=0,SAT=0,finetune=0,test_reads=0,protected_files=protected)
 write('PREFLIGHT_CONTRACT.json',contract);loader=D.pf.Loader();initial=torch.load(PRE/'INITIAL_STATE.pt',map_location='cuda',weights_only=False);m=M.fresh('cuda');m.load_state_dict(initial['model']);m.eval();before=M.state_digest(m);assert before==initial['digest'];params=list(m.parameters());forwards=autograd=0;stats=[];ledger=[];vectors={};cal=[]
 def vjp(loss):
  nonlocal autograd
  vv=torch.autograd.grad(loss,params,retain_graph=True,allow_unused=True);autograd+=1
  v=np.concatenate([np.zeros(p.numel(),np.float32) if x is None else x.detach().cpu().numpy().ravel() for p,x in zip(params,vv)]);assert np.isfinite(v).all();return v
 for step in range(1,33):
  a,b=D.dualbatch(loader,step);assert a['loss']['candidates'].shape==(12,3);assert all(r['unit_id'] in loader.training for r in a['records']);assert all(loader.training[r['unit_id']]['split']=='train' for r in a['records'])
  with torch.no_grad():
   za,aa=m.encode(a['graph']);zb,ab=m.encode(b['graph']);parts,base,j,_,auxa,auxb=D.objective(za,zb,a['loss'],0.)
  forwards+=2;assert float(j)>=-1e-7 and float(j)<=np.log(2)+1e-7
  for x,au in [(a,aa),(b,ab)]:assert au['consumed_nodes']==x['graph']['nodes'] and au['consumed_pin_edges']==x['graph']['edges']
  assert min(float(za.std(0,unbiased=False).mean()),float(zb.std(0,unbiased=False).mean()))>1e-5
  # Label-independent JS,shared candidate reordering,and same-code zero checks.
  perm=torch.tensor([2,0,1],device='cuda');same=D.js(auxa['logits'],auxa['logits'],a['loss']['query_weight']);reorder=D.js(auxa['logits'][:,perm],auxb['logits'][:,perm],a['loss']['query_weight']);assert abs(float(same))<1e-7 and abs(float(reorder-j))<1e-7
  stats.append(dict(step=step,nodes_each=a['graph']['nodes'],edges_each=a['graph']['edges'],std_a=float(za.std(0,unbiased=False).mean()),std_b=float(zb.std(0,unbiased=False).mean()),JS=float(j),**{k:float(v) for k,v in parts.items()},**{'base_'+k:float(v) for k,v in base.items()}))
  np.savez_compressed(O/f'preview{step:02}.npz',cone_ids=np.array(a['cone_ids']),root_a=za.cpu().numpy(),root_b=zb.cpu().numpy(),**{k:v.cpu().numpy() for k,v in a['loss'].items()})
  for arm in D.ARMS:ledger.append(dict(arm=arm,step=step,tag_a=step,tag_b=10000+step,logical_units=2,logical_queries=12,encoded_units=4,encoded_queries=24,candidate_distances=72,common_negatives=24,JS_queries=12,features_a_sha=arrsha(a['arrays']['x']),features_b_sha=arrsha(b['arrays']['x']),targets_sha=hashlib.sha256(b''.join(v.detach().cpu().numpy().tobytes() for v in a['loss'].values())).hexdigest()))
  del a,b,za,zb,parts,base,j,auxa,auxb;gc.collect();torch.cuda.empty_cache()
 table('loaded_batches.csv',stats);table('six_arm_budget_ledger.csv',ledger)
 for step in [1,2,16,32]:
  a,b=D.dualbatch(loader,step);za,_=m.encode(a['graph']);zb,_=m.encode(b['graph']);parts,base,j,_,_,_=D.objective(za,zb,a['loss'],0.);forwards+=2
  vv={k:vjp(loss) for k,loss in {**parts,**{'base_'+k:v for k,v in base.items()},'JS':j}.items()}
  for k,v in vv.items():vectors[f'step{step}_{k}']=v
  nj=float(np.linalg.norm(vv['JS']));nr=float(np.linalg.norm(vv['base_R']));assert nj>1e-8 and nr>1e-8
  cal.append(dict(step=step,JS=float(j.detach()),JS_gradient_norm=nj,base_R_gradient_norm=nr,raw_ratio=nj/nr,JS_vs_real_CE_cos=cosine(vv['JS'],vv['CE_R']),JS_vs_wrong_CE_cos=cosine(vv['JS'],vv['CE_P']),real_vs_wrong_CE_cos=cosine(vv['CE_R'],vv['CE_P'])))
  del a,b,za,zb,parts,base,j,vv;gc.collect();torch.cuda.empty_cache()
 coefficient=.25/float(np.median([r['raw_ratio'] for r in cal]));assert np.isfinite(coefficient) and coefficient<=1e4
 for r in cal:r['weighted_ratio']=coefficient*r['raw_ratio']
 assert abs(float(np.median([r['weighted_ratio'] for r in cal]))-.25)<1e-12
 write('FROZEN_COEFFICIENT.json',dict(coefficient=coefficient,rule=contract['coefficient_rule'],calibration_steps=[1,2,16,32],median_weighted_ratio=.25,validation_scores_consumed=0));table('calibration_gradients.csv',cal)
 gradientrows=[]
 for step in [1,2,16,32]:
  a,b=D.dualbatch(loader,step);za,_=m.encode(a['graph']);zb,_=m.encode(b['graph']);parts,base,j,totals,_,_=D.objective(za,zb,a['loss'],coefficient);forwards+=2;vv={}
  for arm,loss in totals.items():
   v=vjp(loss);vv[arm]=v;expected=vectors[f'step{step}_base_{arm[0]}']+(coefficient if arm[1]=='1' else 0.)*vectors[f'step{step}_JS'];error=float(np.linalg.norm(v-expected)/np.linalg.norm(v));assert error<2e-5;vectors[f'step{step}_total_{arm}']=v
   gradientrows.append(dict(step=step,arm=arm,loss=float(loss.detach()),gradient_norm=float(np.linalg.norm(v)),additivity_error=error,JS_scaled_to_this_base_norm=coefficient*float(np.linalg.norm(vectors[f'step{step}_JS']))/float(np.linalg.norm(vectors[f'step{step}_base_{arm[0]}']))))
  assert all(p.grad is None for p in params)
  del a,b,za,zb,parts,base,j,totals;gc.collect();torch.cuda.empty_cache()
 table('six_arm_gradient_checks.csv',gradientrows);np.savez_compressed(O/'gradient_vectors.npz',**vectors)
 # Six actual group clones from same old init,one shared first batch,no backward/update.
 a,b=D.dualbatch(loader,1);clone=[]
 for arm in D.ARMS:
  mm=M.fresh('cuda');mm.load_state_dict(initial['model']);mm.eval();assert M.state_digest(mm)==before
  with torch.no_grad():za,_=mm.encode(a['graph']);zb,_=mm.encode(b['graph']);_,_,j,totals,_,_=D.objective(za,zb,a['loss'],coefficient)
  forwards+=2;expected=next(r for r in gradientrows if r['step']==1 and r['arm']==arm)['loss'];assert abs(float(totals[arm])-expected)<2e-5 and M.state_digest(mm)==before;clone.append(dict(arm=arm,loss=float(totals[arm]),JS=float(j),initial_digest=before));del mm
 table('six_actual_clone_checks.csv',clone)
 # Honest degeneracy fixture:equal candidate distributions have JS=0 without encoding function identity.
 fake=torch.tensor([[0.,1.,2.]],device='cuda');uniform=torch.zeros_like(fake);weights=torch.ones(1,device='cuda')
 assert abs(float(D.js(fake,fake,weights)))<1e-7 and abs(float(D.js(uniform,uniform,weights)))<1e-7
 assert M.state_digest(m)==before and all(p.grad is None for p in params)
 for p,h in protected.items():assert sha(R/p)==h,p
 write('COMPLETE.json',dict(passed=True,planned_arms=D.ARMS,loaded_steps=32,calibration_coefficient=coefficient,model_forwards=forwards,autograd_calls=autograd,optimizer_objects=0,training=0,SAT=0,finetune=0,test_reads=0,validation_scores_consumed=0,initial_state_and_grad_fields_unchanged=True,old_files_unchanged=True,JS_uniform_degeneracy_known=True,claim='eligible for exploratory training only;no guarantee of improved rank or MUX generalization'))
 print('DUALCODE_PREFLIGHT_COMPLETE',coefficient,flush=True)
if __name__=='__main__':
 try:main()
 except Exception:(O/f'failure_{time.strftime("%H%M%S")}.log').write_text(traceback.format_exc(),encoding='utf-8');raise
