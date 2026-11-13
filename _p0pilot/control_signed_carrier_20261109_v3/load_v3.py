"""Strict v3 loader/validator: structured context, driven source signal, phase evidence, absorbed outputs."""
import json
import re

import numpy as np

import Signed_common as S

OUT = S.HERE
REQUIRED = ['relation_id', 'split', 'source_object', 'implementation_flow', 'source_cell', 'source_output_pin',
            'source_signal', 'target_signal', 'target_driver_cells', 'target_output_pin', 'target_rows',
            'relation_type', 'polarity', 'boundary_aliases', 'k_inputs', 'context', 'host_usage',
            'source_sha', 'target_sha', 'mapping_sha', 'evidence_ids', 'proof_scope',
            'accepted_or_unresolved', 'current_y', 'current_trusted']


def norm(name):
    n = name.lstrip('g').lstrip('_')
    n = n.split('.')[0]
    return re.sub(r'_\d+$', '', n)


def driver(g, net):
    o = g['drivers'].get(g['find'](net), set())
    assert len(o) == 1, ('driver_missing_or_ambiguous', net, sorted(o))
    return next(iter(o))


def out_pin(g, cell, net):
    typ, conns = g['pins'][cell]
    hits = [p for p, n in conns if n == g['find'](net) and p in S.lib_pins[typ]['outputs']]
    assert len(hits) == 1, ('output_pin', cell, net, hits)
    return hits[0]


def input_nets(g, cell):
    typ, conns = g['pins'][cell]
    return {p: n for p, n in conns if p in S.lib_pins[typ]['inputs']}


def is_inverter(g, cell):
    typ, conns = g['pins'][cell]
    if not typ.upper().startswith(('INV', 'NBUFF')):
        return None
    for pin in ('QN', 'Q'):
        try:
            ast = S.LIB.ast(typ, pin)
        except AssertionError:
            continue
        if ast[0] == '~':
            ins = [n for p, n in conns if p in ('IN', 'A')]
            return ins[0] if len(ins) == 1 else None
    return None


def load_rows(path):
    rows = S.rows(path)
    assert rows
    return rows


def validate(rows, members, netlists=None, snapshots=None, check_hashes=True):
    members = members if members is not None else S.rows(OUT / 'REGION_MEMBERS_V3.csv')
    nets = netlists if netlists is not None else {}
    snaps = snapshots if snapshots is not None else {'train': S.load_snapshot('train')}

    def g(kind, src, view=None):
        key = (kind, src, view)
        if key not in nets:
            p = S.F / kind / ((src + '.v') if kind == 'orig' else (view + '.v'))
            nets[key] = S.raw_network(p, S.lib_pins)
        return nets[key]

    for r in rows:
        rid = r['relation_id']
        for k in REQUIRED:
            assert r.get(k) not in (None, ''), ('missing_field', rid, k)
        assert r['relation_type'] in ('signed_signal_equal', 'region_relation', 'absorbed_at_output', 'unresolved')
        assert r['polarity'] in ('+1', '-1', 'n/a')
        assert r['accepted_or_unresolved'] == 'accepted'
        view = r['source_object'] + '__' + r['implementation_flow']
        sg, tg = g('orig', r['source_object']), g('trans', r['source_object'], view)
        if check_hashes:
            assert S.sha(S.F / 'orig' / (r['source_object'] + '.v')) == r['source_sha'], ('source_sha', rid)
            assert S.sha(S.F / 'trans' / (view + '.v')) == r['target_sha'], ('target_sha', rid)
            assert S.sha(S.F / 'mappings' / (view + '.json')) == r['mapping_sha'], ('mapping_sha', rid)
        # ---- source signal binding ----
        if r['relation_type'] == 'absorbed_at_output':
            obs = json.loads(r['source_observation'])
            assert driver(sg, obs['signal']) == obs['cell'], ('source_obs_driver', rid)
            assert out_pin(sg, obs['cell'], obs['signal']) == obs['pin'], ('source_obs_pin', rid)
            tobs = json.loads(r['target_observation'])
            assert driver(tg, tobs['signal']) == tobs['cell'], ('target_obs_driver', rid)
            assert out_pin(tg, tobs['cell'], tobs['signal']) == tobs['pin'], ('target_obs_pin', rid)
        else:
            assert driver(sg, r['source_signal']) == r['source_cell'], ('source_signal_driver', rid)
            assert out_pin(sg, r['source_cell'], r['source_signal']) == r['source_output_pin'], ('source_signal_pin', rid)
        # ---- target driver ----
        actual_driver = driver(tg, r['target_signal'])
        assert actual_driver == r['target_driver_cells'], ('target_driver_mismatch', rid, actual_driver)
        assert out_pin(tg, actual_driver, r['target_signal']) == r['target_output_pin'], ('target_pin', rid)
        # ---- coordinates / labels ----
        split = r['split']
        if split not in snaps:
            snaps[split] = S.load_snapshot(split)
        _, arr, names, views = snaps[split]
        row = S.view_rows(views, names, view).get(actual_driver, '')
        assert str(row) == r['target_rows'], ('row_mismatch', rid, row, r['target_rows'])
        if row != '':
            assert int(r['current_y']) == int(arr['y'][row]), ('y_mismatch', rid)
            assert (str(r['current_trusted']).lower() == 'true') == bool(arr['trusted'][row]), ('trusted_mismatch', rid)
        # ---- structured context ----
        ctx = json.loads(r['context'])
        assert set(ctx) == {'free_vars', 'fixed', 'state'}, ('context_keys', rid, sorted(ctx))
        free = list(ctx['free_vars'])
        assert len(free) == len(set(free)), ('context_dup_free', rid)
        aliases = json.loads(r['boundary_aliases'])
        assert set(free) == {a['source_net'] for a in aliases}, ('context_free_mismatch', rid)
        all_src = {n for _, conns in sg['pins'].values() for _, n in conns}
        for k, v in ctx['fixed'].items():
            assert k not in free, ('context_free_fixed_conflict', rid, k)
            assert k in all_src or str(k).startswith('#'), ('context_fixed_unknown', rid, k)
            assert str(v) in ('0', '1'), ('context_fixed_value', rid, v)
        for st in ctx['state']:
            assert set(st) == {'net', 'dff_cell', 'pin'}, ('context_state_keys', rid)
            assert st['net'] in free, ('context_state_not_free', rid, st['net'])
            dc = driver(sg, st['net'])
            assert 'DFF' in sg['pins'][dc][0].upper(), ('context_state_not_dff', rid)
            assert norm(dc) == norm(st['dff_cell']), ('context_state_cell', rid, dc)
            assert out_pin(sg, dc, st['net']) == st['pin'], ('context_state_pin', rid)
        # ---- aliases ----
        assert len(aliases) == int(r['k_inputs']), ('k_inputs', rid)
        seen = set()
        for a in aliases:
            snet, tnet, inv, basis = a['source_net'], a['target_net'], bool(a['invert']), a['basis']
            assert snet in all_src or str(snet).startswith('#'), ('alias_source_not_net', rid, snet)
            assert snet not in seen, ('alias_duplicate', rid, snet)
            seen.add(snet)
            if basis == 'exact_name':
                assert not inv, ('alias_invert_without_evidence', rid, basis)
                assert snet == tnet, ('alias_exact', rid)
            elif basis == 'pin_alias':
                assert not inv, ('alias_invert_without_evidence', rid, basis)
                ac, ap = a.get('anchor_cell', ''), a.get('anchor_pin', '')
                assert ac in sg['pins'], ('anchor_cell', rid, ac)
                assert dict(sg['pins'][ac][1]).get(ap) == snet, ('anchor_conn', rid, ac, ap)
                assert tnet == f'{ac}.{ap}', ('alias_pin_name', rid, tnet)
            elif basis == 'driver_cell':
                assert not inv, ('alias_invert_without_evidence', rid, basis)
                assert norm(driver(tg, tnet)) == norm(driver(sg, snet)), ('alias_driver_cell', rid)
            elif basis == 'inv_formula':
                assert inv, ('alias_inv_flag', rid)
                anchor = a.get('anchor_net', '')
                assert anchor, ('anchor_missing', rid)
                assert is_inverter(tg, driver(tg, anchor)) == tnet, ('inv_structure', rid)
            else:
                raise AssertionError(('alias_basis_unknown', rid, basis))
        # ---- truth table ----
        k = len(aliases)
        patterns = 1 << k
        assert patterns <= 4096, ('patterns_over', rid)
        vals = np.arange(patterns)
        src_env, tgt_env = {}, {}
        for j, a in enumerate(aliases):
            v = ((vals >> j) & 1).astype(bool)
            src_env[a['source_net']] = v
            tgt_env[a['target_net']] = ~v if a['invert'] else v
        if r['relation_type'] == 'absorbed_at_output':
            sv, _ = S.evaluate(sg, S.LIB, json.loads(r['source_observation'])['signal'], src_env)
            tv, _ = S.evaluate(tg, S.LIB, json.loads(r['target_observation'])['signal'], tgt_env)
            expected = src_env['g10801_orig'] | src_env['TrojanD_t4']
            assert np.array_equal(sv, expected), ('absorbed_source_expression', rid)
            assert np.array_equal(tv, expected), ('absorbed_target_expression', rid)
            flip = dict(tgt_env)
            flip['TrojanDP2.S'] = ~flip['TrojanDP2.S']
            tv2, _ = S.evaluate(tg, S.LIB, json.loads(r['target_observation'])['signal'], flip)
            assert np.array_equal(tv, tv2), ('absorbed_not_independent', rid)
        else:
            sv, _ = S.evaluate(sg, S.LIB, r['source_signal'], src_env)
            tv, _ = S.evaluate(tg, S.LIB, r['target_signal'], tgt_env)
            if r['polarity'] == '+1':
                assert np.array_equal(tv, sv), ('polarity_plus_fail', rid)
            else:
                assert np.array_equal(tv, ~sv), ('polarity_minus_fail', rid)
        # ---- host usage ----
        paths = S.pin_paths(tg, actual_driver, S.lib_pins)
        assert (r['host_usage'] == 'dead') == bool(paths['closed_no_PO_no_register']), ('host_usage', rid)
        if r['relation_type'] == 'absorbed_at_output':
            endpoints = json.loads(r['host_endpoints'])
            joined = '|'.join(str(x) for route in paths['PO_paths'] for x in route) + '|' + '|'.join(tg['po'])
            for e in endpoints:
                assert e in joined, ('host_endpoint_missing', rid, e)
        # ---- region members ----
        for m in [x for x in members if x['relation_id'] == rid]:
            assert m['cell'] in tg['pins'], ('member_cell', rid, m['cell'])
            assert out_pin(tg, m['cell'], m['signal']) == m['output_pin'], ('member_pin', rid)
            if m['polarity'] in ('+1', '-1') and r['relation_type'] == 'signed_signal_equal':
                env = dict(tgt_env)
                env[r['target_signal']] = tv
                mv, _ = S.evaluate(tg, S.LIB, m['signal'], env)
                sv, _ = S.evaluate(sg, S.LIB, r['source_signal'], src_env)
                want = sv if m['polarity'] == '+1' else ~sv
                assert np.array_equal(mv, want), ('member_polarity', rid, m['cell'])
    return dict(relations=len(rows), members=len(members))


def main():
    rows = load_rows(OUT / 'RELATIONS_V3.csv')
    result = validate(rows, None)
    result.update(passed=True, training=0, SAT=0, solver_calls=0, model_forwards=0, labels_changed=False,
                  files={f: S.sha(OUT / f) for f in ('RELATIONS_V3.csv', 'REGION_MEMBERS_V3.csv', 'load_v3.py')})
    S.write_json(OUT / 'VERIFIED_V3.json', result)
    print(json.dumps({k: v for k, v in result.items() if k != 'files'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
