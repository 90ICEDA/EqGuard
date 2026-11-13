"""Independent verification of the signed-carrier relations (read-only, no model calls).

Re-derives each relation from the raw netlists, re-checks coordinates, labels, host use,
hashes and counterexample outcomes; then writes VERIFIED.json and the result hash list.
"""
import json
from pathlib import Path

import numpy as np

import Signed_common as S

OUT = S.HERE


def load_netlists():
    d = 's15850t100__injdelta_d1_s42'
    a = 's35932t200__injalpha_d1_s42'
    return dict(
        o_delta=S.raw_network(S.F / 'orig' / (d + '.v'), S.lib_pins),
        t_delta=S.raw_network(S.F / 'trans' / (d + '__ys_nand.v'), S.lib_pins),
        o_alpha=S.raw_network(S.F / 'orig' / (a + '.v'), S.lib_pins),
        t_alpha=S.raw_network(S.F / 'trans' / (a + '__ys_abc.v'), S.lib_pins))


def bits(n, k):
    v = np.arange(1 << k)
    return [((v >> j) & 1).astype(bool) for j in range(n)]


def main():
    rels = S.rows(OUT / 'SIGNED_CARRIER_RELATIONS.csv')
    ce = S.rows(OUT / 'COUNTEREXAMPLES.csv')
    contract, arrays, names, views = S.load_snapshot()
    n = load_netlists()
    rows_alpha = S.view_rows(views, names, 's35932t200__injalpha_d1_s42__ys_abc')
    rows_delta = S.view_rows(views, names, 's15850t100__injdelta_d1_s42__ys_nand')

    required = ['relation_id', 'split', 'source_object', 'implementation_flow', 'source_cell', 'source_output_pin',
                'source_signal', 'target_signal', 'target_driver_cells', 'target_rows', 'relation_type', 'polarity',
                'aligned_boundary', 'query_context', 'host_usage', 'observable_use_endpoints',
                'physical_D_or_PO_paths', 'source_sha', 'target_sha', 'mapping_sha', 'evidence_ids', 'proof_scope',
                'accepted_or_unresolved', 'exclusion_reason', 'current_y', 'current_trusted']
    checks = []
    for r in rels:
        rid = r['relation_id']
        missing = [k for k in required if r.get(k) == '' and k not in ('exclusion_reason', 'named_copy', 'named_copy_rows')]
        assert not missing, (rid, missing)
        assert r['accepted_or_unresolved'] in ('accepted', 'unresolved')
        assert r['relation_type'] in ('signed_signal_equal', 'region_relation', 'absorbed_at_output', 'unresolved')
        assert r['polarity'] in ('+1', '-1', 'n/a')
        checks.append(rid)

    # --- R1: alpha P2 <-> _0384_, polarity -1 ---
    a, b, c, u1, u2 = bits(5, 5)
    es = {'n8566': a, 'WX3484': b, 'DFF_955_n1': c, 'n4183': u1, 'n2940': u2}
    et = {'TrojanAP0.IN2': a, 'TrojanAP1.IN2': b, 'DFF_955_n1': c, 'TrojanAT1.IN1': u1, 'TrojanAT1.IN2': u2}
    p2, _ = S.evaluate(n['o_alpha'], S.LIB, 'TrojanA_p2', es)
    tgt, _ = S.evaluate(n['t_alpha'], S.LIB, '_0384_', et)
    assert np.array_equal(tgt, ~p2)
    r1 = next(r for r in rels if r['relation_id'] == 'R1_alpha_P2_carrier')
    assert r1['polarity'] == '-1' and r1['host_usage'] == 'active'
    assert r1['target_signal'] == '_0384_' and int(r1['target_rows']) == rows_alpha['g__0384__527']
    assert int(r1['current_y']) == int(arrays['y'][rows_alpha['g__0384__527']]) == 0
    assert str(r1['current_trusted']).strip().lower() == 'false'
    assert r1['named_copy'] == 'g_TrojanA_p2_528' and int(r1['named_copy_y']) == 1
    assert int(r1['named_copy_rows']) == rows_alpha['g_TrojanA_p2_528']
    # host use recomputed
    paths = S.pin_paths(n['t_alpha'], 'g__0384__527', S.lib_pins)
    assert paths['PO_paths'] and paths['first_register_paths']
    # named copy is dead
    named_paths = S.pin_paths(n['t_alpha'], 'g_TrojanA_p2_528', S.lib_pins)
    assert named_paths['closed_no_PO_no_register']

    # --- R2: alpha T <-> _0383_, polarity -1 ---
    src_t, _ = S.evaluate(n['o_alpha'], S.LIB, 'TrojanA_t1', es)
    tgt_t, _ = S.evaluate(n['t_alpha'], S.LIB, '_0383_', et)
    assert np.array_equal(src_t, ~(u1 | u2)) and np.array_equal(tgt_t, ~src_t)

    # --- R3: alpha H <-> _0001_, polarity -1 ---
    h = np.array([0, 1], bool)
    assert np.array_equal(S.evaluate(n['t_alpha'], S.LIB, '_0001_', {'test_so62_orig': h})[0], ~h)

    # --- R4/R5: delta dead copies, polarity +1 ---
    x, t = bits(2, 2)
    ed = {'n533': x, 'TrojanDHJ.S': t, 'TrojanDP2.S': ~x, '_0473_': ~t}
    for rid, gate, out in (('R4_delta_DP0_dead_copy', 'TrojanDP0', 'TrojanD_p0'),
                           ('R5_delta_DP2_dead_copy', 'TrojanDP2', 'TrojanD_p2')):
        src_v, _ = S.evaluate(n['o_delta'], S.LIB, out, {'n533': x, 'TrojanD_t4': t})
        r = next(q for q in rels if q['relation_id'] == rid)
        inv_cell = r['target_driver_cells'].split('|')[0]
        _, inv_net = S.output_net(n['t_delta'], inv_cell)
        tgt_v, _ = S.evaluate(n['t_delta'], S.LIB, inv_net, ed)
        assert np.array_equal(tgt_v, src_v) and np.array_equal(src_v, x | t)
        assert r['polarity'] == '+1' and r['host_usage'] == 'dead'
        assert int(r['current_y']) == 1 and str(r['current_trusted']).strip().lower() == 'true'
        assert S.pin_paths(n['t_delta'], inv_cell, S.lib_pins)['closed_no_PO_no_register']

    # --- R6: absorbed output ---
    xx, tt, hh = np.meshgrid(x, t, np.array([0, 1], bool), indexing='ij')
    xx, tt, hh = xx.ravel(), tt.ravel(), hh.ravel()
    ea = {'n533': xx, 'TrojanDHJ.S': tt, 'TrojanDHJ.IN1': hh, '_0473_': ~tt, '_0729_': ~hh, 'TrojanDP2.S': ~xx}
    out_v, _ = S.evaluate(n['t_delta'], S.LIB, 'TrojanDHJ.Q', ea)
    assert np.array_equal(out_v, hh | tt)
    assert np.array_equal(out_v, S.evaluate(n['t_delta'], S.LIB, 'TrojanDHJ.Q',
                                            dict(ea) | {'n533': ~xx, 'TrojanDP2.S': xx})[0])
    assert np.array_equal(S.evaluate(n['o_delta'], S.LIB, 'TrojanD_p0', {'n533': xx, 'TrojanD_t4': tt})[0], xx | tt)

    # --- counterexamples ---
    verdicts = {r['check']: r['verdict'] for r in ce}
    assert all(v == 'pass' for v in verdicts.values()), verdicts
    assert int(next(r for r in ce if r['check'] == 'C1_polarity_removed')['mismatch_patterns']) == 32
    assert int(next(r for r in ce if r['check'] == 'C2_unaligned_boundary')['mismatch_patterns']) == 32
    assert int(next(r for r in ce if r['check'] == 'C3_name_only_dead_copy')['mismatch_patterns']) == 0
    assert int(next(r for r in ce if r['check'] == 'C4_freeQ_vs_tiedQ')['mismatch_patterns']) >= 1

    # --- input hashes ---
    hashes = S.rows(OUT / 'INPUT_HASHES.csv')
    for r in hashes:
        p = Path(r['path']) if Path(r['path']).is_absolute() else S.ROOT / r['path']
        assert S.sha(p) == r['sha256'], r['path']

    # --- result file hashes ---
    files = ['SIGNED_CARRIER_RELATIONS.csv', 'COUNTEREXAMPLES.csv', 'UNRESOLVED.csv', 'EXCLUDED.csv',
             'INPUT_HASHES.csv', 'build_relations.py', 'Signed_common.py']
    result = dict(passed=True, relations=len(rels), accepted=sum(r['accepted_or_unresolved'] == 'accepted' for r in rels),
                  unresolved=sum(r['accepted_or_unresolved'] == 'unresolved' for r in rels),
                  signed_relations=sum(r['relation_type'] == 'signed_signal_equal' for r in rels),
                  absorbed=sum(r['relation_type'] == 'absorbed_at_output' for r in rels),
                  polarity_plus=sum(r['polarity'] == '+1' for r in rels),
                  polarity_minus=sum(r['polarity'] == '-1' for r in rels),
                  live=sum(r['host_usage'] == 'active' for r in rels), dead=sum(r['host_usage'] == 'dead' for r in rels),
                  counterexamples=verdicts, local_truth_patterns=32 + 4 + 2 + 4 + 4 + 8,
                  training=0, SAT=0, solver_calls=0, model_forwards=0, labels_changed=False,
                  files={f: S.sha(OUT / f) for f in files})
    S.write_json(OUT / 'VERIFIED.json', result)
    print(json.dumps({k: v for k, v in result.items() if k != 'files'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
