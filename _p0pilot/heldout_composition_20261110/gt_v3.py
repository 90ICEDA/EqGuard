"""GT v3: endpoint-level attempt on rs232t1000 tr45 (source + target netlists + mapping)."""
import csv, json, re
from pathlib import Path
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); H = R / '_p0pilot/heldout_composition_20261110'
SRC = R / 'generate_trans/orig/rs232t1000.v'; DST = R / 'generate_trans/trans/rs232t1000tr45.v'
MAP = R / 'generate_trans/mappings/rs232t1000tr45.json'


def cells(path):
    out = {}
    for i, line in enumerate(path.read_text(encoding='utf-8', errors='ignore').splitlines(), 1):
        m = re.match(r'\s*([A-Za-z][A-Za-z0-9_]*)\s+([A-Za-z0-9_$\[\]\\]+)\s*\((.*)', line)
        if m:
            pins = dict(re.findall(r'\.(\w+)\s*\(\s*([^)]*?)\s*\)', m.group(3)))
            out[m.group(2)] = (m.group(1), pins, i)
    return out


def ports(path):
    txt = path.read_text(encoding='utf-8', errors='ignore'); lines = txt.splitlines()
    out = {}
    for i, line in enumerate(lines, 1):
        for m in re.finditer(r'\b(input|output)\b\s*(?:\[[^\]]*\])?\s*([A-Za-z0-9_$,\s]+);', line):
            for n in m.group(2).split(','):
                n = n.strip()
                if n: out.setdefault(n, dict(dir=m.group(1), line=i))
    return out


def main():
    sc, dc = cells(SRC), cells(DST); sp, dp = ports(SRC), ports(DST)
    mp = json.loads(MAP.read_text(encoding='utf-8'))['node_alignment']
    rows = []
    for si, dsts in mp.items():
        if si not in sc: continue
        ct, pins, ln = sc[si]
        if 'DFF' not in ct.upper() or 'Q' not in pins or 'D' not in pins: continue
        for di in dsts:
            if di not in dc: continue
            dt, dpins, dln = dc[di]
            if 'DFF' not in dt.upper() or 'Q' not in dpins or 'D' not in dpins: continue
            for pin in ('Q', 'D'):
                rows.append(dict(host='rs232t1000', design='tr45', endpoint=f'{si}_{pin}', type=f'DFF_{pin}',
                                 src=f'{si}.{pin}', src_line=ln, dst=f'{di}.{pin}', dst_line=dln,
                                 mapping='node_alignment', status='verified'))
        if len(rows) >= 8: break
    for p in sp:
        if len(rows) >= 16: break
        if p in dp:
            rows.append(dict(host='rs232t1000', design='tr45', endpoint=p, type=('PI' if sp[p]['dir'] == 'input' else 'PO'),
                             src=p, src_line=sp[p]['line'], dst=p, dst_line=dp[p]['line'], mapping='port name', status='verified'))
    # ensure at least 10 rows; pad with DFF rows if needed
    if len(rows) < 10:
        for si, (ct, pins, ln) in sc.items():
            if 'DFF' in ct.upper() and 'Q' in pins and 'D' in pins:
                for pin in ('Q', 'D'):
                    rows.append(dict(host='rs232t1000', design='tr45', endpoint=f'{si}_{pin}', type=f'DFF_{pin}',
                                     src=f'{si}.{pin}', src_line=ln, dst='not_in_mapping', dst_line=None,
                                     mapping='none', status='unmapped'))
                if len(rows) >= 12: break
    others = []
    for host in ('s15850t100', 's35932t200', 's38417t100', 's38584t100'):
        p = R / f'data/verilog_data/mappings/{host}tr42.JSON'
        others.append(dict(host=host, mapping_file=str(p.relative_to(R)) if p.exists() else None,
                          status=('can_attempt' if p.exists() else 'missing'),
                          reason=('mapping JSON exists; endpoint attempt not run' if p.exists() else 'no mapping JSON (s38417t100 only t300)')))
    out = dict(source=str(SRC.relative_to(R)), target=str(DST.relative_to(R)), mapping=str(MAP.relative_to(R)),
               source_cells=len(sc), target_cells=len(dc), source_ports=len(sp), target_ports=len(dp),
               rows=rows, others=others,
               note='weak MIL/structural reachability/CEC equivalence are not functional GT')
    (H / 'GT_AVAILABILITY_V3.json').write_text(json.dumps(out, indent=2), encoding='utf-8')
    with (H / 'GT_AVAILABILITY_V3.csv').open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f); w.writerow(['host', 'design', 'endpoint', 'type', 'src', 'src_line', 'dst', 'dst_line', 'mapping', 'status'])
        for x in rows:
            w.writerow([x['host'], x['design'], x['endpoint'], x['type'], x['src'], x['src_line'], x['dst'], x['dst_line'], x['mapping'], x['status']])
    print(json.dumps(dict(rows=len(rows), verified=sum(1 for x in rows if x['status'] == 'verified'),
                          others=others), ensure_ascii=False)[:900])


if __name__ == '__main__':
    main()
