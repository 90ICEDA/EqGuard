"""Only v3/H seeds1,2; frozen seed42 v3 engine, legacy H schedules and matching init."""
from pathlib import Path
import json,hashlib,shutil,importlib.util,datetime
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;B=R/'_p0pilot/control_fair200_20261104';S=R/'_p0pilot/version_baseline_seed42_20261104';V=R/'_p0pilot/control_boundary_v3_20261104'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,a):p.write_text(json.dumps(a,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
 O.mkdir(exist_ok=True);assert read(S/'COMPLETE.json')['new_training_runs']==1;assert read(V/'PREFLIGHT_COMPLETE.json')['all_six_splits_verified']
 copy=['manifest.json','orig_base_mask.npy','trans_base_mask.npy','orig_C_slots.npy','orig_H_slots.npy','trans_C_slots.npy','trans_H_slots.npy','init_s1.pt','init_s2.pt']
 for name in copy:
  p=O/name
  if p.exists():assert sha(p)==sha(B/name),name
  else:shutil.copyfile(B/name,p)
 enginefile=O/'frozen_engine_v3.py'
 if enginefile.exists():assert sha(enginefile)==sha(S/'frozen_engine_v3.py')
 else:shutil.copyfile(S/'frozen_engine_v3.py',enginefile)
 sp=importlib.util.spec_from_file_location('v3_seeds12_engine',enginefile);engine=importlib.util.module_from_spec(sp);sp.loader.exec_module(engine);T=engine.T;np=engine.np;torch=engine.torch
 assert 'ginvenv_gpu' in engine.sys.executable and torch.cuda.is_available();assert T.MASK_MODE=='old' and T.ENCODING=='39' and not T.EXTRA and T.EQ==0
 contract=read(V/'input_contract.json');parent=T.CONTRACT
 for key,q in contract['shared_inputs'].items():
  old=parent['shared_inputs'][key];assert q['views']==old['views'] and q['nodes']==old['nodes'] and q['edges']==old['edges']
  for name in ['edge_index','edge_roles','y','trusted','physical']:assert sha(R/q['folder']/(name+'.npy'))==sha(R/old['folder']/(name+'.npy'))
 for p,h in contract['files'].items():assert sha(R/p)==h,p
 manifest=read(O/'manifest.json')
 for p,h in manifest['files'].items():assert sha(O/p)==h,p
 binding={}
 for seed in [1,2]:
  old=read(B/f'seed{seed}/H/EVALUATED.json');cfg=read(B/f'seed{seed}/H/config.json');b=read(B/f'seed{seed}/H/binding.json');assert cfg['updates']==200 and old['init_sha']==sha(O/f'init_s{seed}.pt') and old['checkpoint_sha']==sha(B/f'seed{seed}/H/best.pt')
  for p,k in [(R/'_p0pilot/control_best200_20261104/evaluate.py','model_source_sha'),(R/'_p0pilot/p2b_main_20261031/train_ab.py','loader_sha'),(R/'train_test2.2.py','loss_source_sha')]:assert sha(p)==b[k]
  binding[str(seed)]=dict(init_sha=old['init_sha'],v2_result_sha=sha(B/f'seed{seed}/H/EVALUATED.json'),v2_checkpoint_sha=old['checkpoint_sha'])
 T.CONTRACT=contract;T.NORM=np.load(V/'normalization.npz')
 write(O/'EXPERIMENT_CONTRACT.json',dict(seeds=[1,2],updates=200,arm='H',engine_identical_to_seed42=True,engine_sha=sha(enginefile),feature_contract_sha=sha(V/'input_contract.json'),normalization_sha=sha(V/'normalization.npz'),manifest_sha=sha(O/'manifest.json'),v2_bindings=binding,seed42_reused_from=str(S),SAT=False,region_weights_changed=False,pool_changed=False,old_H_slots=True,python=engine.sys.executable,cuda=torch.cuda.get_device_name()))
 report=[]
 for seed in [1,2]:
  result=engine.train(seed,'H',manifest);assert result['init_sha']==binding[str(seed)]['init_sha'];report.append(result)
 write(O/'TRAINING_COMPLETE.json',dict(new_runs=2,new_updates=400,seeds=[1,2],seed42_reused=True,v2_reused=True,SAT=0,region_weight_changed=False,runs=report,time=datetime.datetime.now().astimezone().isoformat()))
 print('Two v3 seeds complete',flush=True)
if __name__=='__main__':main()
