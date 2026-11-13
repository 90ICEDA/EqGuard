"""Create adapted runner from retained, audited runner; originals untouched."""
from pathlib import Path
O=Path(__file__).resolve().parent;R=O.parents[1]
old=(R/'_p0pilot/cec_freeq_zrp_seed42_20261107/run.py').read_text(encoding='utf-8')
train=old[old.index('def train('):old.index('def evaluate(')]
for a,b in [("PRE/'initial_loss_preview.csv'","PREF/'loaded_batches.csv'"),("(18,3)","(12,3)"),("(18,2)","(12,2)"),('context_families=3,unit_slots=3,queries=18,candidate_distances=54,common_negative_terms=18','context_families=2,unit_slots=2,queries=12,candidate_distances=36,common_negative_terms=12'),('unit_slots=3,query_slots=18,candidate_distances=54,common_negative_terms=18','unit_slots=2,query_slots=12,candidate_distances=36,common_negative_terms=12'),("C/'SUPERVISION_BUDGET.json'","C/'BUDGET.json'")]:
 assert a in train,a
 train=train.replace(a,b)
head='''import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import collections,csv,gc,hashlib,json,shutil,sys,time,traceback
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent
PRE=R/'_p0pilot/cec_freeq_preflight_20261106';C=R/'_p0pilot/cec_repaired_contract_20261107';PREF=R/'_p0pilot/cec_repaired_preflight_20261107'
sys.path.insert(0,str(R/'_p0pilot/cec_freeq_zrp_seed42_20261107'))
import run as original
sys.path.insert(0,str(PREF));import run as unused
# Load preflight module explicitly to avoid its generic name colliding with old runner.
import importlib.util
spec=importlib.util.spec_from_file_location('repaired_preflight',PREF/'run.py');pf=importlib.util.module_from_spec(spec);spec.loader.exec_module(pf)
M=pf.M;torch=M.torch;ARMS=['Z','R','P']
read=original.read;sha=original.sha;arrsha=original.arrsha
original.O=O
write=original.write;save=original.save;table=original.table
def freeze():
 assert read(PREF/'VERIFIED.json')['passed']
 protected=dict(read(PREF/'EXECUTION_CONTRACT.json')['protected_files'])
 for folder in [PREF,C,R/'_p0pilot/cec_freeq_zrp_seed42_20261107']:
  for p in folder.iterdir():
   if p.is_file() and p.suffix in ['.json','.py','.csv','.pt','.npz']:protected[str(p.relative_to(R))]=sha(p)
 protected[str(Path(__file__).relative_to(R))]=sha(Path(__file__))
 contract=dict(authorization='user authorized repaired seed42 Z/R/P each32 steps;supersedes historical prepared-only flags without editing them',initialization_sha=sha(PRE/'INITIAL_STATE.pt'),arms=ARMS,seed=42,updates_each=32,primary='73 repaired H3 validation units,root64 familymacro pairwise win;9000 primary,9001 predefined sensitivity',checkpoint='fixedlast32 only,no validation selection',fixed='7 triples/21classes/4sources/2families;47360params,old init,25d fullfreeQ DAG roles/phase;Adam lr.0002 wd.001 clip1;FP32/noTF32/noAMP;same objectives and schedule',budget=read(C/'BUDGET.json'),evaluation_tags=[9000,9001],finetune=0,SAT=0,test_reads=0,protected_files=protected)
 if (O/'EXECUTION_CONTRACT.json').exists():assert read(O/'EXECUTION_CONTRACT.json')==contract
 else:write('EXECUTION_CONTRACT.json',contract)
 for p,h in protected.items():assert sha(R/p)==h,p
 return contract,hashlib.sha256(json.dumps(contract,sort_keys=True).encode()).hexdigest()
'''
tail='''
def main():
 assert 'ginvenv_gpu' in sys.executable and torch.cuda.is_available()
 torch.set_num_threads(1);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
 start=time.perf_counter();contract,binding=freeze();loader=pf.Loader()
 # Diagnostic PO units are unchanged. Main eligibility is the repaired73 only.
 panel=R/'_p0pilot/cec_boundary_panel_expand_20261107'
 pp={'train_frozen_pool':list(loader.training.values()),'val_boundary_all':read(C/'VAL_H3_NONFORCED.json'),'val_old_PO':[u for u in read(panel/'STRICT_PO_REFERENCE_UNCHANGED.json') if u['split']=='val'],'val_new_PO':[u for u in read(panel/'CORE_EXACT_PO_DIAGNOSTIC.json') if u['split']=='val']}
 assert len(pp['val_boundary_all'])==73
 write('EVALUATION_PANELS.json',pp)
 if not (O/'TRAINING_COMPLETE.json').exists():train(loader,contract,binding)
 else:
  for arm in ARMS:assert read(O/arm/'COMPLETE.json')['checkpoint_sha']==sha(O/arm/'resume.pt')
 original.evaluate(loader,pp,contract)
 for p,h in contract['protected_files'].items():assert sha(R/p)==h,p
 write('COMPLETE.json',dict(actual_optimizer_updates=96,updates_each=32,arms=ARMS,old_files_unchanged=True,evaluation_completed=True,finetune=0,SAT=0,test_reads=0,seconds_this_execution=time.perf_counter()-start))
 print('REPAIRED_TRAINING_AND_EVALUATION_COMPLETE',flush=True)
if __name__=='__main__':
 try:main()
 except Exception:
  (O/f'failure_{time.strftime("%H%M%S")}.log').write_text(traceback.format_exc(),encoding='utf-8');raise
'''
# The reused evaluator's global path is set only in memory; it writes solely to this new folder.
(O/'run.py').write_text(head+train+tail,encoding='utf-8')
print('Runner prepared in independent output directory.')
