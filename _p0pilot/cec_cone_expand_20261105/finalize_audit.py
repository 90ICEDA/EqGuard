"""Finish final corpus audit using existing files only; no solver or model calls."""
from pathlib import Path
import collections
import csv
import hashlib
import json
import re
import sys
import numpy as np

R = Path(__file__).resolve().parents[2]
O = Path(__file__).resolve().parent
sys.path.insert(0, str(R / '_p0pilot/cec_cone_audit_20261105'))
from audit import read, rows, sha, ident, cone, module, SCHEMA
sys.path.insert(0, str(R / '_p0pilot/round10_20261025'))
import native as N

def write(name, value):
    path = O / name
    assert not path.exists(), 'Refuse to overwrite: ' + name
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')

def table(name, records):
    path = O / name
    assert not path.exists()
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(records[0]))
        w.writeheader()
        w.writerows(records)

def main():
    assert not (O / 'FINAL_COMPLETE.json').exists()
    pairs = read(O / 'final_pairs.json')
    cones = {c['cone_id']: c for c in read(O / 'final_cones.json')}
    assert len({p['pair_id'] for p in pairs}) == len(pairs)
    assert len(cones) == len(read(O / 'final_cones.json'))
    primary = [p for p in pairs if p['proof_ids']]
    supplement = [p for p in pairs if not p['proof_ids']]
    input_contract_path = R / '_p0pilot/control_boundary_v3_20261104/input_contract.json'
    contract = read(input_contract_path)
    meta = {v['view']: v for v in rows(R / 'generate_trans/folds/hosts_bt31/views_meta.csv')}
    vm = {v['view']: (k, v) for k, q in contract['shared_inputs'].items()
          if k.startswith('trans_') for v in q['views']}
    name_path = R / 'generate_trans/folds/hosts_bt31/data/processed/node_names_trans.txt'
    names = [x.strip().lstrip('\\') for x in name_path.read_text(encoding='utf-8').splitlines()]
    frozen = dict(read(O / 'EXPANDED.json')['inputs'])
    frozen.update(read(R / '_p0pilot/cec_cone_audit_20261105/COMPLETE.json')['files'])
    for path, checksum in frozen.items():
        assert sha(R / path) == checksum, ('Frozen evidence changed', path)
    raw = {}
    maps = {}
    arrays = {}
    layouts = {}
    for c in cones.values():
        view = c['view']
        if view in raw:
            continue
        assert c['split'] in ('train', 'val')
        assert sha(R / c['raw_path']) == c['raw_sha']
        assert sha(R / 'generate_trans/folds/hosts_bt31/trans' / (view + '.v')) == c['source_sha']
        m = next(iter(read(R / c['raw_path'])['modules'].values()))
        raw[view] = m
        key, v = vm[view]
        maps[view] = {n: v['start'] + j for j, n in enumerate(names[v['old_start']:v['old_stop']])}
        layouts[view] = N.layout(m)
        if key not in arrays:
            folder = R / contract['shared_inputs'][key]['folder']
            arrays[key] = {}
            for n in ('x39', 'physical', 'trusted', 'y'):
                pth = folder / (n + '.npy')
                assert sha(pth) == contract['files'][str(pth.relative_to(R))]
                arrays[key][n] = np.load(pth, mmap_mode='r')
    # Independently rebuild every final cone and verify graph coordinate attachment.
    coordinate_checks = []
    for cid, c in cones.items():
        view = c['view']
        m = raw[view]
        z = cone(m, c['root_bit'], maps[view], c['raw_sha'])
        for field in ('members', 'graph_rows', 'leaves', 'constants', 'errors', 'unmapped_members', 'nontrivial'):
            assert z[field] == c[field], (cid, field)
        assert not z['errors'] and not z['unmapped_members'] and z['nontrivial']
        assert m['cells'][c['output_cell']]['connections'][c['output_pin']] == [c['root_bit']]
        assert maps[view][c['output_cell']] == c['root_row']
        assert ident([c['source_sha'], c['output_cell'], c['output_pin']]) == cid
        key, v = vm[view]
        ii = np.asarray(c['graph_rows'], dtype=np.int64)
        assert len(ii) == len(set(ii)) and len(ii) > 0
        assert ((ii >= v['start']) & (ii < v['physical_stop'])).all()
        assert arrays[key]['physical'][ii].all() and np.isfinite(arrays[key]['x39'][ii]).all()
        assert c['root_row'] in ii
        coordinate_checks.append(dict(cone_id=cid, split=c['split'], view=view,
                                      root_row=c['root_row'], root_bit=c['root_bit'],
                                      root_pin=c['output_pin'], physical_members=len(ii), rebuilt=True))
    print('Rebuilt and attached', len(cones), 'cones', flush=True)
    proofs = read(O / 'reused_proofs.json')
    codes = {}
    query_checks = []
    for pid, q in proofs.items():
        folder = R / q['folder']
        for n, field in [('model.v', 'model_sha'), ('run.log', 'log_sha')]:
            assert sha(folder / n) == q[field]
        script = (folder / 'run.ys').read_text(encoding='utf-8')
        assert hashlib.sha256(script.encode()).hexdigest() == q['script_sha']
        commands = [s for s in script.splitlines() if s.startswith('sat ')]
        query = commands[int(q['query_id'])]
        assert query.startswith('sat ' + q['args'] + ' -timeout ')
        # No hidden assumptions or undef-enabled semantics admitted by this audit.
        assert re.fullmatch(r'sat ' + re.escape(q['args']) + r' -timeout \d+(?: -show-inputs)?(?: -show-outputs)?(?: -dump_json "[^"]+")?', query.strip()), query
        log = (folder / 'run.log').read_text(encoding='utf-8')
        blocks = re.split(r'^(?:Q|QUERY)\d{4}\s*$', log, flags=re.M)
        block = blocks[int(q['query_id']) + 1]
        assert 'no model found: SUCCESS' in block and 'TIMEOUT' not in block and 'ERROR:' not in log
        assert ident([q['model_sha'], q['args']]) == pid
        codes[pid] = (folder / 'model.v').read_text(encoding='utf-8')
        query_checks.append(dict(proof_id=pid, args=q['args'], query_id=q['query_id'],
                                 hashes_and_exact_success_verified=True))
    # Recheck exact observation/probe projection for ALL pairs, not only large cones.
    projection = []
    regenerated_modules = {}
    verified_module_bindings = set()
    rootchecks = []
    canonical = set()
    for p in pairs:
        a, b = [cones[p[x]] for x in ('left_cone', 'right_cone')]
        assert p['split'] == a['split'] == b['split']
        assert meta[a['view']]['src_view'] == meta[b['view']]['src_view'] == p['source_object']
        assert layouts[a['view']] == layouts[b['view']]
        ctx = ident(dict(PI=layouts[a['view']][0], physicalQ=layouts[a['view']][1], free=True))
        assert ctx == p['context_id']
        canonical_id = ident([p['source_object'], ctx, sorted([a['cone_id'], b['cone_id']])])
        assert canonical_id == p['pair_id'] and canonical_id not in canonical
        canonical.add(canonical_id)
        assert not p['labels_used_for_function_acceptance']
        assert not p['current_detection_training_allowed']
        assert p['enum']['equal'] is not False
        for c, end in zip((a, b), p['root_endpoints']):
            ar = arrays[vm[c['view']][0]]
            i = c['root_row']
            assert end == dict(view=c['view'], row=i, cell=c['output_cell'], pin=c['output_pin'],
                               label=int(ar['y'][i]), trusted=bool(ar['trusted'][i]), physical=bool(ar['physical'][i]))
        diagnostic = all(x['trusted'] and x['physical'] for x in p['root_endpoints']) and p['root_endpoints'][0]['label'] == p['root_endpoints'][1]['label']
        assert diagnostic == p['detection_stability_diagnostic_eligible']
        rootchecks.append(dict(pair_id=p['pair_id'], split=p['split'], source=p['source_object'],
                               root_label_a=p['root_endpoints'][0]['label'], root_label_b=p['root_endpoints'][1]['label'],
                               independent_label_diagnostic_eligible=diagnostic))
        for pid in p['proof_ids']:
            q = proofs[pid]
            text = codes[pid]
            check = module(text, 'check')
            case8 = 'sat_cases_round8' in q['folder']
            modules = ['design_ys_id', 'design_ys_abc'] if case8 else ['left_design', 'right_design']
            arg = q['args']
            if arg in ('-prove observation_diff 0', '-prove po_d_diff 0'):
                field = 'obs'
                assert ('assign observation_diff=|(oa^ob);' if not case8 else 'assign po_d_diff=|(oa^ob)') in check
                expected_index = None
            else:
                field = 'p' if case8 else 'sigs'
                match = re.fullmatch(r'-prove delta\[(\d+)\] 0', arg)
                if match:
                    expected_index = int(match[1])
                    assert 'assign delta=a^b;' in check
                else:
                    assert arg == '-prove mismatch 0'
                    match = re.search(r'assign mismatch=a\[(\d+)\]\^b\[\1\];', check)
                    assert match
                    expected_index = int(match[1])
            terms = []
            for c, mn in zip((a, b), modules):
                body = module(text, mn)
                match = re.search(r'assign ' + field + r'\s*=\s*\{(.*?)\};', body)
                assert match, (p['pair_id'], mn, field)
                terms.append([x.strip() for x in match[1].split(',')][::-1])
                if not case8 and (pid, c['view'], mn) not in verified_module_bindings:
                    m = raw[c['view']]
                    net = next(n for n, z in m['netnames'].items() if len(z['bits']) == 1)
                    if (c['view'], mn) not in regenerated_modules:
                        regenerated_modules[c['view'], mn], _ = N.emit(m, mn, [net] * 5)
                    generated = regenerated_modules[c['view'], mn]
                    strip = lambda s: re.sub(r'assign sigs=\{.*?\};', 'assign sigs=BOUND;', s)
                    assert strip(generated) == strip(body)
                    verified_module_bindings.add((pid, c['view'], mn))
            inds = [j for j, (u, v) in enumerate(zip(*terms))
                    if u == 'b' + str(a['root_bit']) and v == 'b' + str(b['root_bit'])]
            assert inds and (expected_index is None or expected_index in inds), (p['pair_id'], pid)
            if case8:
                assert "left(env,1'b0,1'b0,a,oa)" in check and "right(env,1'b0,1'b0,b,ob)" in check
            else:
                assert 'left_design l(env,a,oa)' in check and 'right_design r(env,b,ob)' in check
            projection.append(dict(pair_id=p['pair_id'], proof_id=pid, split=p['split'],
                                   projection='whole_PO_D_entailment' if expected_index is None else 'exact_probe',
                                   observation_indices='|'.join(map(str, inds)), root_a=a['root_bit'], root_b=b['root_bit']))
    for cert in read(O / 'positive_observation_proof_certificates.json'):
        found = [r for r in projection if r['pair_id'] == cert['pair_id'] and r['proof_id'] == cert['proof_id']]
        assert any(str(cert['observation_index']) in r['observation_indices'].split('|') for r in found)
        assert all(r['root_a'] == cert['root_a'] and r['root_b'] == cert['root_b'] for r in found)
    # Canonical connected components within source, split and common PI/Q context.
    parent = {}
    def find(x):
        parent.setdefault(x, x)
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]
    for p in primary:
        a, b = find((p['split'], p['source_object'], p['context_id'], p['left_cone'])), find((p['split'], p['source_object'], p['context_id'], p['right_cone']))
        parent[max(a, b)] = min(a, b)
    groups = collections.defaultdict(list)
    for p in primary:
        component = find((p['split'], p['source_object'], p['context_id'], p['left_cone']))
        groups[component].append(p)
    sources = {s: sorted({p['source_object'] for p in primary if p['split'] == s}) for s in ('train', 'val', 'test')}
    assert not set(sources['train']) & set(sources['val'])
    weightrows = []
    for comp, pp in sorted(groups.items()):
        split, source, ctx, coneid = comp
        nc = sum(k[0] == split and k[1] == source for k in groups)
        for p in pp:
            weightrows.append(dict(pair_id=p['pair_id'], split=split, source_object=source,
                                   context_id=ctx, component=coneid,
                                   weight=1 / len(sources[split]) / nc / len(pp)))
    for split in ('train', 'val'):
        ww = [w for w in weightrows if w['split'] == split]
        assert np.isclose(sum(w['weight'] for w in ww), 1)
        for source in sources[split]:
            assert np.isclose(sum(w['weight'] for w in ww if w['source_object'] == source), 1 / len(sources[split]))
    source_summary = []
    overlap_summary = []
    for split in ('train', 'val'):
        for source in sources[split]:
            pp = [p for p in primary if p['split'] == split and p['source_object'] == source]
            ids = {p[k] for p in pp for k in ('left_cone', 'right_cone')}
            exposure = collections.Counter((cones[c]['view'], i) for c in ids for i in cones[c]['graph_rows'])
            source_summary.append(dict(split=split, source_object=source, pairs=len(pp),
                                       components=sum(k[0] == split and k[1] == source for k in groups),
                                       unique_cones=len(ids), unique_physical_members=len(exposure),
                                       max_cone_membership=max(exposure.values()),
                                       positive_root_pairs=sum(p['root_endpoints'][0]['label'] == 1 for p in pp),
                                       negative_root_pairs=sum(p['root_endpoints'][0]['label'] == 0 for p in pp)))
            overlap_summary.append(dict(split=split, source=source,
                                        shared_members=sum(n > 1 for n in exposure.values()),
                                        unique_members=len(exposure), total_cone_memberships=sum(exposure.values()),
                                        independence='overlapping cones are NOT independent observations'))
    artifact_hashes = {n: sha(O / n) for n in ('final_pairs.json', 'final_cones.json')}
    plan = dict(status='FINAL_DATA_PREFLIGHT_ONLY', primary={s: [p['pair_id'] for p in primary if p['split'] == s] for s in sources},
                enum_only_supplement=[p['pair_id'] for p in supplement],
                data_hashes=artifact_hashes, input_contract_sha=sha(input_contract_path),
                weights={r['pair_id']: r['weight'] for r in weightrows},
                weight_rule='equal source, then equal context+cone component, then equal observed edge within each split',
                no_transitive_cartesian_expansion=True, detector_risk_consistency_allowed=False,
                whole_embedding_alignment_allowed=False, security_label_transfer_allowed=False,
                auxiliary_head_implemented=False, training_protocol_implemented=False,
                train_allowed_as_functional_data_only=True, val_evaluation_only=True, test_pairs=0)
    write('FINAL_CONTRACT.json', plan)
    table('FINAL_weights.csv', weightrows)
    table('FINAL_source_summary.csv', source_summary)
    table('FINAL_overlap_summary.csv', overlap_summary)
    table('FINAL_coordinate_checks.csv', coordinate_checks)
    table('FINAL_proof_queries.csv', query_checks)
    table('FINAL_proof_projection.csv', projection)
    table('FINAL_independent_root_labels.csv', rootchecks)
    from final_pair_adapter import FinalCECConePairs
    loaded = []
    for split in ('train', 'val', 'test'):
        ds = FinalCECConePairs(split)
        for z in ds:
            assert z['functional_training_data_eligible'] == (split == 'train')
            assert 'root_endpoints' not in z and 'label' not in z
            for side in ('left', 'right'):
                assert not z[side]['members'].flags.writeable
            loaded.append(dict(pair_id=z['pair_id'], split=split, source=z['source_object'],
                               weight=z['weight'], root_bit_and_pin_retained=True, labels_excluded_from_payload=True))
    for invalid in ('all', '', None):
        try:
            FinalCECConePairs(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError('Mixed split accepted')
    assert len(loaded) == len(primary)
    table('FINAL_adapter_preflight.csv', loaded)
    report = dict(status='FINAL_DATA_PREFLIGHT_PASS_NOT_TRAINING_RESULT', training=0, model_forward=0, new_SAT_queries=0,
                  pairs=len(primary), primary_by_split={s: len(plan['primary'][s]) for s in sources},
                  components=len(groups), components_by_split=dict(collections.Counter(k[0] for k in groups)),
                  sources_by_split={s: len(v) for s, v in sources.items()},
                  hosts_by_split={s: len({v.split('__')[0] for v in vs}) for s, vs in sources.items()},
                  enum_only_supplement=len(supplement), raw_views=len(raw), rebuilt_cones=len(cones),
                  proof_queries_rechecked=len(proofs), proof_projection_rows=len(projection),
                  loaded_pairs=len(loaded), split_mixing_rejected=True, weights_verified=True,
                  positive_root_pairs={s: sum(p['root_endpoints'][0]['label'] == 1 for p in primary if p['split'] == s) for s in sources},
                  nonconstant_information=read(O / 'INFORMATION_CHECK_FINAL.json'),
                  previous_artifacts_unchanged=True,
                  training_ready=False, remaining='functional-head/anti-collapse/equal-budget protocol and runner not implemented')
    write('FINAL_VERIFIED.json', report)
    generated = sorted(x.name for x in O.glob('FINAL_*'))
    generated += ['final_pair_adapter.py', 'finalize_audit.py', 'final_pairs.json', 'final_cones.json']
    write('FINAL_COMPLETE.json', dict(status='DATA_AUDIT_COMPLETE', report='FINAL_VERIFIED.json',
                                    files={str((O / n).relative_to(R)): sha(O / n) for n in generated},
                                    frozen_evidence_files_checked=len(frozen), training=0, new_SAT_queries=0))
    print(json.dumps(report, ensure_ascii=False), flush=True)

if __name__ == '__main__':
    main()
