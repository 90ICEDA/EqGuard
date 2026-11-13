"""Diagnose aig inconsistency (B: name-preserving metric breaks under aig), update status."""
import json
from pathlib import Path
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); H = R / '_p0pilot/heldout_composition_20261110'
ka = json.loads((H / 'KEEP_AUDIT.json').read_text(encoding='utf-8'))
ka['aig_diagnosis'] = dict(conclusion='B',
    reason='aig conversion renames/rebuilds Trojan instances (source TrojanAT1 -> output TrojanA_t1); none and cur outputs both contain the same 4 transformed names, so anchor_text_surv=0.444 is a name-metric artifact, not keep retention',
    evidence=dict(source_trojan_names=9, none_trojan_names=4, cur_trojan_names=4,
                  example=['TrojanAT1 -> TrojanA_t1'],
                  keep_attrs_in_source=False,
                  note='text-name survival invalid under aig; use structural/cell-level metric'),
    extra_syntheses=0)
ka['keep_removal_pilot_supported'] = False
ka['keep_removal_scope_note'] = 'stage1: 4/6 supported; aig text metric invalid -> recipe-specific structural check needed'
ka['panel_contract']['decision'] = 'not_started_metric_revision_needed'
ka['panel_contract']['note'] = 'under aig, anchor survival must be cell/structure-level, not text-name'
(H / 'KEEP_AUDIT.json').write_text(json.dumps(ka, indent=2), encoding='utf-8')
st = json.loads((H / 'STATUS.json').read_text(encoding='utf-8'))
st['phase'] = 'no_keep_stage1_aig_diagnosis'
st['nokeep'] = dict(st.get('nokeep', {}), keep_removal='stage1_inconsistent (aig)', stage1='4/6 supported; aig inconsistent',
                    aig_diagnosis='B: text-name metric invalid under aig')
st['keep_removal_pilot_supported'] = False
st['not_done'] = list(dict.fromkeys(st.get('not_done', []) + ['structural anchor metric', 'panel-wide keep removal', 'CEC', 'panel GT']))
st['note'] = 'stage1 12 syntheses; aig diagnosis B; panel/CEC not started'
(H / 'STATUS.json').write_text(json.dumps(st, indent=2), encoding='utf-8')
print('ok')
