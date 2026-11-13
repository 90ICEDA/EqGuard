"""Create one-view plans for parallel s15850 injection extraction."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
T = ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables/sat_s15850_round22'
main = json.loads((T / 'plan.json').read_text(encoding='utf-8'))


def main_plan():
    views = [x for x in main['views'] if '__inj' in x['view']]
    for item in views:
        plan = dict(main)
        plan.pop('plan_sha', None)
        plan['views'] = [item]
        plan['selection'] = 'single s15850 injection view; no labels'
        plan['plan_sha'] = hashlib.sha256(
            json.dumps(plan, sort_keys=True).encode()).hexdigest()
        out = T / 'views' / item['view']
        out.mkdir(parents=True, exist_ok=True)
        (out / 'plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
        print(item['view'], item['family'], item['split'], out)


if __name__ == '__main__':
    main_plan()
