"""AIG structural diff: multiset diff of cells/nets, type distribution; no synthesis."""
import csv, json, re
from collections import Counter
from pathlib import Path
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); BASE = R / 'generate_trans/keepab_panel_stage1/conv/rs232t1000'
H = R / '_p0pilot/heldout_composition_20261110'


def parse(path):
    txt = path.read_text(encoding='utf-8', errors='ignore'); cs = []
    for m in re.finditer(r'([A-Za-z][A-Za-z0-9_]*)\s+([A-Za-z0-9_$\[\]\\]+)\s*\((.*?)\);', txt, re.S):
        pins = dict(re.findall(r'\.(\w+)\s*\(\s*([^)]*?)\s*\)', m.group(3)))
        cs.append((m.group(1), m.group(2), tuple(sorted(pins.items()))))
    nets = set()
    for _, _, pins in cs:
        for _, n in pins:
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
    nf = BASE / f'{view}__keepnone__ys_aig.v'; cf = BASE / f'{view}__keepcur__ys_aig.v'
    nc, nn = parse(nf); cc, cn = parse(cf)
    sig_n = Counter(nc); sig_c = Counter(cc)
    removed = list((sig_c - sig_n).elements()); added = list((sig_n - sig_c).elements())
    types_n = Counter(typ(t) for t, _, _ in nc); types_c = Counter(typ(t) for t, _, _ in cc)
    rows.append(dict(view=view, none_inst=len(nc), cur_inst=len(cc), none_nets=len(nn), cur_nets=len(cn),
                     fanin_none=round(sum(len(p) for _, _, p in nc) / max(1, len(nc)), 4),
                     fanin_cur=round(sum(len(p) for _, _, p in cc) / max(1, len(cc)), 4),
                     cells_removed=len(removed), cells_added=len(added),
                     nets_removed=len(cn - nn), nets_added=len(nn - cn),
                     type_diff={k: types_n.get(k, 0) - types_c.get(k, 0) for k in set(types_n) | set(types_c)},
                     removed_examples=[dict(type=t, inst=i) for t, i, _ in removed[:5]],
                     added_examples=[dict(type=t, inst=i) for t, i, _ in added[:5]]))
# classification: no reliable mapping to source anchor cone -> unresolved
for r in rows:
    r['aig_anchor_struct_diff'] = 'unresolved'
    r['reason'] = 'no reliable source-anchor cone projection for aig gate network; diff cannot be attributed'
out = dict(rows=rows, aig_conclusion='aig_structure_differs_unresolved',
           note='structural difference exists but cannot be attributed to keep; not functional GT')
(H / 'AIG_STRUCT_DIFF.json').write_text(json.dumps(out, indent=2), encoding='utf-8')
with (H / 'AIG_STRUCT_DIFF.csv').open('w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f); w.writerow(['view', 'none_inst', 'cur_inst', 'none_nets', 'cur_nets', 'fanin_none', 'fanin_cur', 'cells_removed', 'cells_added', 'nets_removed', 'nets_added', 'type_diff', 'aig_anchor_struct_diff'])
    for r in rows:
        w.writerow([r[k] for k in ('view', 'none_inst', 'cur_inst', 'none_nets', 'cur_nets', 'fanin_none', 'fanin_cur', 'cells_removed', 'cells_added', 'nets_removed', 'nets_added', 'type_diff', 'aig_anchor_struct_diff')])
print(json.dumps([{k: r[k] for k in ('view', 'none_inst', 'cur_inst', 'none_nets', 'cur_nets', 'cells_removed', 'cells_added')} for r in rows], ensure_ascii=False))
