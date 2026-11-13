"""Stage2a structural metrics and 4/4 verdict."""
import csv, json, re
from collections import Counter
from pathlib import Path
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); BASE = R / 'generate_trans/keepab_panel_20_stage2a/conv/rs232t1000'
H = R / '_p0pilot/heldout_composition_20261110'


def parse(path):
    txt = path.read_text(encoding='utf-8', errors='ignore'); cs = []
    for m in re.finditer(r'([A-Za-z][A-Za-z0-9_]*)\s+([A-Za-z0-9_$\[\]\\]+)\s*\((.*?)\);', txt, re.S):
        pins = dict(re.findall(r'\.(\w+)\s*\(\s*([^)]*?)\s*\)', m.group(3)))
        cs.append((m.group(1), m.group(2), pins))
    nets = set()
    for _, _, pins in cs:
        for n in pins.values():
            for tok in re.findall(r'[A-Za-z0-9_$\\\[\]]+', n):
                if tok not in ('0', '1'): nets.add(tok)
    return cs, nets


def typ(t):
    u = t.upper()
    for k in ('SDFF', 'DFF', 'MUX', 'XOR', 'NAND', 'NOR', 'AND', 'OR', 'INV', 'BUF'):
        if k in u: return k
    return 'OTHER'

rows = []
for view in ('rs232t1000__injalpha_d1_s42', 'rs232t1000__injdelta_d1_s42'):
    for rec in ('abc', 'nand'):
        d = {}
        for sch in ('keepnone', 'keepcur'):
            f = BASE / f'{view}__{sch}__ys_{rec}.v'
            cs, nets = parse(f)
            anchor = sum(1 for t, i, _ in cs if 'TROJAN' in i.upper() or 'CTL' in i.upper())
            dff = sum(1 for t, _, _ in cs if 'DFF' in t.upper())
            d[sch] = dict(inst=len(cs), nets=len(nets), anchor=anchor, dff=dff,
                          types=Counter(typ(t) for t, _, _ in cs))
        n, c = d['keepnone'], d['keepcur']
        rows.append(dict(host='rs232t1000', view=view, recipe=rec,
                         none_anchor=n['anchor'], cur_anchor=c['anchor'], d_anchor=n['anchor'] - c['anchor'],
                         none_dff=n['dff'], cur_dff=c['dff'], d_dff=n['dff'] - c['dff'],
                         none_inst=n['inst'], cur_inst=c['inst'], d_inst=n['inst'] - c['inst'],
                         none_nets=n['nets'], cur_nets=c['nets'], d_nets=n['nets'] - c['nets'],
                         type_diff={k: n['types'].get(k, 0) - c['types'].get(k, 0) for k in set(n['types']) | set(c['types'])},
                         status='supported' if (n['anchor'] == 0 and c['anchor'] > 0 and n['dff'] == c['dff']) else 'inconsistent'))
(H / 'KEEP_STAGE2A.json').write_text(json.dumps(dict(rows=rows, supported=sum(1 for r in rows if r['status'] == 'supported'), total=len(rows)), indent=2), encoding='utf-8')
with (H / 'KEEP_STAGE2A.csv').open('w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f); w.writerow(['host', 'view', 'recipe', 'none_anchor', 'cur_anchor', 'd_anchor', 'none_dff', 'cur_dff', 'd_dff', 'none_inst', 'cur_inst', 'd_inst', 'none_nets', 'cur_nets', 'type_diff', 'status'])
    for r in rows:
        w.writerow([r[k] for k in ('host', 'view', 'recipe', 'none_anchor', 'cur_anchor', 'd_anchor', 'none_dff', 'cur_dff', 'd_dff', 'none_inst', 'cur_inst', 'd_inst', 'none_nets', 'cur_nets', 'type_diff', 'status')])
print(json.dumps([{k: r[k] for k in ('view', 'recipe', 'none_anchor', 'cur_anchor', 'd_dff', 'status')} for r in rows], ensure_ascii=False))
