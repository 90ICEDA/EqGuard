"""Hidden durable sequential queue: P2-B then existing SAT completion queue."""
import os,sys,json,datetime,subprocess,signal,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];H=Path(__file__).resolve().parent;R29=ROOT/'_p0pilot/round29_20261029'
def stamp():return datetime.datetime.now().astimezone().isoformat()
def write(p,x):
    tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
    for i in range(40):
        try:os.replace(tmp,p);return
        except PermissionError:
            if i==39:raise
            time.sleep(.05)
def main():
    out=Path(sys.argv[1]);sys.stdout=(out/'supervisor.out.log').open('a',encoding='utf-8',buffering=1);sys.stderr=(out/'supervisor.err.log').open('a',encoding='utf-8',buffering=1)
    sys.path.insert(0,str(ROOT/'_p0pilot/round27_20261027'));import k4_runtime as R
    stages=[('P2_B_three_seeds',ROOT/'ginvenv_gpu/Scripts/python.exe',H/'run_p2b.py',[]),('SAT_validation_test_resume',ROOT/'ginvenv/Scripts/python.exe',R29/'holdout_k4.py',['--queue',str(out/'sat_queue')])]
    with R.exclusive_lock(H/'pipeline.lock'):
        results=[]
        for index,(stage,python,script,args) in enumerate(stages):
            log=out/f'{index:02d}_{stage}.log';command=[str(python),'-B','-u','-X','utf8',str(R29/'immune_runner.py'),str(script),*args]
            with log.open('ab') as f:
                p=subprocess.Popen(command,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,creationflags=subprocess.DETACHED_PROCESS|subprocess.CREATE_NEW_PROCESS_GROUP,close_fds=True)
                write(out/'state.json',dict(time=stamp(),phase='running',stage=stage,child_pid=p.pid,command=command,results=results))
                rc=p.wait()
            results.append(dict(stage=stage,rc=rc,log=str(log.relative_to(ROOT)),ended=stamp()))
            write(out/'state.json',dict(time=stamp(),phase='stage_returned',results=results))
            # SAT completion is independently authorized and still runs if B fails; logs are retained.
        write(out/'state.json',dict(time=stamp(),phase='complete' if all(x['rc']==0 for x in results) else 'finished_with_failures',results=results))
if __name__=='__main__':
    try:main()
    except BaseException as e:
        write(Path(sys.argv[1])/'failure.json',dict(time=stamp(),error=repr(e)));raise
