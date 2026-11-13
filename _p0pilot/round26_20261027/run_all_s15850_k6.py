"""Run the four k=6 s15850 panel views sequentially (memory-safe)."""
import concurrent.futures as cf
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
T = ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables/sat_k6_s15850_round26'
PY = ROOT / 'ginvenv/Scripts/python.exe'
RUNNER = Path(__file__).with_name('run_one_s15850_k6.py')
LOGS = T / 'logs'
LOGS.mkdir(exist_ok=True)
views = [p.name for p in sorted((T / 'views').iterdir()) if p.is_dir()]
missing = [v for v in views if not (T / 'views' / v / 'coverage.json').exists()]
print(f'total={len(views)} missing={len(missing)}', flush=True)


def run_one(v):
    t = time.perf_counter()
    log = LOGS / (v + '.log')
    with log.open('w', encoding='utf-8') as f:
        p = subprocess.run([str(PY), '-X', 'utf8', str(RUNNER), v],
                           cwd=str(ROOT), stdout=f, stderr=subprocess.STDOUT,
                           timeout=3600)
    return dict(view=v, rc=p.returncode, seconds=round(time.perf_counter() - t, 3))


results = []
with cf.ThreadPoolExecutor(max_workers=10) as ex:
    futs = {ex.submit(run_one, v): v for v in missing}
    for i, fut in enumerate(cf.as_completed(futs), 1):
        v = futs[fut]
        try:
            r = fut.result()
        except Exception as e:
            r = dict(view=v, rc=-1, error=repr(e))
        results.append(r)
        print(f'[{i}/{len(missing)}] {json.dumps(r, ensure_ascii=False)}', flush=True)

summary = dict(total=len(views), launched=len(missing),
               ok=sum(x.get('rc') == 0 for x in results),
               failed=[x for x in results if x.get('rc') != 0], results=results)
(T / 'run_all_s15850_k6_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
