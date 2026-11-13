"""Seed42 one-factor ablation: functional pretraining dropout .2 -> 0 only."""
from pathlib import Path
import gc,importlib.util,json,sys,time,traceback
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;PRE=R/'_p0pilot/cec_pretrain_ready_20261105'
sys.path.insert(0,str(PRE));import engine as E
spec=importlib.util.spec_from_file_location('old_controller',R/'_p0pilot/cec_pretrain_seed42_20261105/run_controlled.py');C=importlib.util.module_from_spec(spec);spec.loader.exec_module(C)
torch=E.torch

def main():
 O.mkdir(exist_ok=True);assert 'ginvenv_gpu' in sys.executable and torch.cuda.is_available()
 contract=dict(seed=42,arms=['Z','R','P'],single_change='all five encoder dropout calls p=.2 to p=0 during pretrain ONLY',batchnorm='unchanged train mode and running-stat updates',pretrain_updates=50,finetune_updates=200,finetune_dropout=.2,sampling='exact old main seed42 frozen schedule;382 unique/500 slots',loss='unchanged MSE+different-function hinge+.1variance',features='same39v3,noSAT',original_contract_sha=E.sha(PRE/'RUN_CONTRACT.json'),controller_sha=E.sha(Path(__file__)),pooling_sha=E.sha(Path(C.__file__)),new_SAT=0,new_seeds=0,selection='same fixed pretrain50;fine validation AP every5')
 for name in ['schedule.json','function_inventory.json','RUN_CONTRACT.json']:
  dst=O/name
  if dst.exists():assert E.sha(dst)==E.sha(PRE/name)
  else:dst.write_bytes((PRE/name).read_bytes())
 if (O/'EXECUTION_CONTRACT.json').exists():assert E.read(O/'EXECUTION_CONTRACT.json')==contract
 else:E.write(O/'EXECUTION_CONTRACT.json',contract)
 E.O=O;E.make_embeddings=C.packed_pool;original_binding=E.prepare_binding
 def binding(mode,seed,arm):
  b=original_binding(mode,seed,arm);b.update(dropout_contract_sha=E.sha(O/'EXECUTION_CONTRACT.json'));return b
 E.prepare_binding=binding
 E.write(O/'POOL_SANITY.json',C.pool_sanity())
 original_dropout=E.F.dropout;original_save=E.save;calls=[];current={}
 def no_dropout(input,p=.5,training=True,inplace=False):
  assert p==.2,('unexpected dropout',p)
  if training:calls.append(float(p))
  return original_dropout(input,p=0.,training=training,inplace=inplace)
 def save(path,value):
  original_save(path,value)
  if Path(path).name=='resume.pt' and value.get('completed')==1:
   assert all(bool(torch.isfinite(t).all()) for t in value['model'].values() if t.is_floating_point())
   peak=torch.cuda.max_memory_allocated();total=torch.cuda.get_device_properties(0).total_memory;assert peak/total<.95
   if current['stage']=='pretrain':
    d=value['history'][0];assert d['representation_std']>.01 and len(calls)>=5
    assert sum(int(t) for k,t in value['model'].items() if k.endswith('num_batches_tracked'))>0
   E.write(O/f"FIRST_{current['stage']}_{current['arm']}.json",dict(passed=True,peak_bytes=peak,total_bytes=total,history=value['history'][0],pretrain_dropout_calls_disabled=len(calls)))
 E.save=save;results=[]
 for arm in ['Z','R','P']:
  gc.collect();torch.cuda.empty_cache();torch.cuda.reset_peak_memory_stats();current.update(stage='pretrain',arm=arm);calls.clear();E.F.dropout=no_dropout
  try:pre=E.pretrain('main',42,arm)
  finally:E.F.dropout=original_dropout
  E.write(O/f'DROPOUT_{arm}.json',dict(disabled_calls=len(calls),restored_for_finetuning=E.F.dropout is original_dropout,pretrain=pre))
  gc.collect();torch.cuda.empty_cache();current.update(stage='finetune');E.finetune('main',42,arm)
  results.append(dict(arm=arm,pretrain=pre,finetune=E.read(O/f'runs/main/seed42/{arm}/finetune/COMPLETE.json')));E.write(O/'progress.json',dict(completed=[r['arm'] for r in results]));print('ARM_COMPLETE',arm,flush=True)
 E.write(O/'TRAINING_COMPLETE.json',dict(seed=42,arms=results,total_pretrain_updates=150,total_finetune_updates=600,new_SAT_queries=0))
 spec=importlib.util.spec_from_file_location('ablation_analysis',R/'_p0pilot/cec_pretrain_seed42_20261105/analyze.py');A=importlib.util.module_from_spec(spec);spec.loader.exec_module(A);A.O=O;A.PRE=O;A.main()

if __name__=='__main__':
 try:main()
 except Exception:
  O.mkdir(exist_ok=True);(O/f'failure_{time.strftime("%H%M%S")}.txt').write_text(traceback.format_exc(),encoding='utf-8');raise
