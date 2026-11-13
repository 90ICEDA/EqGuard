"""Freeze round-6 expansion candidates: 16 deep cuts, 8 designs, real timestamp."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import hashlib
import itertools
import json
import re
import sys
from collections import deque
from datetime import datetime
from pathlib import Path

ROOT = Path(_eqguard_path(''))
WORK = ROOT / "generate_trans/folds/hosts_bt31"
R3 = ROOT / "_p0pilot/round3_20261025"
R6 = ROOT / "_p0pilot/round6_20261025"
TAB6 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_expand_round6"
sys.path.insert(0, str(R3))
sys.path.insert(0, str(ROOT / "phase2/ys"))
import sat_functional_relations as P0  # noqa: E402
from r3_nets import build_index, dff_d_targets, net_of_bit, out_ports, reach  # noqa: E402


def hkey(s: str) -> str:
    return hashlib.sha256(("r6|" + s).encode()).hexdigest()


def load_index(v: Path) -> dict:
    """Parse each design once; write Yosys JSON only if not already cached."""
    js = R6 / "struct_raw" / f"{v.stem}.json"
    js.parent.mkdir(parents=True, exist_ok=True)
    (R6 / "logs").mkdir(parents=True, exist_ok=True)
    if not js.exists():
        head = v.read_text(encoding="utf-8", errors="replace")[:4000]
        m = re.search(r"^module\s+([^\s(]+)", head, re.M)
        if not m:
            raise RuntimeError(f"no module header in {v}")
        top = m.group(1)
        script = (f"read_verilog {P0.wsl(v)}\n"
                  f"hierarchy -top {top}\nproc\nopt_clean\n"
                  f"write_json {P0.wsl(js)}\n")
        out = P0.run_yosys(script, R6 / "logs" / f"{v.stem}.struct.log", timeout=600)
        if not js.exists():
            raise RuntimeError(f"write_json failed for {v.name}: {out[-500:]}")
    mods = json.loads(js.read_text(encoding="utf-8"))["modules"]
    return build_index(next(iter(mods.values())))


def deep_cut_bfs(idx, net, max_cut=4, depth=5, min_depth=2):
    bits = idx["netbits"].get(net, ())
    if len(bits) != 1:
        return dict(leaves=[], leaf_total=0, truncated=False,
                    reason="target_not_single_bit")
    start = bits[0]
    seen, q, leaves = {start}, deque([(start, 0)]), []
    truncated = False
    while q:
        b, d = q.popleft()
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
                if len(seen) >= 512:
                    truncated = True
                    continue
                seen.add(nb)
                q.append((nb, d + 1))
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
    if len(chosen) < 2:
        return dict(leaves=[], leaf_total=len(items), truncated=truncated,
                    reason="cut_too_small")
    dists = [d for _, d in chosen]
    if max(dists) < 3:
        return dict(leaves=[], leaf_total=len(items), truncated=truncated,
                    reason="cut_not_deep_enough")
    return dict(leaves=[nm for nm, _ in chosen], distances=dists,
                leaf_total=len(items), truncated=truncated, reason="",
                cut_kind=("full_boundary" if len(items) <= max_cut and not truncated
                          else "partial_probe"),
                selected_ratio=len(chosen) / max(1, len(items)))


def main() -> int:
    import pandas as pd
    used = set()
    used_names = set()
    r5 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_nonlocal_round5/r5_nonlocal_relations.csv"
    for _, r in pd.read_csv(r5, encoding="utf-8-sig").iterrows():
        used.add((str(r.design), str(r.target)))
        used_names.add(str(r.target))
    specs = [
        ("train", "rs232t1000", "ctlmatcha", "ys_abc", "control",
         "rs232t1000__ctlmatcha_d1_s42__ys_abc"),
        ("train", "rs232t1000", "injzeta", "ys_abc", "noncontrol",
         "rs232t1000__injzeta_d1_s42__ys_abc"),
        ("train", "rs232t1000", "ctldup", "ys_abc", "control",
         "rs232t1000__ctldup_d1_s42__ys_abc"),
        ("train", "s15850t100", "ctlmatcha", "ys_id", "control",
         "s15850t100__ctlmatcha_d1_s42__ys_id"),
        ("train", "s15850t100", "a4ctlequiv_s0", "keepcur__ys_id", "noncontrol",
         "s15850t100__a4ctlequiv_s0_d1_s42__keepcur__ys_id"),
        ("train", "s15850t100", "ctldup", "ys_id", "control",
         "s15850t100__ctldup_d1_s42__ys_id"),
        ("val", "s38417t100", "ctlmatcha", "ys_aig", "control",
         "s38417t100__ctlmatcha_d1_s42__ys_aig"),
        ("val", "s38417t100", "injzeta", "ys_aig", "noncontrol",
         "s38417t100__injzeta_d1_s42__ys_aig"),
    ]
    frozen, rejected = [], []
    for role, host, inst, recipe, usage, stem in specs:
        v = WORK / "trans" / f"{stem}.v"
        if not v.exists():
            continue
        idx = load_index(v)
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
        pool = [t for t in pool if (v.name, t["target"]) not in used
                and t["target"] not in used_names]
        pool.sort(key=lambda t: (t["kind"], -(t["reach_po"] > 0),
                                 -(t["reach_dff"] > 0), hkey(t["target"])))
        picked, kinds = [], set()
        for t in pool:
            if len(picked) >= 2:
                break
            if t["kind"] in kinds:
                continue
            cut = deep_cut_bfs(idx, t["target"])
            if cut["reason"] or len(cut["leaves"]) != 4:
                rejected.append(dict(design=v.name, target=t["target"],
                                     reason=cut["reason"] or "cut_not_4"))
                continue
            k = len(cut["leaves"])
            frozen.append(dict(
                role=role, host=host, inst=inst, recipe=recipe, usage=usage,
                design=v.name, target=t["target"], kind=t["kind"],
                target_bit=t["bit"], reach_po=t["reach_po"],
                reach_dff=t["reach_dff"],
                driver=next(iter(idx["bit_driver"].get(t["bit"], {""}))),
                cut=cut["leaves"], cut_distances=cut["distances"],
                cut_leaf_total=cut["leaf_total"], cut_kind=cut["cut_kind"],
                selected_ratio=cut["selected_ratio"],
                cut_truncated=int(cut["truncated"]),
                patterns=["".join(str(b) for b in p)
                          for p in itertools.product([0, 1], repeat=k)],
                n_patterns=2 ** k,
                target_id=f"{v.name}|{t['bit']}|{t['target']}"))
            picked.append(t)
            kinds.add(t["kind"])
            used_names.add(t["target"])
        for t in pool:
            if len(picked) >= 2:
                break
            if t in picked:
                continue
            cut = deep_cut_bfs(idx, t["target"])
            if cut["reason"] or len(cut["leaves"]) != 4:
                continue
            k = len(cut["leaves"])
            frozen.append(dict(
                role=role, host=host, inst=inst, recipe=recipe, usage=usage,
                design=v.name, target=t["target"], kind=t["kind"],
                target_bit=t["bit"], reach_po=t["reach_po"],
                reach_dff=t["reach_dff"],
                driver=next(iter(idx["bit_driver"].get(t["bit"], {""}))),
                cut=cut["leaves"], cut_distances=cut["distances"],
                cut_leaf_total=cut["leaf_total"], cut_kind=cut["cut_kind"],
                selected_ratio=cut["selected_ratio"],
                cut_truncated=int(cut["truncated"]),
                patterns=["".join(str(b) for b in p)
                          for p in itertools.product([0, 1], repeat=k)],
                n_patterns=2 ** k,
                target_id=f"{v.name}|{t['bit']}|{t['target']}"))
            picked.append(t)
            used_names.add(t["target"])
    return _save(frozen[:16], rejected)


def _save(frozen, rejected) -> int:
    plan = dict(created=datetime.now().astimezone().isoformat(timespec="seconds"),
                rule=("8 designs x 2 targets; backward BFS depth=5, leaves at "
                      "distance>=2, <=4 single-bit leaves by sha256('r6|name'), "
                      "max shortest distance>=3; full 2^k enumeration; exclude "
                      "round-5 targets; no labels/test/positive neighborhoods"),
                frozen=frozen, rejected=rejected, relations=len(frozen),
                expected_queries=sum(2 * r["n_patterns"] for r in frozen),
                budget=dict(expansion_max=512, review_max=48, joint_max=16,
                            total_max=576, timeout_s=5, wall_cap_min=30),
                pre_registered="yes (created before queries)")
    blob = json.dumps(plan, ensure_ascii=False, sort_keys=True)
    plan["plan_sha256"] = hashlib.sha256(blob.encode()).hexdigest()
    (TAB6 / "r6_candidate_plan.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(dict(created=plan["created"], relations=len(frozen),
                          queries=plan["expected_queries"],
                          designs=len({r["design"] for r in frozen}),
                          hosts=sorted({r["host"] for r in frozen}),
                          val_designs=sorted({r["design"] for r in frozen
                                              if r["role"] == "val"}),
                          plan_sha256=plan["plan_sha256"]), ensure_ascii=False,
                     indent=2), flush=True)
    for r in frozen:
        print(f"{r['design']} {r['kind']} {r['target']} k={len(r['cut'])} "
              f"dist={r['cut_distances']} kind={r['cut_kind']} "
              f"ratio={r['selected_ratio']:.2f}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
