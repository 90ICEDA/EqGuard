"""Run the four k=8 s15850 panel views sequentially (memory-safe)."""
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
T = ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables/sat_k8_s15850_round25'
PY = ROOT / 'ginvenv/Scripts/python.exe'
RUNNER = Path(__file__).with_name('run_one_s15850_k8.py')
LOGS = T / 'logs'
LOGS.mkdir(exist_ok=True)
views = [p.name for p in sorted((T / 'views').iterdir()) if p.is_dir()]
missing = [v for v in views if not (T / 'views' / v / 'coverage.json').exists()]
print(f'total={len(views)} missing={len(missing)}', flush=True)

results = []
for i, v in enumerate(missing, 1):
    t = time.perf_counter()
    log = LOGS / (v + '.log')
    with log.open('w', encoding='utf-8') as f:
        p = subprocess.run([str(PY), '-X', 'utf8', str(RUNNER), v],
                           cwd=str(ROOT), stdout=f, stderr=subprocess.STDOUT,
                           timeout=3600)
    r = dict(view=v, rc=p.returncode, seconds=round(time.perf_counter() - t, 3))
    results.append(r)
    print(f'[{i}/{len(missing)}] {json.dumps(r, ensure_ascii=False)}', flush=True)

summary = dict(total=len(views), launched=len(missing),
               ok=sum(x.get('rc') == 0 for x in results),
               failed=[x for x in results if x.get('rc') != 0], results=results)
(T / 'run_all_s15850_k8_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
