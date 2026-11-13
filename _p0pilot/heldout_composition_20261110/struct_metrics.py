"""Structural metrics on stage1 conv netlists: cell types, anchors, DFF, fanin/fanout."""
import csv, json, re
from pathlib import Path
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); OUT = R / 'generate_trans/keepab_panel_stage1/conv/rs232t1000'
H = R / '_p0pilot/heldout_composition_20261110'


def cells(path):
    txt = path.read_text(encoding='utf-8', errors='ignore'); out = []
    for m in re.finditer(r'([A-Za-z][A-Za-z0-9_]*)\s+([A-Za-z0-9_$\[\]\\]+)\s*\((.*?)\);', txt, re.S):
        pins = re.findall(r'\.(\w+)\s*\(\s*([^)]*?)\s*\)', m.group(3))
        out.append(dict(type=m.group(1), inst=m.group(2), pins=pins))
    return out


def classify(t):
    u = t.upper()
    for k in ('SDFF', 'DFF', 'MUX', 'XOR', 'NAND', 'NOR', 'AND', 'OR', 'INV', 'BUF'):
        if k in u: return k
    return 'OTHER'


rows = []
for view in ('rs232t1000__injalpha_d1_s42', 'rs232t1000__injdelta_d1_s42'):
    for rec in ('abc', 'aig', 'nand'):
        d = {}
        for sch in ('keepnone', 'keepcur'):
            f = OUT / f'{view}__{sch}__ys_{rec}.v'
            cs = cells(f)
            types = {}
            for c in cs:
                k = classify(c['type']); types[k] = types.get(k, 0) + 1
            anchor = sum(1 for c in cs if ('TROJAN' in c['inst'].upper() or 'CTL' in c['inst'].upper()))
            dff = sum(1 for c in cs if 'DFF' in c['type'].upper())
            nets = set()
            for c in cs:
                for _, n in c['pins']:
                    for tok in re.findall(r'[A-Za-z0-9_$\\\[\]]+', n):
                        if tok not in ('1\'b0', '1\'b1', '1\'bx', '0', '1'):
                            nets.add(tok)
            fanin = [len(c['pins']) for c in cs]
            d[sch] = dict(inst=len(cs), nets=len(nets), anchor=anchor, dff=dff, types=types,
                          fanin_mean=sum(fanin) / max(1, len(fanin)), fanin_max=max(fanin) if fanin else 0)
        n, c = d['keepnone'], d['keepcur']
        rows.append(dict(view=view, recipe=rec, none_inst=n['inst'], cur_inst=c['inst'], d_inst=n['inst'] - c['inst'],
                         none_anchor=n['anchor'], cur_anchor=c['anchor'], d_anchor=n['anchor'] - c['anchor'],
                         none_dff=n['dff'], cur_dff=c['dff'], d_dff=n['dff'] - c['dff'],
                         none_nets=n['nets'], cur_nets=c['nets'], d_nets=n['nets'] - c['nets'],
                         none_fanin=n['fanin_mean'], cur_fanin=c['fanin_mean'],
                         d_fanin=round(n['fanin_mean'] - c['fanin_mean'], 3), types_none=n['types'], types_cur=c['types']))
(H / 'STRUCT_METRICS.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
with (H / 'STRUCT_METRICS.csv').open('w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f)
    w.writerow(['view', 'recipe', 'none_inst', 'cur_inst', 'd_inst', 'none_anchor', 'cur_anchor', 'd_anchor',
                'none_dff', 'cur_dff', 'd_dff', 'none_nets', 'cur_nets', 'd_nets', 'none_fanin', 'cur_fanin', 'd_fanin'])
    for r in rows:
        w.writerow([r[k] for k in ('view', 'recipe', 'none_inst', 'cur_inst', 'd_inst', 'none_anchor', 'cur_anchor', 'd_anchor',
                                   'none_dff', 'cur_dff', 'd_dff', 'none_nets', 'cur_nets', 'd_nets', 'none_fanin', 'cur_fanin', 'd_fanin')])
# judgment
aig = [r for r in rows if r['recipe'] == 'aig']
aig_status = 'aig_keep_removal_supported' if all(r['d_anchor'] < 0 for r in aig) else (
    'aig_text_metric_invalid_and_structure_same' if all(r['d_anchor'] == 0 for r in aig) else 'aig_unresolved')
rep = dict(rows=rows, aig_status=aig_status,
           aig_d_anchor=[(r['view'], r['d_anchor']) for r in aig],
           note='structural metrics only for keep-removal, not functional GT')
(H / 'STRUCT_METRICS.json').write_text(json.dumps(rep, indent=2), encoding='utf-8')
print(json.dumps(dict(aig=aig_status, d_anchor=[(r['view'], r['d_anchor'], r['d_inst']) for r in aig]), ensure_ascii=False))
