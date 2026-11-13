"""Compare structural statistics of one netlist across its synthesis recipes (read-only).

Robust metrics only: cell count, pin-connection (edge) count, DFF count, PI/PO bits,
cell-type histogram and Jensen-Shannon divergence vs ys_id. Depth/fanout are omitted
because escaped Verilog identifiers make a reliable net graph hard to rebuild here.
"""
from pathlib import Path
import collections
import json
import math
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
TRANS = ROOT / 'generate_trans/folds/hosts_bt31/trans'
PREFIX = (sys.argv[1] if len(sys.argv) > 1 else 'rs232t1000__injalpha_d1_s42__keepbnd__ys_')
RECIPES = ['id', 'abc', 'opt', 'aig', 'nand', 'rt']

CELL_RE = re.compile(r'^\s*([A-Za-z_][\w$]*)\s+([\\\w.$\[\]]+)\s*\(')
PIN_RE = re.compile(r'\.([A-Za-z_]\w*)\s*\(\s*([^)]*?)\s*\)')
OUT_PINS = ('Y', 'Q', 'QN', 'Z', 'S', 'CO')


def parse(path):
    lines = path.read_text(encoding='utf-8', errors='ignore').splitlines()
    cells = []
    buf = ''
    in_cell = False
    for ln in lines:
        if not in_cell:
            m = CELL_RE.match(ln)
            if m and not ln.lstrip().startswith(('module', 'wire', 'assign', 'input', 'output', 'endmodule')):
                in_cell = True
                buf = ln
                if ');' in ln:
                    cells.append(buf); in_cell = False
        else:
            buf += ' ' + ln.strip()
            if ');' in ln:
                cells.append(buf); in_cell = False
    parsed = []
    for c in cells:
        m = CELL_RE.match(c)
        if not m:
            continue
        pins = {p: n.strip() for p, n in PIN_RE.findall(c)}
        parsed.append(dict(type=m.group(1), inst=m.group(2), pins=pins))
    def width(pat):
        w = 0
        for ln in lines:
            m = re.match(pat, ln)
            if m:
                w += abs(int(m.group(1)) - int(m.group(2))) + 1 if m.group(1) else 1
        return w
    return parsed, width(r'\s*input\s*\[\s*(\d+)\s*:\s*(\d+)\s*\]'), width(r'\s*output\s*\[\s*(\d+)\s*:\s*(\d+)\s*\]')


def stats(cells):
    types = collections.Counter(c['type'] for c in cells)
    dff = sum(v for k, v in types.items() if 'DFF' in k.upper())
    edges = sum(1 for c in cells for p in c['pins'] if p not in OUT_PINS)
    return dict(cells=len(cells), dff=dff, edges=edges, types=len(types),
                type_hist=dict(types.most_common()))


def js(p, q):
    keys = set(p) | set(q)
    P = [p.get(k, 0) for k in keys]; Q = [q.get(k, 0) for k in keys]
    sp, sq = sum(P) or 1, sum(Q) or 1
    P = [x / sp for x in P]; Q = [x / sq for x in Q]
    m = [(a + b) / 2 for a, b in zip(P, Q)]
    kl = lambda a, b: sum(x * math.log2(x / y) for x, y in zip(a, b) if x > 0 and y > 0)
    return 0.5 * kl(P, m) + 0.5 * kl(Q, m)


def main():
    rows = {}
    for r in RECIPES:
        p = TRANS / f'{PREFIX}{r}.v'
        if not p.exists():
            print('missing', p.name); continue
        cells, pin, pout = parse(p)
        s = stats(cells); s.update(recipe=r, PI=pin, PO=pout)
        rows[r] = s
        print(json.dumps(s, ensure_ascii=False), flush=True)
    base = rows.get('id')
    out = dict(netlist=PREFIX, rows=rows, pairwise={})
    for r, s in rows.items():
        if r == 'id':
            continue
        out['pairwise'][r] = dict(
            d_cells=round(s['cells'] / base['cells'] - 1, 4) if base['cells'] else None,
            d_edges=round(s['edges'] / base['edges'] - 1, 4) if base['edges'] else None,
            d_dff=s['dff'] - base['dff'],
            d_PI=s['PI'] - base['PI'], d_PO=s['PO'] - base['PO'],
            js_types=round(js(base['type_hist'], s['type_hist']), 4))
    print(json.dumps(out['pairwise'], ensure_ascii=False, indent=1))
    name = 'compare_report_' + PREFIX.split('__')[0] + '_' + PREFIX.split('__')[1] + '.json'
    (Path(__file__).resolve().parent / name).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
