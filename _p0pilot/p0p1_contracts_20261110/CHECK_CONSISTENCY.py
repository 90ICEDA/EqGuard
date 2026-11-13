"""P3 consistency check across CEC/PANEL/GT and forbidden strings."""
import json
from pathlib import Path
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
H = R / '_p0pilot/heldout_composition_20261110'; D = R / '_p0pilot/p0p1_contracts_20261110'
issues = []
a = json.loads((H / 'CEC_STAGE3A.json').read_text(encoding='utf-8'))
b = json.loads((H / 'CEC_STAGE3B.json').read_text(encoding='utf-8'))
rows = a['rows'] + b['rows']
if len(rows) != 40: issues.append(f'CEC rows {len(rows)}')
if sum(1 for r in rows if r['status'] == 'PASS') != 40: issues.append('CEC PASS != 40')
if any((r.get('unproven') or 0) != 0 for r in rows): issues.append('CEC unproven != 0')
p = json.loads((H / 'PANEL_STATUS.json').read_text(encoding='utf-8'))
if p.get('total_combos') != 20: issues.append('panel combos')
if p.get('syntheses') != 40: issues.append('panel syntheses')
if str(p.get('cec')) != '40/40 PASS': issues.append('panel cec')
g = json.loads((H / 'GT_AVAILABILITY_V5.json').read_text(encoding='utf-8'))
if len(g.get('host_status', [])) != 5: issues.append('GT host rows')
if not any(x['host'] == 's38417t100' and x['status'] == 'missing' for x in g['host_status']): issues.append('s38417 missing')
if g.get('panel_gt') != 'not_built': issues.append('panel GT built flag')
bad = []
for base in (H, D):
    for f in list(base.glob('*.json')) + list(base.glob('*.md')) + list(base.glob('*.csv')):
        if f.name == 'CHECK_CONSISTENCY.json': continue
        t = f.read_text(encoding='utf-8', errors='ignore')
        for s in ('30-combo', 'cec_plan not run', 'PASS(bypass-gate)'):
            if s in t: bad.append(f'{f.name}:{s}')
out = dict(status='PASS' if not issues and not bad else 'PARTIAL', issues=issues, forbidden=bad,
           cec_rows=len(rows), cec_pass=sum(1 for r in rows if r['status'] == 'PASS'),
           panel_combos=p.get('total_combos'), panel_syntheses=p.get('syntheses'), panel_cec=p.get('cec'),
           gt_hosts=len(g.get('host_status', [])), panel_gt=g.get('panel_gt'))
(H / 'CHECK_CONSISTENCY.json').write_text(json.dumps(out, indent=2), encoding='utf-8')
print(json.dumps(out, ensure_ascii=False))
