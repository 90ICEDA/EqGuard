"""Consistency checks for aig exclusion + panel 20; stage2a manifest hashes."""
import csv, hashlib, json
from pathlib import Path
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); H = R / '_p0pilot/heldout_composition_20261110'
issues = []
st1 = json.loads((H / 'KEEP_STAGE1.json').read_text(encoding='utf-8'))
ka = json.loads((H / 'KEEP_AUDIT.json').read_text(encoding='utf-8'))
ad = json.loads((H / 'AIG_STRUCT_DIFF_V2.json').read_text(encoding='utf-8'))
st = json.loads((H / 'STATUS.json').read_text(encoding='utf-8'))
for name, d in (('KEEP_STAGE1', st1), ('KEEP_AUDIT', ka), ('AIG_STRUCT_DIFF_V2', ad)):
    s = json.dumps(d, ensure_ascii=False)
    if 'aig_unresolved' in s or 'structural same' in s or '15/14' in s:
        issues.append(f'{name}: forbidden string')
if ka.get('aig_conclusion') != 'aig_not_usable_for_keep_ablation': issues.append('KEEP_AUDIT aig status')
if st1.get('aig_conclusion') != 'aig_not_usable_for_keep_ablation': issues.append('KEEP_STAGE1 aig status')
if ad.get('aig_status') != 'aig_not_usable_for_keep_ablation': issues.append('AIG status')
# table/csv rows
csv_rows = list(csv.DictReader((H / 'KEEP_STAGE1_TABLE.csv').open(encoding='utf-8-sig')))
if len(csv_rows) != len(st1['table']): issues.append('table/csv row count')
# panel
pc = ka.get('panel_contract', {})
if pc.get('combos') != 20 or pc.get('total_syntheses') != 40: issues.append('panel 20/40')
# stage2a
s2 = json.loads((H / 'KEEP_STAGE2A.json').read_text(encoding='utf-8'))
if s2.get('supported') != 4 or s2.get('total') != 4: issues.append('stage2a 4/4')
mp = R / 'generate_trans/keepab_panel_20_stage2a/ys_manifest.csv'
sha = hashlib.sha256(mp.read_bytes()).hexdigest() if mp.exists() else None
out = dict(status='PASS' if not issues else 'PARTIAL', issues=issues,
           table_rows=len(st1['table']), csv_rows=len(csv_rows), panel=pc.get('combos'),
           total_syntheses=pc.get('total_syntheses'), stage2a=s2.get('supported'),
           stage2a_manifest_sha=sha)
(H / 'CHECK_KEEP_STATE.json').write_text(json.dumps(out, indent=2), encoding='utf-8')
print(json.dumps(out, ensure_ascii=False))
