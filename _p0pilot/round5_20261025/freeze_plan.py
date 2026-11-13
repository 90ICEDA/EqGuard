"""Round-5 deep-cut construction and frozen candidate plan (no SAT)."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import hashlib
import itertools
import json
import sys
from pathlib import Path

ROOT = Path(_eqguard_path(''))
WORK = ROOT / "generate_trans/folds/hosts_bt31"
R3 = ROOT / "_p0pilot/round3_20261025"
R5 = ROOT / "_p0pilot/round5_20261025"
TAB5 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_nonlocal_round5"
sys.path.insert(0, str(R3))
sys.path.insert(0, str(ROOT / "phase2/ys"))
import sat_functional_relations as P0  # noqa: E402
from r3_nets import (build_index, dff_d_targets, load_module, net_of_bit,
                     out_ports, reach)  # noqa: E402


def hkey(s: str) -> str:
    return hashlib.sha256(("r5|" + s).encode()).hexdigest()


def deep_cut(idx: dict, net: str, max_cut: int = 4, depth: int = 4,
             min_depth: int = 2) -> dict:
    bits = idx["netbits"].get(net, ())
    if len(bits) != 1:
        return dict(leaves=[], leaf_total=0, truncated=False,
                    reason="target_not_single_bit")
    start = bits[0]
    seen, frontier, leaves = {start}, [(start, 0)], []
    truncated = False
    while frontier:
        b, d = frontier.pop()
        drv = idx["bit_driver"].get(b, set())
        is_dff = bool(drv) and all(c in idx["dff_cells"] for c in drv)
        if d >= depth or not drv or len(drv) != 1 or is_dff:
            leaves.append((b, d))
            continue
        cn = next(iter(drv))
        for _pin, ibits in idx["cell_inputs"].get(cn, []):
            for nb in ibits:
                if not isinstance(nb, int) or nb == b or nb in seen:
                    continue
                if len(seen) >= 256:
                    truncated = True
                    continue
                seen.add(nb)
                frontier.append((nb, d + 1))
    named = []
    for b, d in leaves:
        nm = net_of_bit(idx, b)
        if not nm or nm in ("0", "1", "x", "z") or nm.startswith("$"):
            continue
        if d < min_depth:
            continue
        named.append((d, nm))
    best = {}
    for d, nm in named:
        if nm not in best or d < best[nm]:
            best[nm] = d
    items = sorted(best.items(), key=lambda kv: hkey(kv[0]))
    chosen = items[:max_cut]
    depths = [d for _, d in chosen]
    if len(chosen) < 2:
        return dict(leaves=[], leaf_total=len(items), truncated=truncated,
                    reason="cut_too_small")
    if max(depths) < 3:
        return dict(leaves=[], leaf_total=len(items), truncated=truncated,
                    reason="cut_not_deep_enough")
    return dict(leaves=[nm for nm, _ in chosen], leaf_depths=depths,
                leaf_total=len(items), truncated=truncated, reason="")


def gate_type(design: str, cell: str) -> str:
    raw = R3 / "struct_raw" / (Path(design).stem + ".json")
    mods = json.loads(raw.read_text(encoding="utf-8"))["modules"]
    mod = next(iter(mods.values()))
    c = mod.get("cells", {}).get(cell)
    return str(c.get("type", "")) if c else ""


def main() -> int:
    plan_spec = [
        ("train", "rs232t1000", "ctlmatcha", "ys_abc", "control"),
        ("train", "rs232t1000", "injzeta", "ys_abc", "noncontrol"),
        ("train", "s15850t100", "ctlmatcha", "ys_id", "control"),
        ("train", "s15850t100", "a4ctlequiv_s0", "ys_id", "noncontrol"),
        ("val", "s38417t100", "ctlmatcha", "ys_aig", "control"),
        ("val", "s38417t100", "injzeta", "ys_aig", "noncontrol"),
    ]
    return _freeze(plan_spec)


def _freeze(plan_spec: list) -> int:
    frozen, rejected, prepared = [], [], []
    for role, host, inst, recipe, usage in plan_spec:
        v = WORK / "trans" / f"{host}__{inst}_d1_s42__{recipe}.v"
        if not v.exists():
            continue
        mods = json.loads((R3 / "struct_raw" / f"{v.stem}.json").read_text(
            encoding="utf-8"))["modules"]
        idx = build_index(next(iter(mods.values())))
        pool = []
        for t in dff_d_targets(idx):
            t["reach_po"], t["reach_dff"] = reach(idx, t["bit"])
            pool.append(t)
        for p in out_ports(idx):
            bits = [b for b in idx["ports"][p].get("bits", []) if isinstance(b, int)]
            if len(bits) != 1:
                continue
            drv = idx["bit_driver"].get(bits[0], set())
            if drv and all(c in idx["dff_cells"] for c in drv):
                continue
            rp, rd = reach(idx, bits[0])
            pool.append(dict(kind="cone", cell=None, target=p, bit=bits[0],
                             reach_po=rp, reach_dff=rd))
        pool.sort(key=lambda t: (-(t["reach_po"] > 0), -(t["reach_dff"]),
                                 hkey(t["target"])))
        prepared.append(dict(role=role, host=host, inst=inst, recipe=recipe,
                             usage=usage, v=v, idx=idx, pool=pool))
        taken, kinds = 0, set()
        for t in pool:
            if taken >= 1:
                break
            if t["kind"] in kinds and len(pool) > 2:
                continue
            cut = deep_cut(idx, t["target"])
            if cut["reason"]:
                rejected.append(dict(design=v.name, target=t["target"],
                                     reason=cut["reason"],
                                     leaf_total=cut["leaf_total"]))
                continue
            k = len(cut["leaves"])
            pats = ["".join(str(b) for b in p)
                    for p in itertools.product([0, 1], repeat=k)]
            drv = next(iter(idx["bit_driver"].get(t["bit"], {""})))
            frozen.append(dict(
                role=role, host=host, inst=inst, recipe=recipe, usage=usage,
                design=v.name, target=t["target"], kind=t["kind"],
                target_bit=t["bit"], reach_po=t["reach_po"],
                reach_dff=t["reach_dff"], driver=drv,
                driver_type=gate_type(v.name, drv),
                cut=cut["leaves"], cut_depths=cut["leaf_depths"],
                cut_leaf_total=cut["leaf_total"],
                cut_truncated=int(cut["truncated"]),
                patterns=pats, n_patterns=len(pats),
                target_id=f"{v.name}|{t['bit']}|{t['target']}"))
            taken += 1
            kinds.add(t["kind"])
    # second pass: add one more target per design until 8, keeping all 6 designs
    for p in prepared:
        if len(frozen) >= 8:
            break
        v, idx = p["v"], p["idx"]
        used = {r["target"] for r in frozen if r["design"] == v.name}
        added = 0
        for t in p["pool"]:
            if added >= 1 or len(frozen) >= 8:
                break
            if t["target"] in used:
                continue
            cut = deep_cut(idx, t["target"])
            if cut["reason"]:
                continue
            k = len(cut["leaves"])
            pats = ["".join(str(b) for b in q)
                    for q in itertools.product([0, 1], repeat=k)]
            drv = next(iter(idx["bit_driver"].get(t["bit"], {""})))
            frozen.append(dict(
                role=p["role"], host=p["host"], inst=p["inst"], recipe=p["recipe"],
                usage=p["usage"], design=v.name, target=t["target"],
                kind=t["kind"], target_bit=t["bit"], reach_po=t["reach_po"],
                reach_dff=t["reach_dff"], driver=drv,
                driver_type=gate_type(v.name, drv),
                cut=cut["leaves"], cut_depths=cut["leaf_depths"],
                cut_leaf_total=cut["leaf_total"],
                cut_truncated=int(cut["truncated"]),
                patterns=pats, n_patterns=len(pats),
                target_id=f"{v.name}|{t['bit']}|{t['target']}"))
            used.add(t["target"])
            added += 1
    plan = dict(created="2026-10-25T18:10:00+08:00",
                rule=("6 designs (control/noncontrol by fold-declared family) x up to 2 "
                      "targets; deep backward cone depth=4, leaves only at depth>=2, "
                      "<=4 single-bit leaves by sha256('r5|name'); at least one leaf at "
                      "depth>=3; full 2^k enumeration; no labels or positives used"),
                frozen=frozen, rejected=rejected,
                relations=len(frozen),
                expected_queries=sum(2 * r["n_patterns"] for r in frozen),
                budget=dict(nonlocal_max=256, propagation_max=64, review_max=64,
                            total_max=384, timeout_s=5, wall_cap_min=30))
    (TAB5 / "r5_candidate_plan.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(dict(relations=len(frozen),
                          expected_queries=plan["expected_queries"],
                          designs=len({r["design"] for r in frozen}),
                          hosts=len({r["host"] for r in frozen}),
                          roles=sorted({r["role"] for r in frozen})),
                     ensure_ascii=False, indent=2), flush=True)
    for r in frozen:
        print(f"{r['design']} {r['kind']} {r['target']} k={len(r['cut'])} "
              f"depths={r['cut_depths']} cut={r['cut']}", flush=True)
    print("rejected", len(rejected), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
