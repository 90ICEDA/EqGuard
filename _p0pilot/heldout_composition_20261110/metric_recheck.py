"""Unified metric recheck for stage1 and stage2a (no synthesis)."""
import csv, json, re
from collections import Counter
from pathlib import Path
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); H = R / '_p0pilot/heldout_composition_20261110'
SKIP = {'module', 'input', 'output', 'inout', 'wire', 'assign', 'parameter', 'localparam', 'endmodule', 'end'}
TYPES = ('AND', 'OR', 'XOR', 'XNOR', 'MUX', 'INV', 'SDFF', 'DFF', 'OTHER')


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
    dff = types.get('SDFF', 0) + types.get('DFF', 0)
    return dict(inst=len(cs), nets=len(nets), anchor=anchor, dff=dff,
                types={k: types.get(k, 0) for k in TYPES},
                fanin=round(sum(len(p) for _, _, p in cs) / max(1, len(cs)), 4))


def pair(base, view, rec):
    n = parse(base / f'{view}__keepnone__ys_{rec}.v'); c = parse(base / f'{view}__keepcur__ys_{rec}.v')
    return dict(none=n, cur=c, d_anchor=n['anchor'] - c['anchor'], d_inst=n['inst'] - c['inst'],
                d_nets=n['nets'] - c['nets'], d_dff=n['dff'] - c['dff'],
                d_type_L1=sum(abs(n['types'][k] - c['types'][k]) for k in TYPES),
                disturbance_L1=sum(abs(n['types'][k] - c['types'][k]) for k in TYPES))


recheck = {'stage1': [], 'stage2a': []}
b1 = R / 'generate_trans/keepab_panel_stage1/conv/rs232t1000'
b2 = R / 'generate_trans/keepab_panel_20_stage2a/conv/rs232t1000'
for view in ('rs232t1000__injalpha_d1_s42', 'rs232t1000__injdelta_d1_s42'):
    for rec in ('abc', 'aig', 'nand'):
        if rec == 'aig': continue
        r = pair(b1, view, rec); r.update(view=view, recipe=rec); recheck['stage1'].append(r)
    for rec in ('abc', 'nand'):
        r = pair(b2, view, rec); r.update(view=view, recipe=rec); recheck['stage2a'].append(r)
# compare with stored values
old1 = {(t['view'], t['recipe']): t for t in json.loads((H / 'KEEP_STAGE1.json').read_text(encoding='utf-8'))['table']}
old2 = {(r['view'], r['recipe']): r for r in json.loads((H / 'KEEP_STAGE2A.json').read_text(encoding='utf-8'))['rows']}
diff = []
for r in recheck['stage1']:
    o = old1.get((r['view'], r['recipe']))
    if o and (o.get('structural_none_anchor') != r['none']['anchor'] or o.get('structural_cur_anchor') != r['cur']['anchor']):
        diff.append(dict(stage='stage1', view=r['view'], recipe=r['recipe'], old=(o.get('structural_none_anchor'), o.get('structural_cur_anchor')), new=(r['none']['anchor'], r['cur']['anchor'])))
for r in recheck['stage2a']:
    o = old2.get((r['view'], r['recipe']))
    if o and (o.get('none_anchor') != r['none']['anchor'] or o.get('cur_anchor') != r['cur']['anchor']):
        diff.append(dict(stage='stage2a', view=r['view'], recipe=r['recipe'], old=(o.get('none_anchor'), o.get('cur_anchor')), new=(r['none']['anchor'], r['cur']['anchor'])))
(H / 'METRIC_RECHECK.json').write_text(json.dumps(dict(spec='METRIC_SPEC.md', stage1=recheck['stage1'], stage2a=recheck['stage2a'], mismatches=diff), indent=2), encoding='utf-8')
print(json.dumps(dict(stage1=len(recheck['stage1']), stage2a=len(recheck['stage2a']), mismatches=len(diff)), ensure_ascii=False))
