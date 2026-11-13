"""f8_audit_po.py -- 只读审计 F8 图：孤立木马门 + 输出接 PO 的单元。"""
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

VDIR = F8.VDIR


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


def module_ports(v: Path):
    txt = v.read_text(encoding="utf-8", errors="replace").splitlines()
    outs, ins = set(), set()
    for ln in txt:
        s = ln.strip()
        if s.startswith("output "):
            outs.add(s.split()[1].strip(";").lstrip("\\"))
        elif s.startswith("input "):
            ins.add(s.split()[1].strip(";").lstrip("\\"))
    return ins, outs


def audit(host: str, inst: str, recipe: str, hops: int, cap: int):
    v = VDIR / f"{host}__{inst}_d1_s42__{recipe}.v"
    cells = F8.parse_v(v)
    drv, cons = F8.build_graph(cells)
    seeds = {c for c in cells if "trojan" in c.lower()}
    nodes = region(cells, drv, cons, seeds, hops, cap)
    ins, outs = module_ports(v)

    print(f"\n=== {v.name} ===")
    print(f"cells={len(cells)} trojan_seeds={len(seeds)} region={len(nodes)} hops={hops} cap={cap}")
    print(f"top-level outputs={len(outs)} inputs={len(ins)}")

    # 图内边（与 build_dot 完全一致：只看 subset 内驱动、排除时钟脚）
    edges = []
    for c in sorted(nodes):
        typ, pins = cells[c]
        for p, net in pins.items():
            if p.upper() in F8.OUT_PINS:
                continue
            if p.upper() in {"CK", "CLK"}:
                continue
            hit = [u for u in drv.get(net, ()) if u in nodes and u != c]
            if hit:
                edges.append((hit[0], c, p, net))

    iso_trojan, iso_other = [], []
    for c in sorted(nodes):
        up = [u for u, v2, _p, _n in edges if v2 == c]
        down = [v2 for u, v2, _p, _n in edges if u == c]
        if not up and not down:
            (iso_trojan if "trojan" in c.lower() else iso_other).append(c)
    print(f"isolated trojan cells ({len(iso_trojan)}): {iso_trojan}")
    print(f"isolated non-trojan cells ({len(iso_other)}): {iso_other}")

    print("\n-- cells whose output drives a top-level output (PO) --")
    hit_any = False
    for c in sorted(nodes):
        typ, pins = cells[c]
        for p, net in pins.items():
            if p.upper() in F8.OUT_PINS and net in outs:
                hit_any = True
                print(f"  {c:16s} {typ:10s} {p}->{net} (PO)")
    if not hit_any:
        print("  none")

    print("\n-- cells whose output has NO consumer in this .v (dangling) --")
    for c in sorted(nodes):
        typ, pins = cells[c]
        for p, net in pins.items():
            if p.upper() not in F8.OUT_PINS:
                continue
            if net in outs:
                continue
            load = [x for x in cells if net in cells[x][1].values()]
            if not load:
                print(f"  {c:16s} {typ:10s} {p}->{net} (no consumer)")

    # 同时打印每个节点的类型/输入/输出，便于核对图
    print("\n-- region cells --")
    for c in sorted(nodes):
        typ, pins = cells[c]
        ip = {p: n for p, n in pins.items() if p.upper() not in F8.OUT_PINS}
        op = {p: n for p, n in pins.items() if p.upper() in F8.OUT_PINS}
        tag = []
        for p, n in op.items():
            if n in outs:
                tag.append(f"{p}->{n}=PO")
        print(f"  {c:16s} {typ:10s} in={ip} out={op} {' '.join(tag)}")


if __name__ == "__main__":
    audit("s38417t100", "injalpha", "ys_id", 2, 16)
    audit("s38417t100", "injalpha", "ys_abc", 2, 16)
