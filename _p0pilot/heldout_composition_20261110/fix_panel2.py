"""Panel coverage fix, keep logic audit, GT availability (read-only), L_cone boundary append."""
import csv, json
from pathlib import Path
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); H = R / '_p0pilot/heldout_composition_20261110'
p = H / 'NO_KEEP_PANEL.json'; d = json.loads(p.read_text(encoding='utf-8'))
panel = d['panel']
for x in panel:
    x['cec_covered'] = bool(x['cec_rows']); x['keep_variant'] = x['keep_files'] > 0; x['no_keep_variant'] = False
    x['classification'] = 'plain design only; keep/no-keep side not proven'
d['coverage'] = dict(combos=len(panel), cec_covered=sum(1 for x in panel if x['cec_rows']),
                     manifest_covered=sum(1 for x in panel if x['manifest_rows']),
                     paired=sum(1 for x in panel if x['paired']), keep_variant=sum(1 for x in panel if x['keep_files']),
                     no_keep_variant=0)
p.write_text(json.dumps(d, indent=2), encoding='utf-8')
# keep audit
ka = dict(schemes={'none': 'no keep commands issued', 'cur': 'keep trojan/control nets',
                   'bnd': 'keep register Q + PO + trojan/control', 'full': 'setattr keep 1 w:*'},
          none_logic=['keep_cmds("none") returns []', 'body = proc + opt -full',
                      'write_verilog -noattr (attributes hidden in output, not removal before opt)'],
          plain_file_side='unknown; single plain design file per combo, no keep/noattr pair',
          keep_removal_proven=False,
          minimal_counterexample=['source netlist containing (* keep *) attribute',
                                 'run scheme none; check opt log/stat whether kept cell survives',
                                 'inspect post-opt netlist for keep attribute/lines',
                                 'compare against explicit keep variant'])
(H / 'KEEP_AUDIT.json').write_text(json.dumps(ka, indent=2), encoding='utf-8')
# GT availability (candidates only; mapping unverified)
gt = {}
for base in (R / 'data/verilog_data/mappings', R / 'generate_trans/mappings'):
    if base.exists():
        gt[str(base.relative_to(R))] = [x.name for x in base.iterdir()][:20]
(H / 'GT_AVAILABILITY.json').write_text(json.dumps(dict(
    candidates=gt,
    endpoints={k: 'unknown (not verified per host/design)' for k in ('DFF_Q', 'DFF_D', 'PO', 'PI')},
    note='weak MIL / structural reachability / CEC equivalence are not functional GT'), indent=2), encoding='utf-8')
# L_cone boundary append
q = R / '10.15/00_说明/返回审计_Lcone评价闭环_20261110.md'
if '机制探针' not in q.read_text(encoding='utf-8'):
    q.write_bytes(q.read_bytes() + """

## 边界（2026-11-10 追加）

- L_cone 使用 group_A 的 502 正例 / 11,187 锥，仅作机制探针；不替代四组组成结论，也不与 hoco（287/10,742）横向比较。
""".encode('utf-8'))
# STATUS
st = json.loads((H / 'STATUS.json').read_text(encoding='utf-8'))
st['phase'] = 'lcone_closed_nokeep_panel_requires_rebuild'
st['nokeep'] = dict(combos=len(panel), cec_covered=0, paired=0, keep_variant=0, no_keep_variant=0,
                    gt='unknown', keep_removal='unproven')
(H / 'STATUS.json').write_text(json.dumps(st, indent=2), encoding='utf-8')
# CSV rewrite with coverage
with (H / 'NO_KEEP_PANEL.csv').open('w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f); w.writerow(['host', 'kind', 'recipe', 'n_files', 'keep', 'plain', 'paired', 'cec_rows', 'cec_covered', 'manifest_rows', 'keep_variant', 'no_keep_variant', 'needs_synthesis'])
    for x in panel:
        w.writerow([x['host'], x['kind'], x['recipe'], x['n_files'], x['keep_files'], x['plain_files'], x['paired'],
                    x['cec_rows'], x['cec_covered'], x['manifest_rows'], x['keep_variant'], x['no_keep_variant'], x['needs_synthesis']])
print(json.dumps(d['coverage'], ensure_ascii=False))
