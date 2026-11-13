"""Mark the k=4 control plan correctly (the extraction itself used max_inputs=4)."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
T = ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables/sat_k4_rs232_round23'


def sign(plan):
    plan.pop('plan_sha', None)
    plan['plan_sha'] = hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()
    return plan['plan_sha']


main = json.loads((T / 'plan.json').read_text(encoding='utf-8'))
main['cut_rule']['max_inputs'] = 4
main['selection'] = 'all 113 rs232 train views; k=4 control; no labels'
sign(main)
(T / 'plan.json').write_text(json.dumps(main, ensure_ascii=False, indent=2), encoding='utf-8')
for p in (T / 'views').glob('*/plan.json'):
    plan = json.loads(p.read_text(encoding='utf-8'))
    plan['cut_rule']['max_inputs'] = 4
    plan['selection'] = 'single rs232 train view; k=4 control; no labels'
    sign(plan)
    p.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
print('updated', len(list((T / 'views').glob('*/plan.json'))), 'view plans')
