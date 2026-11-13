"""Audit prior D proof reuse without running an equivalence solver."""
import csv
from collections import Counter, defaultdict
from functools import cache
from pathlib import Path

from audit import CACHE, EVIDENCE, OUT, P, read, sha, write_csv, write_json
from verify_blockers import LogicOnlyPath, S, panel

SOURCE = 's35932t200__injepsilon_d1_s42'
VIEW = SOURCE + '__ys_nand'


def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as handle:
        yield from csv.DictReader(handle)


def main():
    frequency = OUT / 'GROUP_PROOF_FREQUENCY.csv'
    selected = [r for r in rows(frequency) if r['view'] == VIEW and r['reference'] == 'v5_best'
                and ((r['always'] == 'True' and r['proof_status'] == 'unknown') or r['proof_status'] == 'partial_negative')]
    assert Counter(r['proof_status'] for r in selected) == {'unknown': 19, 'partial_negative': 2}
    endpoint_ids = {c for r in selected for c in r['cones'].split('|')}
    selection_path = P / 'lcone_head_prep_20261112/all_eligible/SELECTION.json'
    specs = {r['view']: r for r in read(selection_path)['data'] if r['source'] == SOURCE}
    old_panel = P / 'lcone_head_prep_20261112/TRAIN_ENDPOINTS.json'
    evidence = defaultdict(set)
    for path in (EVIDENCE, old_panel):
        for r in read(path):
            if r['source'] == SOURCE and r['cone_id'] in endpoint_ids and r['label'] == 0:
                assert r['evidence'] in ('exhaustive_free_PI_Q', 'identical_boolean_expression')
                evidence[r['view'], r['cone_id']].add((r['evidence'], tuple(r['member_rows'])))
    verified_path = OUT / 'BLOCKER_PROOFS_VERIFIED.json'
    for r in read(verified_path)['records']:
        if r['source'] == SOURCE and r['cone_id'] in endpoint_ids and r['status'] == 'negative':
            assert r['independent_exhaustive_assignments'] == 1 << r['inputs']
            evidence[r['view'], r['cone_id']].add(('bdd_and_exhaustive', tuple(r['member_rows'])))

    cache_rows = {(r['view'],r['cone_id']): r for r in rows(CACHE)
                  if r['split']=='train' and r['view'] in specs and r['cone_id'] in endpoint_ids}
    _, arrays, names, layouts = S.load_snapshot('train')
    expressions = panel.Expressions()
    bindings = {}

    @cache
    def graph(path):
        return panel.endpoints(LogicOnlyPath(path))

    for v, spec in specs.items():
        files = [Path(p) for p in spec['files']]
        assert [sha(p) for p in files] == spec['sha256']
        assert spec['cec']['cec_status'] == 'PASS' and spec['cec']['unproven'] == '0'
        designs = [graph(p) for p in files[:3]]
        _, replacements, _ = panel.bind_lineage(spec['provenance'], *designs[:2])
        states, _, _ = panel.binding(*designs, replacements)
        evals = [panel.construct(design, expressions, states) for design in designs]
        physical_map = S.view_rows(layouts, names, v)
        for endpoint in sorted(endpoint_ids):
            if (v,endpoint) not in cache_rows:
                continue
            row = cache_rows[v, endpoint]
            identity = endpoint[2:]
            assert identity in states
            nets = [dict(g[0]['pins'][identity][1])['D'] for g in designs]
            g = designs[-1][0]
            assert g['find'](row['endpoint']) == g['find'](nets[-1])
            assert g['drivers'][g['find'](nets[-1])] == {row['driver']}
            roots_and_members = [ev(net) for ev, net in zip(evals, nets)]
            assert all(panel.structural_cone(d,n)==(set(item[1]),[]) for d,n,item in zip(designs,nets,roots_and_members))
            physical = tuple(map(int, row['phys_rows'].split('|')))
            members = roots_and_members[-1][1]
            assert not (members - physical_map.keys() - set(g['virtual_names']))
            assert tuple(sorted(physical_map[n] for n in members if n in physical_map)) == physical
            assert all(arrays['physical'][i] for i in physical)
            proofs = sorted({method for method, rows_tuple in evidence[v,endpoint] if rows_tuple == physical})
            roots = tuple(item[0] for item in roots_and_members)
            bindings[v,endpoint] = dict(roots=roots, physical_nets=nets, proofs=proofs,
                                        variables=len(set().union(*(expressions.inputs(r) for r in roots))))

    mapping_path = Path(specs[VIEW]['files'][2]).parent.parent / 'mappings' / f'{VIEW}.json'
    node_alignment = read(mapping_path)['node_alignment']
    endpoint_results = {}
    for c in sorted(endpoint_ids):
        d = bindings[VIEW,c]
        comparable = {v: b for (v,cid), b in bindings.items() if cid == c and v != VIEW and b['proofs']}
        transferable = [v for v, b in comparable.items() if d['roots'] == b['roots']]
        # Identity is structural equality of already-bound expressions, with no new solver.
        direct_identity = len(set(d['roots'])) == 1
        status = ('existing_exact_endpoint' if d['proofs'] else 'existing_certificate_exact_structural_transfer'
                  if transferable else 'all_three_expression_identity' if direct_identity else 'unknown')
        mapping = node_alignment.get(c[2:], [])
        endpoint_results[c] = dict(endpoint=c, status=status, target_proofs='|'.join(d['proofs']),
                                   other_recipes_with_exact_d_proof='|'.join(sorted(comparable)),
                                   transferable_recipes='|'.join(sorted(transferable)), clean_D=d['physical_nets'][0],
                                   orig_D=d['physical_nets'][1], target_D=d['physical_nets'][2], variables=d['variables'],
                                   clean_orig_identical=d['roots'][0]==d['roots'][1], orig_target_identical=d['roots'][1]==d['roots'][2],
                                   old_node_alignment='|'.join(mapping), old_alignment_single_identity=mapping==[c[2:]])
    result_groups = []
    for r in selected:
        members = r['cones'].split('|')
        proven = sum(endpoint_results[c]['status']!='unknown' for c in members)
        result_groups.append(dict(group=r['group'], cones=r['cones'], prior_status=r['proof_status'],
                                  status='full_negative' if proven==len(members) else 'partial_negative' if proven else 'unknown',
                                  proven_members=proven, members=len(members)))
    write_csv(OUT / 'EPSILON_EXISTING_D_PROOF_AUDIT.csv', list(endpoint_results.values()))
    write_csv(OUT / 'EPSILON_EXISTING_GROUP_PROOF_AUDIT.csv', result_groups)
    write_json(OUT / 'EPSILON_EXISTING_PROOF_PROVENANCE.json', dict(view=VIEW, comparison_views=sorted(specs),
               hashes={p.name:sha(p) for p in (frequency,selection_path,mapping_path,verified_path)},
               endpoint_status=dict(Counter(x['status'] for x in endpoint_results.values())),
               group_status=dict(Counter(x['status'] for x in result_groups)), optimizer_steps=0, forward_passes=0,
               sat_cec_calls=0, labels_modified=False))
    print(len(endpoint_ids), Counter(x['status'] for x in endpoint_results.values()),
          Counter(x['status'] for x in result_groups), flush=True)
    print('clean_orig_identical', sum(x['clean_orig_identical'] for x in endpoint_results.values()), flush=True)
    for c in ('D:DFF_1399_Q_reg','D:DFF_1404_Q_reg'):
        print(endpoint_results[c], flush=True)


if __name__ == '__main__':
    main()
