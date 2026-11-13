"""Effective MUX-role control: all views deranged, reuse three true-role runs."""
import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import sys,importlib.util,json,collections,time,traceback,gc,shutil
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;PILOT=R/'_p0pilot/cec_pinrole_seed42_20261106';BOUND=R/'_p0pilot/cec_boundary_seed42_20261106'
spec=importlib.util.spec_from_file_location('frozen_pin_model',PILOT/'run.py');D=importlib.util.module_from_spec(spec);spec.loader.exec_module(D)
D.O=O;B=D.B;B.O=O;E=D.E;torch=D.torch;read=D.read;write=D.write;table=D.table
def rolemap(rank,condition):
 # No identity anchor: every MUX is actively deranged. Per-view conventions differ.
 # A single global permutation could just be learned as a renaming of role channels.
 shift=0 if condition=='shared' else 1+rank%2
 return np.array([0,1]+[2+(j+shift)%3 for j in range(3)],np.int64)
D.rolemap=rolemap

def exposure(cones):
 import gzip
 st={}
 with gzip.open(B.I/'cone_pin_incidence.jsonl.gz','rt',encoding='utf-8') as f:
  for line in f:
   p=json.loads(line);st[p['cone_id']]=sum(op=='MUX' for op in p['op'])
 inv={p['pair_id']:p for p in read(B.PRE/'function_inventory.json')};schedule=[r for r in read(B.PRE/'schedule.json') if r['mode']=='main' and r['seed']==42];ids=[r[k] for r in schedule for k in ['pair_a','pair_b']];rr=[]
 for pid in sorted(set(ids)):
  p=inv[pid];has=any(st[p[k]] for k in ['left_cone','right_cone']);rr.append(dict(pair_id=pid,source=p['source'],exposures=ids.count(pid),contains_mux=has,contains_changed_mux=has))
 table('train_mux_exposure.csv',rr)
 certs=read(R/'_p0pilot/cec_cert_expand_20261105/validation_negative_certificates.json');vv=[dict(certificate_id=c['certificate_id'],source=c['source'],contains_mux=any(st[k] for k in c['cones']),contains_changed_mux=any(st[k] for k in c['cones'])) for c in certs];table('validation_mux_blocks.csv',vv)
 z=dict(training_unique_pairs=382,training_unique_pairs_with_mux=sum(r['contains_mux'] for r in rr),training_unique_pairs_with_changed_mux=sum(r['contains_changed_mux'] for r in rr),training_slots=500,training_slots_with_mux=sum(r['exposures'] for r in rr if r['contains_mux']),training_slots_with_changed_mux=sum(r['exposures'] for r in rr if r['contains_changed_mux']),validation_blocks=68,validation_blocks_with_mux=sum(r['contains_mux'] for r in vv),validation_blocks_with_changed_mux=sum(r['contains_changed_mux'] for r in vv),control='all-view MUX roles deranged;COMM/NOT unchanged',selection='same existing frozen pairs and certificates;no result or label based selection')
 assert z['training_unique_pairs_with_changed_mux']==102 and z['validation_blocks_with_changed_mux']==28
 write('MUX_COVERAGE.json',z)

def main():
 O.mkdir(exist_ok=True);assert 'ginvenv_gpu' in sys.executable and torch.cuda.is_available();B.initial=D.initial
 E.set_inputs();cones={c['cone_id']:c for c in read(E.J/'final_cones.json')};b=D.PinBoundary(E.T.CONTRACT,cones);D.fixtures(b,cones);exposure(cones)
 # Correct audit annotation for the revised control; no row or original source changed.
 import csv
 with (O/'pin_loading_audit.csv').open(encoding='utf-8-sig') as f:audit=list(csv.DictReader(f))
 for r in audit:r['correct_to_control_mux_role_change']=int(r['mux_cells'])>0
 table('pin_loading_audit.csv',audit)
 oldload=read(O/'PIN_LOADING_VERIFIED.json');oldload['control']='every view MUX cyclically deranged by view rank;no identity anchor';write('PIN_LOADING_VERIFIED.json',oldload)
 inventory=read(B.PRE/'function_inventory.json');byid={p['pair_id']:p for p in inventory};schedule=collections.defaultdict(list)
 for row in read(B.PRE/'schedule.json'):
  if row['mode']=='main' and row['seed']==42:schedule[row['update']].append(row)
 assert len(schedule)==50 and all(cones[byid[r[k]][s]]['split']=='train' for rr in schedule.values() for r in rr for k in ['pair_a','pair_b'] for s in ['left_cone','right_cone'])
 reuse=[]
 for arm in ['Z','R','P']:
  old=PILOT/('shared_'+arm);co=read(old/'COMPLETE.json');assert co['updates']==50 and co['checkpoint_sha']==E.sha(old/'resume.pt')
  # Semantic code path for shared was unchanged: same model, data, weights, schedule/loss.
  assert np.array_equal(rolemap(0,'shared'),np.arange(5)) and np.array_equal(D.rolemap(3,'shared'),np.arange(5))
  new=O/('shared_'+arm);new.mkdir(exist_ok=True)
  for n in ['resume.pt','history.json','COMPLETE.json','FIRST_STEP.json']:
   src,dst=old/n,new/n
   if dst.exists():assert E.sha(src)==E.sha(dst)
   else:shutil.copy2(src,dst)
  reuse.append(dict(arm=arm,source=str(old.relative_to(R)),checkpoint_sha=co['checkpoint_sha'],source_binding=co['binding'],reused_updates=50,new_optimizer_updates=0))
 write('REUSED_TRUE_ROLE_RUNS.json',reuse)
 paths=[Path(__file__),PILOT/'run.py',BOUND/'run.py',B.PRE/'engine.py',B.PRE/'schedule.json',B.PRE/'function_inventory.json',B.PRE/'negative_certificates.json',E.J/'final_pairs.json',E.J/'final_cones.json',E.H/'init_s42.pt',E.V/'input_contract.json',E.V/'normalization.npz',B.I/'SCHEMA.json',B.I/'cone_pin_incidence.jsonl.gz',B.I/'boundary_maps_audit_only.json',R/'_p0pilot/cec_cert_expand_20261105/validation_negative_certificates.json',R/'_p0pilot/cec_cert_expand_20261105/validation_witness_contexts.json',*b.raw_files]
 paths += [p for folder in [PILOT,BOUND] for p in folder.rglob('*') if p.is_file() and p.suffix in ['.pt','.json','.csv','.npy','.npz']]
 frozen={str(p.relative_to(R)):E.sha(p) for p in paths}
 discarded={}
 for arm in ['Z','R','P']:
  ck=torch.load(PILOT/('viewshuffle_'+arm)/'resume.pt',map_location='cpu',weights_only=False);discarded[arm]=ck['completed'];del ck
 contract=dict(frozen_files=frozen,seed=42,conditions={'shared':'true pin roles;reused valid pilot ZRP50','viewshuffle':'all-view MUX roles deranged;new ZRP50'},boundary_identity='correct/shared in both',parameters=52455,updates_per_condition=50,effective_comparison_updates=300,reused_updates=150,new_updates_this_runner=150,superseded_control_saved_updates=discarded,original_pretrain_loss_unchanged=True,fixed='39v3/shared_boundary/dual2+2+post1/init/head/382pairs500slots/Adam/dropout.2/BN/BF16/final50',role_control='COMM/NOT unchanged;each view MUX cyclic shift1+rank%2;no identity anchor;different view ranks alternate permutations',validation_remaps=[9000,9001],new_SAT=0,detector_updates=0,test_reads=0,no_new_selection='revised control motivated by pre-existing incidence coverage,not validation performance')
 if (O/'EXECUTION_CONTRACT.json').exists():assert read(O/'EXECUTION_CONTRACT.json')==contract
 else:write('EXECUTION_CONTRACT.json',contract)
 x,e=B.graph('trans_train')
 if not (O/'PREFLIGHT.json').exists():D.preflight(x,e,b,cones,byid,schedule)
 assert read(O/'PREFLIGHT.json')['passed'] and read(O/'MUX_COVERAGE.json')['validation_blocks_with_changed_mux']==28
 for arm in ['Z','R','P']:B.train('viewshuffle',arm,x,e,b,cones,byid,schedule,dict(contract_sha=E.sha(O/'EXECUTION_CONTRACT.json'),alignment='viewshuffle',arm=arm))
 del x,e;gc.collect();torch.cuda.empty_cache()
 if not (O/'ANALYSIS_COMPLETE.json').exists():B.evaluate(b,cones)
 for p,h in frozen.items():assert E.sha(R/p)==h,p
 write('COMPLETE.json',dict(effective_comparison_updates=300,reused_true_role_updates=150,new_updates_this_runner=150,superseded_control_saved_updates=discarded,total_unique_saved_optimizer_updates_this_task=300+sum(discarded.values()),preflight_backward_calls_this_runner=1,finetune_updates=0,SAT=0,test_reads=0,old_inputs_and_results_unchanged=True,all_six_runs_complete=True))
 print('ALL_COMPLETE_EFFECTIVE',flush=True)
if __name__=='__main__':
 try:main()
 except Exception:
  O.mkdir(exist_ok=True);(O/f'failure_{time.strftime("%Y%m%d_%H%M%S")}.txt').write_text(traceback.format_exc(),encoding='utf-8');raise
