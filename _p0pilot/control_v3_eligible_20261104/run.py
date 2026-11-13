"""Only six equal-weight eligible-pool H/C runs on frozen v3, using frozen engine."""
from pathlib import Path
import json,hashlib,importlib.util,shutil,datetime
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;S=R/'_p0pilot/version_baseline_multiseed_20261104';V=R/'_p0pilot/control_boundary_v3_20261104';B=R/'_p0pilot/control_fair200_20261104'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 manifest=read(O/'manifest.json');assert manifest['feature_contract_sha']==sha(V/'input_contract.json') and manifest['normalization_sha']==sha(V/'normalization.npz')
 for p,h in manifest['files'].items():assert sha(O/p)==h,p
 for seed in [42,1,2]:assert sha(O/f'init_s{seed}.pt')==manifest['initializations'][str(seed)]==sha(B/f'init_s{seed}.pt')
 path=O/'frozen_engine_v3.py'
 if path.exists():assert sha(path)==sha(S/'frozen_engine_v3.py')
 else:shutil.copyfile(S/'frozen_engine_v3.py',path)
 sp=importlib.util.spec_from_file_location('eligible_v3_engine',path);engine=importlib.util.module_from_spec(sp);sp.loader.exec_module(engine);T=engine.T;assert 'ginvenv_gpu' in engine.sys.executable and engine.torch.cuda.is_available();assert T.MASK_MODE=='old' and not T.EXTRA and T.EQ==0
 c=read(V/'input_contract.json')
 for p,h in c['files'].items():assert sha(R/p)==h,p
 T.CONTRACT=c;T.NORM=engine.np.load(V/'normalization.npz')
 (O/'EXPERIMENT_CONTRACT.json').write_text(json.dumps(dict(manifest_sha=sha(O/'manifest.json'),engine_sha=sha(path),engine_identical_to_previous_v3=True,seeds=[42,1,2],arms=['H','C'],updates=200,weights_changed=False,SAT=False,feature_contract_sha=sha(V/'input_contract.json'),python=engine.sys.executable,cuda=engine.torch.cuda.get_device_name()),ensure_ascii=False,indent=2),encoding='utf-8')
 report=[]
 for seed in [42,1,2]:
  for arm in ['H','C']:report.append(engine.train(seed,arm,manifest))
 (O/'TRAINING_COMPLETE.json').write_text(json.dumps(dict(runs=report,new_runs=6,updates=1200,SAT=0,weights_changed=False,time=datetime.datetime.now().astimezone().isoformat()),ensure_ascii=False,indent=2),encoding='utf-8');print('Six eligible-pool runs complete',flush=True)
if __name__=='__main__':main()
