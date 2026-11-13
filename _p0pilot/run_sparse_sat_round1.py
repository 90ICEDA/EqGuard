"""Serial CUDA controls with identical 47 dimensions, seed and budget."""
from __future__ import annotations
import argparse
import json
import os
import subprocess
import time
from datetime import datetime,timezone,timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'10.15/06_统一评测协议/N4_三向泛化/tables/sparse_sat_round1'


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--smoke',action='store_true')
    a=ap.parse_args()
    env=os.environ.copy()
    env.update(GNN_GRAD_CKPT='1',PYTORCH_CUDA_ALLOC_CONF='expandable_segments:True')
    py=ROOT/'ginvenv_gpu/Scripts/python.exe'
    common=[str(py),'-X','utf8','-u',str(ROOT/'train_test2.3.py'),
            '--work-dir','generate_trans/folds/hosts_bt31',
            '--fold-json','generate_trans/folds/hosts_bt31/views.json',
            '--pt-dir','generate_trans/folds/hosts_bt31/data/processed',
            '--config','_devcfg/dual.yaml','--fold-mode','fold','--steps-per-epoch','1',
            '--val-every','5','--view-policy','all','--amp','--epochs','2' if a.smoke else '100',
            '--train-mode','4','--label-mask','trust','--save-ckpt','--extra-feats','satrel_node','--seed','42']
    runs=[('real_bounded','real','bounded'),('perm_bounded','permuted','bounded'),
          ('zero_bounded','zero','bounded'),('real_legacy','real','covered')]
    if a.smoke:
        runs=[('smoke_bounded','real','bounded')]
    record=[]
    for name,variant,norm in runs:
        tag='fghtl_SparseR1_'+name+'_s42'
        dump=ROOT/f'_devcfg/gnn_sparseR1_{name}_s42.npz'
        result=ROOT/f'results/hosts_bt31_seed42mode4_allb1_fold_{tag}'
        if dump.exists() and (result/'run_config.json').exists() and not a.smoke:
            print(f'[skip-complete] {name}',flush=True)
            continue
        command=common+['--norm-extra',norm,'--extra-node-file',f'satrel_node_feats_sparseR1_{variant}.npy',
                        '--tag',tag,'--dump-scores',str(dump)]
        log=ROOT/f'logs/sparseR1_{name}.log'
        if log.exists():
            raise FileExistsError(f'refusing to overwrite {log}')
        start=datetime.now(timezone(timedelta(hours=8))).isoformat()
        print(f'[start] {name} {start}',flush=True)
        t=time.perf_counter()
        with log.open('w',encoding='utf-8') as f:
            p=subprocess.run(command,cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT,
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        row=dict(name=name,command=command,start=start,elapsed_s=time.perf_counter()-t,
                 exit_code=p.returncode,log=str(log.relative_to(ROOT)),dump=str(dump.relative_to(ROOT)))
        record.append(row)
        (OUT/('smoke_runs.json' if a.smoke else 'training_runs.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
        if p.returncode or not dump.exists() or not (result/'run_config.json').exists():
            raise RuntimeError(f'{name} failed; inspect {log}')
        cfg=json.loads((result/'run_config.json').read_text())
        assert cfg['device']=='cuda:0' and cfg['in_channels']==47 and cfg['normalization']['extra']==norm
        print(f'[done] {name} elapsed_s={row["elapsed_s"]:.1f}',flush=True)


if __name__=='__main__':
    main()
