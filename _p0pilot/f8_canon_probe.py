"""f8_canon_probe.py -- 只读：assign 别名合并后的 region 边表 + PO' 候选。"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[1]))
from eqguard_paths import project_path as _eqguard_path

import re
import sys
from collections import deque
from pathlib import Path

ROOT = Path(_eqguard_path(''))
sys.path.insert(0, str(ROOT / "phase2/ys"))
import f8_rewrite_case as F8  # noqa: E402

ASSIGN_RE = re.compile(r"^\s*assign\s+\\?([^\s=]+)\s*=\s*\\?([^\s;]+)\s*;")
PAYLOAD_RE = re.compile(r"^Trojan[Am]_[pt]\d+$|^TrojanA_[pt]\d+$")


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


def probe(recipe, hops=2, cap=16):
    v = F8.VDIR / f"s38417t100__injalpha_d1_s42__{recipe}.v"
    cells = F8.parse_v(v)
    dsu = DSU()
    tops = set()
    for ln in v.read_text(encoding="utf-8", errors="replace").splitlines():
        s = ln.strip()
        if s.startswith("output "):
            tops.add(s.split()[1].strip(";").lstrip("\\"))
        m = ASSIGN_RE.match(s)
        if m:
            dsu.union(m.group(1), m.group(2))
    canon_cells = {c: (typ, {p: dsu.find(n) for p, n in pins.items()})
                   for c, (typ, pins) in cells.items()}
    drv, cons = F8.build_graph(canon_cells)
    seeds = {c for c in cells if "trojan" in c.lower()}
    nodes = region(canon_cells, drv, cons, seeds, hops, cap)
    top_c = {dsu.find(o) for o in tops}
    pay_c = {dsu.find(n) for n in dsu.p if PAYLOAD_RE.match(n)}

    print(f"\n=== {recipe} ===")
    edges = []
    for c in sorted(nodes):
        for p, cnet in canon_cells[c][1].items():
            if p.upper() in F8.OUT_PINS or p.upper() in {"CK", "CLK"}:
                continue
            hit = [u for u in drv.get(cnet, ()) if u in nodes and u != c]
            if hit:
                edges.append((hit[0], c, p, cells[c][1][p]))
    print(f"nodes={len(nodes)} edges={len(edges)}")
    for e in edges:
        print(f"  {e[0]} -> {e[1]}:{e[2]} [{e[3]}]")
    iso = [c for c in sorted(nodes)
           if not [1 for u, v2, _p, _n in edges if v2 == c or u == c]]
    print(f"isolated={iso}")
    print("-- PO' candidates (payload / top-level) --")
    for c in sorted(nodes):
        for p, cnet in canon_cells[c][1].items():
            if p.upper() not in F8.OUT_PINS:
                continue
            tags = []
            if cnet in top_c:
                tags.append("TOP")
            if cnet in pay_c:
                tags.append("PAYLOAD")
            if tags:
                print(f"  {c}:{p} net={cells[c][1][p]} canon={cnet} -> {'+'.join(tags)}")


if __name__ == "__main__":
    probe("ys_id")
    probe("ys_abc")
