"""Safe coordinator: read-only status by default; explicit --run resumes SAT."""
import argparse
import concurrent.futures as cf
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from k4_runtime import (PANEL, ROOT, exclusive_lock, fresh_dir, memory_available_gib,
                        prepare_inputs, read_plan, validate_complete, write_new)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',action='store_true')
    parser.add_argument('--workers',type=int,choices=(1,2,3,4),default=2)
    parser.add_argument('--max-workers',type=int,choices=(1,2,3,4),default=4)
    parser.add_argument('--min-free-gib',type=float,default=8)
    parser.add_argument('--min-memory-gib',type=float,default=2)
    parser.add_argument('--prepare-only',action='store_true')
    parser.add_argument('--limit',type=int)
    a=parser.parse_args()
    if a.workers>a.max_workers:parser.error('workers cannot exceed max-workers')
    if a.min_free_gib<4 or a.min_memory_gib<1 or (a.limit is not None and a.limit<1):
        parser.error('Require disk >=4 GiB, available memory >=1 GiB and positive limit')
    plan=read_plan(PANEL/'plan.json');pending=[];complete=[]
    for item in plan['views']:
        v=item['view'];ok,detail=validate_complete(PANEL/'views'/v)
        (complete if ok else pending).append(v)
        print(json.dumps(dict(view=v,complete=ok,detail=detail),ensure_ascii=False),flush=True)
    print(json.dumps(dict(total=len(plan['views']),verified_complete=len(complete),
        pending=len(pending),free_gib=shutil.disk_usage(ROOT).free/2**30,
        memory_gib=memory_available_gib(),workers=a.workers,run=a.run)),flush=True)
    if not a.run:return
    def ready(workers=1):
        return (shutil.disk_usage(ROOT).free/2**30>=a.min_free_gib
                and memory_available_gib()>=max(a.min_memory_gib,workers*.75+.5))
    if not ready(a.workers):raise RuntimeError('Insufficient disk/memory; no SAT launched')
    with exclusive_lock(PANEL/'coordinator.lock'):
        prepare_inputs()
        if a.prepare_only:return
        run=fresh_dir(PANEL/'runs','run')
        print(f'RUN_DIR={run}\nSTOP_FILE={run / "STOP"}',flush=True)
        write_new(run/'control.json',dict(workers=a.workers))
        env=os.environ.copy()
        env.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',
                   PYTHONDONTWRITEBYTECODE='1',SAT_K4_STOP_FILE=str(run/'STOP'))
        def one(v):
            started=time.perf_counter();log=run/(v+'.log')
            with log.open('x',encoding='utf-8') as f:
                rc=subprocess.call([str(ROOT/'ginvenv/Scripts/python.exe'),'-B','-X','utf8',
                    str(Path(__file__).with_name('run_one_k4_alltrain.py')),v],
                    cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT)
            valid,detail=validate_complete(PANEL/'views'/v)
            return dict(view=v,rc=rc,verified_complete=valid,detail=detail,
                seconds=time.perf_counter()-started,log=str(log.relative_to(ROOT)))
        pending=pending[:a.limit] if a.limit else pending
        remaining=iter(pending);results=[];active={};stopped=False
        with cf.ThreadPoolExecutor(max_workers=a.max_workers) as ex:
            while True:
                try:limit=max(1,min(a.max_workers,int(json.loads((run/'control.json').read_text())['workers'])))
                except (OSError,ValueError,KeyError):limit=a.workers
                while len(active)<limit and not stopped:
                    if (run/'STOP').exists() or shutil.disk_usage(ROOT).free/2**30<a.min_free_gib:
                        stopped=True
                        print('Disk/STOP guard: dispatch paused, existing evidence retained',flush=True)
                        break
                    if not ready(len(active)+1):break
                    v=next(remaining,None)
                    if v is None:break
                    active[ex.submit(one,v)]=v
                if not active:
                    if stopped:break
                    if len(results)>=len(pending):break
                    time.sleep(10)
                    continue
                done,_=cf.wait(active,timeout=15,return_when=cf.FIRST_COMPLETED)
                for f in done:
                    v=active.pop(f)
                    try:r=f.result()
                    except Exception as e:r=dict(view=v,rc=-1,verified_complete=False,error=repr(e))
                    results.append(r);write_new(run/f'result_{len(results):04d}.json',r)
                    print(json.dumps(r,ensure_ascii=False),flush=True)
        summary=dict(already_verified=complete,requested=pending,results=results,
            resource_or_stop_guard=stopped,initial_workers=a.workers,max_workers=a.max_workers,
            fully_complete=len(complete)+sum(r['verified_complete'] for r in results)==len(plan['views']))
        write_new(run/'summary.json',summary)
        if not summary['fully_complete']:raise SystemExit(2)


if __name__=='__main__':main()
