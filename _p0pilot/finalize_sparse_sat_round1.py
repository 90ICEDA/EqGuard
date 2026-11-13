"""Wait for this round's four serial jobs, then verify, evaluate and update notes."""
import json
import argparse
import os
import subprocess
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'10.15/06_统一评测协议/N4_三向泛化/tables/sparse_sat_round1'


def state(phase,**kwargs):
    (OUT/'completion_status.json').write_text(json.dumps(dict(phase=phase,**kwargs),indent=2),encoding='utf-8')
    print('[stage]',phase,flush=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--resume-after-frozen',action='store_true')
    args=parser.parse_args()
    state('await_training')
    deadline=time.monotonic()+7200
    while True:
        path=OUT/'training_runs.json'
        if path.exists():
            try:
                runs=json.loads(path.read_text(encoding='utf-8'))
            except json.JSONDecodeError:
                runs=[]
            if any(r['exit_code'] for r in runs):
                raise RuntimeError('a training job failed')
            if len(runs)==4:
                break
        if time.monotonic()>deadline:
            raise TimeoutError('round did not finish within 2 hours')
        time.sleep(5)
    stages=[('frozen','ginvenv_gpu','frozen_sparse_sat_round1.py'),
            ('evaluate','ginvenv','evaluate_sparse_sat_round1.py'),
            ('publish','ginvenv','publish_sparse_sat_round1.py')]
    if args.resume_after_frozen:
        assert all((ROOT/f'_devcfg/gnn_sparseR1_frozen_{k}_s42.npz').exists() for k in ['real','perm','zero'])
        repeat=json.loads((OUT/'frozen_repeat_integrity.json').read_text())
        assert repeat['max_diff']==0
        stages=stages[1:]
    for name,venv,script in stages:
        state(name)
        cmd=[str(ROOT/f'{venv}/Scripts/python.exe'),'-X','utf8','-u',str(ROOT/'_p0pilot'/script)]
        with (ROOT/f'logs/sparseR1_{name}.log').open('w',encoding='utf-8') as f:
            p=subprocess.run(cmd,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        if p.returncode:
            state('failed',failed_stage=name,exit_code=p.returncode)
            raise RuntimeError(f'{name} failed: {p.returncode}')
    state('done',notes_updated=['SAT作用证明.md','SAT工作总结.md'])


if __name__=='__main__':
    main()
