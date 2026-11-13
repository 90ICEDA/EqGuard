"""Apply corrected aig verdict across STRUCT_METRICS/KEEP_STAGE1/KEEP_AUDIT/STATUS."""
import json
from pathlib import Path
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); H = R / '_p0pilot/heldout_composition_20261110'
sm = json.loads((H / 'STRUCT_METRICS.json').read_text(encoding='utf-8'))
for r in sm['rows']:
    if r['recipe'] == 'aig':
        r['structural_status'] = 'aig_unresolved'
        r['aig_note'] = 'structure differs (523/524 inst; 599/602 or 599/599 nets); anchor-name metric not applicable'
sm['aig_status'] = 'aig_anchor_metric_not_applicable'
sm['aig_conclusion'] = 'aig_structure_differs_unresolved'
(H / 'STRUCT_METRICS.json').write_text(json.dumps(sm, indent=2), encoding='utf-8')
st1 = json.loads((H / 'KEEP_STAGE1.json').read_text(encoding='utf-8'))
for t in st1['table']:
    if t['recipe'] == 'aig':
        t['structural_status'] = 'aig_unresolved'
st1['aig_conclusion'] = 'aig_structure_differs_unresolved'
st1['aig_anchor_metric'] = 'not_applicable (no reliable source-anchor cone projection)'
(H / 'KEEP_STAGE1.json').write_text(json.dumps(st1, indent=2), encoding='utf-8')
ka = json.loads((H / 'KEEP_AUDIT.json').read_text(encoding='utf-8'))
ka['aig_conclusion'] = 'aig_structure_differs_unresolved'
ka['aig_anchor_metric'] = 'not_applicable; structural diff (523/524 inst) cannot be attributed to keep'
ka['stage1_structural'] = dict(supported=4, total=6, aig='unresolved', conclusion='panel not started')
(H / 'KEEP_AUDIT.json').write_text(json.dumps(ka, indent=2), encoding='utf-8')
st = json.loads((H / 'STATUS.json').read_text(encoding='utf-8'))
st['nokeep'] = dict(st.get('nokeep', {}), keep_removal='4/6 supported; aig unresolved',
                    stage1='4/6 supported; aig unresolved', aig_conclusion='aig_structure_differs_unresolved')
st['note'] = 'stage1 structural recheck: 4/6 supported; aig unresolved; panel/CEC not started'
(H / 'STATUS.json').write_text(json.dumps(st, indent=2), encoding='utf-8')
print('ok')
