"""Stage2b structural metrics (16 combos) + panel status."""
import csv, json, re
from collections import Counter
from pathlib import Path
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); BASE = R / 'generate_trans/keepab_panel_20_stage2b/conv'
H = R / '_p0pilot/heldout_composition_20261110'
TYPES = ('AND', 'OR', 'XOR', 'XNOR', 'MUX', 'INV', 'SDFF', 'DFF', 'OTHER')
SKIP = {'module', 'input', 'output', 'inout', 'wire', 'assign', 'parameter', 'localparam', 'endmodule', 'end'}


def typ(t):
    u = t.upper()
    for k in ('XNOR', 'XOR', 'SDFF', 'DFF', 'MUX', 'NAND', 'NOR', 'AND', 'OR', 'INV', 'BUF'):
        if k in u:
            return {'NAND': 'AND', 'NOR': 'OR', 'BUF': 'OTHER'}.get(k, k)
    return 'OTHER'


def parse(path):
    txt = re.sub(r'/\*.*?\*/', '', path.read_text(encoding='utf-8', errors='ignore'), flags=re.S)
    txt = re.sub(r'//.*', '', txt)
    cs = []
    for m in re.finditer(r'([A-Za-z_][A-Za-z0-9_]*)\s+([A-Za-z0-9_$\[\]\\]+)\s*\((.*?)\);', txt, re.S):
        if m.group(1).lower() in SKIP: continue
        pins = dict(re.findall(r'\.(\w+)\s*\(\s*([^)]*?)\s*\)', m.group(3)))
        if pins: cs.append((m.group(1), m.group(2), pins))
    nets = set()
    for _, _, pins in cs:
        for n in pins.values():
            for tok in re.findall(r'[A-Za-z0-9_$\\\[\]]+', n):
                if tok not in ('0', '1'): nets.add(tok)
    types = Counter(typ(t) for t, _, _ in cs)
    anchor = sum(1 for t, i, _ in cs if 'TROJAN' in i.upper() or 'CTL' in i.upper())
    return dict(inst=len(cs), nets=len(nets), anchor=anchor, dff=types.get('SDFF', 0) + types.get('DFF', 0),
                types={k: types.get(k, 0) for k in TYPES})

rows = []
for host in ('s15850t100', 's35932t200', 's38417t100', 's38584t100'):
    for view in (f'{host}__injalpha_d1_s42', f'{host}__injdelta_d1_s42'):
        for rec in ('abc', 'nand'):
            n = parse(BASE / host / f'{view}__keepnone__ys_{rec}.v'); c = parse(BASE / host / f'{view}__keepcur__ys_{rec}.v')
            rows.append(dict(host=host, view=view, recipe=rec, none_anchor=n['anchor'], cur_anchor=c['anchor'],
                             d_anchor=n['anchor'] - c['anchor'], none_dff=n['dff'], cur_dff=c['dff'], d_dff=n['dff'] - c['dff'],
                             none_inst=n['inst'], cur_inst=c['inst'], d_inst=n['inst'] - c['inst'],
                             none_nets=n['nets'], cur_nets=c['nets'], d_nets=n['nets'] - c['nets'],
                             d_type_L1=sum(abs(n['types'][k] - c['types'][k]) for k in TYPES),
                             status='supported' if (n['anchor'] == 0 and c['anchor'] > 0 and n['dff'] == c['dff']) else 'inconsistent'))
supported = sum(1 for r in rows if r['status'] == 'supported')
(H / 'KEEP_STAGE2B.json').write_text(json.dumps(dict(rows=rows, supported=supported, total=len(rows)), indent=2), encoding='utf-8')
with (H / 'KEEP_STAGE2B.csv').open('w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f); w.writerow(['host', 'view', 'recipe', 'none_anchor', 'cur_anchor', 'd_anchor', 'none_dff', 'cur_dff', 'd_dff', 'none_inst', 'cur_inst', 'd_inst', 'none_nets', 'cur_nets', 'd_nets', 'd_type_L1', 'status'])
    for r in rows:
        w.writerow([r[k] for k in ('host', 'view', 'recipe', 'none_anchor', 'cur_anchor', 'd_anchor', 'none_dff', 'cur_dff', 'd_dff', 'none_inst', 'cur_inst', 'd_inst', 'none_nets', 'cur_nets', 'd_nets', 'd_type_L1', 'status')])
s2a = json.loads((H / 'KEEP_STAGE2A.json').read_text(encoding='utf-8'))
panel = dict(total_combos=20, supported=s2a['supported'] + supported, inconsistent=20 - s2a['supported'] - supported,
             syntheses=40, stage2a=s2a['supported'], stage2b=supported,
             note='abc/nand only; aig excluded as not usable; CEC not run')
(H / 'PANEL_STATUS.json').write_text(json.dumps(panel, indent=2), encoding='utf-8')
print(json.dumps(dict(rows=len(rows), supported=supported, panel=panel), ensure_ascii=False))
