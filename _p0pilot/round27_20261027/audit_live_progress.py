"""Read-only live progress, repeated successful attempts and recent throughput."""
import collections
import datetime
import json
from pathlib import Path
import time
import k4_runtime as R

now=time.time();begin=datetime.datetime(2026,10,28,13,53,58).timestamp()
counts=dict(batch_folders=0,saved_results=0,new_executions=0,new_solver_nonzero=0)
duplicates=[];nonzero=[];recent=collections.Counter();recent_queries=collections.Counter()
for vf in (R.PANEL/'views').iterdir():
    qr=vf/'queries'/vf.name
    if not qr.exists():continue
    for batch in qr.iterdir():
        if not batch.is_dir():continue
        counts['batch_folders']+=1
        candidates=([batch/'results.json'] if (batch/'results.json').exists() else [])+list(batch.glob('attempt_*/results.json'))
        counts['saved_results']+=len(candidates)
        # Multiple saved successes require inspection, not merely multiple
        # directories: failed and interrupted attempts are intentionally kept.
        if len(candidates)>1:
            binding=collections.defaultdict(list)
            for p in candidates:
                d=json.loads(p.read_text(encoding='utf-8'))
                if all(q['status'] in ('proved','refuted') for q in d['queries']):
                    key=(d['source_sha'],d['raw_sha'],d['model_sha'])
                    binding[key].append(p)
            for files in binding.values():
                if len(files)>1 and any(p.stat().st_mtime>=begin for p in files):
                    duplicates.append([str(p.relative_to(R.ROOT)) for p in files])
        for p in candidates:
            age=now-p.stat().st_mtime
            if 0<=age<1200:
                d=json.loads(p.read_text(encoding='utf-8'))
                if all(q['status'] in ('proved','refuted') for q in d['queries']):
                    bucket='last_10min' if age<600 else 'previous_10min'
                    recent[bucket]+=len(d['tables']);recent_queries[bucket]+=len(d['queries'])
        executions=([batch/'run.execution.json'] if (batch/'run.execution.json').exists() else [])+list(batch.glob('attempt_*/run.execution.json'))
        for p in executions:
            if p.stat().st_mtime<begin:continue
            d=json.loads(p.read_text(encoding='utf-8'));counts['new_executions']+=1
            if d['rc'] or d.get('timeout'):
                counts['new_solver_nonzero']+=1;nonzero.append(dict(path=str(p.relative_to(R.ROOT)),rc=d['rc'],timeout=d.get('timeout')))
stats={k:dict(targets=recent[k],queries=recent_queries[k],targets_per_second=recent[k]/600) for k in ['previous_10min','last_10min']}
report=dict(time=datetime.datetime.now().astimezone().isoformat(),counts=counts,
    repeated_successful_batches_since_restart=duplicates,nonzero_solver_executions=nonzero,
    recent_throughput=stats,note='Counts committed unique target/cut tasks, not all graph nodes. Different views and cuts prevent treating throughput ratios as a matched benchmark. Reuse/replay does not launch SAT; duplicate detection groups the same source/raw/model per batch.',new_solver_calls=0)
out=R.fresh_dir(Path(__file__).parent/'live_progress_reviews','review');R.write_new(out/'report.json',report)
print(json.dumps(dict(report=str(out),**report),ensure_ascii=False))
