import json
from pathlib import Path

H = Path(r'_p0pilot/p2b_main_20261031')
for s in (42, 1, 2):
    d = json.loads((H / f'seed{s}_AB_oldmask.json').read_text(encoding='utf-8'))
    for arm in ('A', 'B'):
        r = d[arm]
        v = r['val']['trusted']['ap']; t = r['test']['trusted']['ap']
        print(f'seed{s} {arm}: valAP={v:.4f} testAP={t:.4f} gap={v - t:+.4f} epoch={r["selected"]["epoch"]}')
