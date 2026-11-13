"""Append L_cone corrections, verify I, and build no-keep panel inventory (read-only)."""
import csv, json, re
from pathlib import Path
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
H = R / '_p0pilot/heldout_composition_20261110'
BASE = R / 'generate_trans/yslib_test'
HOSTS = ('rs232t1000', 's15850t100', 's35932t200', 's38417t100', 's38584t100')
KINDS = ('injalpha', 'injdelta'); RECS = ('ys_abc', 'ys_aig', 'ys_nand')
# 1) append correction to old audit
p = R / '10.15/00_说明/返回审计_Lcone三seed_20261110.md'
if '数值更正' not in p.read_text(encoding='utf-8'):
    p.write_bytes(p.read_bytes() + """

## 数值更正（2026-11-10 追加，不改写历史）

- 旧表 N：seed1 .2913 / seed2 .3021 → 正确 **.2731 / .3448**；
- 旧表 C：seed1 .0235 / seed2 .0095 → 正确 **.0811 / .0580**；
- 依据 `LCONE_SEEDS12.json` 与 `LCONE_EVAL_V3.json`；旧表作废，**V3 为准**。
""".encode('utf-8'))
# 2) correction note for last entries
cc = json.loads((H / 'CORRECTION_LCONE_FULL.json').read_text(encoding='utf-8'))
for k, v in cc.items():
    if v.get('point') == 'last':
        v['note'] = (v.get('note', '') + '; best_step only recorded; actual completed step = completed').strip('; ')
(H / 'CORRECTION_LCONE_FULL.json').write_text(json.dumps(cc, indent=2), encoding='utf-8')
# 3) SAT docs check
for name in ('SAT作用证明.md', 'SAT工作总结.md'):
    q = R / '10.15/00_说明' / name
    t = q.read_text(encoding='utf-8', errors='ignore')
    if any(x in t for x in ('0.2913', '0.3021', '0.0235', '0.0095')):
        q.write_bytes(q.read_bytes() + """

### 追加更正（2026-11-10）

- L_cone 旧 N/C 数值（N seed1 .2913、seed2 .3021；C seed1 .0235、seed2 .0095）作废；
- 正确值以 `LCONE_EVAL_V3.json` 为准：N seed1 .2731、seed2 .3448；C seed1 .0811、seed2 .0580。
""".encode('utf-8'))
# 4) recompute I from V3
d = json.loads((H / 'LCONE_EVAL_V3.json').read_text(encoding='utf-8'))
agg = {}
for point in ('best', 'last'):
    for arm in ('NC1', 'NC01'):
        for fam in ('base', 'add'):
            ds = [d[f'{seed}_{arm}_{point}'][f'{fam}_ap'] - d[f'{seed}_N_{point}'][f'{fam}_ap'] for seed in (42, 1, 2)]
            agg[f'{arm}_{point}_{fam}'] = ds
(H / 'LCONE_I_RECHECK.json').write_text(json.dumps(agg, indent=2), encoding='utf-8')
# 5) panel inventory
files = [p for p in BASE.rglob('*') if p.is_file()]
cec_rows = []
cec = BASE / 'cec_tolib.csv'
if cec.exists(): cec_rows = list(csv.DictReader(cec.open(encoding='utf-8-sig')))
man = BASE / 'convert_manifest.csv'
man_rows = list(csv.DictReader(man.open(encoding='utf-8-sig'))) if man.exists() else []
panel = []
for h in HOSTS:
    for k in KINDS:
        for r in RECS:
            tok = f'{h}__{k}'
            hits = [p for p in files if tok in p.name and r in p.name]
            keep = [p for p in hits if 'keep' in p.name.lower()]
            plain = [p for p in hits if 'keep' not in p.name.lower()]
            def mod(p):
                try:
                    for line in p.read_text(encoding='utf-8', errors='ignore').splitlines()[:20]:
                        m = re.match(r'\s*module\s+([A-Za-z0-9_$]+)', line)
                        if m: return m.group(1)
                except Exception:
                    pass
                return None
            mods = [mod(p) for p in hits]
            suffix_ok = all(m and m.split('_')[-1] in p.stem.split('_')[-1] for m, p in zip(mods, hits)) if hits else None
            cec_hits = [x for x in cec_rows if x.get('host') == h and x.get('recipe') == r and k in x.get('stem', '')]
            man_hits = [x for x in man_rows if x.get('host') == h and x.get('recipe') == r and k in x.get('stem', '')]
            panel.append(dict(host=h, kind=k, recipe=r, n_files=len(hits), keep_files=len(keep), plain_files=len(plain),
                              paired=bool(keep and plain), names=[p.name for p in hits],
                              keep_names=[p.name for p in keep], plain_names=[p.name for p in plain],
                              module_names=mods, module_suffix_ok=suffix_ok,
                              cec_rows=len(cec_hits), cec_empty=sum(1 for x in cec_hits if not (x.get('cec') or '').strip()),
                              manifest_rows=len(man_hits), manifest_clean=sum(1 for x in man_hits if str(x.get('clean', '')).lower() == 'true'),
                              needs_synthesis=(not (keep and plain))))
gt = {}
for token in ('DFF', 'mappings', 'alpha', 'delta'):
    gt[token] = [str(p.relative_to(R)) for p in R.rglob(f'*{token}*') if p.is_file()][:10]
(H / 'NO_KEEP_PANEL.json').write_text(json.dumps(dict(panel=panel, cec_rows=len(cec_rows),
                                                     cec_empty=sum(1 for x in cec_rows if not (x.get('cec') or '').strip()),
                                                     manifest_rows=len(man_rows), gt=gt), indent=2), encoding='utf-8')
with (H / 'NO_KEEP_PANEL.csv').open('w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f); w.writerow(['host', 'kind', 'recipe', 'n_files', 'keep', 'plain', 'paired', 'mod_ok', 'cec_rows', 'cec_empty', 'needs_synthesis'])
    for x in panel:
        w.writerow([x['host'], x['kind'], x['recipe'], x['n_files'], x['keep_files'], x['plain_files'], x['paired'], x['module_suffix_ok'], x['cec_rows'], x['cec_empty'], x['needs_synthesis']])
print(json.dumps(dict(panel=len(panel), paired=sum(1 for x in panel if x['paired']), needs=sum(1 for x in panel if x['needs_synthesis']),
                      cec=len(cec_rows), empty=sum(1 for x in cec_rows if not (x.get('cec') or '').strip())), ensure_ascii=False))
