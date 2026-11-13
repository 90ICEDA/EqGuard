"""Read current extraction progress across original and resumed run directories."""
import collections,datetime,json,shutil
from pathlib import Path
import psutil
import k4_runtime as R

def main():
    expected=set(json.loads((R.ROOT/'generate_trans/folds/hosts_bt31/views.json').read_text())['train_views'])
    panels=[R.TABLES/'sat_k4_rs232_round23',R.TABLES/'sat_s15850_round22',R.PANEL,R.PANEL/'train_controls_complement']
    done={}
    for panel in panels:
        for item in R.read_plan(panel/'plan.json')['views']:
            v=item['view'];assert v in expected
            p=panel/'views'/v/'coverage.json'
            if p.exists():
                assert v not in done
                c=json.loads(p.read_text());done[v]=dict(nodes=sum(s['nodes'] for s in c['splits'].values()),covered=sum(s['covered'] for s in c['splits'].values()))
    processes=[];active=set()
    for p in psutil.process_iter(['pid','name','cmdline']):
        cmd=' '.join(p.info['cmdline'] or [])
        if 'python' in (p.info['name'] or '').lower() and any(s in cmd for s in ['run_all_k4_alltrain.py','run_one_k4_alltrain.py','finish_fullrun.py','finish_after_cpu_pool.py','merge_full_training_k4.py','holdout_k4.py --queue']):
            processes.append(dict(pid=p.pid,command=cmd))
            if 'run_one_k4_alltrain.py' in cmd:active.add(p.info['cmdline'][-1])
    runs=[];logs=[]
    for run in sorted((R.PANEL/'runs').glob('run_*')):
        results=[json.loads(p.read_text()) for p in sorted(run.glob('result_*.json'))]
        runs.append(dict(run=str(run.relative_to(R.ROOT)),returned=len(results),failed=[r for r in results if not r.get('verified_complete')],summary_exists=(run/'summary.json').exists()))
        for v in sorted(active):
            p=run/(v+'.log')
            if p.exists():logs.append(dict(view=v,run=run.name,modified=p.stat().st_mtime,tail=p.read_text(encoding='utf-8',errors='replace').splitlines()[-2:]))
    holdouts={}
    for label in ['validation','test']:
        panel=R.TABLES/f'sat_k4_{label}_round29'
        if not (panel/'plan.json').exists():continue
        plan=R.read_plan(panel/'plan.json');completed=[]
        for item in plan['views']:
            path=panel/'views'/item['view']/'coverage.json'
            if path.exists():completed.append(json.loads(path.read_text()))
        holdouts[label]=dict(planned_views=len(plan['views']),planned_nodes=sum(i['nodes'] for i in plan['views']),completed_views=len(completed),completed_nodes=sum(d['nodes'] for c in completed for d in c['splits'].values()),covered_nodes=sum(d['covered'] for c in completed for d in c['splits'].values()))
        for run in sorted((panel/'runs').glob('run_*')):
            for v in sorted(active):
                p=run/(v+'.log')
                if p.exists():logs.append(dict(view=v,run=str(run.relative_to(R.ROOT)),modified=p.stat().st_mtime,tail=p.read_text(encoding='utf-8',errors='replace').splitlines()[-2:]))
    queue_states=[]
    for p in sorted((R.ROOT/'_p0pilot/round29_20261029/queue_runs').glob('run_*/state.json')):
        queue_states.append(dict(path=str(p.relative_to(R.ROOT)),**json.loads(p.read_text())))
    latest_logs={}
    for l in sorted(logs,key=lambda l:l['modified']):latest_logs[l['view']]=l
    s=dict(time=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),completed_views=len(done),planned_views=len(expected),completed_nodes=sum(s['nodes'] for s in done.values()),planned_nodes=1250510,covered_nodes=sum(s['covered'] for s in done.values()),pending_views=sorted(expected-set(done)),hosts={h:dict(completed=sum(v.startswith(h+'__') for v in done),planned=sum(v.startswith(h+'__') for v in expected)) for h in ['rs232t1000','s15850t100','s35932t200']},active=list(latest_logs.values()),processes=processes,runs=runs,disk_free_gib=shutil.disk_usage(R.ROOT).free/2**30,memory_available_gib=R.memory_available_gib(),new_sat_queries=0,note='Completed coverage markers counted here; strict content validation is performed by the extraction coordinator and final audits.')
    s.update(holdout_panels=holdouts,holdout_queue_states=queue_states,all_splits_planned_views=len(expected)+sum(v['planned_views'] for v in holdouts.values()),all_splits_completed_views=len(done)+sum(v['completed_views'] for v in holdouts.values()))
    out=R.fresh_dir(Path(__file__).parent/'status_reviews','review');R.write_new(out/'status.json',s)
    print(json.dumps(dict(report=str(out),**s),ensure_ascii=False))

if __name__=='__main__':main()
