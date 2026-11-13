"""Stage1 6-combo table + status update (inconsistent aig)."""
import csv, json
from pathlib import Path
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); H = R / '_p0pilot/heldout_composition_20261110'
rows = list(csv.DictReader((R / '10.15/01_数据与标签/A3_keep三方案/tables/a3_keep_pilot.csv').open(encoding='utf-8-sig')))
def get(r, k, d=0.0):
    try: return float(r.get(k) or d)
    except: return d
out = []
for r in rows:
    out.append(dict(view=r.get('view'), recipe=r.get('recipe'), scheme=r.get('scheme'),
                    anchor_surv=get(r, 'anchor_text_surv'), anchor_alive=get(r, 'anchor_text_alive'),
                    dffq=get(r, 'dffq_text_surv'), out_insts=int(get(r, 'out_insts')), keep_attrs=r.get('keep_list', ''),
                    cec=r.get('cec', '')))
# pair none/cur per (view,recipe)
pairs = {}
for x in out:
    pairs.setdefault((x['view'], x['recipe']), {})[x['scheme']] = x
table = []
for (v, rec), d in sorted(pairs.items()):
    n = d.get('none'); c = d.get('cur')
    ok = n and c and n['anchor_surv'] < 0.05 and c['anchor_surv'] > 0.05
    table.append(dict(host='rs232t1000', view=v, recipe=rec, none_anchor=n['anchor_surv'] if n else None,
                      cur_anchor=c['anchor_surv'] if c else None, none_insts=n['out_insts'] if n else None,
                      cur_insts=c['out_insts'] if c else None, supported=bool(ok),
                      status='supported' if ok else 'inconsistent'))
with (H / 'KEEP_STAGE1_TABLE.csv').open('w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f); w.writerow(['host', 'view', 'recipe', 'none_anchor', 'cur_anchor', 'none_insts', 'cur_insts', 'supported', 'status'])
    for x in table:
        w.writerow([x['host'], x['view'], x['recipe'], x['none_anchor'], x['cur_anchor'], x['none_insts'], x['cur_insts'], x['supported'], x['status']])
(H / 'KEEP_STAGE1.json').write_text(json.dumps(dict(table=table, combos=len(table), supported=sum(1 for x in table if x['supported']),
                                                    inconsistent=[x for x in table if not x['supported']]), indent=2), encoding='utf-8')
ka = json.loads((H / 'KEEP_AUDIT.json').read_text(encoding='utf-8'))
ka['command_status'] = 'executed_stage1_inconsistent'
ka['stage1'] = dict(host='rs232t1000', combos=len(table), supported=sum(1 for x in table if x['supported']),
                    inconsistent=[f"{x['view']}/{x['recipe']}" for x in table if not x['supported']])
ka['keep_removal_pilot_supported'] = False
ka['keep_removal_scope_note'] = 'two-host pilot used 1 view/abc only; stage1 shows aig none retains anchors -> recipe-dependent'
ka['panel_contract']['decision'] = 'not_started_inconsistent'
ka['panel_contract']['note'] = 'none does not uniformly remove anchors under aig; no-keep must be stratified by recipe/injection'
(H / 'KEEP_AUDIT.json').write_text(json.dumps(ka, indent=2), encoding='utf-8')
st = json.loads((H / 'STATUS.json').read_text(encoding='utf-8'))
st['phase'] = 'no_keep_panel_stage1'
st['keep_counterexample'] = 'executed_stage1_inconsistent'
st.setdefault('completed', []).append('two-host keep pilot')
st.setdefault('completed', []).append('stage1 6-combo pilot')
st['not_done'] = list(dict.fromkeys(st.get('not_done', []) + ['panel-wide keep removal', 'CEC', 'panel GT']))
st['nokeep'] = dict(st.get('nokeep', {}), stage1='4/6 supported; aig inconsistent', panel='not started')
st['note'] = 'stage1 12 syntheses done; aig inconsistent; panel/CEC not started'
(H / 'STATUS.json').write_text(json.dumps(st, indent=2), encoding='utf-8')
print(json.dumps(dict(combos=len(table), supported=sum(1 for x in table if x['supported']), bad=[f"{x['view']}/{x['recipe']}" for x in table if not x['supported']]), ensure_ascii=False))
