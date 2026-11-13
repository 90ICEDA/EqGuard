"""Finalize CEC/status text and supersede old manifest."""
import json
from pathlib import Path
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); B = R / 'generate_trans/keepab_panel_20_stage2b'
H = R / '_p0pilot/heldout_composition_20261110'
sha = json.loads((H / 'MANIFEST_STAGE2B.json').read_text(encoding='utf-8'))['sha256']
(B / 'ys_manifest.SUPERSEDED').write_text('superseded by MANIFEST_STAGE2B.csv sha ' + sha, encoding='utf-8')
st2 = json.loads((H / 'KEEP_STAGE2B.json').read_text(encoding='utf-8'))
st2['manifest_rows'] = 32; st2['combos'] = 16; st2['manifest_sha'] = sha; st2['cec'] = 'skipped (all rows)'
(H / 'KEEP_STAGE2B.json').write_text(json.dumps(st2, indent=2), encoding='utf-8')
p = json.loads((H / 'PANEL_STATUS.json').read_text(encoding='utf-8'))
p.update(dict(manifest_rows=32, combos=20, stage2b_combos=16, manifest_sha=sha,
              cec='skipped (all rows); not PASS', cec_plan='40 none/cur pairs, not run',
              note='CEC not run; clean != CEC PASS; aig excluded as not usable'))
(H / 'PANEL_STATUS.json').write_text(json.dumps(p, indent=2), encoding='utf-8')
ka = json.loads((H / 'KEEP_AUDIT.json').read_text(encoding='utf-8'))
ka['cec'] = dict(status='not_run', manifest='skipped', note='clean is not CEC PASS', plan='40 none/cur pairs')
(H / 'KEEP_AUDIT.json').write_text(json.dumps(ka, indent=2), encoding='utf-8')
s = json.loads((H / 'STATUS.json').read_text(encoding='utf-8'))
s['nokeep'] = dict(s.get('nokeep', {}), cec='not run', manifest_sha=sha, panel='20/20 supported; frozen')
s['note'] = 'panel frozen 20/20 supported; manifest rebuilt 32 rows; CEC/GT not run'
(H / 'STATUS.json').write_text(json.dumps(s, indent=2), encoding='utf-8')
# scan forbidden strings
bad = []
for f in H.rglob('*.json'):
    try: t = f.read_text(encoding='utf-8', errors='ignore')
    except: continue
    if 'PASS(bypass-gate)' in t or '5dbf0e62' in t: bad.append(str(f.relative_to(H)))
    if 'cec' in t and 'PASS(bypass' in t: bad.append(str(f.relative_to(H)))
(H / 'CEC_TEXT_CHECK.json').write_text(json.dumps(dict(forbidden_hits=bad, sha=sha), indent=2), encoding='utf-8')
print(json.dumps(dict(sha=sha, bad=bad), ensure_ascii=False))
