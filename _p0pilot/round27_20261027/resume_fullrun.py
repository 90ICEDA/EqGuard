"""Resume authorized extraction using unchanged solver and coordinator scripts."""
import datetime,json,os,subprocess,time
from pathlib import Path
import psutil
import k4_runtime as R

def main():
    for p in psutil.process_iter(['pid','name','cmdline']):
        cmd=' '.join(p.info['cmdline'] or [])
        if 'python' in (p.info['name'] or '').lower() and any(x in cmd for x in ['run_all_k4_alltrain.py','run_one_k4_alltrain.py','finish_fullrun.py','finish_after_cpu_pool.py']):
            raise RuntimeError(f'Existing extraction/supervisor {p.pid}; refusing duplicate launch')
    import shutil
    if shutil.disk_usage(R.ROOT).free<8*2**30 or R.memory_available_gib()<1.25:
        raise RuntimeError('Insufficient disk/memory; no process launched')
    scripts=Path(__file__).resolve().parent;out=R.fresh_dir(scripts/'resume_runs','run')
    frozen={p.name:R.sha(p) for p in [scripts/n for n in ['run_all_k4_alltrain.py','run_one_k4_alltrain.py','extract_k4_alltrain.py','k4_runtime.py']]}
    evidence=[]
    for v,last in [('s35932t200__ctlmatche_d1_s42__ys_aig','17088'),('s35932t200__ctlmatchf_d1_s42__ys_aig','09088')]:
        for ordinal in ['00000',last]:
            q=R.PANEL/'views'/v/'queries'/v/ordinal
            files=([q/'results.json'] if (q/'results.json').exists() else [])+sorted(q.glob('attempt_*/results.json'))
            for f in files:evidence.append(dict(path=str(f.relative_to(R.ROOT)),sha256=R.sha(f)))
    env=os.environ.copy();env.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1',PYTHONUNBUFFERED='1')
    python=R.ROOT/'ginvenv/Scripts/python.exe'
    args=[str(python),'-B','-X','utf8',str(scripts/'run_all_k4_alltrain.py'),'--run','--workers','1','--max-workers','2','--min-memory-gib','1.25','--min-free-gib','8']
    def spawn(cmd,name):
        with (out/(name+'.out.log')).open('xb') as stdout,(out/(name+'.err.log')).open('xb') as stderr:
            base=subprocess.DETACHED_PROCESS|subprocess.CREATE_NEW_PROCESS_GROUP
            try:
                process=subprocess.Popen(cmd,cwd=R.ROOT,env=env,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,creationflags=base|subprocess.CREATE_BREAKAWAY_FROM_JOB)
                mode='detached and breakaway from parent job'
            except OSError as e:
                if e.winerror!=5:raise
                process=subprocess.Popen(cmd,cwd=R.ROOT,env=env,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,creationflags=base)
                mode='detached; parent job refused breakaway'
        return process,mode
    primary,mode=spawn(args,'primary')
    fincmd=[str(python),'-B','-X','utf8',str(scripts/'finish_fullrun.py'),'--pid',str(primary.pid)]
    finisher,finmode=spawn(fincmd,'finisher')
    report=dict(time=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),primary_pid=primary.pid,finisher_pid=finisher.pid,primary_command=args,finisher_command=fincmd,primary_detachment=mode,finisher_detachment=finmode,
        plan_sha256=R.sha(R.PANEL/'plan.json'),extraction_scripts=frozen,old_success_samples=evidence,initial_workers=1,max_workers=2,min_memory_gib=1.25,min_disk_gib=8,new_training_runs=0,
        note='Original coordinator validates completed views before scheduling. Successful bound batches replay; interrupted unsaved batches use a new attempt. Old files and failure logs retained. Startup one worker; control may rise to two under unchanged resource gates.')
    R.write_new(out/'launch.json',report);print(json.dumps(dict(out=str(out),**report),ensure_ascii=False),flush=True)

if __name__=='__main__':main()
