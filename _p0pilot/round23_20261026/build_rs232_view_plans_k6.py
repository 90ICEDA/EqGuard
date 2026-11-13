"""Create one-view plans for all rs232 k=6 extraction workers."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
T = ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables/sat_k6_rs232_round23'
main = json.loads((T / 'plan.json').read_text(encoding='utf-8'))
for item in main['views']:
    plan = dict(main)
    plan.pop('plan_sha', None)
    plan['views'] = [item]
    plan['selection'] = 'single rs232 train view; k=6; no labels'
    plan['plan_sha'] = hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()
    out = T / 'views' / item['view']
    out.mkdir(parents=True, exist_ok=True)
    (out / 'plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
print('wrote', len(main['views']))
