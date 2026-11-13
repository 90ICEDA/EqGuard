"""Native physical-Q Boolean context and deterministic bounded cut extraction.

DFF Q is an unrestricted named state variable; QN is its complement. No reset,
scan-mode, reachability or sequential transition assertion is introduced.
Descriptors for a DFF node concern its physical D DATA INPUT, explicitly typed;
they do not describe its current Q or its full scan/reset next-state function.
"""
from __future__ import annotations

from collections import deque


def layout(m):
    offset, ports = 0, {}
    for name, p in sorted(m['ports'].items()):
        if p['direction'] == 'input':
            ports[name] = list(range(offset, offset + len(p['bits'])))
            offset += len(p['bits'])
    states = {name: offset + i for i, (name, c) in enumerate(
        sorted((name, c) for name, c in m['cells'].items() if 'DFF' in c['type'].upper()))}
    return ports, states, offset + len(states)


def scalar(bs):
    if len(bs) != 1:
        raise ValueError('Scalar library pins required')
    return bs[0]


def bitref(b):
    if isinstance(b, int):
        return f'b{b}'
    if b in ('0', '1'):
        return "1'b" + b
    raise ValueError('X/Z constants require a separately defined abstraction')


def logic(m):
    ports, states, width = layout(m)
    if not width:
        raise ValueError('No primary inputs/state variables')
    bits = sorted({b for c in m['cells'].values() for bs in c['connections'].values()
                   for b in bs if isinstance(b, int)} |
                  {b for p in m['ports'].values() for b in p['bits'] if isinstance(b, int)})
    lines = ['wire ' + ','.join(bitref(b) for b in bits) + ';']
    driven = set()
    def assign(bit, expr):
        if not isinstance(bit, int) or bit in driven:
            raise ValueError(f'Constant/multiply driven bit {bit}')
        driven.add(bit); lines.append(f'assign {bitref(bit)}={expr};')
    for name, offsets in ports.items():
        for b, i in zip(m['ports'][name]['bits'], offsets):
            assign(b, f'env[{i}]')
    for name, c in m['cells'].items():
        con, typ = c['connections'], c['type']
        g = lambda pin: bitref(scalar(con[pin]))
        if name in states:
            for pin, inv in [('Q', False), ('QN', True)]:
                if pin in con:
                    assign(scalar(con[pin]), ('~' if inv else '') + f'env[{states[name]}]')
            continue
        if typ in ('AND2X2', 'OR2X1', 'XOR2X1'):
            op, sym = 'Q', {'AND2X2':'&','OR2X1':'|','XOR2X1':'^'}[typ]
            expr = f'{g("IN1")}{sym}{g("IN2")}'
        elif typ == 'INVX0': op, expr = 'QN', '~' + g('IN')
        elif typ == 'MX2X1_RS': op, expr = 'Y', f'{g("S0")}?{g("B")}:{g("A")}'
        elif typ in ('$and', '$or', '$xor'):
            op, sym = 'Y', {'$and':'&','$or':'|','$xor':'^'}[typ]
            expr = f'{g("A")}{sym}{g("B")}'
        elif typ == '$not': op, expr = 'Y', '~' + g('A')
        elif typ == '$mux': op, expr = 'Y', f'{g("S")}?{g("B")}:{g("A")}'
        else: raise ValueError('Unsupported cell ' + typ)
        assign(scalar(con[op]), expr)
    referenced = {b for c in m['cells'].values() for bs in c['connections'].values()
                  for b in bs if isinstance(b, int)}
    if referenced - driven:
        raise ValueError('Undriven native bits: ' + str(sorted(referenced-driven)[:8]))
    return lines, width


def dependency_index(m):
    drivers = {}
    for name, c in m['cells'].items():
        for pin, bs in c['connections'].items():
            dirs = c.get('port_directions', {})
            if dirs.get(pin) == 'output' or (not dirs and pin in ('Q','QN','Y')):
                b = scalar(bs)
                if isinstance(b, int):
                    if b in drivers: raise ValueError('Multiple native drivers')
                    drivers[b] = (name, pin)
    dependencies = {}
    for b, (name, pin) in drivers.items():
        c = m['cells'][name]
        if 'DFF' in c['type'].upper(): continue
        ins = []
        for p, bs in c['connections'].items():
            if p != pin:
                ins.extend(x for x in bs if isinstance(x, int))
        dependencies[b] = sorted(set(ins))
    pending = {b:len(set(ins)&set(dependencies)) for b, ins in dependencies.items()}
    consumers = {}
    for b, ins in dependencies.items():
        for x in set(ins)&set(dependencies): consumers.setdefault(x,[]).append(b)
    ready = deque(b for b,n in pending.items() if n==0)
    visited = 0
    while ready:
        b=ready.popleft();visited+=1
        for nxt in consumers.get(b,[]):
            pending[nxt]-=1
            if pending[nxt]==0: ready.append(nxt)
    if visited != len(dependencies): raise ValueError('Combinational cycle')
    return drivers, dependencies


def choose_cut(root, dependencies, max_inputs=4, max_depth=4):
    """Expand a COMPLETE frontier, never choose a subset of a gate's fanins."""
    if not isinstance(root, int): return [], {}, 'constant_target'
    frontier = {root: 0}
    expanded = set()
    while True:
        chosen = None
        for b, depth in sorted(frontier.items(), key=lambda item:(item[1],item[0])):
            if depth >= max_depth or b not in dependencies: continue
            ins = dependencies[b]
            if b in ins: raise ValueError('Combinational cycle in candidate cone')
            # Do not reintroduce a previously expanded reconvergent frontier.
            if any(x in expanded for x in ins): continue
            trial = set(frontier) - {b} | set(ins)
            if len(trial) <= max_inputs:
                chosen = b, depth, ins; break
        if chosen is None: break
        b, depth, ins = chosen
        del frontier[b]; expanded.add(b)
        for x in ins: frontier[x] = min(frontier.get(x, max_depth+1), depth+1)
    if root in frontier: return [], {}, 'unexpanded_target'
    if not frontier: return [], {}, 'constant_cone'
    return sorted(frontier), dict(expanded_nodes=len(expanded),
                                  max_depth=max(frontier.values()),
                                  nonlocal_cut=int(len(expanded)>1)), 'eligible'


def model(m, records):
    lines, width = logic(m)
    n = len(records)
    code = [f'module check(input [{width-1}:0] env,input [3:0] pattern,',
            f'output [{n-1}:0] premise,output [{n-1}:0] target);'] + lines
    for i, r in enumerate(records):
        k = len(r['cut_bits'])
        cut = '{' + ','.join(bitref(b) for b in reversed(r['cut_bits'])) + '}'
        code += [f'assign premise[{i}]=({cut}==pattern[{k-1}:0]);',
                 f'assign target[{i}]={bitref(r["target_bit"])};']
    return '\n'.join(code+['endmodule'])+'\n'
