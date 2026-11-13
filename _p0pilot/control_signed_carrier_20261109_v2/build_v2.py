"""v2: signed/phase carrier relations with strict driver separation and region members.

Fixes vs v1:
  - target_driver_cells is exactly the single driver of the target signal;
  - intermediate expansion cells live in region_members with their own output pin and polarity;
  - R4/R5 target the phase-correct carrier node only (the INV output), not the whole region;
  - boundary aliases are recorded with a structural basis (exact / pin_alias / driver_cell / inv_formula).
Read-only: no training, no SAT/CEC/Yosys, no model calls.
"""
import collections
import json
import re
from pathlib import Path

import numpy as np

import Signed_common as S

OUT = S.HERE
FLOWS = {'delta': 'ys_nand', 'alpha': 'ys_abc'}
SRC_DELTA = 's15850t100__injdelta_d1_s42'
SRC_ALPHA = 's35932t200__injalpha_d1_s42'


def is_inv(lib, typ):
    try:
        ast = lib.ast(typ, 'QN')
    except AssertionError:
        try:
            ast = lib.ast(typ, 'Q')
        except AssertionError:
            return False
    return ast[0] == '~'


def driver(g, net):
    owners = g['drivers'].get(g['find'](net), set())
    assert len(owners) == 1, ('driver', net, owners)
    return next(iter(owners))


def norm_cell(name):
    n = name.lstrip('g').lstrip('_')
    n = n.split('.')[0]
    return re.sub(r'_\d+$', '', n)


def out_pin_of(g, cell, net):
    typ, conns = g['pins'][cell]
    hits = [p for p, n in conns if n == g['find'](net) and p in S.lib_pins[typ]['outputs']]
    assert len(hits) == 1, (cell, net, hits)
    return hits[0]


def bits(n, k):
    v = np.arange(1 << k)
    return [((v >> j) & 1).astype(bool) for j in range(n)]


def eval_with(g, lib, signal, env):
    return S.evaluate(g, lib, signal, env)


def main():
    assert not (OUT / 'RELATIONS_V2.csv').exists(), 'v2 already built'
    o_d = S.raw_network(S.F / 'orig' / (SRC_DELTA + '.v'), S.lib_pins)
    t_d = S.raw_network(S.F / 'trans' / (SRC_DELTA + '__' + FLOWS['delta'] + '.v'), S.lib_pins)
    o_a = S.raw_network(S.F / 'orig' / (SRC_ALPHA + '.v'), S.lib_pins)
    t_a = S.raw_network(S.F / 'trans' / (SRC_ALPHA + '__' + FLOWS['alpha'] + '.v'), S.lib_pins)
    c, arr, names, views = S.load_snapshot('train')
    rows_a = S.view_rows(views, names, SRC_ALPHA + '__' + FLOWS['alpha'])
    rows_d = S.view_rows(views, names, SRC_DELTA + '__' + FLOWS['delta'])

    def snap(rows, cell):
        if cell not in rows:
            return '', ''
        r = rows[cell]
        return int(arr['y'][r]), bool(arr['trusted'][r])

    rels, members = [], []

    def add_member(rid, g, cell, signal, polarity, role, note=''):
        pin = out_pin_of(g, cell, signal)
        members.append(dict(relation_id=rid, cell=cell, output_pin=pin, signal=signal,
                            polarity=polarity, role=role, note=note))

    # ---------------- R1 alpha P2 -> _0384_ ----------------
    a, b, cc, u1, u2 = bits(5, 5)
    es = {'n8566': a, 'WX3484': b, 'DFF_955_n1': cc, 'n4183': u1, 'n2940': u2}
    et = {'TrojanAP0.IN2': a, 'TrojanAP1.IN2': b, 'DFF_955_n1': cc, 'TrojanAT1.IN1': u1, 'TrojanAT1.IN2': u2}
    p2, _ = eval_with(o_a, S.LIB, 'TrojanA_p2', es)
    t1, _ = eval_with(t_a, S.LIB, '_0384_', et)
    assert np.array_equal(t1, ~p2)
    d1 = driver(t_a, '_0384_')
    boundary = [
        dict(source_net='n8566', target_net='TrojanAP0.IN2', invert=False, basis='pin_alias',
             anchor_cell='TrojanAP0', anchor_pin='IN2'),
        dict(source_net='WX3484', target_net='TrojanAP1.IN2', invert=False, basis='pin_alias',
             anchor_cell='TrojanAP1', anchor_pin='IN2'),
        dict(source_net='DFF_955_n1', target_net='DFF_955_n1', invert=False, basis='exact_name'),
        dict(source_net='n4183', target_net='TrojanAT1.IN1', invert=False, basis='pin_alias',
             anchor_cell='TrojanAT1', anchor_pin='IN1'),
        dict(source_net='n2940', target_net='TrojanAT1.IN2', invert=False, basis='pin_alias',
             anchor_cell='TrojanAT1', anchor_pin='IN2'),
    ]
    rels.append(dict(relation_id='R1_alpha_P2_carrier', split='train', source_object=SRC_ALPHA,
                     implementation_flow=FLOWS['alpha'], source_cell='TrojanAP2', source_output_pin='Q',
                     source_signal='TrojanA_p2', target_signal='_0384_', target_driver_cells=d1,
                     target_output_pin=out_pin_of(t_a, d1, '_0384_'), target_rows=str(rows_a[d1]),
                     relation_type='signed_signal_equal', polarity='-1',
                     boundary_aliases=json.dumps(boundary, ensure_ascii=False), k_inputs=len(boundary),
                     region_members='', context='free_cut;T=NOT(u1 OR u2);no register used',
                     host_usage='active', observable_use_endpoints='PO test_so62;first-register D inputs',
                     physical_D_or_PO_paths='_0384_ -> g_test_so62_530 -> test_so62; -> g__U6001.Q_2345 -> DFF_1113_Q_reg.D',
                     source_sha=S.sha(S.F / 'orig' / (SRC_ALPHA + '.v')),
                     target_sha=S.sha(S.F / 'trans' / (SRC_ALPHA + '__' + FLOWS['alpha'] + '.v')),
                     mapping_sha=S.sha(S.F / 'mappings' / (SRC_ALPHA + '__' + FLOWS['alpha'] + '.json')),
                     evidence_ids='LOCAL_TRUTH:R1(32);SIGNAL_CHAIN;CARRIER_TO_HOST_PATHS',
                     proof_scope='aligned 5-input local cut with real behavioral-library formulas;NOT whole-design CEC',
                     accepted_or_unresolved='accepted', exclusion_reason='',
                     current_y=snap(rows_a, d1)[0], current_trusted=snap(rows_a, d1)[1],
                     source_y='', source_trusted='',
                     named_copy='g_TrojanA_p2_528', named_copy_rows=str(rows_a['g_TrojanA_p2_528']),
                     named_copy_y=snap(rows_a, 'g_TrojanA_p2_528')[0],
                     named_copy_trusted=snap(rows_a, 'g_TrojanA_p2_528')[1]))
    add_member('R1_alpha_P2_carrier', t_a, 'g_TrojanA_p2_528', 'TrojanAHJ.IN2', '+1', 'named_copy_inv',
               'inverts _0384_ back to P2; dangling')

    # ---------------- R2 alpha T -> _0383_ ----------------
    src_t = ~(u1 | u2)
    assert np.array_equal(eval_with(o_a, S.LIB, 'TrojanA_t1', es)[0], src_t)
    assert np.array_equal(eval_with(t_a, S.LIB, '_0383_', et)[0], ~src_t)
    d2 = driver(t_a, '_0383_')
    rels.append(dict(relation_id='R2_alpha_T_carrier', split='train', source_object=SRC_ALPHA,
                     implementation_flow=FLOWS['alpha'], source_cell='TrojanAT1', source_output_pin='QN',
                     source_signal='TrojanA_t1', target_signal='_0383_', target_driver_cells=d2,
                     target_output_pin=out_pin_of(t_a, d2, '_0383_'), target_rows=str(rows_a[d2]),
                     relation_type='signed_signal_equal', polarity='-1',
                     boundary_aliases=json.dumps(boundary[3:], ensure_ascii=False), k_inputs=2,
                     region_members='', context='free_cut;T=NOT(u1 OR u2);no register used',
                     host_usage='active', observable_use_endpoints='PO test_so62;first-register D inputs',
                     physical_D_or_PO_paths='_0383_ -> g__0385__529 -> g_test_so62_530 -> test_so62 / DFF branches',
                     source_sha=S.sha(S.F / 'orig' / (SRC_ALPHA + '.v')),
                     target_sha=S.sha(S.F / 'trans' / (SRC_ALPHA + '__' + FLOWS['alpha'] + '.v')),
                     mapping_sha=S.sha(S.F / 'mappings' / (SRC_ALPHA + '__' + FLOWS['alpha'] + '.json')),
                     evidence_ids='LOCAL_TRUTH:R2(4)', proof_scope='aligned 2-input local complement;NOT whole-design CEC',
                     accepted_or_unresolved='accepted', exclusion_reason='',
                     current_y=snap(rows_a, d2)[0], current_trusted=snap(rows_a, d2)[1],
                     source_y='', source_trusted='', named_copy='', named_copy_rows='',
                     named_copy_y='', named_copy_trusted=''))

    # ---------------- R3 alpha H -> _0001_ ----------------
    h = np.array([0, 1], bool)
    assert np.array_equal(eval_with(t_a, S.LIB, '_0001_', {'test_so62_orig': h})[0], ~h)
    d3 = driver(t_a, '_0001_')
    rels.append(dict(relation_id='R3_alpha_H_carrier', split='train', source_object=SRC_ALPHA,
                     implementation_flow=FLOWS['alpha'], source_cell='DFF_1081_Q_reg', source_output_pin='Q',
                     source_signal='test_so62_orig', target_signal='_0001_', target_driver_cells=d3,
                     target_output_pin=out_pin_of(t_a, d3, '_0001_'), target_rows=str(rows_a[d3]),
                     relation_type='signed_signal_equal', polarity='-1',
                     boundary_aliases=json.dumps([dict(source_net='test_so62_orig', target_net='test_so62_orig',
                                                       invert=False, basis='exact_name')], ensure_ascii=False),
                     k_inputs=1, region_members='', context='free_state;DFF Q treated as free input;no next-state analysis',
                     host_usage='active', observable_use_endpoints='PO test_so62',
                     physical_D_or_PO_paths='_0001_ -> g__0385__529 -> g_test_so62_530 -> test_so62',
                     source_sha=S.sha(S.F / 'orig' / (SRC_ALPHA + '.v')),
                     target_sha=S.sha(S.F / 'trans' / (SRC_ALPHA + '__' + FLOWS['alpha'] + '.v')),
                     mapping_sha=S.sha(S.F / 'mappings' / (SRC_ALPHA + '__' + FLOWS['alpha'] + '.json')),
                     evidence_ids='LOCAL_TRUTH:R3(2)', proof_scope='local complement of free host state;NOT state-transition proof',
                     accepted_or_unresolved='accepted', exclusion_reason='',
                     current_y=snap(rows_a, d3)[0], current_trusted=snap(rows_a, d3)[1],
                     source_y='', source_trusted='', named_copy='', named_copy_rows='',
                     named_copy_y='', named_copy_trusted=''))

    # ---------------- R4/R5 delta phase-correct carrier only ----------------
    x, t = bits(2, 2)
    ed = {'n533': x, 'TrojanDHJ.S': t, 'TrojanDP2.S': ~x, '_0473_': ~t}
    for rid, gate, out, and_cell, inv_cell, tgt_sig in (
            ('R4_delta_DP0_carrier', 'TrojanDP0', 'TrojanD_p0', 'g_TrojanD_p0_8957', 'g_TrojanD_p0_8958', 'TrojanDP0.Q'),
            ('R5_delta_DP2_carrier', 'TrojanDP2', 'TrojanD_p2', 'g_TrojanD_p2_934', 'g_TrojanD_p2_935', 'TrojanDP2.Q')):
        src_v, _ = eval_with(o_d, S.LIB, out, {'n533': x, 'TrojanD_t4': t})
        assert np.array_equal(src_v, x | t)
        tv, _ = eval_with(t_d, S.LIB, tgt_sig, ed)
        assert np.array_equal(tv, src_v)
        d = driver(t_d, tgt_sig)
        assert d == inv_cell
        # region member: the AND stage is the opposite phase
        _, and_out = S.output_net(t_d, and_cell)
        mv, _ = eval_with(t_d, S.LIB, and_out, ed)
        assert np.array_equal(mv, ~src_v)
        rels.append(dict(
            relation_id=rid, split='train', source_object=SRC_DELTA, implementation_flow=FLOWS['delta'],
            source_cell=gate, source_output_pin='Q', source_signal=out,
            target_signal=tgt_sig, target_driver_cells=d, target_output_pin=out_pin_of(t_d, d, tgt_sig),
            target_rows=str(rows_d[d]), relation_type='signed_signal_equal', polarity='+1',
            boundary_aliases=json.dumps([
                dict(source_net='TrojanD_t4', target_net='_0473_', invert=True, basis='inv_formula',
                     anchor_net='TrojanDHJ.S'),
                dict(source_net='n533', target_net='TrojanDP2.S', invert=True, basis='inv_formula',
                     anchor_net='n533'),
            ], ensure_ascii=False), k_inputs=2, region_members=json.dumps([and_cell], ensure_ascii=False),
            context='free_cut;x,T free;DFF not used',
            host_usage='dead', observable_use_endpoints='none',
            physical_D_or_PO_paths='closed component: no PO and no register',
            source_sha=S.sha(S.F / 'orig' / (SRC_DELTA + '.v')),
            target_sha=S.sha(S.F / 'trans' / (SRC_DELTA + '__' + FLOWS['delta'] + '.v')),
            mapping_sha=S.sha(S.F / 'mappings' / (SRC_DELTA + '__' + FLOWS['delta'] + '.json')),
            evidence_ids='LOCAL_TRUTH:%s(4)' % rid[:2],
            proof_scope='aligned 2-input local equality at the phase-correct carrier;region member is NOT a node-pair positive',
            accepted_or_unresolved='accepted', exclusion_reason='',
            current_y=snap(rows_d, d)[0], current_trusted=snap(rows_d, d)[1],
            source_y='', source_trusted='', named_copy=and_cell, named_copy_rows=str(rows_d[and_cell]),
            named_copy_y=snap(rows_d, and_cell)[0], named_copy_trusted=snap(rows_d, and_cell)[1]))
        add_member(rid, t_d, and_cell, and_out, '-1', 'expansion_stage', 'same region, opposite phase; must not be paired as positive')

    # ---------------- R6 delta absorbed ----------------
    xx, tt, hh = np.meshgrid(x, t, np.array([0, 1], bool), indexing='ij')
    xx, tt, hh = xx.ravel(), tt.ravel(), hh.ravel()
    ea = {'n533': xx, 'TrojanDHJ.S': tt, 'TrojanDHJ.IN1': hh, '_0473_': ~tt, '_0729_': ~hh, 'TrojanDP2.S': ~xx}
    out_v, _ = eval_with(t_d, S.LIB, 'TrojanDHJ.Q', ea)
    assert np.array_equal(out_v, hh | tt)
    d6 = driver(t_d, 'TrojanDHJ.Q')
    rels.append(dict(relation_id='R6_delta_absorbed_at_output', split='train', source_object=SRC_DELTA,
                     implementation_flow=FLOWS['delta'], source_cell='TrojanDP0|TrojanDP2', source_output_pin='Q',
                     source_signal='TrojanD_p0|TrojanD_p2', target_signal='TrojanDHJ.Q', target_driver_cells=d6,
                     target_output_pin=out_pin_of(t_d, d6, 'TrojanDHJ.Q'), target_rows=str(rows_d[d6]),
                     relation_type='absorbed_at_output', polarity='n/a',
                     boundary_aliases=json.dumps([
                         dict(source_net='TrojanD_t4', target_net='_0473_', invert=True, basis='inv_formula',
                              anchor_net='TrojanDHJ.S'),
                         dict(source_net='g10801_orig', target_net='_0729_', invert=True, basis='inv_formula',
                              anchor_net='TrojanDHJ.IN1'),
                         dict(source_net='n533', target_net='TrojanDP2.S', invert=True, basis='inv_formula',
                              anchor_net='n533'),
                     ], ensure_ascii=False), k_inputs=3, region_members='',
                     context='free_cut;x,T,H free;DFF not used',
                     host_usage='active', observable_use_endpoints='PO g10801',
                     physical_D_or_PO_paths='TrojanDHJ.Q -> PO g10801',
                     source_sha=S.sha(S.F / 'orig' / (SRC_DELTA + '.v')),
                     target_sha=S.sha(S.F / 'trans' / (SRC_DELTA + '__' + FLOWS['delta'] + '.v')),
                     mapping_sha=S.sha(S.F / 'mappings' / (SRC_DELTA + '__' + FLOWS['delta'] + '.json')),
                     evidence_ids='LOCAL_TRUTH:R6(8)', proof_scope='final output = H OR T over aligned cut;x-dependence absorbed;no node pairing',
                     accepted_or_unresolved='accepted', exclusion_reason='',
                     current_y=snap(rows_d, d6)[0], current_trusted=snap(rows_d, d6)[1],
                     source_y='', source_trusted='', named_copy='', named_copy_rows='',
                     named_copy_y='', named_copy_trusted=''))
    add_member('R6_delta_absorbed_at_output', t_d, 'g_g10801_1672', 'g10801__g1671', '-1', 'output_stage',
               'AND stage computing NOT(H OR T); not a node-pair positive')

    S.table(OUT / 'RELATIONS_V2.csv', rels)
    S.table(OUT / 'REGION_MEMBERS_V2.csv', members)
    S.write_json(OUT / 'BUILD_V2_SUMMARY.json', dict(relations=len(rels), region_members=len(members),
                                                     training=0, SAT=0, model_forwards=0, labels_changed=False))
    print('built', len(rels), 'relations', len(members), 'region members')


if __name__ == '__main__':
    main()
