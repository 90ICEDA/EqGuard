"""Endpoint-cone builder with declaration-based PI recognition.

Key rules:
  - PI boundary comes ONLY from module input/inout declarations (bit-expanded and alias-merged);
    "no driver" never implies PI.
  - internal no-driver nets, constants, X/Z, direct-Q, single-point, D/SI and PO drivers are classified separately.
  - register bodies are excluded from members; D cone includes the combinational driver of D;
    PO cone includes the actual driver gate even when it is the only member.
"""
import collections
import re
import sys
from pathlib import Path

ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
sys.path.insert(0, str(ROOT / '_p0pilot/control_signed_carrier_20261109_v3'))
import Signed_common as S  # noqa: E402

CONST = {'#0', '#1'}
XZ = {'#x', '#z', '#X', '#Z'}


def _strip(text):
    return re.sub(r'/\*.*?\*/|//[^\n]*|\(\*.*?\*\)', '', text, flags=re.S)


def _parts(s):
    aa, start, depth = [], 0, 0
    for i, ch in enumerate(s):
        depth += int(ch in '{(') - int(ch in '})')
        if ch == ',' and depth == 0:
            aa.append(s[start:i].strip()); start = i + 1
    aa.append(s[start:].strip())
    return aa


def declared_ports(text):
    """Return (pi_bits, po_bits) from input/inout/output declarations."""
    pi, po = set(), set()
    for st in [x.strip() for x in _strip(text).split(';') if x.strip()]:
        m = re.match(r'^(input|inout|output)\b(.*)$', st, re.S)
        if not m:
            continue
        kind, rest = m.group(1), m.group(2).strip()
        rng = re.match(r'^\[\s*(\d+)\s*:\s*(\d+)\s*\]\s*(.*)$', rest, re.S)
        if rng:
            hi, lo, body = int(rng.group(1)), int(rng.group(2)), rng.group(3)
            step = -1 if hi >= lo else 1
            names = []
            for n0 in _parts(body):
                i = hi
                while (step > 0 and i <= lo) or (step < 0 and i >= lo):
                    names.append(f'{n0}[{i}]')
                    i += step
        else:
            names = _parts(rest)
        tgt = pi if kind in ('input', 'inout') else po
        for n in names:
            n = n.strip().lstrip('\\')
            if n:
                tgt.add(n)
    return pi, po


def build(path):
    path = Path(path)
    g = S.raw_network(path, S.lib_pins)
    pins, find = g['pins'], g['find']
    pi_bits, po_bits = declared_ports(path.read_text(encoding='utf-8', errors='ignore'))
    pi = {find(x) for x in pi_bits}
    po = {find(x) for x in po_bits} | {find(x) for x in g['po']}

    VIRT = {'V2_ASSIGN_AND': (['A', 'B'], ['Q']), 'V2_ASSIGN_OR': (['A', 'B'], ['Q']),
            'V2_ASSIGN_XOR': (['A', 'B'], ['Q']), 'V2_ASSIGN_NOT': (['A'], ['Q']),
            'V2_ASSIGN_MUX': (['S', 'A', 'B'], ['Q'])}

    def pinfo(typ):
        if typ in S.lib_pins:
            return S.lib_pins[typ]['inputs'], S.lib_pins[typ]['outputs']
        return VIRT.get(typ, ([], []))

    def is_dff(cell):
        return 'DFF' in pins[cell][0].upper()

    def ins(cell):
        typ, conns = pins[cell]
        return [n for p, n in conns if p in pinfo(typ)[0]]

    def outs(cell):
        typ, conns = pins[cell]
        return {p: n for p, n in conns if p in pinfo(typ)[1]}

    def walk(endpoint):
        e = find(endpoint)
        members, seen, unknown = [], set(), []
        boundary = collections.Counter()
        if e in pi:
            boundary['pi'] += 1
            return members, unknown, boundary, dict(flag='direct_pi')
        if e in CONST:
            boundary['const'] += 1
            return members, unknown, boundary, dict(flag='const')
        if e in XZ:
            boundary['xz'] += 1
            return members, unknown, boundary, dict(flag='xz')
        owners = g['drivers'].get(e, set())
        if not owners:
            unknown.append(endpoint); boundary['dangling'] += 1
            return members, unknown, boundary, dict(flag='dangling')
        first = True
        stack = [(endpoint, 0)]
        while stack:
            net, depth = stack.pop(0)
            f = find(net)
            if f in pi:
                boundary['pi'] += 1
                continue
            if f in CONST:
                boundary['const'] += 1
                continue
            if f in XZ:
                boundary['xz'] += 1
                continue
            owners = g['drivers'].get(f, set())
            if not owners:
                unknown.append(net)
                boundary['dangling'] += 1
                continue
            for cell in owners:
                if is_dff(cell):
                    boundary['dff_q'] += 1
                    continue
                if cell in seen:
                    continue
                seen.add(cell)
                members.append(dict(cell=cell, gate=pins[cell][0], depth=depth,
                                    role='driver' if first else 'comb'))
                for inp in ins(cell):
                    stack.append((inp, depth + 1))
            first = False
        return members, unknown, boundary, dict(flag='')

    cones = []
    for cell in pins:
        if not is_dff(cell):
            continue
        typ, conns = pins[cell]
        d = dict(conns).get('D')
        if d is not None:
            members, unknown, boundary, meta = walk(d)
            cones.append(dict(cone_id=f'D:{cell}', kind='D', endpoint=d, endpoint_pin='D',
                              driver=members[0]['cell'] if members else '', members=members,
                              unknown=unknown, boundary=dict(boundary), **meta))
        if 'SI' in S.lib_pins[typ]['inputs']:
            si = dict(conns).get('SI')
            if si is not None:
                members, unknown, boundary, meta = walk(si)
                cones.append(dict(cone_id=f'SI:{cell}', kind='SI', endpoint=si, endpoint_pin='SI',
                                  driver=members[0]['cell'] if members else '', members=members,
                                  unknown=unknown, boundary=dict(boundary), **meta))
    seen_po = set()
    for raw in sorted(po_bits):
        e = find(raw)
        if e in seen_po:
            continue
        seen_po.add(e)
        members, unknown, boundary, meta = walk(raw)
        cones.append(dict(cone_id=f'PO:{raw}', kind='PO', endpoint=raw, endpoint_pin='',
                          driver=members[0]['cell'] if members else '', members=members,
                          unknown=unknown, boundary=dict(boundary), **meta))
    return dict(path=str(path), cones=cones, pi=sorted(pi_bits), po=sorted(po_bits))


def summarize(b):
    rows = []
    for c in b['cones']:
        m = c['members']
        rows.append(dict(cone_id=c['cone_id'], kind=c['kind'], endpoint=c['endpoint'], driver=c['driver'],
                         members=len(m), unknown=len(c['unknown']), flag=c.get('flag', ''),
                         singleton=int(len(m) == 1), direct_pi=int(c.get('flag') == 'direct_pi'),
                         direct_q=int(len(m) == 0 and c['boundary'].get('dff_q') and not c.get('flag')),
                         empty_comb=int(len(m) == 0)))
    return rows


if __name__ == '__main__':
    import json
    b = build(sys.argv[1])
    print(json.dumps(dict(cones=len(b['cones']), pi=len(b['pi']), po=len(b['po'])), ensure_ascii=False))
