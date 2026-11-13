"""v2 bounded retry of the 7 unresolved objects: exact alias / pin alias / driver alias / INV bridge.

Rules (conservative, no arbitrary XOR-chain inversion):
  - exact net name;
  - target net named '<anchor>.<pin>' where anchor/pin is a source cell pin connected to the source net;
  - target net driven by a cell whose normalized name equals the source net's driver;
  - target net is the INV (behavioral formula ~IN) of a net matched by the above (or vice versa).
Each candidate boundary is verified by full local truth table (<=12 inputs, <=4096 patterns).
No SAT/CEC/Yosys, no model calls, no training.
"""
import collections
import hashlib
import json
import re

import numpy as np

import Signed_common as S

OUT = S.HERE
V1 = S.ROOT / '_p0pilot/control_signed_carrier_20261109'
TOTAL_BUDGET = 65536
MAX_INPUTS = 12
MAX_DESC = 5


def norm(name):
    n = name.lstrip('g').lstrip('_')
    n = n.split('.')[0]
    return re.sub(r'_\d+$', '', n)


def driver(g, net):
    o = g['drivers'].get(g['find'](net), set())
    return next(iter(o)) if len(o) == 1 else None


def inv_of(g, net):
    """If net is driven by an INV, return its input net."""
    c = driver(g, net)
    if c is None:
        return None
    typ, conns = g['pins'][c]
    if not typ.upper().startswith(('INV', 'NBUFF')):
        return None
    try:
        ast = S.LIB.ast(typ, 'QN' if 'QN' in [p for p, _ in conns] else 'Q')
    except AssertionError:
        return None
    if ast[0] != '~':
        return None
    ins = [n for p, n in conns if p in ('IN', 'A')]
    return ins[0] if len(ins) == 1 else None


def aliases_for(snet, sg, tg, t_in):
    """Return list of (tnet, invert, basis, extra) candidates for one source input net."""
    out = []
    if snet in t_in.values():
        out.append((snet, False, 'exact_name', {}))
    # pin alias of any source cell pin connected to snet
    for cell, (typ, conns) in sg['pins'].items():
        for pin, net in conns:
            if net == snet:
                cand = f'{cell}.{pin}'
                if cand in t_in.values() or tg['drivers'].get(tg['find'](cand)):
                    out.append((cand, False, 'pin_alias', dict(anchor_cell=cell, anchor_pin=pin)))
    # driver-cell alias
    cs = driver(sg, snet)
    if cs is not None:
        for tnet in t_in.values():
            ct = driver(tg, tnet)
            if ct is not None and norm(ct) == norm(cs):
                out.append((tnet, False, 'driver_cell', {}))
    # direct INV at target: target input is inverted form of snet
    for tnet in t_in.values():
        if inv_of(tg, tnet) == snet:
            out.append((tnet, True, 'inv_formula', dict(anchor_net=snet)))
    # source net is the inverted form of a target input
    si = inv_of(sg, snet)
    if si is not None:
        for tnet in t_in.values():
            if tnet == si:
                out.append((tnet, True, 'inv_formula', dict(anchor_net=si)))
    return out


def main():
    assert not (OUT / 'EXTENDED_V2.csv').exists()
    sel = S.rows(V1 / 'SELECTION.csv')
    unres1 = S.rows(V1 / 'EXTENSION_UNRESOLVED.csv')
    lineage = S.rows(S.ROOT / '_p0pilot/control_role_pattern_20261107/NODE_LINEAGE.csv')
    snaps = {'train': S.load_snapshot('train'), 'val': S.load_snapshot('val')}
    nets = {}

    def g(kind, src, view=None):
        key = (kind, src, view)
        if key not in nets:
            p = S.F / kind / ((src + '.v') if kind == 'orig' else (view + '.v'))
            nets[key] = S.raw_network(p, S.lib_pins)
        return nets[key]

    retry = {int(u['rank']) for u in unres1}
    attempts, rels = [], []
    used = 0
    for s in sel:
        rank = int(s['rank'])
        if rank not in retry:
            continue
        src, gate, split = s['source'], s['gate'], s['split']
        sg = g('orig', src)
        s_in = S.input_nets(sg, gate)
        s_out_pin, s_out = S.output_net(sg, gate)
        desc = [r for r in lineage if r['key'].startswith('trans') and r['source'] == src
                and gate in r['parents'].split('|')]
        seen, uniq = set(), []
        for d in desc:
            k = (d['view'], d['node_name'])
            if k not in seen:
                seen.add(k); uniq.append(d)
        uniq.sort(key=lambda d: hashlib.sha256(f"{d['view']}|{d['node_name']}".encode()).hexdigest())
        unchecked = max(0, len(uniq) - MAX_DESC)
        if not uniq:
            attempts.append(dict(rank=rank, split=split, source=src, gate=gate, view='', node='',
                                 k='', patterns='', result='no_descendant', reason='no_descendant', unchecked=0))
            continue
        got = False
        for d in uniq[:MAX_DESC]:
            view, node = d['view'], d['node_name']
            tg = g('trans', src, view)
            t_in = S.input_nets(tg, node)
            t_out_pin, t_out = S.output_net(tg, node)
            # per source input, first viable alias
            chosen, ok = {}, True
            for sp, snet in s_in.items():
                cand = [c for c in aliases_for(snet, sg, tg, t_in) if c[0] in t_in.values()]
                if not cand:
                    ok = False
                    break
                chosen[sp] = cand[0]
            if not ok:
                attempts.append(dict(rank=rank, split=split, source=src, gate=gate, view=view, node=node,
                                     k=len(s_in), patterns='', result='boundary_not_aligned',
                                     reason='no_alias_for_some_source_input', unchecked=unchecked))
                continue
            k = len(chosen)
            if k > MAX_INPUTS:
                attempts.append(dict(rank=rank, split=split, source=src, gate=gate, view=view, node=node,
                                     k=k, patterns='', result='inputs_over_12', reason='k>12', unchecked=unchecked))
                continue
            patterns = 1 << k
            if used + patterns > TOTAL_BUDGET:
                attempts.append(dict(rank=rank, split=split, source=src, gate=gate, view=view, node=node,
                                     k=k, patterns=patterns, result='budget', reason='total_budget', unchecked=unchecked))
                continue
            vals = np.arange(patterns)
            src_env, tgt_env, alias_rows = {}, {}, []
            for j, sp in enumerate(s_in):
                tnet, inv, basis, extra = chosen[sp]
                v = ((vals >> j) & 1).astype(bool)
                src_env[s_in[sp]] = v
                tgt_env[tnet] = ~v if inv else v
                alias_rows.append(dict(source_net=s_in[sp], target_net=tnet, invert=inv, basis=basis, **extra))
            used += patterns
            sv, _ = S.evaluate(sg, S.LIB, s_out, src_env)
            try:
                tv, _ = S.evaluate(tg, S.LIB, t_out, tgt_env)
            except AssertionError:
                attempts.append(dict(rank=rank, split=split, source=src, gate=gate, view=view, node=node,
                                     k=k, patterns=patterns, result='unresolved_nets', reason='evaluation_hit_unbound',
                                     unchecked=unchecked))
                continue
            pol = '+1' if np.array_equal(tv, sv) else ('-1' if np.array_equal(tv, ~sv) else None)
            if pol is None:
                attempts.append(dict(rank=rank, split=split, source=src, gate=gate, view=view, node=node,
                                     k=k, patterns=patterns, result='function_mismatch', reason='neither_equal_nor_complement',
                                     unchecked=unchecked))
                continue
            paths = S.pin_paths(tg, node, S.lib_pins)
            _, arr, names, views = snaps[split]
            row = S.view_rows(views, names, view).get(node, '')
            rels.append(dict(
                relation_id=f'V2_EXT{rank:02d}_{node}', split=split, source_object=src,
                implementation_flow=view[len(src) + 2:], source_cell=gate, source_output_pin=s_out_pin,
                source_signal=s_out, target_signal=t_out, target_driver_cells=node,
                target_output_pin=t_out_pin, target_rows=str(row), relation_type='signed_signal_equal',
                polarity=pol, boundary_aliases=json.dumps(alias_rows, ensure_ascii=False), k_inputs=k,
                context='free_cut;local cut only;no register used' if 'DFF' not in ' '.join(t_in.values()) else 'free_state',
                host_usage='active' if not paths['closed_no_PO_no_register'] else 'dead',
                observable_use_endpoints='PO/DFF' if not paths['closed_no_PO_no_register'] else 'none',
                physical_D_or_PO_paths=('PO=' + str(len(paths['PO_paths'])) + ';firstDFF=' + str(len(paths['first_register_paths']))),
                source_sha=S.sha(S.F / 'orig' / (src + '.v')),
                target_sha=S.sha(S.F / 'trans' / (view + '.v')),
                mapping_sha=S.sha(S.F / 'mappings' / (view + '.json')),
                evidence_ids=f'V2_EXT_BRIDGE;patterns={patterns};bases=' + ','.join(sorted({a['basis'] for a in alias_rows})),
                proof_scope='aligned local Boolean cut with real behavioral-library formulas;NOT whole-design CEC',
                accepted_or_unresolved='accepted', exclusion_reason='',
                current_y=int(arr['y'][row]) if row != '' else '',
                current_trusted=bool(arr['trusted'][row]) if row != '' else '',
                source_y='', source_trusted='', named_copy='', named_copy_rows='',
                named_copy_y='', named_copy_trusted=''))
            attempts.append(dict(rank=rank, split=split, source=src, gate=gate, view=view, node=node,
                                 k=k, patterns=patterns, result=f'accepted_{pol}', reason='', unchecked=unchecked))
            got = True
            break
        if not got and not any(a['rank'] == rank for a in attempts[-MAX_DESC:] if a['result'].startswith('accepted')):
            pass
    S.table(OUT / 'EXTENDED_V2.csv', rels)
    S.table(OUT / 'ATTEMPT_LOG.csv', attempts)
    # coverage
    rows = []
    for split in ('train', 'val'):
        objs = [s for s in sel if s['split'] == split]
        attempted = {a['rank'] for a in attempts if a['split'] == split}
        accepted = {r['relation_id'].split('_')[1] for r in rels if r['split'] == split}
        rows.append(dict(split=split, candidates=len(objs), retried_objects=len(attempted),
                         accepted_objects=len(accepted), relations=len([r for r in rels if r['split'] == split]),
                         flows_attempted=len({a['view'][len(a['source']) + 2:] for a in attempts if a['split'] == split and a['view']}),
                         flows_accepted=len({r['implementation_flow'] for r in rels if r['split'] == split}),
                         plus=len([r for r in rels if r['split'] == split and r['polarity'] == '+1']),
                         minus=len([r for r in rels if r['split'] == split and r['polarity'] == '-1']),
                         live=len([r for r in rels if r['split'] == split and r['host_usage'] == 'active']),
                         dead=len([r for r in rels if r['split'] == split and r['host_usage'] == 'dead']),
                         attempts=len([a for a in attempts if a['split'] == split]),
                         unaligned=len([a for a in attempts if a['split'] == split and a['result'] == 'boundary_not_aligned']),
                         mismatch=len([a for a in attempts if a['split'] == split and a['result'] == 'function_mismatch']),
                         unchecked_descendants=sum(a['unchecked'] for a in attempts if a['split'] == split)))
    total = dict(split='total', **{k: sum(r[k] for r in rows) for k in rows[0]
                                   if k not in ('split', 'flows_attempted', 'flows_accepted')})
    total['flows_attempted'] = len({a['view'][len(a['source']) + 2:] for a in attempts if a['view']})
    total['flows_accepted'] = len({r['implementation_flow'] for r in rels})
    S.table(OUT / 'COVERAGE_V2.csv', rows + [total])
    S.write_json(OUT / 'EXTENSION_V2_SUMMARY.json', dict(retried=len(retry), relations=len(rels),
                                                         attempts=len(attempts), patterns_used=used,
                                                         budget=TOTAL_BUDGET, training=0, SAT=0, model_forwards=0))
    print('v2 extension:', dict(retried=len(retry), relations=len(rels), attempts=len(attempts), patterns=used))


if __name__ == '__main__':
    main()
