"""f8_tpo_audit.py -- 只读：TrojanA_p*/t* 的消费者分类，判断哪些真的接到正常网表。"""
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
import f8_dot as D  # noqa: E402

PAY = re.compile(r"^TrojanA_[pt]\d+$")


def trojan_cone(cells, seeds, hops=4):
    """从木马种子做无向 BFS；返回“木马内部 cell”集合。"""
    from collections import defaultdict
    cons_by_net = defaultdict(list)
    for c, (_t, pins) in cells.items():
        for p, n in pins.items():
            if p.upper() not in F8.OUT_PINS:
                cons_by_net[n].append(c)
    fan = {c: set() for c in cells}
    for c, (_t, pins) in cells.items():
        for p, n in pins.items():
            if p.upper() in F8.OUT_PINS:
                for u in cons_by_net.get(n, ()):
                    if u != c:
                        fan[c].add(u)
                        fan[u].add(c)
    seen, q = set(seeds), deque(seeds)
    while q:
        c = q.popleft()
        for u in fan.get(c, ()):
            if u not in seen:
                seen.add(u)
                q.append(u)
    return seen


def audit(recipe: str):
    p = F8.VDIR / f"s38417t100__injalpha_d1_s42__{recipe}.v"
    cells = F8.parse_v(p)
    dsu, tops = D.parse_assign_alias(p)
    cc = D.canonical_cells(cells, dsu)
    seeds = {c for c in cells if "trojan" in c.lower()}
    cone = trojan_cone(cells, seeds, hops=4)
    names = {n for _t, pins in cells.values() for n in pins.values()} | set(dsu.p)
    pays = sorted(n for n in names if PAY.match(n))

    print(f"\n=== {recipe} seeds={len(seeds)} cone={len(cone)} payload_names={pays} ===")
    for sig in pays:
        root = dsu.find(sig)
        members = sorted(n for n in names if dsu.find(n) == root)
        cons = []
        for c in sorted(cells):
            reads = [p for p, n in cells[c][1].items()
                     if p.upper() not in F8.OUT_PINS and dsu.find(n) == root]
            if reads:
                cons.append((c, cells[c][0], reads,
                             "trojan_cone" if c in cone else "NORMAL"))
        po = sorted(o for o in tops if dsu.find(o) == root)
        print(f"\n  {sig}  root={root}")
        print(f"    aliases={members}")
        print(f"    top-level PO={po}")
        for c, t, ports, kind in cons:
            ins = {pp: nn for pp, nn in cells[c][1].items()
                   if pp.upper() not in F8.OUT_PINS}
            normal_in = [nn for nn in ins.values() if "trojan" not in str(nn).lower()]
            print(f"    <- {c} ({t}) ports={ports} [{kind}]")
            print(f"       ins={ins} normal_ins={normal_in}")
        if not cons and not po:
            print("    (no consumer / no PO)")


if __name__ == "__main__":
    audit("ys_id")
    audit("ys_abc")
