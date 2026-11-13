"""Build the signed/phase carrier relations for the three frozen cases (read-only).

Relations:
  R1 alpha: source TrojanA_p2 (P2)  <-> target _0384_ (driver g__0384__527), polarity -1
  R2 alpha: source TrojanA_t1 (T)   <-> target _0383_ (driver g__0383__520), polarity -1
  R3 alpha: source test_so62_orig(H)<-> target _0001_ (driver g__0001__2), polarity -1
  R4 delta: source TrojanD_p0       <-> named copy g_TrojanD_p0_8957/8958, polarity +1, dead
  R5 delta: source TrojanD_p2       <-> named copy g_TrojanD_p2_934/935, polarity +1, dead
  R6 delta: absorbed_at_output (no node pairing), final g10801 = H OR T
No training, no SAT/CEC/Yosys, no model calls; labels are read-only snapshots.
"""
import collections
import hashlib
import json
from pathlib import Path

import numpy as np

import Signed_common as S

OUT = S.HERE


def patterns(*arrays):
    return np.array(arrays, dtype=bool).T if len(arrays) > 1 else arrays[0]


def bits(n, k):
    v = np.arange(1 << k)
    return [((v >> j) & 1).astype(bool) for j in range(n)]


def main():
    assert not (OUT / 'SIGNED_CARRIER_RELATIONS.csv').exists(), 'already built'
    contract, arrays, names, views = S.load_snapshot()
    lineage = {(r['source'], r['node_name']): r for r in S.rows(S.ROOT / '_p0pilot/control_role_pattern_20261107/NODE_LINEAGE.csv')}

    src_delta = 's15850t100__injdelta_d1_s42'
    src_alpha = 's35932t200__injalpha_d1_s42'
    flows = {'delta': 'ys_nand', 'alpha': 'ys_abc'}
    o_delta = S.raw_network(S.F / 'orig' / (src_delta + '.v'), S.lib_pins)
    t_delta = S.raw_network(S.F / 'trans' / (src_delta + '__' + flows['delta'] + '.v'), S.lib_pins)
    o_alpha = S.raw_network(S.F / 'orig' / (src_alpha + '.v'), S.lib_pins)
    t_alpha = S.raw_network(S.F / 'trans' / (src_alpha + '__' + flows['alpha'] + '.v'), S.lib_pins)

    rows_alpha = S.view_rows(views, names, src_alpha + '__' + flows['alpha'])
    rows_delta = S.view_rows(views, names, src_delta + '__' + flows['delta'])

    def snap(view_rows, cell):
        if cell not in view_rows:
            return '', ''
        r = view_rows[cell]
        return int(arrays['y'][r]), bool(arrays['trusted'][r])

    rels = []

    # ---------- R1 alpha P2 <-> _0384_ (polarity -1) ----------
    a, b, c, u1, u2 = bits(5, 5)
    es = {'n8566': a, 'WX3484': b, 'DFF_955_n1': c, 'n4183': u1, 'n2940': u2}
    et = {'TrojanAP0.IN2': a, 'TrojanAP1.IN2': b, 'DFF_955_n1': c, 'TrojanAT1.IN1': u1, 'TrojanAT1.IN2': u2}
    p2, used_s = S.evaluate(o_alpha, S.LIB, 'TrojanA_p2', es)
    tgt, used_t = S.evaluate(t_alpha, S.LIB, '_0384_', et)
    assert np.array_equal(tgt, ~p2), 'R1 polarity'
    rels.append(dict(
        relation_id='R1_alpha_P2_carrier', split='train', source_object=src_alpha, implementation_flow=flows['alpha'],
        source_cell='TrojanAP2', source_output_pin='Q', source_signal='TrojanA_p2',
        target_signal='_0384_', target_driver_cells='g__0384__527', target_rows=str(rows_alpha['g__0384__527']),
        relation_type='signed_signal_equal', polarity='-1',
        aligned_boundary='a=n8566,b=WX3484,c=DFF_955_n1,u1=n4183~TrojanAT1.IN1,u2=n2940~TrojanAT1.IN2;T=NOT(u1 OR u2)',
        query_context='free PI nets a,b,c; T represented by NOR inputs u1,u2; DFF_1081_Q_reg not used',
        host_usage='active', observable_use_endpoints='PO test_so62; first-register D inputs',
        physical_D_or_PO_paths='_0384_ -> g_test_so62_530 -> test_so62 (PO); -> g__U6001.Q_2345 -> DFF_1113_Q_reg.D; -> g__2422__5179 chain',
        source_sha=S.sha(S.F / 'orig' / (src_alpha + '.v')),
        target_sha=S.sha(S.F / 'trans' / (src_alpha + '__' + flows['alpha'] + '.v')),
        mapping_sha=S.sha(S.F / 'mappings' / (src_alpha + '__' + flows['alpha'] + '.json')),
        evidence_ids='LOCAL_TRUTH:R1(32);CASE_CONCLUSIONS.csv;SIGNAL_CHAIN.csv;CARRIER_TO_HOST_PATHS.json',
        proof_scope='aligned 5-input local Boolean cut with real behavioral-library formulas;NOT whole-design CEC;NOT reachable-state activation',
        accepted_or_unresolved='accepted', exclusion_reason='',
        current_y=snap(rows_alpha, 'g__0384__527')[0], current_trusted=snap(rows_alpha, 'g__0384__527')[1],
        source_y=lineage[(src_alpha, 'TrojanAP2')]['old_y'], source_trusted=lineage[(src_alpha, 'TrojanAP2')]['old_trusted'],
        named_copy='g_TrojanA_p2_528', named_copy_rows=str(rows_alpha['g_TrojanA_p2_528']),
        named_copy_y=snap(rows_alpha, 'g_TrojanA_p2_528')[0], named_copy_trusted=snap(rows_alpha, 'g_TrojanA_p2_528')[1]))

    # ---------- R2 alpha T <-> _0383_ (polarity -1) ----------
    tval = ~(u1 | u2)
    src_t, _ = S.evaluate(o_alpha, S.LIB, 'TrojanA_t1', es)
    tgt_t, _ = S.evaluate(t_alpha, S.LIB, '_0383_', et)
    assert np.array_equal(src_t, tval) and np.array_equal(tgt_t, ~tval), 'R2 polarity'
    rels.append(dict(
        relation_id='R2_alpha_T_carrier', split='train', source_object=src_alpha, implementation_flow=flows['alpha'],
        source_cell='TrojanAT1', source_output_pin='QN', source_signal='TrojanA_t1',
        target_signal='_0383_', target_driver_cells='g__0383__520', target_rows=str(rows_alpha['g__0383__520']),
        relation_type='signed_signal_equal', polarity='-1',
        aligned_boundary='u1=n4183~TrojanAT1.IN1,u2=n2940~TrojanAT1.IN2;T=NOT(u1 OR u2)',
        query_context='free NOR inputs;trigger signal free;no DFF',
        host_usage='active', observable_use_endpoints='PO test_so62;first-register D inputs',
        physical_D_or_PO_paths='_0383_ -> g__0385__529 -> g_test_so62_530 -> test_so62 / DFF branches',
        source_sha=S.sha(S.F / 'orig' / (src_alpha + '.v')),
        target_sha=S.sha(S.F / 'trans' / (src_alpha + '__' + flows['alpha'] + '.v')),
        mapping_sha=S.sha(S.F / 'mappings' / (src_alpha + '__' + flows['alpha'] + '.json')),
        evidence_ids='LOCAL_TRUTH:R2(4);SIGNAL_CHAIN.csv;CARRIER_TO_HOST_PATHS.json',
        proof_scope='aligned 2-input local complement;NOT whole-design CEC',
        accepted_or_unresolved='accepted', exclusion_reason='',
        current_y=snap(rows_alpha, 'g__0383__520')[0], current_trusted=snap(rows_alpha, 'g__0383__520')[1],
        source_y=lineage[(src_alpha, 'TrojanAT1')]['old_y'], source_trusted=lineage[(src_alpha, 'TrojanAT1')]['old_trusted'],
        named_copy='', named_copy_rows='', named_copy_y='', named_copy_trusted=''))

    # ---------- R3 alpha H <-> _0001_ (polarity -1) ----------
    h = np.array([0, 1], bool)
    es_h = {'test_so62_orig': h}
    et_h = {'test_so62_orig': h}
    src_h, _ = S.evaluate(o_alpha, S.LIB, 'test_so62_orig', es_h)
    tgt_h, _ = S.evaluate(t_alpha, S.LIB, '_0001_', et_h)
    assert np.array_equal(tgt_h, ~src_h), 'R3 polarity'
    rels.append(dict(
        relation_id='R3_alpha_H_carrier', split='train', source_object=src_alpha, implementation_flow=flows['alpha'],
        source_cell='DFF_1081_Q_reg', source_output_pin='Q', source_signal='test_so62_orig',
        target_signal='_0001_', target_driver_cells='g__0001__2', target_rows=str(rows_alpha['g__0001__2']),
        relation_type='signed_signal_equal', polarity='-1',
        aligned_boundary='h=DFF_1081_Q_reg.Q (free state)',
        query_context='free register state;no clock/next-state analysis',
        host_usage='active', observable_use_endpoints='PO test_so62',
        physical_D_or_PO_paths='_0001_ -> g__0385__529 -> g_test_so62_530 -> test_so62',
        source_sha=S.sha(S.F / 'orig' / (src_alpha + '.v')),
        target_sha=S.sha(S.F / 'trans' / (src_alpha + '__' + flows['alpha'] + '.v')),
        mapping_sha=S.sha(S.F / 'mappings' / (src_alpha + '__' + flows['alpha'] + '.json')),
        evidence_ids='LOCAL_TRUTH:R3(2);SIGNAL_CHAIN.csv',
        proof_scope='local complement of host state;NOT state-transition proof',
        accepted_or_unresolved='accepted', exclusion_reason='',
        current_y=snap(rows_alpha, 'g__0001__2')[0], current_trusted=snap(rows_alpha, 'g__0001__2')[1],
        source_y='', source_trusted='',
        named_copy='', named_copy_rows='', named_copy_y='', named_copy_trusted=''))

    # ---------- R4/R5 delta DP0/DP2 named copies (polarity +1, dead) ----------
    x, t = bits(2, 2)
    es_d = {'n533': x, 'TrojanD_t4': t}
    et_d = {'n533': x, 'TrojanDHJ.S': t, 'TrojanDP2.S': ~x, '_0473_': ~t}
    for rid, gate, out, base, inv in (
            ('R4_delta_DP0_dead_copy', 'TrojanDP0', 'TrojanD_p0', 'g_TrojanD_p0_8957', 'g_TrojanD_p0_8958'),
            ('R5_delta_DP2_dead_copy', 'TrojanDP2', 'TrojanD_p2', 'g_TrojanD_p2_934', 'g_TrojanD_p2_935')):
        src_v, _ = S.evaluate(o_delta, S.LIB, out, es_d)
        _, base_net = S.output_net(t_delta, base)
        _, inv_net = S.output_net(t_delta, inv)
        mid, _ = S.evaluate(t_delta, S.LIB, base_net, et_d)
        tgt_v, _ = S.evaluate(t_delta, S.LIB, inv_net, et_d)
        assert np.array_equal(src_v, x | t), rid + ' source'
        assert np.array_equal(tgt_v, src_v), rid + ' target'
        assert np.array_equal(mid, ~src_v), rid + ' mid'
        paths = S.pin_paths(t_delta, inv, S.lib_pins)
        assert paths['closed_no_PO_no_register'], rid + ' not dead'
        rels.append(dict(
            relation_id=rid, split='train', source_object=src_delta, implementation_flow=flows['delta'],
            source_cell=gate, source_output_pin='Q', source_signal=out,
            target_signal=gate + '.Q', target_driver_cells=inv + '|' + base, target_rows=str(rows_delta[inv]),
            relation_type='signed_signal_equal', polarity='+1',
            aligned_boundary='x=n533,T=TrojanDHJ.S;target copies use NOT T (_0473_) and NOT x (TrojanDP2.S)',
            query_context='free x,T;DFF states not used',
            host_usage='dead',
            observable_use_endpoints='none',
            physical_D_or_PO_paths='closed component: no PO and no register',
            source_sha=S.sha(S.F / 'orig' / (src_delta + '.v')),
            target_sha=S.sha(S.F / 'trans' / (src_delta + '__' + flows['delta'] + '.v')),
            mapping_sha=S.sha(S.F / 'mappings' / (src_delta + '__' + flows['delta'] + '.json')),
            evidence_ids='LOCAL_TRUTH:%s(4);CARRIER_TO_HOST_PATHS.json' % rid[:2],
            proof_scope='aligned 2-input local equality;copy is structurally dead;NOT a host carrier',
            accepted_or_unresolved='accepted', exclusion_reason='dead_copy_not_host_carrier',
            current_y=snap(rows_delta, inv)[0], current_trusted=snap(rows_delta, inv)[1],
            source_y=lineage[(src_delta, gate)]['old_y'], source_trusted=lineage[(src_delta, gate)]['old_trusted'],
            named_copy=inv, named_copy_rows=str(rows_delta[inv]),
            named_copy_y=snap(rows_delta, inv)[0], named_copy_trusted=snap(rows_delta, inv)[1]))

    # ---------- R6 delta absorbed at output ----------
    h2 = np.array([0, 1], bool)
    xv, tv, hv = np.meshgrid(x, t, h2, indexing='ij')
    xv, tv, hv = xv.ravel(), tv.ravel(), hv.ravel()
    et_abs = {'n533': xv, 'TrojanDHJ.S': tv, 'TrojanDHJ.IN1': hv, '_0473_': ~tv, '_0729_': ~hv, 'TrojanDP2.S': ~xv}
    out_v, _ = S.evaluate(t_delta, S.LIB, 'TrojanDHJ.Q', et_abs)
    assert np.array_equal(out_v, hv | tv), 'R6 final expression'
    # x is irrelevant to the final output: flip x and compare
    et_flip = dict(et_abs) | {'n533': ~xv, 'TrojanDP2.S': xv}
    out_flip, _ = S.evaluate(t_delta, S.LIB, 'TrojanDHJ.Q', et_flip)
    assert np.array_equal(out_v, out_flip), 'R6 x-dependence'
    p0_v, _ = S.evaluate(o_delta, S.LIB, 'TrojanD_p0', {'n533': xv, 'TrojanD_t4': tv})
    assert np.array_equal(p0_v, xv | tv)
    rels.append(dict(
        relation_id='R6_delta_absorbed_at_output', split='train', source_object=src_delta, implementation_flow=flows['delta'],
        source_cell='TrojanDP0|TrojanDP2', source_output_pin='Q', source_signal='TrojanD_p0|TrojanD_p2',
        target_signal='g10801', target_driver_cells='g_g10801_1673', target_rows=str(rows_delta['g_g10801_1673']),
        relation_type='absorbed_at_output', polarity='n/a',
        aligned_boundary='x=n533,T=TrojanDHJ.S,H=TrojanDHJ.IN1',
        query_context='free x,T,H;DFF states not used',
        host_usage='active', observable_use_endpoints='PO g10801',
        physical_D_or_PO_paths='g_g10801_1673 -> PO g10801',
        source_sha=S.sha(S.F / 'orig' / (src_delta + '.v')),
        target_sha=S.sha(S.F / 'trans' / (src_delta + '__' + flows['delta'] + '.v')),
        mapping_sha=S.sha(S.F / 'mappings' / (src_delta + '__' + flows['delta'] + '.json')),
        evidence_ids='LOCAL_TRUTH:R6(8);CASE_CONCLUSIONS.csv',
        proof_scope='final output = H OR T over the aligned cut;x-dependence absorbed;no node-level pairing produced',
        accepted_or_unresolved='accepted', exclusion_reason='',
        current_y=snap(rows_delta, 'g_g10801_1673')[0], current_trusted=snap(rows_delta, 'g_g10801_1673')[1],
        source_y=lineage[(src_delta, 'TrojanDP0')]['old_y'], source_trusted=lineage[(src_delta, 'TrojanDP0')]['old_trusted'],
        named_copy='g_TrojanD_p0_8957|g_TrojanD_p2_934', named_copy_rows='',
        named_copy_y='', named_copy_trusted=''))

    S.table(OUT / 'SIGNED_CARRIER_RELATIONS.csv', rels)

    # ---------- counterexamples ----------
    ce = []
    # C1 polarity removed: R1 +1 would mismatch on all patterns
    ce.append(dict(check='C1_polarity_removed', relation='R1_alpha_P2_carrier',
                   manipulation='treat _0384_ as equal (polarity +1) instead of inverted',
                   mismatch_patterns=int((tgt != p2).sum()), total_patterns=int(len(p2)), expected='reject',
                   verdict='pass' if (tgt != p2).all() else 'fail'))
    # C2 unaligned boundary: misalign the T phase (T = u1 OR u2 instead of NOT(u1 OR u2))
    es_swap = {'n8566': a, 'WX3484': b, 'DFF_955_n1': c, 'n4183': u1, 'n2940': u2, 'TrojanA_t1': (u1 | u2)}
    p2_swap, _ = S.evaluate(o_alpha, S.LIB, 'TrojanA_p2', es_swap)
    ce.append(dict(check='C2_unaligned_boundary', relation='R1_alpha_P2_carrier',
                   manipulation='misalign the T phase: T=(u1 OR u2) instead of NOT(u1 OR u2)',
                   mismatch_patterns=int((tgt != ~p2_swap).sum()), total_patterns=int(len(p2)), expected='reject',
                   verdict='pass' if (tgt != ~p2_swap).any() else 'fail'))
    # C3 name-only: named copy equals P2 but is dead
    named_v, _ = S.evaluate(t_alpha, S.LIB, 'TrojanAHJ.IN2', et)
    ce.append(dict(check='C3_name_only_dead_copy', relation='R1_alpha_P2_carrier',
                   manipulation='accept target by name g_TrojanA_p2_528 without host-use check',
                   mismatch_patterns=int((named_v != p2).sum()), total_patterns=int(len(p2)),
                   expected='function matches (+1) but host_usage=dead -> must not be the only carrier',
                   verdict='pass' if (named_v == p2).all() else 'fail'))
    # C4 context mixing: free H vs tied H, at assignments where T=0 so the output can be 1
    n4 = 4
    u1_4 = np.ones(n4, bool); u2_4 = np.zeros(n4, bool)     # T = NOT(u1 OR u2) = 0
    a4 = np.array([0, 1, 0, 1], bool); b4 = np.array([0, 0, 1, 1], bool); c4 = np.array([0, 0, 0, 0], bool)
    et4 = {'TrojanAP0.IN2': a4, 'TrojanAP1.IN2': b4, 'DFF_955_n1': c4, 'TrojanAT1.IN1': u1_4, 'TrojanAT1.IN2': u2_4}
    test_free, _ = S.evaluate(t_alpha, S.LIB, 'test_so62', dict(et4) | {'test_so62_orig': np.array([0, 1, 0, 1], bool)})
    test_tied, _ = S.evaluate(t_alpha, S.LIB, 'test_so62', dict(et4) | {'test_so62_orig': np.zeros(n4, bool)})
    ce.append(dict(check='C4_freeQ_vs_tiedQ', relation='R1_alpha_P2_carrier',
                   manipulation='mix free register state with tied-to-0 state (T=0 assignments)',
                   mismatch_patterns=int((test_free != test_tied).sum()), total_patterns=int(n4),
                   expected='context difference changes outputs -> declare query_context',
                   verdict='pass' if (test_free != test_tied).any() else 'fail'))
    S.table(OUT / 'COUNTEREXAMPLES.csv', ce)

    # ---------- unresolved / excluded ----------
    unresolved = [
        dict(item='delta DP0 -> surviving trigger/output one-to-one', reason='payload absorbed;no independent active root', relation='R6',
             scope='do not fabricate node pairing'),
        dict(item='delta DP2 -> surviving trigger/output one-to-one', reason='same as DP0', relation='R6',
             scope='do not fabricate node pairing'),
        dict(item='alpha P2 -> named copy as the only carrier', reason='named copy is dead;live carrier is inverted', relation='R1',
             scope='signed relation required'),
    ]
    S.table(OUT / 'UNRESOLVED.csv', unresolved)
    excluded = [
        dict(item='delta DP0/DP2 full-chain orig->nand CEC', reason='not proved;only local cut replay', relation='R6'),
        dict(item='alpha P2 orig->abc whole-output equivalence', reason='reused certificates cover T/P0/P1 upstream only', relation='R1'),
        dict(item='any test-set pairing', reason='no reliable pair availability;out of scope', relation='n/a'),
    ]
    S.table(OUT / 'EXCLUDED.csv', excluded)

    # input hashes
    inputs = [S.F / 'orig' / (src_delta + '.v'), S.F / 'orig' / (src_alpha + '.v'),
              S.F / 'trans' / (src_delta + '__' + flows['delta'] + '.v'),
              S.F / 'trans' / (src_alpha + '__' + flows['alpha'] + '.v'),
              S.F / 'mappings' / (src_delta + '__' + flows['delta'] + '.json'),
              S.F / 'mappings' / (src_alpha + '__' + flows['alpha'] + '.json'),
              S.CONTRACT, S.F / 'data/processed/node_names_trans.txt',
              S.ROOT / '_p0pilot/control_role_pattern_20261107/NODE_LINEAGE.csv',
              S.ROOT / '_p0pilot/control_carrier_trace_20261109/CASE_CONCLUSIONS.csv',
              S.LIB.path]
    S.table(OUT / 'INPUT_HASHES.csv', [dict(path=(str(p.relative_to(S.ROOT)) if str(p).startswith(str(S.ROOT)) else str(p)), sha256=S.sha(p)) for p in inputs])
    S.write_json(OUT / 'BUILD_SUMMARY.json', dict(relations=len(rels), counterexamples=len(ce),
                                                  unresolved=len(unresolved), excluded=len(excluded),
                                                  training=0, SAT=0, solver_calls=0, model_forwards=0,
                                                  labels_changed=False))
    print('built', len(rels), 'relations')


if __name__ == '__main__':
    main()
