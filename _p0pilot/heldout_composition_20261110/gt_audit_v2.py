"""GT availability v2 + keep counterexample plan finalize (read-only)."""
import csv, json
from pathlib import Path
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); H = R / '_p0pilot/heldout_composition_20261110'
MAP = R / 'data/verilog_data/mappings'
HOSTS = ('rs232t1000', 's15850t100', 's35932t200', 's38417t100', 's38584t100')
rows = []
structure = {}
for host in HOSTS:
    p = MAP / f'{host}tr42.JSON'
    if not p.exists():
        rows.append(dict(host=host, design='tr42', mapping_file=None, status='missing',
                         reason='no mapping JSON for this host (s38417t100 only has s38417t300)'))
        continue
    d = json.loads(p.read_text(encoding='utf-8'))
    na = d.get('node_alignment', {})
    structure[host] = dict(keys=list(d), src=d.get('src_verilog'), dst=d.get('dst_verilog'),
                           node_alignment_n=len(na), sample={k: na[k] for k in list(na)[:3]})
    # endpoint-level: JSON has no Q/D/PO/PI fields
    for ep in ('DFF_Q', 'DFF_D', 'PO', 'PI'):
        rows.append(dict(host=host, design='tr42', endpoint=ep, original='NA', rewritten='NA',
                         mapping_source=str(p.relative_to(R)), status='unmapped',
                         reason='node_alignment only maps instances->instances; no pin/Q/D/PO/PI fields'))
(H / 'GT_AVAILABILITY_V2.json').write_text(json.dumps(dict(structure=structure, rows=rows,
                                                          note='weak MIL / structural reachability / CEC equivalence are not functional GT'), indent=2), encoding='utf-8')
with (H / 'GT_AVAILABILITY_V2.csv').open('w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f); w.writerow(['host', 'design', 'endpoint', 'original', 'rewritten', 'mapping_source', 'status', 'reason'])
    for x in rows:
        w.writerow([x['host'], x['design'], x.get('endpoint', 'NA'), x.get('original', 'NA'), x.get('rewritten', 'NA'), x.get('mapping_source', 'NA'), x['status'], x['reason']])
# keep audit update
ka = json.loads((H / 'KEEP_AUDIT.json').read_text(encoding='utf-8'))
ka['minimal_counterexample'] = dict(status='not_executed', inputs=['source netlist with (* keep *) attribute'],
                                    commands=['py phase2/ys/keep_ablation.py --schemes none,cur,bnd --recipes abc'],
                                    evidence=['opt log / stat cell survival', 'post-opt netlist keep lines',
                                              'compare none vs cur/bnd cell counts'],
                                    criteria=['non-keep cell survives opt in none', 'keep attribute absent in written netlist',
                                              'cur/bnd retain anchor cells'],
                                    estimate='1 次综合约 1–3 分钟 + 日志核对')
ka['keep_removal_proven'] = False
(H / 'KEEP_AUDIT.json').write_text(json.dumps(ka, indent=2), encoding='utf-8')
# STATUS
st = json.loads((H / 'STATUS.json').read_text(encoding='utf-8'))
st['phase'] = 'gt_mapping_audit_and_keep_plan'
st['gt'] = dict(structure_parsed=True, endpoint_verified=0, missing=['s38417t100'], unmapped='Q/D/PO/PI fields absent')
st['keep_counterexample'] = 'not_executed'
st['synthesis_cec'] = 'not_started'
(H / 'STATUS.json').write_text(json.dumps(st, indent=2), encoding='utf-8')
print(json.dumps(dict(hosts=len(HOSTS), rows=len(rows), structure=list(structure), missing=['s38417t100']), ensure_ascii=False))
