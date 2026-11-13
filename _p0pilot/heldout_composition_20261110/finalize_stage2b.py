"""Finalize stage2b/panel statuses."""
import hashlib, json
from pathlib import Path
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); H = R / '_p0pilot/heldout_composition_20261110'
mp = R / 'generate_trans/keepab_panel_20_stage2b/ys_manifest.csv'
sha = hashlib.sha256(mp.read_bytes()).hexdigest() if mp.exists() else None
ka = json.loads((H / 'KEEP_AUDIT.json').read_text(encoding='utf-8'))
ka['panel_contract'].update(dict(decision='completed_20_of_20_supported', syntheses_done=40,
                                 stage2a='4/4', stage2b='16/16', cec='not run'))
ka['stage2b'] = dict(combos=16, supported=16, manifest_sha=sha, note='abc/nand only; aig excluded')
(H / 'KEEP_AUDIT.json').write_text(json.dumps(ka, indent=2), encoding='utf-8')
st = json.loads((H / 'STATUS.json').read_text(encoding='utf-8'))
st['nokeep'] = dict(st.get('nokeep', {}), keep_removal='20/20 supported (abc/nand)', stage1='4/6 (aig excluded)',
                    panel='20/20 supported; 40 syntheses done', cec='not run', gt='not built')
st['note'] = 'panel 20/20 supported; CEC/GT not done; aig excluded'
(H / 'STATUS.json').write_text(json.dumps(st, indent=2), encoding='utf-8')
(H / 'PANEL_STATUS.json').write_text(json.dumps(dict(total_combos=20, supported=20, inconsistent=0, syntheses=40,
                                                    stage2a=4, stage2b=16, manifest_sha=sha,
                                                    note='abc/nand only; aig excluded; CEC not run'), indent=2), encoding='utf-8')
print('ok', sha)
