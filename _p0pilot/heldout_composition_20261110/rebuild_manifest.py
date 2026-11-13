"""Rebuild stage2b 32-row manifest from logs; recheck metrics and panel status."""
import csv, hashlib, json, re
from collections import Counter
from pathlib import Path
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); B = R / 'generate_trans/keepab_panel_20_stage2b'
H = R / '_p0pilot/heldout_composition_20261110'
LOGS = B / 'logs'; CONV = B / 'conv'
TYPES = ('AND', 'OR', 'XOR', 'XNOR', 'MUX', 'INV', 'SDFF', 'DFF', 'OTHER')
SKIP = {'module', 'input', 'output', 'inout', 'wire', 'assign', 'parameter', 'localparam', 'endmodule', 'end'}


def typ(t):
    u = t.upper()
    for k in ('XNOR', 'XOR', 'SDFF', 'DFF', 'MUX', 'NAND', 'NOR', 'AND', 'OR', 'INV', 'BUF'):
        if k in u: return {'NAND': 'AND', 'NOR': 'OR', 'BUF': 'OTHER'}.get(k, k)
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
                types={k: types.get(k, 0) for k in TYPES}, cells=len(cs))


rows = []
issues = []
for rc in sorted(LOGS.glob('*.rc')):
    stem = rc.stem
    m = re.match(r'(.+?)__(keepnone|keepcur)__ys_(abc|nand)$', stem)
    if not m: continue
    prefix, scheme, rec = m.group(1), m.group(2), m.group(3)
    host = prefix.split('__')[0]
    view = prefix
    conv = CONV / host / f'{stem}.v'
    rcval = (rc.read_text(encoding='utf-8', errors='ignore').strip() or 'NA')
    secs = (LOGS / f'{stem}.secs').read_text(encoding='utf-8', errors='ignore').strip() if (LOGS / f'{stem}.secs').exists() else ''
    ok = (rcval == '0' and conv.exists() and conv.stat().st_size > 0)
    met = parse(conv) if conv.exists() else None
    rows.append(dict(host=host, view=view, recipe=rec, scheme=scheme, rc=rcval, secs=secs,
                     log_path=str((LOGS / f'{stem}.log').relative_to(R)), stdout_path=str((LOGS / f'{stem}.stdout').relative_to(R)),
                     conv_path=str(conv.relative_to(R)), out_path=str((B / 'out ' / host).relative_to(R)),
                     bytes=(conv.stat().st_size if conv.exists() else 0), cells=(met['cells'] if met else 0),
                     cec='skipped', status='ok' if ok else 'failed'))
    if not ok: issues.append(stem)
if len(rows) != 32: issues.append(f'row count {len(rows)}')
for r in rows:
    if r['status'] != 'ok': issues.append(r['view'] + ' failed')
# manifest
mp = H / 'MANIFEST_STAGE2B.csv'
with mp.open('w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
sha = hashlib.sha256(mp.read_bytes()).hexdigest()
# metrics recompute 16 combos
metr = {}
for r in rows:
    if r['scheme'] == 'keepnone': metr.setdefault((r['view'], r['recipe']), {})['none'] = parse(CONV / r['host'] / Path(r['conv_path']).name)
    else:
        metr.setdefault((r['view'], r['recipe']), {})['cur'] = parse(CONV / r['host'] / Path(r['conv_path']).name)
stage = json.loads((H / 'KEEP_STAGE2B.json').read_text(encoding='utf-8'))
mism = []
for row in stage['rows']:
    m = metr[(row['view'], row['recipe'])]
    for k, key in (('none', 'none_anchor'), ('cur', 'cur_anchor')):
        if m[k]['anchor'] != row[key]: mism.append((row['view'], row['recipe'], key))
panel = json.loads((H / 'PANEL_STATUS.json').read_text(encoding='utf-8'))
panel.update(dict(manifest_rows=32, combos=20, stage2b_combos=16, manifest_sha=sha, cec='skipped (all rows)',
                  note='CEC not run; clean != CEC PASS; aig excluded as not usable'))
(H / 'PANEL_STATUS.json').write_text(json.dumps(panel, indent=2), encoding='utf-8')
(H / 'MANIFEST_STAGE2B.json').write_text(json.dumps(dict(rows=32, sha256=sha, issues=issues, metric_mismatches=mism), indent=2), encoding='utf-8')
print(json.dumps(dict(rows=len(rows), issues=issues, sha=sha, mismatches=len(mism)), ensure_ascii=False))
