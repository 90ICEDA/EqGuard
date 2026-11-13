"""One bounded extra worker using unchanged extraction and per-view locks.

No independent feature store, new search or altered solver semantics. The normal
coordinator remains responsible for final validation, merging and supervision.
"""
import argparse
import ctypes
import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import k4_runtime as R


def alive(pid):
    k=ctypes.windll.kernel32
    k.OpenProcess.restype=ctypes.c_void_p
    k.GetExitCodeProcess.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_ulong)]
    k.CloseHandle.argtypes=[ctypes.c_void_p]
    h=k.OpenProcess(0x1000,False,pid)
    if not h:return False
    try:
        code=ctypes.c_ulong()
        return bool(k.GetExitCodeProcess(h,ctypes.byref(code))) and code.value==259
    finally:k.CloseHandle(h)


def main():
    a=argparse.ArgumentParser();a.add_argument('--coordinator-pid',type=int,required=True)
    a.add_argument('--limit',type=int,default=4);args=a.parse_args()
    if not 1<=args.limit<=4:raise ValueError('Bounded tail worker: at most four views')
    with R.exclusive_lock(R.PANEL/'acceleration.lock'):
        out=R.fresh_dir(Path(__file__).parent/'acceleration_runs','run')
        env=os.environ.copy();env.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1',SAT_K4_STOP_FILE=str(out/'STOP'))
        plan=R.read_plan(R.PANEL/'plan.json');views=[v['view'] for v in plan['views']]
        immutable=['extract_k4_alltrain.py','run_one_k4_alltrain.py','k4_runtime.py']
        initial={n:R.sha(Path(__file__).with_name(n)) for n in immutable}
        R.write_new(out/'started.json',dict(time=datetime.datetime.now().astimezone().isoformat(),coordinator_pid=args.coordinator_pid,extra_workers=1,max_views=args.limit,extraction_sha=initial,plan_sha=R.sha(R.PANEL/'plan.json')))
        print('RUN_DIR='+str(out),flush=True)
        results=[]
        for _ in range(args.limit):
            if not alive(args.coordinator_pid) or (out/'STOP').exists():break
            # The primary worker traverses from the front. Keep a generous gap;
            # the existing worker lock is the final exclusion mechanism.
            pending=[v for v in views if not (R.PANEL/'views'/v/'coverage.json').exists()]
            if len(pending)<=24:break
            if R.memory_available_gib()<2 or shutil.disk_usage(R.ROOT).free<10*2**30:break
            if any(R.sha(Path(__file__).with_name(n))!=h for n,h in initial.items()):
                raise RuntimeError('Extractor changed; tail acceleration stopped')
            view=pending[-1];folder=R.PANEL/'views'/view
            if R.validate_complete(folder)[0]:continue
            # Never reclaim or overwrite an existing attempt.
            log=out/(view+'.log');started=time.perf_counter()
            print(json.dumps(dict(dispatch=view,available_gib=R.memory_available_gib())),flush=True)
            with log.open('x',encoding='utf-8') as f:
                proc=subprocess.Popen([sys.executable,'-B','-X','utf8',str(Path(__file__).with_name('run_one_k4_alltrain.py')),view],cwd=R.ROOT,env=env,stdout=f,stderr=subprocess.STDOUT)
                R.write_new(out/f'worker_{len(results):02d}.json',dict(pid=proc.pid,view=view,log=str(log)))
                while proc.poll() is None:
                    if (R.memory_available_gib()<1.25 or shutil.disk_usage(R.ROOT).free<8*2**30 or not alive(args.coordinator_pid)):
                        (out/'STOP').touch(exist_ok=True)
                    time.sleep(10)
            ok,detail=R.validate_complete(folder)
            result=dict(view=view,rc=proc.returncode,verified_complete=ok,detail=detail,seconds=time.perf_counter()-started)
            results.append(result);R.write_new(out/f'result_{len(results):02d}.json',result);print(json.dumps(result),flush=True)
            if not ok:break
        R.write_new(out/'summary.json',dict(results=results,extra_workers=1,stopped=(out/'STOP').exists(),new_training_runs=0))


if __name__=='__main__':main()
