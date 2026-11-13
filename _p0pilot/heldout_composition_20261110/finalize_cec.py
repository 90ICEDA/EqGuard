"""Summarize CEC 3a/3b, update panel/keep/status, GT v4."""
import csv, hashlib, json, re
from pathlib import Path
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); H = R / '_p0pilot/heldout_composition_20261110'
def parse_raw(path):
    out = []
    for line in path.read_text(encoding='utf-8', errors='ignore').splitlines():
        parts = [p.strip() for p in line.split(',')]
        if len(parts) < 4: continue
        if '__' in parts[0]:
            view = parts[0]; host = view.split('__')[0]; scheme = parts[1]; rec = parts[2]
            rest = ','.join(parts[3:])
        else:
            host = parts[0]; view = parts[1]; scheme = parts[2]; rec = parts[3]
            rest = ','.join(parts[4:]) if len(parts) > 4 else ''
        m = re.search(r'total=(\d+) proven=(\d+) unproven=(\d+) (\w+)', rest)
        out.append(dict(host=host, view=view, recipe=rec, scheme=scheme,
                        reference=f'generate_trans/hosts_bt2/{host}/{view}.v',
                        total=int(m.group(1)) if m else None, proven=int(m.group(2)) if m else None,
                        unproven=int(m.group(3)) if m else None,
                        status=(m.group(4) if m else 'NA'),
                        counterexample='' if (m and m.group(4) == 'PASS') else 'see log',
                        log=f'generate_trans/cec_panel_stage3{ "a" if "stage3a" in str(path) else "b" }/{view}__{scheme}__ys_{rec}.log'))
    return out
rows3a = parse_raw(R / 'generate_trans/cec_panel_stage3a/CEC_STAGE3A_RAW.txt')
rows3b = parse_raw(R / 'generate_trans/cec_panel_stage3b/CEC_STAGE3B_RAW.txt')
for tag, rows in (('3A', rows3a), ('3B', rows3b)):
    with (H / f'CEC_STAGE{tag}.csv').open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    (H / f'CEC_STAGE{tag}.json').write_text(json.dumps(dict(rows=rows, total=len(rows),
        passed=sum(1 for r in rows if r['status'] == 'PASS')), indent=2), encoding='utf-8')
allrows = rows3a + rows3b
passed = sum(1 for r in allrows if r['status'] == 'PASS')
sha = hashlib.sha256((H / 'CEC_STAGE3B.csv').read_bytes()).hexdigest()
p = json.loads((H / 'PANEL_STATUS.json').read_text(encoding='utf-8'))
p.update(dict(cec=f'{passed}/{len(allrows)} PASS', cec_stage3a=f'{sum(1 for r in rows3a if r["status"]=="PASS")}/{len(rows3a)}',
              cec_stage3b=f'{sum(1 for r in rows3b if r["status"]=="PASS")}/{len(rows3b)}',
              cec_sha3b=sha, gt='partial (host-level example only)',
              note='CEC vs corresponding trojan view; clean not used; aig excluded'))
(H / 'PANEL_STATUS.json').write_text(json.dumps(p, indent=2), encoding='utf-8')
ka = json.loads((H / 'KEEP_AUDIT.json').read_text(encoding='utf-8'))
ka['cec'] = dict(status=f'{passed}/{len(allrows)} PASS', reference='corresponding trojan source view',
                 clean_used=False, note='clean is not CEC PASS; local equivalence != functional impact',
                 stage3a=f'{sum(1 for r in rows3a if r["status"]=="PASS")}/{len(rows3a)}',
                 stage3b=f'{sum(1 for r in rows3b if r["status"]=="PASS")}/{len(rows3b)}')
(H / 'KEEP_AUDIT.json').write_text(json.dumps(ka, indent=2), encoding='utf-8')
s = json.loads((H / 'STATUS.json').read_text(encoding='utf-8'))
s['nokeep'] = dict(s.get('nokeep', {}), cec=f'{passed}/{len(allrows)} PASS', gt='partial')
s['note'] = 'CEC 40/40 PASS vs trojan views; GT partial (host-level only)'
(H / 'STATUS.json').write_text(json.dumps(s, indent=2), encoding='utf-8')
# GT v4
g3 = json.loads((H / 'GT_AVAILABILITY_V3.json').read_text(encoding='utf-8'))
g4 = dict(host_example=dict(host='rs232t1000', design='tr45', rows=g3['rows'], counts=g3['counts']),
          host_status=[dict(host='rs232t1000', status='verified_example'),
                       dict(host='s15850t100', status='can_attempt'),
                       dict(host='s35932t200', status='can_attempt'),
                       dict(host='s38417t100', status='missing'),
                       dict(host='s38584t100', status='can_attempt')],
          panel_gt='not built per combo; example not extrapolated', note='weak MIL/CEC equivalence not functional GT')
(H / 'GT_AVAILABILITY_V4.json').write_text(json.dumps(g4, indent=2), encoding='utf-8')
with (H / 'GT_AVAILABILITY_V4.csv').open('w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f); w.writerow(['host', 'status'])
    for x in g4['host_status']: w.writerow([x['host'], x['status']])
print(json.dumps(dict(cec=passed, total=len(allrows), a=len(rows3a), b=len(rows3b)), ensure_ascii=False))
