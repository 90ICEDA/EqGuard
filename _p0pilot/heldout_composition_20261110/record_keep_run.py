"""Record executed keep counterexample + variant strategy."""
import json
from pathlib import Path
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); H = R / '_p0pilot/heldout_composition_20261110'
ka = json.loads((H / 'KEEP_AUDIT.json').read_text(encoding='utf-8'))
ka['executed'] = True
ka['synthesis_runs'] = 3
ka['keep_removal_proven'] = True
ka['run'] = dict(host='rs232t1000', view='rs232t1000__injalpha_d1_s42', recipe='abc',
                 schemes=['none', 'cur', 'bnd'], out='generate_trans/keepab_gtcheck', skip_cec=True,
                 evidence=dict(none_anchor_surv=0.0, cur_bnd_anchor_surv=0.444,
                               none_out_insts=274, cur_bnd_out_insts=273, dffq_surv=0.916,
                               keep_strings_in_conv_netlists=0),
                 artifacts=['generate_trans/keepab_gtcheck/ys_manifest.csv',
                            'generate_trans/keepab_gtcheck/logs/', 'generate_trans/keepab_gtcheck/conv/',
                            'generate_trans/keepab_gtcheck/out /'])
ka['minimal_counterexample']['status'] = 'executed'
ka['variant_strategy'] = dict(
    no_keep='none products', keep='cur products (bnd as sensitivity)',
    naming='{host}__{view}__{scheme}__{recipe}.v under keepab_gtcheck/conv/{host}/',
    per_combo_runs=2, panel_combos=30, panel_syntheses=60, cec='not run; required separately',
    note='keep side cur; bnd only sensitivity; do not fabricate pairs')
(H / 'KEEP_AUDIT.json').write_text(json.dumps(ka, indent=2), encoding='utf-8')
st = json.loads((H / 'STATUS.json').read_text(encoding='utf-8'))
st['keep_counterexample'] = 'executed_keep_removal_proven'
st['keep_variant_strategy'] = 'none=no-keep, cur=keep; 30 combos x2 = 60 syntheses planned, not run'
st['synthesis_cec'] = 'pilot 3 syntheses done; panel and CEC not started'
(H / 'STATUS.json').write_text(json.dumps(st, indent=2), encoding='utf-8')
print('ok')
