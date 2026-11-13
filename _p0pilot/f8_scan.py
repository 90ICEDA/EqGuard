"""f8_scan.py -- 解析一次，扫描 hops/cap 下的 region 规模、孤立红门、Q->PO。"""
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


def load(recipe):
    v = F8.VDIR / f"s38417t100__injalpha_d1_s42__{recipe}.v"
    cells = F8.parse_v(v)
    outs = set()
    dsu = DSU()
    for ln in v.read_text(encoding="utf-8", errors="replace").splitlines():
        s = ln.strip()
        if s.startswith("output "):
            outs.add(s.split()[1].strip(";").lstrip("\\"))
        m = ASSIGN_RE.match(s)
        if m:
            dsu.union(m.group(1), m.group(2))
    out_roots = {dsu.find(o) for o in outs}
    drv, cons = F8.build_graph(cells)
    seeds = {c for c in cells if "trojan" in c.lower()}
    return cells, drv, cons, seeds, outs, dsu, out_roots


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


def stats(loaded, hops, cap):
    cells, drv, cons, seeds, outs, dsu, out_roots = loaded
    nodes = region(cells, drv, cons, seeds, hops, cap)
    edges = []
    for c in sorted(nodes):
        for p, net in cells[c][1].items():
            if p.upper() in F8.OUT_PINS or p.upper() in {"CK", "CLK"}:
                continue
            hit = [u for u in drv.get(net, ()) if u in nodes and u != c]
            if hit:
                edges.append((hit[0], c, p, net))
    iso = [c for c in sorted(nodes)
           if not [1 for u, v2, _p, _n in edges if v2 == c or u == c]]
    iso_t = [c for c in iso if "trojan" in c.lower()]
    po = []
    for c in sorted(nodes):
        for p, net in cells[c][1].items():
            if p.upper() in F8.OUT_PINS and dsu.find(net) in out_roots:
                po.append((c, p, net))
    return len(nodes), len(edges), len(iso_t), po


if __name__ == "__main__":
    for recipe in ("ys_id", "ys_abc"):
        loaded = load(recipe)
        print(f"\n## {recipe}: cells={len(loaded[0])} seeds={len(loaded[3])}")
        for hops in (1, 2, 3, 4):
            for cap in (12, 16, 20, 24, 40):
                n, e, ni, po = stats(loaded, hops, cap)
                mark = "  <== isolated_trojan=5" if ni == 5 else ""
                if po:
                    mark += f"  PO={po}"
                print(f"  hops={hops} cap={cap:2d}: nodes={n:2d} edges={e:2d} iso_trojan={ni}{mark}")
