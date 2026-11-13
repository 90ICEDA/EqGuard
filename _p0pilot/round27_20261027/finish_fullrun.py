"""One-shot completion supervisor for the explicitly requested full extraction.

Wait for this run, retry pending views at most twice, merge only complete data,
then audit and append the completion status. No training, deletion or moving.
"""
import argparse
import ctypes
import datetime
import json
import os
import subprocess
import sys
from pathlib import Path
import k4_runtime as R


def wait_for_process(pid):
    kernel=ctypes.windll.kernel32
    kernel.OpenProcess.argtypes=[ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong]
    kernel.OpenProcess.restype=ctypes.c_void_p
    kernel.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_ulong]
    kernel.CloseHandle.argtypes=[ctypes.c_void_p]
    handle=kernel.OpenProcess(0x100000|0x1000,0,pid)
    if not handle:return
    try:
        while kernel.WaitForSingleObject(handle,30000)==258:pass
    finally:kernel.CloseHandle(handle)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--pid',type=int,required=True)
    p.add_argument('--secondary-pid',type=int)
    a=p.parse_args();scripts=Path(__file__).parent
    out=R.fresh_dir(scripts/'completion_reports','completion')
    R.write_new(out/'started.json',dict(pid=a.pid,time=datetime.datetime.now().astimezone().isoformat()))
    print('Waiting for',a.pid,'report',out,flush=True);wait_for_process(a.pid)
    if a.secondary_pid:wait_for_process(a.secondary_pid)
    commands=[]
    def call(name,args=(),panel=None):
        log=out/(f'{len(commands):02d}_'+name+'.log')
        with log.open('x',encoding='utf-8') as f:
            env=os.environ.copy()
            if panel is not None:env['SAT_K4_PANEL']=str(panel)
            rc=subprocess.call([sys.executable,'-B','-X','utf8',str(scripts/name),*args],
                               cwd=R.ROOT,env=env,stdout=f,stderr=subprocess.STDOUT)
        commands.append(dict(script=name,args=list(args),panel=str(panel),rc=rc,log=str(log.relative_to(R.ROOT))))
        return rc
    attempts=0
    while True:
        pending=[v['view'] for v in R.read_plan(R.PANEL/'plan.json')['views']
                 if not R.validate_complete(R.PANEL/'views'/v['view'])[0]]
        if not pending or attempts>=2:break
        attempts+=1
        print('Bounded retry',attempts,'pending',len(pending),flush=True)
        call('run_all_k4_alltrain.py',['--run','--workers','2','--max-workers','4'])
    complete=not pending
    complement=R.PANEL/'train_controls_complement'
    if complete:
        for retry in range(3):
            extra_pending=[v['view'] for v in R.read_plan(complement/'plan.json')['views']
                           if not R.validate_complete(complement/'views'/v['view'])[0]]
            if not extra_pending:break
            call('run_all_k4_alltrain.py',['--run','--workers','2','--max-workers','4'],complement)
        extra_pending=[v['view'] for v in R.read_plan(complement/'plan.json')['views']
                       if not R.validate_complete(complement/'views'/v['view'])[0]]
        pending+=extra_pending;complete=not pending
        if complete and call('merge_k4_alltrain.py',['--write'],complement)!=0:complete=False
    if complete:
        for name,args in [('merge_k4_alltrain.py',['--write']),('audit_existing_k4.py',[]),
                          ('audit_model_bindings.py',[]),('merge_full_training_k4.py',['--write'])]:
            if call(name,args)!=0:
                complete=False;break
    status=dict(time=datetime.datetime.now().astimezone().isoformat(),complete=complete,
                pending=pending,retries=attempts,commands=commands,new_training_runs=0)
    R.write_new(out/'status.json',status)
    label='全量提取、合并及审计完成' if complete else '未完成，需检查本次 status.json 与日志'
    entry=f'\n\n### SATk4 全量后台收尾状态（{status["time"]}）\n\n{label}。待完成视图 {len(pending)}；自动重试 {attempts} 次；未启动训练。收尾报告：`{out.relative_to(R.ROOT)}`。\n'
    for name in ('SAT作用证明.md','SAT工作总结.md'):
        with (R.ROOT/'10.15/00_说明'/name).open('a',encoding='utf-8') as f:f.write(entry)
    print(json.dumps(status,ensure_ascii=False),flush=True)
    if not complete:raise SystemExit(2)


if __name__=='__main__':main()
