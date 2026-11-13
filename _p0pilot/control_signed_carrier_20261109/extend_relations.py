"""Bounded extension: probe the 12 frozen source-gate objects for signed carriers.

Alignment bridge (conservative, deterministic):
  target input t matches source input pin sp / net s if
    (1) t == s (exact name), or
    (2) t has the form '<G>.INk' with the same pin suffix and G = source gate name, or
    (3) the driver cell of t has the same normalized name as the driver cell of s, or
    (4) t is the INV of a net matching (1)-(3).
  The resulting boundary is then verified by full local truth tables (<=12 inputs, <=4096 patterns).
No SAT/CEC/Yosys, no model calls, no training.
"""
import collections
import hashlib
import re

import numpy as np

import Signed_common as S

OUT = S.HERE
TOTAL_PATTERN_BUDGET = 65536
MAX_INPUTS = 12
MAX_DESCENDANTS = 5


def norm_cell(name):
    n = name.lstrip('g').lstrip('_')
    n = n.split('.')[0]
    n = re.sub(r'_\d+$', '', n)
    return n


def driver_cell(g, net):
    owners = g['drivers'].get(g['find'](net), set())
    return next(iter(owners)) if len(owners) == 1 else None


def inv_input(g, net):
    c = driver_cell(g, net)
    if c is None:
        return None
    typ, conns = g['pins'][c]
    if not typ.upper().startswith(('INV', 'NBUFF')):
        return None
    ins = [n for p, n in conns if p in ('IN', 'A')]
    return ins[0] if len(ins) == 1 else None


def match_input(t, s, sp, gate, sg, tg):
    if t == s:
        return False
    if t.endswith('.' + sp) and norm_cell(t.split('.')[0]) == norm_cell(gate):
        return False
    ct, cs = driver_cell(tg, t), driver_cell(sg, s)
    if ct is not None and cs is not None and norm_cell(ct) == norm_cell(cs):
        return False
    ti = inv_input(tg, t)
    if ti is not None:
        inner = match_input(ti, s, sp, gate, sg, tg)
        if inner is not None:
            return not inner
    si = inv_input(sg, s)
    if si is not None and t == si:
        return True
    return None


def main():
    assert not (OUT / 'EXTENDED_RELATIONS.csv').exists()
    sel = S.rows(OUT / 'SELECTION.csv')
    lineage = S.rows(S.ROOT / '_p0pilot/control_role_pattern_20261107/NODE_LINEAGE.csv')
    snaps = {'train': S.load_snapshot('train'), 'val': S.load_snapshot('val')}
    nets = {}

    def get(kind, source, view=None):
        key = (kind, source, view)
        if key not in nets:
            p = S.F / kind / ((source + '.v') if kind == 'orig' else (view + '.v'))
            nets[key] = S.raw_network(p, S.lib_pins)
        return nets[key]

    rels, unresolved, checked = [], [], []
    patterns_used = 0
    for s in sel:
        src, gate, split = s['source'], s['gate'], s['split']
        sg = get('orig', src)
        try:
            s_out_pin, s_out = S.output_net(sg, gate)
            s_in = S.input_nets(sg, gate)
        except AssertionError:
            unresolved.append(dict(rank=s['rank'], split=split, source=src, gate=gate, reason='source_gate_not_found'))
            continue
        desc = [r for r in lineage if r['key'].startswith('trans') and r['source'] == src
                and gate in r['parents'].split('|')]
        # de-duplicate (view, node_name)
        seen, uniq = set(), []
        for d in desc:
            k = (d['view'], d['node_name'])
            if k not in seen:
                seen.add(k); uniq.append(d)
        uniq.sort(key=lambda d: hashlib.sha256(f"{d['view']}|{d['node_name']}".encode()).hexdigest())
        checked.append(dict(rank=s['rank'], split=split, source=src, gate=gate, role=s['role'],
                            descendants=len(uniq), views='|'.join(sorted({d['view'] for d in uniq}))))
        if not uniq:
            unresolved.append(dict(rank=s['rank'], split=split, source=src, gate=gate, reason='no_descendant'))
            continue
        found = False
        for d in uniq[:MAX_DESCENDANTS]:
            view, node = d['view'], d['node_name']
            tg = get('trans', src, view)
            try:
                t_out_pin, t_out = S.output_net(tg, node)
                t_in = S.input_nets(tg, node)
            except AssertionError:
                continue
            # align each source pin
            mapping = {}
            ok = True
            for sp, snet in s_in.items():
                hit = None
                for tp, tnet in t_in.items():
                    inv = match_input(tnet, snet, sp, gate, sg, tg)
                    if inv is not None:
                        hit = (tp, tnet, inv); break
                if hit is None:
                    ok = False; break
                mapping[sp] = hit
            if not ok:
                continue
            k = len(s_in)
            if k > MAX_INPUTS:
                unresolved.append(dict(rank=s['rank'], split=split, source=src, gate=gate, reason='inputs_over_12'))
                ok = False; break
            patterns = 1 << k
            if patterns_used + patterns > TOTAL_PATTERN_BUDGET:
                unresolved.append(dict(rank=s['rank'], split=split, source=src, gate=gate, reason='pattern_budget'))
                ok = False; break
            vals = np.arange(patterns)
            src_env = {s_in[sp]: ((vals >> j) & 1).astype(bool) for j, sp in enumerate(s_in)}
            tgt_env = {}
            for j, sp in enumerate(s_in):
                tp, tnet, inv = mapping[sp]
                v = ((vals >> j) & 1).astype(bool)
                tgt_env[tnet] = ~v if inv else v
            sv, _ = S.evaluate(sg, S.LIB, s_out, src_env)
            tv, _ = S.evaluate(tg, S.LIB, t_out, tgt_env)
            patterns_used += patterns
            if np.array_equal(tv, sv):
                pol = '+1'
            elif np.array_equal(tv, ~sv):
                pol = '-1'
            else:
                continue
            paths = S.pin_paths(tg, node, S.lib_pins)
            _, arrays, names, views = snaps[split]
            vr = S.view_rows(views, names, view)
            row = vr.get(node, '')
            y = int(arrays['y'][row]) if row != '' else ''
            trusted = bool(arrays['trusted'][row]) if row != '' else ''
            rels.append(dict(
                relation_id=f"EXT{int(s['rank']):02d}_{node}", split=split, source_object=src,
                implementation_flow=view[len(src) + 2:],
                source_cell=gate, source_output_pin=s_out_pin, source_signal=s_out,
                target_signal=t_out, target_driver_cells=node, target_rows=str(row),
                relation_type='signed_signal_equal', polarity=pol,
                aligned_boundary=';'.join(f'{sp}->{mapping[sp][1]}{"(inv)" if mapping[sp][2] else ""}' for sp in s_in),
                query_context=f'free source inputs k={k};local cut only',
                host_usage='active' if not paths['closed_no_PO_no_register'] else 'dead',
                observable_use_endpoints='PO/DFF' if not paths['closed_no_PO_no_register'] else 'none',
                physical_D_or_PO_paths=('PO=' + str(len(paths['PO_paths'])) + ';firstDFF=' + str(len(paths['first_register_paths']))),
                source_sha=S.sha(S.F / 'orig' / (src + '.v')),
                target_sha=S.sha(S.F / 'trans' / (view + '.v')),
                mapping_sha=S.sha(S.F / 'mappings' / (view + '.json')) if (S.F / 'mappings' / (view + '.json')).exists() else '',
                evidence_ids=f'AUTO_BRIDGE;patterns={patterns};role={s["role"]}',
                proof_scope='aligned local Boolean cut with real behavioral-library formulas;NOT whole-design CEC',
                accepted_or_unresolved='accepted', exclusion_reason='',
                current_y=y, current_trusted=trusted, source_y='', source_trusted='',
                named_copy='', named_copy_rows='', named_copy_y='', named_copy_trusted=''))
            found = True
            break
        if not found:
            unresolved.append(dict(rank=s['rank'], split=split, source=src, gate=gate, reason='boundary_not_aligned_or_function_mismatch'))

    S.table(OUT / 'EXTENDED_RELATIONS.csv', rels)
    S.table(OUT / 'EXTENSION_UNRESOLVED.csv', unresolved)
    S.table(OUT / 'EXTENSION_CHECKED.csv', checked)
    # coverage by split / source / flow
    cov = collections.defaultdict(lambda: dict(objects=0, signed_plus=0, signed_minus=0, live=0, dead=0, unresolved=0))
    for c in checked:
        cov[(c['split'], c['source'])]['objects'] += 1
    for r in rels:
        d = cov[(r['split'], r['source_object'])]
        d['signed_plus' if r['polarity'] == '+1' else 'signed_minus'] += 1
        d['live' if r['host_usage'] == 'active' else 'dead'] += 1
    for u in unresolved:
        cov[(u['split'], u['source'])]['unresolved'] += 1
    S.table(OUT / 'EXTENSION_COVERAGE.csv',
            [dict(split=k[0], source=k[1], **v) for k, v in sorted(cov.items())])
    S.write_json(OUT / 'EXTENSION_SUMMARY.json', dict(objects=len(sel), signed=len(rels), unresolved=len(unresolved),
                                                      patterns_used=patterns_used, budget=TOTAL_PATTERN_BUDGET,
                                                      training=0, SAT=0, model_forwards=0))
    print('extension:', dict(objects=len(sel), signed=len(rels), unresolved=len(unresolved), patterns_used=patterns_used))


if __name__ == '__main__':
    main()
