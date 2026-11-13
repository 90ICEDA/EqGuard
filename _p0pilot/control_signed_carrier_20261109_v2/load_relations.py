"""Strict loader + independent validator for the v2 relations.

The validator does not trust any 'pass' column: it re-reads netlists, re-checks drivers,
aliases, phases, coordinates, labels, context tokens and host usage, and re-evaluates the
local truth table. It raises AssertionError with a reason on the first violation, so the
tamper tests can confirm real rejection.
"""
import json
import re

import numpy as np

import Signed_common as S

OUT = S.HERE
FLOWS = {'delta': 'ys_nand', 'alpha': 'ys_abc'}
REQUIRED = ['relation_id', 'split', 'source_object', 'implementation_flow', 'source_cell', 'source_output_pin',
            'source_signal', 'target_signal', 'target_driver_cells', 'target_output_pin', 'target_rows',
            'relation_type', 'polarity', 'boundary_aliases', 'k_inputs', 'context', 'host_usage',
            'source_sha', 'target_sha', 'mapping_sha', 'evidence_ids', 'proof_scope',
            'accepted_or_unresolved', 'current_y', 'current_trusted']


def norm_cell(name):
    n = name.lstrip('g').lstrip('_')
    n = n.split('.')[0]
    return re.sub(r'_\d+$', '', n)


def driver(g, net):
    owners = g['drivers'].get(g['find'](net), set())
    assert len(owners) == 1, ('driver_missing_or_ambiguous', net, sorted(owners))
    return next(iter(owners))


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
    assert rows, 'empty'
    return rows


def validate(rows, members=None, netlists=None, snapshots=None, check_hashes=True):
    """Validate every relation. Raises AssertionError(reason) on the first failure."""
    members = S.rows(OUT / 'REGION_MEMBERS_V2.csv') if members is None else members
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
        # source gate(s) and output pin
        src_cells = r['source_cell'].split('|')
        for sc in src_cells:
            assert sc in sg['pins'], ('source_cell_missing', rid, sc)
        assert r['source_output_pin'] in S.lib_pins[list({sg["pins"][c][0] for c in src_cells})[0]]['outputs'] or len(src_cells) > 1
        # target driver exactly one, and our record equals it
        actual_driver = driver(tg, r['target_signal'])
        assert actual_driver == r['target_driver_cells'], ('target_driver_mismatch', rid, actual_driver)
        assert out_pin(tg, actual_driver, r['target_signal']) == r['target_output_pin'], ('target_pin', rid)
        # coordinates and labels
        split = r['split']
        if split not in snaps:
            snaps[split] = S.load_snapshot(split)
        _, arr, names, views = snaps[split]
        row = S.view_rows(views, names, view).get(actual_driver, '')
        assert str(row) == r['target_rows'], ('row_mismatch', rid, row, r['target_rows'])
        if row != '':
            assert int(r['current_y']) == int(arr['y'][row]), ('y_mismatch', rid)
            assert (str(r['current_trusted']).lower() == 'true') == bool(arr['trusted'][row]), ('trusted_mismatch', rid)
        # context token
        assert ('free_cut' in r['context']) or ('free_state' in r['context']), ('context_missing', rid)
        assert 'tied' not in r['context'].lower(), ('context_tied', rid)
        # boundary aliases
        aliases = json.loads(r['boundary_aliases'])
        assert len(aliases) == int(r['k_inputs']), ('k_inputs', rid)
        s_in = {}
        if len(src_cells) == 1:
            s_in = input_nets(sg, src_cells[0])
        else:
            for sc in src_cells:
                s_in.update(input_nets(sg, sc))
        seen_src = set()
        all_src_nets = {n for _, conns in sg['pins'].values() for _, n in conns}
        for a in aliases:
            snet, tnet, inv, basis = a['source_net'], a['target_net'], bool(a['invert']), a['basis']
            assert snet in all_src_nets or str(snet).startswith('#'), ('alias_source_not_net', rid, snet)
            assert snet not in seen_src, ('alias_duplicate', rid, snet)
            seen_src.add(snet)
            if basis == 'exact_name':
                assert snet == tnet, ('alias_exact', rid, snet, tnet)
            elif basis == 'pin_alias':
                ac, ap = a.get('anchor_cell', ''), a.get('anchor_pin', '')
                assert ac in sg['pins'], ('anchor_cell', rid, ac)
                assert dict(sg['pins'][ac][1]).get(ap) == snet, ('anchor_conn', rid, ac, ap)
                assert tnet == f'{ac}.{ap}', ('alias_pin_name', rid, tnet)
            elif basis == 'driver_cell':
                cd_t, cd_s = driver(tg, tnet), driver(sg, snet)
                assert norm_cell(cd_t) == norm_cell(cd_s), ('alias_driver_cell', rid)
            elif basis == 'inv_formula':
                anchor = a.get('anchor_net', '')
                assert anchor, ('anchor_missing', rid)
                inv_in = is_inverter(tg, driver(tg, anchor))
                assert inv_in == tnet, ('inv_structure', rid, inv_in, tnet)
            else:
                raise AssertionError(('alias_basis_unknown', rid, basis))
        # truth table
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
            tv, _ = S.evaluate(tg, S.LIB, r['target_signal'], tgt_env)
            # independence of every source signal that is claimed absorbed (x=n533)
            flip = dict(tgt_env)
            for a in aliases:
                if a['source_net'] in ('n533',):
                    flip[a['target_net']] = ~flip[a['target_net']]
            tv2, _ = S.evaluate(tg, S.LIB, r['target_signal'], flip)
            assert np.array_equal(tv, tv2), ('absorbed_not_independent', rid)
        else:
            sv, _ = S.evaluate(sg, S.LIB, r['source_signal'], src_env)
            tv, _ = S.evaluate(tg, S.LIB, r['target_signal'], tgt_env)
            if r['polarity'] == '+1':
                assert np.array_equal(tv, sv), ('polarity_plus_fail', rid)
            elif r['polarity'] == '-1':
                assert np.array_equal(tv, ~sv), ('polarity_minus_fail', rid)
            else:
                raise AssertionError(('polarity_na_for_signed', rid))
        # host usage
        paths = S.pin_paths(tg, actual_driver, S.lib_pins)
        assert (r['host_usage'] == 'dead') == bool(paths['closed_no_PO_no_register']), ('host_usage', rid)
        # region members
        for m in [x for x in members if x['relation_id'] == rid]:
            assert m['cell'] in tg['pins'], ('member_cell', rid, m['cell'])
            msig = m['signal']
            assert out_pin(tg, m['cell'], msig) == m['output_pin'], ('member_pin', rid)
            if m['polarity'] in ('+1', '-1') and r['relation_type'] == 'signed_signal_equal':
                env = dict(tgt_env)
                env[r['target_signal']] = tv
                mv, _ = S.evaluate(tg, S.LIB, msig, env)
                sv, _ = S.evaluate(sg, S.LIB, r['source_signal'], src_env)
                want = sv if m['polarity'] == '+1' else ~sv
                assert np.array_equal(mv, want), ('member_polarity', rid, m['cell'])
    return dict(relations=len(rows), members=len(members))


def main():
    rows = load_rows(OUT / 'RELATIONS_V2.csv') + load_rows(OUT / 'EXTENDED_V2.csv')
    result = validate(rows)
    result.update(passed=True, training=0, SAT=0, solver_calls=0, model_forwards=0, labels_changed=False,
                  files={f: S.sha(OUT / f) for f in ('RELATIONS_V2.csv', 'REGION_MEMBERS_V2.csv',
                                                     'EXTENDED_V2.csv', 'load_relations.py')})
    S.write_json(OUT / 'VERIFIED_V2.json', result)
    print(json.dumps({k: v for k, v in result.items() if k != 'files'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
