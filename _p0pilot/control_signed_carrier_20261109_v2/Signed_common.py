"""Shared helpers for the signed-carrier audit (read-only).

Only netlist parsing, local Boolean replay with the real behavioral library, pin/alias
paths and label snapshots. No SAT/CEC/Yosys, no model calls, no training.
"""
from __future__ import annotations

import collections
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
F = ROOT / 'generate_trans/folds/hosts_bt31'
CONTRACT = ROOT / '_p0pilot/control_boundary_v3_20261104/input_contract.json'
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / '_p0pilot/control_boundary_v3_20261104'))
from independent_net import raw_network, parse_expression  # noqa: E402
from phase2 import netlist_lib as NL  # noqa: E402

BEHAVIOR = ROOT.parent / 'GraphSAINT-train/vali/verilog_lib.v'


def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))


def rows(p):
    with Path(p).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def write_json(p, z):
    Path(p).write_text(json.dumps(z, ensure_ascii=False, indent=2), encoding='utf-8')


def table(p, rr):
    p = Path(p)
    if not rr:
        p.write_text('', encoding='utf-8-sig')
        return
    with p.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rr[0]))
        w.writeheader()
        w.writerows(rr)


class Library:
    """Real behavioral formulas from GraphSAINT-train/vali/verilog_lib.v."""

    def __init__(self, path=BEHAVIOR):
        self.path = Path(path)
        self.text = self.path.read_text(encoding='utf-8')
        self.sha = sha(self.path)
        self.asts = {}
        self.formulas = {}

    def ast(self, typ, pin='Q'):
        key = (typ, pin)
        if key not in self.asts:
            mods = re.findall(r'\bmodule\s+' + re.escape(typ) + r'\b.*?endmodule', self.text, re.S)
            assert len(mods) == 1, ('module', typ, len(mods))
            assigns = re.findall(r'\bassign\s+' + re.escape(pin) + r'\s*=\s*([^;]+);', mods[0])
            assert len(assigns) == 1, ('assign', typ, pin, len(assigns))
            self.asts[key] = parse_expression(assigns[0])
            self.formulas[key] = assigns[0]
        return self.asts[key]

    def value(self, ast, env):
        op = ast[0]
        if op == 'leaf':
            if ast[1] in ["1'b0", "1'b1", '0', '1']:
                return np.full_like(next(iter(env.values())), ast[1] in ["1'b1", '1'])
            return env[ast[1]]
        a = [self.value(q, env) for q in ast[1:]]
        if op == '~':
            return ~a[0]
        if op == '&':
            return a[0] & a[1]
        if op == '|':
            return a[0] | a[1]
        if op == '^':
            return a[0] ^ a[1]
        if op == '?':
            return np.where(a[0], a[1], a[2])
        raise AssertionError(op)


def evaluate(g, lib, signal, env, outputs_only=True):
    """Evaluate a signal under env={net: bool array}; returns (value, used_cells)."""
    cache = {g['find'](s): v for s, v in env.items()}
    used = set()

    def ev(net):
        net = g['find'](net)
        if net in cache:
            return cache[net]
        if net in ['#0', '#1']:
            return np.full(len(next(iter(env.values()))), net == '#1', bool)
        owners = g['drivers'].get(net, set())
        assert len(owners) == 1, ('drivers', net, owners)
        name = next(iter(owners))
        typ, connections = g['pins'][name]
        assert 'DFF' not in typ.upper(), ('state', name)
        ports = dict(connections)
        outs = [p for p, n in connections if n == net and p in lib_pins[typ]['outputs']]
        assert len(outs) == 1, ('output pin', name, net, outs)
        result = LIB.value(LIB.ast(typ, outs[0]), {p: ev(ports[p]) for p in lib_pins[typ]['inputs']})
        cache[net] = result
        used.add(name)
        return result

    return ev(signal), used


def load_netlists(sources, flows):
    lib = NL.load_library(F / 'verilog_lib.v')
    global lib_pins
    lib_pins = lib
    nets = {}
    for s in sources:
        nets[('orig', s, s)] = raw_network(F / 'orig' / (s + '.v'), lib)
        for fl in flows:
            v = f'{s}__{fl}'
            nets[('trans', s, v)] = raw_network(F / 'trans' / (v + '.v'), lib)
    return nets


def load_snapshot(split='train'):
    c = read(CONTRACT)
    folder = ROOT / c['shared_inputs']['trans_' + split]['folder']
    arrays = {n: np.load(folder / (n + '.npy'), mmap_mode='r') for n in ('y', 'trusted', 'physical')}
    names = [s.strip().lstrip('\\') for s in (F / 'data/processed/node_names_trans.txt').read_text(encoding='utf-8').splitlines()]
    views = {v['view']: v for v in c['shared_inputs']['trans_' + split]['views']}
    return c, arrays, names, views


def view_rows(views, names, view):
    """Return name -> global row for one view."""
    layout = views[view]
    return {n: layout['start'] + j for j, n in enumerate(names[layout['old_start']:layout['old_stop']])}


def pin_paths(g, start, lib_pins):
    """BFS on the pin/alias graph; returns PO routes and first-register routes."""
    q = collections.deque([start])
    prev = {start: None}
    po, reg = [], []

    def route(n):
        z = []
        while n is not None:
            z.append(n); n = prev[n]
        return list(reversed(z))

    while q:
        n = q.popleft()
        if n in g['pocells']:
            po.append(route(n))
        for t in sorted(g['succ'][n]):
            if 'DFF' in g['pins'][t][0].upper():
                shared = {net for pin, net in g['pins'][n][1] if pin in lib_pins[g['pins'][n][0]]['outputs']}
                ps = [pin for pin, net in g['pins'][t][1] if net in shared and pin in lib_pins[g['pins'][t][0]]['inputs']]
                reg.append(dict(path=route(n) + [t], pins=ps))
            elif t not in prev:
                prev[t] = n; q.append(t)
    return dict(PO_paths=po, first_register_paths=reg, visited_nodes=sorted(prev),
                closed_no_PO_no_register=not (po or reg))


def output_net(g, cell):
    typ, conns = g['pins'][cell]
    outs = [(p, n) for p, n in conns if p in lib_pins[typ]['outputs']]
    assert len(outs) == 1, (cell, outs)
    return outs[0][0], outs[0][1]


def input_nets(g, cell):
    typ, conns = g['pins'][cell]
    return {p: n for p, n in conns if p in lib_pins[typ]['inputs']}


LIB = Library()
lib_pins = NL.load_library(F / 'verilog_lib.v')
