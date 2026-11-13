"""f8_audit_params.py -- 扫描 hops/cap，找 L 侧孤立红门数=5 的参数指纹。"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[1]))
from eqguard_paths import project_path as _eqguard_path

import sys
from collections import deque
from pathlib import Path

ROOT = Path(_eqguard_path(''))
sys.path.insert(0, str(ROOT / "phase2/ys"))
import f8_rewrite_case as F8  # noqa: E402


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


def stats(recipe, hops, cap):
    v = F8.VDIR / f"s38417t100__injalpha_d1_s42__{recipe}.v"
    cells = F8.parse_v(v)
    drv, cons = F8.build_graph(cells)
    seeds = {c for c in cells if "trojan" in c.lower()}
    nodes = region(cells, drv, cons, seeds, hops, cap)
    edges = []
    for c in sorted(nodes):
        for p, net in cells[c][1].items():
            if p.upper() in F8.OUT_PINS or p.upper() in {"CK", "CLK"}:
                continue
            hit = [u for u in drv.get(net, ()) if u in nodes and u != c]
            if hit:
                edges.append((hit[0], c, p, net))
    iso = []
    for c in sorted(nodes):
        up = [u for u, v2, _p, _n in edges if v2 == c]
        down = [v2 for u, v2, _p, _n in edges if u == c]
        if not up and not down:
            iso.append(c)
    iso_t = [c for c in iso if "trojan" in c.lower()]
    return len(nodes), len(edges), len(iso_t), iso_t


if __name__ == "__main__":
    for recipe in ("ys_id", "ys_abc"):
        print(f"\n## {recipe}")
        for hops in (0, 1, 2, 3, 4):
            for cap in (8, 12, 16, 20, 24, 32, 40):
                n, e, ni, _ = stats(recipe, hops, cap)
                mark = "  <== 5 isolated trojan" if ni == 5 else ""
                print(f"  hops={hops} cap={cap:2d}: nodes={n:2d} edges={e:2d} isolated_trojan={ni}{mark}")
