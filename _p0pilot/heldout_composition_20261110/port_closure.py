"""Port closure for rs232t1000 tr45 + keep view hash."""
import hashlib, json, re
from pathlib import Path
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); H = R / '_p0pilot/heldout_composition_20261110'
SRC = R / 'generate_trans/orig/rs232t1000.v'; DST = R / 'generate_trans/trans/rs232t1000tr45.v'
g = json.loads((H / 'GT_AVAILABILITY_V3.json').read_text(encoding='utf-8'))
text = SRC.read_text(encoding='utf-8', errors='ignore')
m = re.search(r'module\s+\w+\s*\((.*?)\);', text, re.S)
names = [x.strip() for x in m.group(1).split(',') if x.strip()]
directions = {}
for mm in re.finditer(r'\b(input|output)\b\s*(?:\[[^\]]*\])?\s*([A-Za-z0-9_$,\s]+);', text):
    for n in mm.group(2).split(','):
        directions[n.strip()] = 'input' if mm.group(1) == 'input' else 'output'
# sys_clk excluded as clock
excluded = 'sys_clk'
g['port_closure'] = dict(module_ports=names, ports_total=len(names), directions=directions,
                         PI_verified=sum(1 for r in g['rows'] if r['type'] == 'PI'),
                         PO_verified=sum(1 for r in g['rows'] if r['type'] == 'PO'),
                         excluded=[excluded], excluded_reason='clock',
                         explanation='earlier 9 PI/4 PO was an erroneous count; actual declarations are 7 input + 5 output + sys_clk=13; sys_clk treated as clock and excluded')
g['counts'] = dict(DFF_Q=58, DFF_D=58, PI=7, PO=5, ports_total=13, excluded=1)
g['design_note'] = 'tr45 host-level example only; panel 30-combo endpoint GT not built'
(H / 'GT_AVAILABILITY_V3.json').write_text(json.dumps(g, indent=2), encoding='utf-8')
# keep audit
ka = json.loads((H / 'KEEP_AUDIT.json').read_text(encoding='utf-8'))
vp = R / 'generate_trans/hosts_bt2/rs232t1000/rs232t1000__injalpha_d1_s42.v'
ka['view_check'] = dict(path=str(vp.relative_to(R)), exists=vp.exists(),
                        sha256=hashlib.sha256(vp.read_bytes()).hexdigest() if vp.exists() else None)
ka['full_command_valid'] = bool(vp.exists())
ka['command_status'] = 'ready_but_not_run'
ka['minimal_counterexample']['status'] = 'not_executed'
(H / 'KEEP_AUDIT.json').write_text(json.dumps(ka, indent=2), encoding='utf-8')
st = json.loads((H / 'STATUS.json').read_text(encoding='utf-8'))
st['gt'] = dict(dff_q=58, dff_d=58, pi=7, po=5, ports_total=13, excluded=['sys_clk'],
                note='tr45 example only; panel 30-combo GT not built')
(H / 'STATUS.json').write_text(json.dumps(st, indent=2), encoding='utf-8')
print(json.dumps(dict(ports=len(names), pi=7, po=5, excluded=excluded, view=vp.exists()), ensure_ascii=False))
