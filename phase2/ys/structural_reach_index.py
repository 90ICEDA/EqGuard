"""Alias-aware, cached combinational reach to PO bits and physical DFF D pins.

No SAT semantics. Build graph indices once per JSON module, not per candidate.
All net aliases are kept; clock/reset/scan-enable pins are not D endpoints.
Truncation is returned explicitly rather than silently interpreted as complete.
"""
from collections import defaultdict


class ReachIndex:
    def __init__(self, module):
        self.bits = {n: tuple(b for b in info.get('bits', []) if isinstance(b, int))
                     for n, info in module.get('netnames', {}).items()}
        self.po = set()
        for n, p in module.get('ports', {}).items():
            self.bits[n] = tuple(b for b in p.get('bits', []) if isinstance(b, int))
            if p.get('direction') == 'output':
                self.po.update(self.bits[n])
        self.adj = defaultdict(set)
        self.dff_d = defaultdict(set)
        self.cache = {}
        self.unsupported = set()
        for cn, cell in module.get('cells', {}).items():
            con = cell.get('connections', {})
            typ = cell.get('type', '').upper()
            if 'DFF' in typ or 'LATCH' in typ:
                for b in con.get('D', []):
                    if isinstance(b, int):
                        self.dff_d[b].add((cn, 'D'))
                continue
            dirs = cell.get('port_directions', {})
            outs = {b for p, bs in con.items()
                    if dirs.get(p) == 'output' or (not dirs and p in ('Y','Q','QN','Z','O'))
                    for b in bs if isinstance(b, int)}
            if not outs:
                self.unsupported.add(cn)
            for p, bs in con.items():
                if dirs.get(p) == 'output' or (not dirs and p in ('Y','Q','QN','Z','O')):
                    continue
                for b in bs:
                    if isinstance(b, int):
                        self.adj[b].update(outs)

    def reach(self, name, max_nodes=None):
        starts = self.bits.get(str(name).lstrip('\\'), ())
        key = (starts, max_nodes)
        if key in self.cache:
            return self.cache[key]
        visited = set(starts)
        stack = list(starts)
        po, dff = set(), set()
        truncated = False
        while stack:
            b = stack.pop()
            if b in self.po:
                po.add(b)
            dff.update(self.dff_d.get(b, ()))
            for out in self.adj.get(b, ()):
                if out not in visited:
                    if max_nodes is not None and len(visited) >= max_nodes:
                        truncated = True
                        continue
                    visited.add(out)
                    stack.append(out)
        result = dict(reach_po=len(po), reach_dff=len(dff), start_found=bool(starts),
                      truncated=truncated, visited=len(visited))
        self.cache[key] = result
        return result
