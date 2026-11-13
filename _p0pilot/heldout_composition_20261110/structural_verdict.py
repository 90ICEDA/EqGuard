"""Update stage1/KEEP_AUDIT/STATUS with structural verdict."""
import csv, json
from pathlib import Path
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); H = R / '_p0pilot/heldout_composition_20261110'
sm = json.loads((H / 'STRUCT_METRICS.json').read_text(encoding='utf-8'))['rows']
st1 = json.loads((H / 'KEEP_STAGE1.json').read_text(encoding='utf-8'))
by = {(r['view'], r['recipe']): r for r in sm}
for t in st1['table']:
    r = by[(t['view'], t['recipe'])]
    t['structural_none_anchor'] = r['none_anchor']; t['structural_cur_anchor'] = r['cur_anchor']
    t['d_anchor'] = r['d_anchor']; t['d_inst'] = r['d_inst']
    t['structural_status'] = 'supported' if r['d_anchor'] < 0 else ('same' if r['d_anchor'] == 0 else 'unresolved')
st1['structural_supported'] = sum(1 for t in st1['table'] if t['structural_status'] == 'supported')
st1['aig_conclusion'] = 'aig_text_metric_invalid_and_structure_same'
(H / 'KEEP_STAGE1.json').write_text(json.dumps(st1, indent=2), encoding='utf-8')
with (H / 'KEEP_STAGE1_TABLE.csv').open('w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f); w.writerow(['host', 'view', 'recipe', 'none_anchor', 'cur_anchor', 'd_anchor', 'd_inst', 'structural_status'])
    for t in st1['table']:
        w.writerow([t['host'], t['view'], t['recipe'], t['structural_none_anchor'], t['structural_cur_anchor'], t['d_anchor'], t['d_inst'], t['structural_status']])
ka = json.loads((H / 'KEEP_AUDIT.json').read_text(encoding='utf-8'))
ka['aig_conclusion'] = 'B: text metric invalid; structural anchor cells 0 in both none and cur'
ka['stage1_structural'] = dict(supported=st1['structural_supported'], total=len(st1['table']),
                               aig='same (0 vs 0 anchor cells)', conclusion='panel not started')
ka['keep_removal_pilot_supported'] = False
(H / 'KEEP_AUDIT.json').write_text(json.dumps(ka, indent=2), encoding='utf-8')
stt = json.loads((H / 'STATUS.json').read_text(encoding='utf-8'))
stt['phase'] = 'no_keep_stage1_structural_recheck'
stt['nokeep'] = dict(stt.get('nokeep', {}), keep_removal='stage1_inconsistent (aig: structural same)',
                     stage1=f"{st1['structural_supported']}/6 structural supported; aig same",
                     aig_conclusion='text metric invalid; structural 0 vs 0')
stt['note'] = 'structural recheck done; panel/CEC not started'
(H / 'STATUS.json').write_text(json.dumps(stt, indent=2), encoding='utf-8')
print(json.dumps(dict(supported=st1['structural_supported'], aig=ka['aig_conclusion']), ensure_ascii=False))
