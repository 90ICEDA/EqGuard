"""Independent verification of the 12-object extension (read-only, no model calls)."""
import json
from pathlib import Path

import numpy as np

import Signed_common as S

OUT = S.HERE


def main():
    rels = S.rows(OUT / 'EXTENDED_RELATIONS.csv')
    unres = S.rows(OUT / 'EXTENSION_UNRESOLVED.csv')
    checked = S.rows(OUT / 'EXTENSION_CHECKED.csv')
    snaps = {'train': S.load_snapshot('train'), 'val': S.load_snapshot('val')}
    nets = {}

    def get(kind, source, view=None):
        key = (kind, source, view)
        if key not in nets:
            p = S.F / kind / ((source + '.v') if kind == 'orig' else (view + '.v'))
            nets[key] = S.raw_network(p, S.lib_pins)
        return nets[key]

    patterns_used = 0
    for r in rels:
        src = r['source_object']; view = src + '__' + r['implementation_flow']
        sg = get('orig', src); tg = get('trans', src, view)
        s_out_pin, s_out = S.output_net(sg, r['source_cell'])
        assert s_out == r['source_signal'] and s_out_pin == r['source_output_pin']
        t_out_pin, t_out = S.output_net(tg, r['target_driver_cells'])
        assert t_out == r['target_signal']
        s_in = S.input_nets(sg, r['source_cell'])
        boundary = {}
        for part in r['aligned_boundary'].split(';'):
            sp, t = part.split('->')
            inv = t.endswith('(inv)')
            boundary[sp] = (t.replace('(inv)', ''), inv)
        assert set(boundary) == set(s_in), (r['relation_id'], boundary, s_in)
        k = len(s_in)
        assert k <= 12, r['relation_id']
        patterns = 1 << k
        assert patterns <= 4096
        patterns_used += patterns
        vals = np.arange(patterns)
        src_env = {s_in[sp]: ((vals >> j) & 1).astype(bool) for j, sp in enumerate(s_in)}
        tgt_env = {}
        for j, sp in enumerate(s_in):
            tnet, inv = boundary[sp]
            v = ((vals >> j) & 1).astype(bool)
            tgt_env[tnet] = ~v if inv else v
        sv, _ = S.evaluate(sg, S.LIB, s_out, src_env)
        tv, _ = S.evaluate(tg, S.LIB, t_out, tgt_env)
        pol = '+1' if np.array_equal(tv, sv) else ('-1' if np.array_equal(tv, ~sv) else 'none')
        assert pol == r['polarity'], (r['relation_id'], pol, r['polarity'])
        # coordinates and labels
        _, arrays, names, views = snaps[r['split']]
        row = S.view_rows(views, names, view).get(r['target_driver_cells'], '')
        assert str(row) == r['target_rows'], (r['relation_id'], row, r['target_rows'])
        if row != '':
            assert int(r['current_y']) == int(arrays['y'][row])
            assert (str(r['current_trusted']).lower() == 'true') == bool(arrays['trusted'][row])
        # host usage
        paths = S.pin_paths(tg, r['target_driver_cells'], S.lib_pins)
        assert (r['host_usage'] == 'dead') == bool(paths['closed_no_PO_no_register']), r['relation_id']
        # evidence
        assert f'patterns={patterns}' in r['evidence_ids']
    assert patterns_used <= 65536
    # selection is frozen and complete
    sel = S.rows(OUT / 'SELECTION.csv')
    assert len(sel) == 12 and len({(s['source'], s['gate']) for s in sel}) == 12
    assert len(checked) == 12
    signed = len(rels); unresolved = len(unres)
    assert signed + unresolved == 12, (signed, unresolved)
    result = dict(passed=True, objects=12, checked=len(checked), signed=signed, unresolved=unresolved,
                  polarity_plus=sum(r['polarity'] == '+1' for r in rels),
                  polarity_minus=sum(r['polarity'] == '-1' for r in rels),
                  live=sum(r['host_usage'] == 'active' for r in rels), dead=sum(r['host_usage'] == 'dead' for r in rels),
                  patterns_used=patterns_used, budget=65536, max_inputs=12,
                  split_counts={'train': sum(r['split'] == 'train' for r in rels),
                                'val': sum(r['split'] == 'val' for r in rels)},
                  training=0, SAT=0, solver_calls=0, model_forwards=0, labels_changed=False,
                  files={f: S.sha(OUT / f) for f in ['EXTENDED_RELATIONS.csv', 'EXTENSION_UNRESOLVED.csv',
                                                     'EXTENSION_COVERAGE.csv', 'SELECTION.csv', 'extend_relations.py']})
    S.write_json(OUT / 'VERIFY_EXTENSION.json', result)
    print(json.dumps({k: v for k, v in result.items() if k != 'files'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
