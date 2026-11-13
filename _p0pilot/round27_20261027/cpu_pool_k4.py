"""Memory guarded CPU scheduling over the existing frozen extraction plan.

Only scheduling changes. Each child takes the original per-view OS lock, then
checks all evidence before running the original extractor. No file is removed.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import time
import psutil
import k4_runtime as R


def active_views():
    views=set()
    for p in psutil.process_iter(['cmdline']):
        try:
            cmd=p.info['cmdline'] or []
            for i,arg in enumerate(cmd):
                if Path(arg).name=='run_one_k4_alltrain.py' and i+1<len(cmd):views.add(cmd[i+1])
                if Path(arg).name=='cpu_pool_k4.py' and '--view' in cmd:views.add(cmd[cmd.index('--view')+1])
        except (psutil.Error,ValueError):pass
    return views


def worker(view):
    if view not in {x['view'] for x in R.read_plan(R.PANEL/'plan.json')['views']}:
        raise ValueError('Outside frozen training plan')
    folder=R.PANEL/'views'/view
    # Refuse contention rather than executing any duplicate SAT commands.
    try:
        lock=R.exclusive_lock(folder/'worker.lock');lock.__enter__()
    except RuntimeError:
        print('VIEW_BUSY: no extraction performed',flush=True);return 75
    try:
        if R.validate_complete(folder)[0]:
            print('Verified complete; reused without solving',flush=True);return 0
        os.environ['SAT_T']=str(folder)
        runpy.run_path(str(Path(__file__).with_name('extract_k4_alltrain.py')),run_name='__main__')
        return 0
    finally:lock.__exit__(None,None,None)


def main(a):
    if a.view:return worker(a.view)
    if not a.coordinator_pid:raise ValueError('Primary coordinator required')
    primary=psutil.Process(a.coordinator_pid);primary_birth=primary.create_time()
    def primary_alive():
        try:return primary.is_running() and primary.create_time()==primary_birth
        except psutil.Error:return False
    with R.exclusive_lock(R.PANEL/'cpu_pool.lock'):
        out=R.fresh_dir(Path(__file__).parent/'cpu_pool_runs','run')
        print('RUN_DIR='+str(out),flush=True)
        plan=R.read_plan(R.PANEL/'plan.json');views=[x['view'] for x in plan['views']]
        # The older bounded acceleration worker owns the last four plan views.
        reserved=set(views[-4:]);inflight={};finished=set();blocked=set();results=[]
        frozen={n:R.sha(Path(__file__).with_name(n)) for n in ['extract_k4_alltrain.py','k4_runtime.py','run_one_k4_alltrain.py']}
        R.write_new(out/'control.json',dict(total_workers=6,max_total_workers=8))
        R.write_new(out/'started.json',dict(time=datetime.datetime.now().astimezone().isoformat(),primary_pid=a.coordinator_pid,primary_birth=primary_birth,source_sha=frozen,plan_sha=R.sha(R.PANEL/'plan.json'),max_workers=8,launch_min_windows_gib=1.75,stop_min_windows_gib=1.25,minimum_free_disk_gib=8))
        started=time.monotonic();last_status=0;last_dispatch=0;closing=False;seq=0
        while True:
            for view,job in list(inflight.items()):
                rc=job['process'].poll()
                if rc is None:continue
                job['file'].close()
                if rc==75:ok=False;detail='Busy; no SAT performed';blocked.add(view)
                else:ok,detail=R.validate_complete(R.PANEL/'views'/view)
                row=dict(view=view,rc=rc,verified_complete=ok,detail=detail,seconds=time.monotonic()-job['started'],guard_stopped=job['stop'].exists())
                results.append(row);R.write_new(out/f'result_{len(results):04d}.json',row);print(json.dumps(row),flush=True)
                (finished if ok else blocked).add(view);del inflight[view]
            memory=R.memory_available_gib();free=shutil.disk_usage(R.ROOT).free/2**30
            if not primary_alive() or (out/'STOP').exists():closing=True
            if any(R.sha(Path(__file__).with_name(n))!=h for n,h in frozen.items()):closing=True
            # Drain one added worker at a time, preserving its current batch.
            if memory<1.25 or free<8 or closing:
                jobs=[j for j in inflight.values() if not j['stop'].exists()]
                if jobs:
                    if closing or free<8:
                        for j in jobs:j['stop'].touch(exist_ok=True)
                    else:jobs[-1]['stop'].touch(exist_ok=True)
            external=active_views();total=len(external)
            control=json.loads((out/'control.json').read_text())
            target=max(1,min(8,int(control['total_workers'])))
            pending=[v for v in views if v not in finished and not (R.PANEL/'views'/v/'coverage.json').exists()]
            # Stop taking work well before the primary reaches the tail. The
            # per-view OS lock remains the authoritative collision protection.
            candidates=[v for v in reversed(pending[24:]) if v not in reserved and v not in external and v not in inflight and v not in blocked]
            cpu=psutil.cpu_percent(interval=None)
            if not closing and total<target and memory>=1.75 and free>=10 and cpu<90 and candidates and time.monotonic()-last_dispatch>=15:
                view=candidates[0];seq+=1;stop=out/f'STOP_{seq:04d}';log=out/(view+'.log')
                env=os.environ.copy();env.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1',SAT_K4_STOP_FILE=str(stop))
                f=log.open('x',encoding='utf-8')
                proc=subprocess.Popen([sys.executable,'-B','-X','utf8',str(Path(__file__)),'--view',view],cwd=R.ROOT,env=env,stdout=f,stderr=subprocess.STDOUT)
                inflight[view]=dict(process=proc,file=f,started=time.monotonic(),stop=stop)
                R.write_new(out/f'worker_{seq:04d}.json',dict(pid=proc.pid,view=view,stop=str(stop),log=str(log)))
                last_dispatch=time.monotonic();print(json.dumps(dict(dispatch=view,pid=proc.pid,total_before=total,memory_gib=memory)),flush=True)
            if time.monotonic()-last_status>=30:
                status=dict(time=datetime.datetime.now().astimezone().isoformat(),target_total=target,active_views=sorted(external),windows_available_gib=memory,free_disk_gib=free,cpu_percent=cpu,successful_pool_views=len(finished),pool_workers=len(inflight),closing=closing)
                # New telemetry files retain all earlier observations.
                R.write_new(out/f'telemetry_{int(time.monotonic()-started):06d}.json',status);print(json.dumps(status),flush=True);last_status=time.monotonic()
            if not inflight and (closing or not candidates):break
            time.sleep(5)
        R.write_new(out/'summary.json',dict(results=results,new_training_runs=0,source_sha=frozen))
    return 0


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--coordinator-pid',type=int);p.add_argument('--view')
    raise SystemExit(main(p.parse_args()))
