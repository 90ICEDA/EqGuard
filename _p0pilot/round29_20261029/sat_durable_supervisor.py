"""One authorized SAT completion pipeline launched through Win32_Process.Create.
No training. Immutable evidence and original extraction contracts are reused.
"""
import os,sys,signal,ctypes,json,datetime,time,subprocess,shutil,hashlib
from pathlib import Path
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];S=HERE.parent/'round27_20261027'
sys.path.insert(0,str(S));import k4_runtime as R
def stamp():return datetime.datetime.now().astimezone().isoformat()
def write(p,d):
    temp=p.with_suffix('.tmp');temp.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
    for attempt in range(40):
        try:os.replace(temp,p);return
        except PermissionError:
            if attempt==39:raise
            time.sleep(.05)
def run(out):
    signal.signal(signal.SIGINT,signal.SIG_IGN)
    if hasattr(signal,'SIGBREAK'):signal.signal(signal.SIGBREAK,signal.SIG_IGN)
    ctypes.windll.kernel32.SetConsoleCtrlHandler(None,True)
    sys.stdout=(out/'supervisor.out.log').open('a',encoding='utf-8',buffering=1);sys.stderr=(out/'supervisor.err.log').open('a',encoding='utf-8',buffering=1)
    commands=[]
    def state(phase,**kw):write(out/'state.json',dict(time=stamp(),phase=phase,pid=os.getpid(),commands=commands,**kw))
    def call(script,args=(),stage='stage'):
        n=len(commands);log=out/f'{n:02d}_{stage}.log';cmd=[sys.executable,'-B','-u','-X','utf8',str(HERE/'immune_runner.py'),str(script),*map(str,args)]
        with log.open('xb') as f:
            child=subprocess.Popen(cmd,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,creationflags=subprocess.DETACHED_PROCESS|subprocess.CREATE_NEW_PROCESS_GROUP,close_fds=True)
            entry=dict(stage=stage,pid=child.pid,command=cmd,log=str(log),started=stamp());commands.append(entry);state('running',stage=stage,child_pid=child.pid)
            while child.poll() is None:
                state('running',stage=stage,child_pid=child.pid,disk_free_gib=shutil.disk_usage(ROOT).free/2**30,memory_available_gib=R.memory_available_gib());time.sleep(20)
            entry.update(rc=child.returncode,ended=stamp());state('stage_returned',stage=stage)
        return child.returncode
    state('starting',launch='WMI service parent; no shared terminal stdin')
    with R.exclusive_lock(R.PANEL/'durable_pipeline.lock'):
        for attempt in range(3):
            while R.memory_available_gib()<1.5 or shutil.disk_usage(ROOT).free/2**30<8:
                state('waiting_resources',stage='training');time.sleep(30)
            rc=call(S/'run_all_k4_alltrain.py',['--run','--workers','1','--max-workers','2','--min-memory-gib','1.25','--min-free-gib','8'],'training_resume')
            if rc==0:break
            text=Path(commands[-1]['log']).read_text(encoding='utf-8',errors='replace')
            if attempt==2:raise RuntimeError(f'Training failed after bounded attempts: {rc}')
            state('retrying_preserving_evidence',previous_rc=rc);time.sleep(15)
        # Safe separate finisher copy: original contract/solver files stay byte-identical.
        original=(S/'finish_fullrun.py').read_text(encoding='utf-8')
        safe=original.replace("['--run','--workers','2','--max-workers','4']","['--run','--workers','1','--max-workers','2','--min-memory-gib','1.25','--min-free-gib','8']")
        # It resolves __file__.parent as the round27 script directory.
        safe=safe.replace("scripts=Path(__file__).parent",f"scripts=Path({str(S)!r})")
        safe=safe.replace('import k4_runtime as R',f"sys.path.insert(0, {str(S)!r})\nimport k4_runtime as R")
        safe_path=out/'finish_fullrun_safe_copy.py';safe_path.write_text(safe,encoding='utf-8')
        if call(safe_path,['--pid','0'],'training_final_audit')!=0:raise RuntimeError('Training completion audit failed; retained logs')
        q=R.fresh_dir(HERE/'queue_runs','run')
        R.write_new(q/'request.json',dict(time=stamp(),wait_for=[],panels={'validation':str(R.TABLES/'sat_k4_validation_round29'),'test':str(R.TABLES/'sat_k4_test_round29')},new_training_runs=0,launch='durable supervisor after successful training finisher'))
        write(out/'holdout_queue.json',dict(path=str(q)))
        if call(HERE/'holdout_k4.py',['--queue',q],'heldout_completion')!=0:raise RuntimeError('Heldout queue failed; inspect stage log')
        state('complete',new_training_runs=0)
if __name__=='__main__':
    out=Path(sys.argv[1])
    try:run(out)
    except BaseException as exc:
        write(out/'failure.json',dict(time=stamp(),error=repr(exc),pid=os.getpid()));raise
