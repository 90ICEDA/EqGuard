"""Clean aig structural diff: exclude non-cell statements, compare (type,inst) sets."""
import csv, json, re
from collections import Counter
from pathlib import Path
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); BASE = R / 'generate_trans/keepab_panel_stage1/conv/rs232t1000'
H = R / '_p0pilot/heldout_composition_20261110'
SKIP = ('module', 'input', 'output', 'inout', 'wire', 'assign', 'endmodule', 'parameter', 'localparam', 'end')


def parse(path):
    txt = path.read_text(encoding='utf-8', errors='ignore')
    txt = re.sub(r'/\*.*?\*/', '', txt, flags=re.S); txt = re.sub(r'//.*', '', txt)
    # drop non-cell statements
    stmts = []
    for m in re.finditer(r'([A-Za-z_][A-Za-z0-9_]*)\s+([A-Za-z0-9_$\[\]\\]+)\s*\((.*?)\);', txt, re.S):
        if m.group(1).lower() in SKIP: continue
        pins = dict(re.findall(r'\.(\w+)\s*\(\s*([^)]*?)\s*\)', m.group(3)))
        if not pins: continue
        stmts.append(dict(type=m.group(1), inst=m.group(2), pins=pins))
    nets = set()
    for c in stmts:
        for n in c['pins'].values():
            for tok in re.findall(r'[A-Za-z0-9_$\\\[\]]+', n):
                if tok not in ('0', '1'): nets.add(tok)
    return stmts, nets


def typ(t):
    u = t.upper()
    for k in ('SDFF', 'DFF', 'MUX', 'XOR', 'NAND', 'NOR', 'AND', 'OR', 'INV', 'BUF'):
        if k in u: return k
    return 'OTHER'

rows = []
for view in ('rs232t1000__injalpha_d1_s42', 'rs232t1000__injdelta_d1_s42'):
    nc, nn = parse(BASE / f'{view}__keepnone__ys_aig.v'); cc, cn = parse(BASE / f'{view}__keepcur__ys_aig.v')
    sn = {(typ(c['type']), c['inst']) for c in nc}; sc = {(typ(c['type']), c['inst']) for c in cc}
    tn = Counter(typ(c['type']) for c in nc); tc = Counter(typ(c['type']) for c in cc)
    rows.append(dict(view=view, none_inst=len(nc), cur_inst=len(cc), none_nets=len(nn), cur_nets=len(cn),
                     type_diff={k: tn.get(k, 0) - tc.get(k, 0) for k in set(tn) | set(tc)},
                     cells_removed=sorted(sc - sn)[:10], cells_added=sorted(sn - sc)[:10],
                     n_removed=len(sc - sn), n_added=len(sn - sc),
                     nets_removed=len(cn - nn), nets_added=len(nn - cn),
                     fanin_none=round(sum(len(c['pins']) for c in nc) / max(1, len(nc)), 4),
                     fanin_cur=round(sum(len(c['pins']) for c in cc) / max(1, len(cc)), 4)))
# judgment
for r in rows:
    only_inv = all(k == 'INV' and abs(v) <= 1 for k, v in r['type_diff'].items() if v != 0) and sum(abs(v) for v in r['type_diff'].values()) <= 1
    r['localized_to_anchor'] = False
    r['aig_status'] = 'aig_not_usable_for_keep_ablation' if only_inv and not r['localized_to_anchor'] else 'aig_unresolved'
out = dict(rows=rows, aig_status='aig_not_usable_for_keep_ablation' if all(r['aig_status'] == 'aig_not_usable_for_keep_ablation' for r in rows) else 'aig_unresolved',
           note='cell sets compared by (type, inst); non-cell statements excluded; no source-anchor cone projection available')
(H / 'AIG_STRUCT_DIFF_V2.json').write_text(json.dumps(out, indent=2), encoding='utf-8')
with (H / 'AIG_STRUCT_DIFF_V2.csv').open('w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f); w.writerow(['view', 'none_inst', 'cur_inst', 'none_nets', 'cur_nets', 'type_diff', 'n_removed', 'n_added', 'nets_removed', 'nets_added', 'aig_status'])
    for r in rows:
        w.writerow([r[k] for k in ('view', 'none_inst', 'cur_inst', 'none_nets', 'cur_nets', 'type_diff', 'n_removed', 'n_added', 'nets_removed', 'nets_added', 'aig_status')])
print(json.dumps([{k: r[k] for k in ('view', 'none_inst', 'cur_inst', 'none_nets', 'cur_nets', 'type_diff', 'n_removed', 'n_added', 'aig_status')} for r in rows], ensure_ascii=False))
