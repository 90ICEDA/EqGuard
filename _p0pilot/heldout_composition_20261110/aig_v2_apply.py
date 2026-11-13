"""Apply aig not_usable verdict; panel 20 combos; remove 15/14 wording."""
import json
from pathlib import Path
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); H = R / '_p0pilot/heldout_composition_20261110'
ad = json.loads((H / 'AIG_STRUCT_DIFF_V2.json').read_text(encoding='utf-8'))
ka = json.loads((H / 'KEEP_AUDIT.json').read_text(encoding='utf-8'))
ka['aig_conclusion'] = 'aig_not_usable_for_keep_ablation'
ka['aig_anchor_metric'] = 'not applicable; cleaned type diff only INV -1, no anchor localization'
ka['aig_clean_diff'] = ad['rows']
ka['stage1_structural'] = dict(supported=4, total=6, aig='excluded (not usable)', conclusion='panel 20 combos')
ka['panel_contract'] = dict(no_keep='none', keep='cur', bnd='not used', combos=20,
                            hosts=5, recipes=['abc', 'nand'], injections=2,
                            synthesis_per_combo=2, total_syntheses=40,
                            naming='{host}__{view}__{scheme}__{recipe}.v under keepab_panel_20/conv/{host}/',
                            cec='separate, not run; clean != CEC PASS',
                            aig='excluded: type diff only INV -1; no anchor localization; metric not usable')
(H / 'KEEP_AUDIT.json').write_text(json.dumps(ka, indent=2), encoding='utf-8')
st1 = json.loads((H / 'KEEP_STAGE1.json').read_text(encoding='utf-8'))
st1['aig_conclusion'] = 'aig_not_usable_for_keep_ablation'
st1['panel'] = dict(combos=20, total_syntheses=40, aig='excluded')
(H / 'KEEP_STAGE1.json').write_text(json.dumps(st1, indent=2), encoding='utf-8')
st = json.loads((H / 'STATUS.json').read_text(encoding='utf-8'))
st['nokeep'] = dict(st.get('nokeep', {}), keep_removal='4/6 supported; aig excluded (not usable)',
                    stage1='4/6 supported; aig excluded', panel='20 combos defined, not started')
st['note'] = 'aig cleaned diff INV -1 only; aig excluded; panel 20 combos defined, not started'
(H / 'STATUS.json').write_text(json.dumps(st, indent=2), encoding='utf-8')
print('ok')
