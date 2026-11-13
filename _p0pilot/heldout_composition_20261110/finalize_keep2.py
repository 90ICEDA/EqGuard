"""Finalize keep pilot status: two hosts, scope, budget contract."""
import hashlib, json
from pathlib import Path
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); H = R / '_p0pilot/heldout_composition_20261110'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
ka = json.loads((H / 'KEEP_AUDIT.json').read_text(encoding='utf-8'))
ka['command_status'] = 'executed_pilot'
ka['keep_removal_scope'] = [
    dict(host='rs232t1000', view='rs232t1000__injalpha_d1_s42', recipe='abc', schemes=['none', 'cur', 'bnd'],
         synthesis_runs=3, manifest_sha=sha(R / 'generate_trans/keepab_gtcheck/ys_manifest.csv'),
         artifacts='generate_trans/keepab_gtcheck/'),
    dict(host='s15850t100', view='s15850t100__injalpha_d1_s42', recipe='abc', schemes=['none', 'cur', 'bnd'],
         synthesis_runs=3, manifest_sha=sha(R / 'generate_trans/keepab_gtcheck_s15850/ys_manifest.csv'),
         artifacts='generate_trans/keepab_gtcheck_s15850/')]
ka['keep_removal_pilot_supported'] = True
ka['minimal_counterexample']['commands'] = [
    'py phase2/ys/keep_ablation.py --host rs232t1000 --views rs232t1000__injalpha_d1_s42 --recipes abc --schemes none,cur,bnd --out generate_trans/keepab_gtcheck --skip-cec --timeout 900',
    'py phase2/ys/keep_ablation.py --host s15850t100 --views s15850t100__injalpha_d1_s42 --recipes abc --schemes none,cur,bnd --out generate_trans/keepab_gtcheck_s15850 --skip-cec --timeout 900']
ka['minimal_counterexample']['logs'] = ['generate_trans/keepab_gtcheck/logs/', 'generate_trans/keepab_gtcheck_s15850/logs/']
ka['pilot_metrics'] = [
    dict(host='rs232t1000', none_anchor_surv=0.0, cur_bnd_anchor_surv=0.444, dffq=0.916, out_insts_none=274, out_insts_cur=273),
    dict(host='s15850t100', none_anchor_surv=0.0, cur_bnd_anchor_surv=0.444, dffq=1.0, out_insts_none=2644, out_insts_cur=2530)]
ka['panel_contract'] = dict(no_keep='none', keep='cur', bnd='sensitivity only', combos=30,
                            synthesis_per_combo=2, total_syntheses=60,
                            naming='{host}__{view}__{scheme}__{recipe}.v under keepab_panel/conv/{host}/',
                            cec='separate, not run; clean != CEC PASS', budget='~1-3 min/synthesis + CEC')
(H / 'KEEP_AUDIT.json').write_text(json.dumps(ka, indent=2), encoding='utf-8')
st = json.loads((H / 'STATUS.json').read_text(encoding='utf-8'))
st['not_done'] = [x for x in st.get('not_done', []) if x != 'keep removal proof']
for x in ('panel-wide keep removal', 'CEC', 'panel GT'):
    if x not in st['not_done']: st['not_done'].append(x)
st['nokeep'] = dict(st.get('nokeep', {}), keep_removal='pilot_supported (rs232t1000, s15850t100 / injalpha / abc)',
                    paired=0, combos=30)
st['note'] = 'pilot 6 syntheses done (2 hosts); panel/CEC not started'
st['synthesis_cec'] = 'pilot 6 syntheses done; 60-synthesis panel + CEC not started'
st['keep_removal_pilot_supported'] = True
(H / 'STATUS.json').write_text(json.dumps(st, indent=2), encoding='utf-8')
print('ok')
