"""f8_audit_ports.py -- 列出 F8 两侧每个节点的输出 net 去向（region 内负载 / 全 v 负载 / PO）。"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[1]))
from eqguard_paths import project_path as _eqguard_path

import re
import sys
from collections import defaultdict, deque
from pathlib import Path

ROOT = Path(_eqguard_path(''))
sys.path.insert(0, str(ROOT / "phase2/ys"))
import f8_rewrite_case as F8  # noqa: E402

ASSIGN_RE = re.compile(r"^\s*assign\s+\\?([^\s=]+)\s*=\s*\\?([^\s;]+)\s*;")


def region(cells, drv, cons, seeds, hops, cap):
    seen, q = set(seeds), deque((s, 0) for s in seeds)
    while q:
        c, d = q.popleft()
        if d >= hops or len(seen) >= cap:
            continue
        nb = set(cons.get(c, set()))
        for pin, net in cells[c][1].items():
            if pin.upper() in F8.OUT_PINS:
                nb |= set(drv.get(net, set()))
        for u in nb:
            if u not in seen and len(seen) < cap:
                seen.add(u)
                q.append((u, d + 1))
    return seen


class DSU:
    def __init__(self):
        self.p = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


def parse(v: Path):
    cells = F8.parse_v(v)
    outs, ins = set(), set()
    dsu = DSU()
    aliases = defaultdict(set)
    for ln in v.read_text(encoding="utf-8", errors="replace").splitlines():
        s = ln.strip()
        if s.startswith("output "):
            outs.add(s.split()[1].strip(";").lstrip("\\"))
        elif s.startswith("input "):
            ins.add(s.split()[1].strip(";").lstrip("\\"))
        m = ASSIGN_RE.match(s)
        if m:
            a, b = m.group(1), m.group(2)
            dsu.union(a, b)
            aliases[a].add(b)
            aliases[b].add(a)
    return cells, outs, ins, dsu, aliases


def audit(host: str, inst: str, recipe: str, hops: int, cap: int):
    v = F8.VDIR / f"{host}__{inst}_d1_s42__{recipe}.v"
    cells, outs, ins, dsu, aliases = parse(v)
    drv, cons = F8.build_graph(cells)
    seeds = {c for c in cells if "trojan" in c.lower()}
    nodes = region(cells, drv, cons, seeds, hops, cap)
    out_roots = defaultdict(list)
    for o in outs:
        out_roots[dsu.find(o)].append(o)

    print(f"\n=== {v.name} region={len(nodes)} seeds={len(seeds)} ===")
    print("-- region consumers are computed on the *literal* net (no assign) --")
    for c in sorted(nodes):
        typ, pins = cells[c]
        for p, net in pins.items():
            if p.upper() not in F8.OUT_PINS:
                continue
            lit = sorted({x for x in nodes if x != c and net in cells[x][1].values()})
            allv = sorted({x for x in cells if x != c and net in cells[x][1].values()})
            po = out_roots.get(dsu.find(net), [])
            al = sorted(aliases.get(net, []))
            print(f"  {c:22s} {p:2s} {net:26s} {typ:9s} "
                  f"region_load={lit} allv_load={allv[:5]}{'...' if len(allv) > 5 else ''} "
                  f"alias={al[:5]}{'...' if len(al) > 5 else ''} PO={po}")


if __name__ == "__main__":
    for hops, cap in ((2, 16),):
        audit("s38417t100", "injalpha", "ys_id", hops, cap)
        audit("s38417t100", "injalpha", "ys_abc", hops, cap)
