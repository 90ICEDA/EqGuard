"""Observational wall-time throughput; no repeated solver executions."""
import datetime
import json
from pathlib import Path
import k4_runtime as R

start=datetime.datetime(2026,10,28,15,36,32).timestamp()
windows=[('before_4min',start-240,start),('after_4min',start,start+240)]
stats={name:dict(batches=0,queries=0,unique_targets=0) for name,_,_ in windows}
for p in (R.PANEL/'views').glob('*/queries/*/*/attempt_*/results.json'):
    mtime=p.stat().st_mtime
    for name,lo,hi in windows:
        if lo<=mtime<hi:
            d=json.loads(p.read_text(encoding='utf-8'))
            if not all(q['status'] in ('proved','refuted') for q in d['queries']):continue
            stats[name]['batches']+=1;stats[name]['queries']+=len(d['queries']);stats[name]['unique_targets']+=len(d['tables'])
for row in stats.values():
    row['queries_per_second']=row['queries']/240;row['targets_per_second']=row['unique_targets']/240
report=dict(time=datetime.datetime.now().astimezone().isoformat(),windows=stats,
    note='Observational batch commit throughput across changing views/cuts. Different SAT difficulty, batch sizes and commit-boundary effects prevent interpreting this ratio as a matched speedup benchmark. Partial batches are excluded.',new_solver_calls=0)
out=R.fresh_dir(Path(__file__).parent/'cpu_pool_runs/run_00000/throughput','check')
R.write_new(out/'report.json',report);print(json.dumps(report,ensure_ascii=False))
