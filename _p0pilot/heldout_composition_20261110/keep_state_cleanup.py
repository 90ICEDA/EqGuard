"""State cleanup for aig exclusion + stage2a helpers."""
import csv, json, re
from pathlib import Path
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); H = R / '_p0pilot/heldout_composition_20261110'
# KEEP_STAGE1: mark aig rows excluded
st1 = json.loads((H / 'KEEP_STAGE1.json').read_text(encoding='utf-8'))
for t in st1['table']:
    if t['recipe'] == 'aig':
        t['structural_status'] = 'aig_not_usable_for_keep_ablation'
        t['excluded'] = True
        t['exclude_reason'] = 'type_diff only INV -1; no anchor localization; metric not usable for keep ablation'
st1['aig_conclusion'] = 'aig_not_usable_for_keep_ablation'
st1['aig_note'] = '指标不可用，不是 aig 无 keep 效应'
(H / 'KEEP_STAGE1.json').write_text(json.dumps(st1, indent=2), encoding='utf-8')
# AIG CSV rename columns
ad = json.loads((H / 'AIG_STRUCT_DIFF_V2.json').read_text(encoding='utf-8'))
for r in ad['rows']:
    r['type_diff_only'] = True
(H / 'AIG_STRUCT_DIFF_V2.json').write_text(json.dumps(ad, indent=2), encoding='utf-8')
with (H / 'AIG_STRUCT_DIFF_V2.csv').open('w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f)
    w.writerow(['view', 'none_inst', 'cur_inst', 'none_nets', 'cur_nets', 'type_diff',
                'name_diff_removed', 'name_diff_added', 'nets_removed', 'nets_added', 'type_diff_only', 'aig_status'])
    for r in ad['rows']:
        w.writerow([r['view'], r['none_inst'], r['cur_inst'], r['none_nets'], r['cur_nets'], r['type_diff'],
                    r['n_removed'], r['n_added'], r['nets_removed'], r['nets_added'], True, r['aig_status']])
# KEEP_AUDIT / STATUS strings
ka = json.loads((H / 'KEEP_AUDIT.json').read_text(encoding='utf-8'))
ka['aig_conclusion'] = 'aig_not_usable_for_keep_ablation'
ka['aig_note'] = '指标不可用，不是 aig 无 keep 效应'
ka['panel_contract'] = dict(ka.get('panel_contract', {}), combos=20, total_syntheses=40,
                            plan='5 hosts x 2 injections x {abc,nand} x none/cur')
(H / 'KEEP_AUDIT.json').write_text(json.dumps(ka, indent=2), encoding='utf-8')
st = json.loads((H / 'STATUS.json').read_text(encoding='utf-8'))
st['nokeep'] = dict(st.get('nokeep', {}), keep_removal='aig excluded; abc/nand 4/6 supported',
                    panel='20 combos / 40 syntheses contracted, not started')
st['note'] = 'aig excluded (not usable); stage2a pending'
(H / 'STATUS.json').write_text(json.dumps(st, indent=2), encoding='utf-8')
print('cleanup ok')
