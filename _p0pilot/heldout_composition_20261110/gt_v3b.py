"""GT v3b: DFF Q/D endpoint rows (all target copies) + accurate PI/PO counts + keep view existence."""
import csv, json, re
from pathlib import Path
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); H = R / '_p0pilot/heldout_composition_20261110'
SRC = R / 'generate_trans/orig/rs232t1000.v'; DST = R / 'generate_trans/trans/rs232t1000tr45.v'
MAP = R / 'generate_trans/mappings/rs232t1000tr45.json'


def cells(path):
    out = {}
    txt = path.read_text(encoding='utf-8', errors='ignore')
    for m in re.finditer(r'([A-Za-z][A-Za-z0-9_]*)\s+([A-Za-z0-9_$\[\]\\]+)\s*\((.*?)\);', txt, re.S):
        pins = dict(re.findall(r'\.(\w+)\s*\(\s*([^)]*?)\s*\)', m.group(3)))
        line = txt.count('\n', 0, m.start()) + 1
        out[m.group(2)] = dict(type=m.group(1), pins=pins, line=line)
    return out


def is_dff(c): return 'DFF' in c['type'].upper() and 'Q' in c['pins'] and 'D' in c['pins']


def ports(path):
    txt = path.read_text(encoding='utf-8', errors='ignore'); out = {}
    for i, line in enumerate(txt.splitlines(), 1):
        for m in re.finditer(r'\b(input|output)\b\s*(?:\[[^\]]*\])?\s*([A-Za-z0-9_$,\s]+);', line):
            for n in m.group(2).split(','):
                n = n.strip()
                if n: out.setdefault(n, dict(dir=m.group(1), line=i))
    return out


sc, dc = cells(SRC), cells(DST); sp, dp = ports(SRC), ports(DST)
mp = json.loads(MAP.read_text(encoding='utf-8'))['node_alignment']
rows = []
for si, dsts in mp.items():
    if si not in sc or not is_dff(sc[si]): continue
    for di in dsts:
        if di not in dc or not is_dff(dc[di]):
            rows.append(dict(host='rs232t1000', design='tr45', type='DFF_QD', endpoint=si, src=si, src_line=sc[si]['line'],
                             src_Q=sc[si]['pins'].get('Q'), src_D=sc[si]['pins'].get('D'), dst=di, dst_line=dc.get(di, {}).get('line'),
                             dst_Q=dc.get(di, {}).get('pins', {}).get('Q'), dst_D=dc.get(di, {}).get('pins', {}).get('D'),
                             mapping='node_alignment', status='unmapped', reason='target instance missing or not DFF'))
            continue
        for pin in ('Q', 'D'):
            rows.append(dict(host='rs232t1000', design='tr45', type=f'DFF_{pin}', endpoint=si, src=si, src_line=sc[si]['line'],
                             src_Q=sc[si]['pins']['Q'], src_D=sc[si]['pins']['D'], dst=di, dst_line=dc[di]['line'],
                             dst_Q=dc[di]['pins']['Q'], dst_D=dc[di]['pins']['D'], pin=pin,
                             mapping='node_alignment', status='verified'))
# name-preserved DFF mapping (target keeps DFF instance names)
for si, c in sc.items():
    if not is_dff(c) or si not in dc or not is_dff(dc[si]):
        continue
    for pin in ('Q', 'D'):
        rows.append(dict(host='rs232t1000', design='tr45', type=f'DFF_{pin}', endpoint=si, src=si, src_line=c['line'],
                         src_Q=c['pins']['Q'], src_D=c['pins']['D'], dst=si, dst_line=dc[si]['line'],
                         dst_Q=dc[si]['pins']['Q'], dst_D=dc[si]['pins']['D'], pin=pin,
                         mapping='instance_name_preserved', status='verified'))
for p in sp:
    if p in dp and p not in ('sys_clk',):
        rows.append(dict(host='rs232t1000', design='tr45', type=('PI' if sp[p]['dir'] == 'input' else 'PO'), endpoint=p,
                         src=p, src_line=sp[p]['line'], src_Q=None, src_D=None, dst=p, dst_line=dp[p]['line'], dst_Q=None, dst_D=None,
                         mapping='port name', status='verified'))
counts = {t: sum(1 for x in rows if x['type'] == t and x['status'] == 'verified') for t in ('DFF_Q', 'DFF_D', 'PI', 'PO')}
# keep view existence
hv = R / 'generate_trans/hosts_bt2' / 'rs232t1000__injalpha_d1_s42'
view_exists = hv.exists()
ka = json.loads((H / 'KEEP_AUDIT.json').read_text(encoding='utf-8'))
ka['view_check'] = dict(path=str(hv.relative_to(R)), exists=view_exists)
ka['full_command_valid'] = bool(view_exists)
(H / 'KEEP_AUDIT.json').write_text(json.dumps(ka, indent=2), encoding='utf-8')
out = dict(source=str(SRC.relative_to(R)), target=str(DST.relative_to(R)), mapping=str(MAP.relative_to(R)),
           counts=counts, rows=rows, design_note='tr45 is one host-level example; panel 30-combo endpoint GT not built per combo',
           note='weak MIL/structural reachability/CEC equivalence are not functional GT')
(H / 'GT_AVAILABILITY_V3.json').write_text(json.dumps(out, indent=2), encoding='utf-8')
with (H / 'GT_AVAILABILITY_V3.csv').open('w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f)
    w.writerow(['host', 'design', 'type', 'endpoint', 'src', 'src_line', 'src_Q', 'src_D', 'dst', 'dst_line', 'dst_Q', 'dst_D', 'pin', 'mapping', 'status'])
    for x in rows:
        w.writerow([x['host'], x['design'], x['type'], x['endpoint'], x['src'], x['src_line'], x.get('src_Q'), x.get('src_D'),
                    x['dst'], x.get('dst_line'), x.get('dst_Q'), x.get('dst_D'), x.get('pin', ''), x['mapping'], x['status']])
print(json.dumps(dict(counts=counts, rows=len(rows), view_exists=view_exists), ensure_ascii=False))
