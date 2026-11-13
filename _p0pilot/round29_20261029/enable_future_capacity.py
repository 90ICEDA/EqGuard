"""One-shot per-run capacity setup; existing resource gates remain authoritative.

Bound to this completion queue. Each new control is touched at most once, so
later manual reductions are respected. Never starts or interrupts a solver.
"""
import argparse,json,time,datetime
from pathlib import Path
import psutil

p=argparse.ArgumentParser();p.add_argument('--queue-pid',type=int,required=True);p.add_argument('--birth',type=float,required=True);p.add_argument('--queue-dir',type=Path,required=True);p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
tables=a.root/'10.15/06_统一评测协议/N4_三向泛化/tables'
panels=[tables/n for n in ['sat_k4_alltrain_round27','sat_k4_validation_round29','sat_k4_test_round29']]
seen={str(p) for panel in panels for p in (panel/'runs').glob('run_*/control.json')}
while True:
    try:
        process=psutil.Process(a.queue_pid)
        if abs(process.create_time()-a.birth)>.01:break
    except psutil.NoSuchProcess:break
    try:
        if json.loads((a.queue_dir/'state.json').read_text())['phase'] in ('complete','failed'):break
    except (OSError,ValueError,KeyError):pass
    for panel in panels:
        for p in (panel/'runs').glob('run_*/control.json'):
            if str(p) in seen or (p.parent/'summary.json').exists():continue
            try:
                old=json.loads(p.read_text());p.write_text(json.dumps(dict(workers=2)),encoding='utf-8');seen.add(str(p))
                with a.out.open('a',encoding='utf-8') as f:f.write(json.dumps(dict(time=datetime.datetime.now().astimezone().isoformat(),control=str(p),old=old,new=dict(workers=2),resource_gates_unchanged=True),ensure_ascii=False)+'\n')
            except (OSError,ValueError):pass
    time.sleep(15)
