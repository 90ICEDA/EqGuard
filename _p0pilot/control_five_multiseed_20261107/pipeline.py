"""Sequential isolated GPU seed runs,then CPU analysis/verification;resumable."""
from pathlib import Path
import json,subprocess,sys,time
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent
assert 'ginvenv_gpu' in sys.executable
def execute(folder,script,stage):
 log=folder/f'{stage}_attempt{1+len(list(folder.glob(stage+"_attempt*.log")))}.log'
 print('START',folder.name,stage,flush=True)
 with log.open('w',encoding='utf-8') as f:r=subprocess.run([sys.executable,str(folder/script)],cwd=R,stdout=f,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
 assert r.returncode==0,(folder,script,log,r.returncode)
 print('DONE',folder.name,stage,flush=True)
start=time.perf_counter()
for seed in [1,2]:
 folder=R/f'_p0pilot/control_five_seed{seed}_20261107'
 if not (folder/'TRAINING_COMPLETE.json').exists():execute(folder,'warm_run.py','run')
 else:print('REUSE_TRAINING',seed,flush=True)
for seed in [1,2]:
 folder=R/f'_p0pilot/control_five_seed{seed}_20261107'
 if not (folder/'ANALYSIS_COMPLETE.json').exists():execute(folder,'analyze.py','analysis')
 if not (folder/'VERIFIED.json').exists():execute(folder,'verify.py','verify')
(O/'PIPELINE_COMPLETE.json').write_text(json.dumps(dict(new_updates=2000,reused_seed42_updates=1000,total_updates=3000,seeds=[42,1,2],seconds=time.perf_counter()-start,SAT=0,EQ=0)),encoding='utf-8');print('BOTH_SEEDS_VERIFIED_COMPLETE',flush=True)
