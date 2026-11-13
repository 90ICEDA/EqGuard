"""临时探针：验证 F8 图中 5 个孤立红门的根因 + 检查区域内是否有 PO。"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[1]))
from eqguard_paths import project_path as _eqguard_path

import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(_eqguard_path(''))
sys.path.insert(0, str(ROOT / "phase2/ys"))
import f8_rewrite_case as F8
import f8_dot as D

ASSIGN_RE = re.compile(r"^\s*assign\s+(\S+)\s*=\s*([^;]+);")
IDENT = re.compile(r"^[A-Za-z_\\$][\w$.\[\]\\$]*$")


class UF:
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


def parse_assigns(p: Path, uf: UF):
    n_plain = n_expr = 0
    for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
        m = ASSIGN_RE.match(ln.strip())
        if not m:
            continue
        lhs, rhs = m.group(1).lstrip("\\"), m.group(2).strip()
        if not IDENT.match(rhs) or rhs.startswith("\\") and "?" in rhs:
            n_expr += 1
            continue
        uf.union(lhs, rhs.lstrip("\\"))
        n_plain += 1
    return n_plain, n_expr


def po_ports(p: Path):
    txt = p.read_text(encoding="utf-8", errors="replace")
    return set(re.findall(r"^\s*output\s+([\w$]+)\s*;", txt, re.M))


def main():
    host, inst = "s38417t100", "injalpha"
    for tag, rcp in (("L", "ys_id"), ("R", "ys_abc")):
        p = F8.VDIR / f"{host}__{inst}_d1_s42__{rcp}.v"
        uf = UF()
        np_, ne_ = parse_assigns(p, uf)
        cells = F8.parse_v(p)
        # 别名归一化
        cells2 = {c: (t, {k: uf.find(v) for k, v in pins.items()}) for c, (t, pins) in cells.items()}
        drv, cons = F8.build_graph(cells2)
        seeds = {c for c in cells2 if "trojan" in c.lower()}
        sub = D.region(cells2, drv, cons, seeds, 2, 16)
        po = {uf.find(x) for x in po_ports(p)}
        print(f"== {tag} {rcp}: assign_plain={np_} assign_expr={ne_} po_ports={len(po)}")
        print(f"   seeds={len(seeds)} region={len(sub)}")
        # 区域内孤立点（无入边/无出边）
        edges = []
        for c in sub:
            for pin, net in cells2[c][1].items():
                if pin.upper() in F8.OUT_PINS:
                    continue
                hit = [u for u in drv.get(net, ()) if u in sub and u != c]
                if hit:
                    edges.append((hit[0], c))
        deg = defaultdict(int)
        for u, v in edges:
            deg[u] += 1
            deg[v] += 1
        iso = sorted(c for c in sub if deg[c] == 0)
        print(f"   edges={len(edges)} isolated={len(iso)}")
        for c in iso:
            print(f"     ISO {c}")
        # 区域内驱动 PO 的门
        for c in sorted(sub):
            for pin, net in cells2[c][1].items():
                if pin.upper() in F8.OUT_PINS and net in po:
                    raw = [k for k, v in cells2[c][1].items() if v == net]
                    print(f"   PO-DRIVER {c} pin={pin} net={net} raw_pins={raw}")
        # 区域外 1 跳内驱动 PO 的门（了解 PO 离图多远）
        near = set(sub)
        for c in sub:
            for pin, net in cells2[c][1].items():
                if pin.upper() in F8.OUT_PINS:
                    continue
                for u in drv.get(net, ()):
                    near.add(u)
        for c in sorted(near):
            for pin, net in cells2[c][1].items():
                if pin.upper() in F8.OUT_PINS and net in po and c not in sub:
                    print(f"   PO-DRIVER-1HOP {c} pin={pin} net={net}")


if __name__ == "__main__":
    main()
