"""f8_audit_assign.py -- 只读审计：用 assign 别名闭包找"输出接 PO"的单元。"""
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

    # 把顶层输出按 DSU 类归组
    out_roots = defaultdict(list)
    for o in outs:
        out_roots[dsu.find(o)].append(o)

    print(f"\n=== {v.name} region={len(nodes)} seeds={len(seeds)} ===")
    print(f"seeds: {sorted(seeds)}")
    print("-- outputs that reach a top-level PO (via assign alias class) --")
    found = False
    for c in sorted(nodes):
        typ, pins = cells[c]
        for p, net in pins.items():
            if p.upper() not in F8.OUT_PINS:
                continue
            po = out_roots.get(dsu.find(net), [])
            if po:
                found = True
                alias = sorted(aliases.get(net, []))
                print(f"  {c:22s} {typ:9s} {p} -> {net}  alias={alias}  PO={po}")
    if not found:
        print("  none")

    print("-- isolated cells: why --")
    edges = []
    for c in sorted(nodes):
        typ, pins = cells[c]
        for p, net in pins.items():
            if p.upper() in F8.OUT_PINS or p.upper() in {"CK", "CLK"}:
                continue
            hit = [u for u in drv.get(net, ()) if u in nodes and u != c]
            if hit:
                edges.append((hit[0], c, p, net))
    for c in sorted(nodes):
        typ, pins = cells[c]
        up = [u for u, v2, _p, _n in edges if v2 == c]
        down = [v2 for u, v2, _p, _n in edges if u == c]
        if up or down:
            continue
        print(f"  {c}  ({typ})")
        for p, net in pins.items():
            if p.upper() in F8.OUT_PINS:
                cons_in = sorted({x for x in cells if net in cells[x][1].values()})
                print(f"    OUT {p}={net} consumers_in_v={cons_in[:6]} alias={sorted(aliases.get(net, []))[:6]}"
                      f" PO={out_roots.get(dsu.find(net), [])}")
            else:
                d = sorted(drv.get(net, []))
                print(f"    IN  {p}={net} drivers_in_v={d[:6]} alias={sorted(aliases.get(net, []))[:6]}"
                      f" in_region={[u for u in d if u in nodes]}")


if __name__ == "__main__":
    audit("s38417t100", "injalpha", "ys_id", 2, 16)
    audit("s38417t100", "injalpha", "ys_abc", 2, 16)
