"""Round-2 extraction: non-local cuts with full small-cut enumeration + stable query IDs.

Fixes vs. round 1:
  * `proc -noopt` avoids yosys `Object '\\0' not found` on ys_id/ys_opt netlists;
  * cut is built 2 levels back from the target (non-local region boundary), not the
    target's own gate inputs;
  * every query has a marker, so a timeout cannot shift later results;
  * status vocabulary: complete / partial_timeout / infeasible / unsupported /
    mapping_ambiguous; unknown is never a negative;
  * graded values: feasible ratio, determinism ratio, per-input influence ratio.

No labels, no Trojan names, no risk scores are read. Candidates come from a fixed
structural rule recorded in selection.json.
"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import argparse
import hashlib
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(_eqguard_path(''))
sys.path.insert(0, str(ROOT / "phase2/ys"))
import sat_functional_relations as P0  # noqa: E402

OUT = ROOT / "_p0pilot/round2_20261025/extraction"
WORK = ROOT / "generate_trans/folds/hosts_bt31"
SEQ_PINS = {"CK", "CLK", "RN", "RST", "RESET", "SN", "SET", "SE", "SI"}


def load_module(js: Path, top: str) -> dict:
    return json.loads(js.read_text(encoding="utf-8"))["modules"][top]


def build_index(mod: dict):
    netbits = {nm: tuple(b for b in info.get("bits", []) if isinstance(b, int))
               for nm, info in mod.get("netnames", {}).items()}
    for nm, p in mod.get("ports", {}).items():
        netbits[nm] = tuple(b for b in p.get("bits", []) if isinstance(b, int))
    bit_driver = defaultdict(set)
    bit_consumer = defaultdict(set)
    cell_inputs = defaultdict(list)
    cell_outs = {}
    dff_cells = {}
    for cn, cell in mod.get("cells", {}).items():
        typ = str(cell.get("type", "")).upper()
        con = cell.get("connections", {})
        dirs = cell.get("port_directions", {})
        outs = []
        for pin, bits in con.items():
            is_out = dirs.get(pin) == "output" or (not dirs and pin in ("Y", "Q", "QN"))
            if is_out:
                outs += [b for b in bits if isinstance(b, int)]
                for b in bits:
                    if isinstance(b, int):
                        bit_driver[b].add(cn)
            elif pin.upper() not in SEQ_PINS:
                cell_inputs[cn].append((pin, bits))
                for b in bits:
                    if isinstance(b, int):
                        bit_consumer[b].add(cn)
        cell_outs[cn] = outs
        if "DFF" in typ or "LATCH" in typ:
            dff_cells[cn] = con
    return dict(netbits=netbits, bit_driver=bit_driver, bit_consumer=bit_consumer,
                cell_inputs=cell_inputs, cell_outs=cell_outs, dff_cells=dff_cells,
                cells=mod.get("cells", {}), ports=mod.get("ports", {}))


def net_of_bit(idx: dict, bit: int) -> str | None:
    for nm, bits in idx["netbits"].items():
        if len(bits) == 1 and bits[0] == bit:
            return nm
    return None


def out_ports(idx: dict) -> list[str]:
    return sorted(n for n, p in idx["ports"].items() if p.get("direction") == "output")


def build_script(v: Path, top: str, cases: list[dict], timeout: int,
                 ports: set[str]) -> tuple[str, int]:
    lines = [f'read_verilog "{P0.wsl(v)}"', f"hierarchy -top {top}", "flatten",
             "proc -noopt", f"select -module {top}"]
    renamed, rlines = {}, []

    def ref(nm: str) -> str:
        if nm in ports:
            return P0.sat_ref(nm)
        if nm in renamed:
            return renamed[nm]
        safe = f"fg_{len(renamed)}"
        renamed[nm] = safe
        rlines.append(f"rename {P0.sat_ref(nm)} {safe}")
        return safe

    for c in cases:
        c["_refs"] = {nm: ref(nm) for nm in c["_cut"]}
        c["_tref"] = ref(c["target"])
    lines += rlines
    if renamed:
        lines.append("setattr -set keep 1 " + " ".join(f"w:{x}" for x in renamed.values()))
    lines += ["techmap -autoproc -map phase2/ys/sat_cells_map.v", "opt -fast"]
    qid = 0
    for c in cases:
        c["_qids"] = []
        for pat in c["patterns"]:
            sets = " ".join(f"-set {c['_refs'][nm]} {v}" for nm, v in zip(c["_cut"], pat))
            for prove in (1, 0):
                qid += 1
                c["_qids"].append(qid)
                lines += [f"log QRY{qid:05d}",
                          f"sat -seq 1 {sets} -prove {c['_tref']} {prove} -timeout {timeout}"]
    return "\n".join(lines) + "\n", qid


def parse_blocks(out: str) -> dict[int, str]:
    import re
    blocks: dict[int, list[str]] = {}
    cur = None
    for line in out.splitlines():
        m = re.match(r"^QRY(\d{5})$", line.strip())
        if m:
            cur = int(m.group(1))
            blocks[cur] = []
            continue
        if cur is None:
            continue
        if "no model found: SUCCESS" in line:
            blocks[cur].append("proved")
        elif "model found: FAIL" in line:
            blocks[cur].append("refuted")
        elif "TIMEOUT" in line:
            blocks[cur].append("timeout")
        elif line.startswith("ERROR"):
            blocks[cur].append("error")
    return {k: (v[0] if v else "no_result") for k, v in blocks.items()}


def summarize(case: dict, statuses: dict[int, str]) -> dict:
    qids = case["_qids"]
    n = len(case["_cut"])
    forced, feas, unres = [], 0, 0
    for i, _pat in enumerate(case["patterns"]):
        s1 = statuses.get(qids[2 * i], "no_result")
        s0 = statuses.get(qids[2 * i + 1], "no_result")
        if s1 == "proved" and s0 == "proved":
            forced.append(None)
            unres += 1
        elif s1 == "proved" and s0 == "refuted":
            forced.append(1)
            feas += 1
        elif s1 == "refuted" and s0 == "proved":
            forced.append(0)
            feas += 1
        elif s1 == "refuted" and s0 == "refuted":
            forced.append(None)
            feas += 1
        else:
            forced.append("unknown")
    comparable, discordant = [0] * n, [0] * n
    pats = case["patterns"]
    for i in range(len(pats)):
        for j in range(i + 1, len(pats)):
            diff = [b for b in range(n) if pats[i][b] != pats[j][b]]
            if len(diff) != 1:
                continue
            b = diff[0]
            if isinstance(forced[i], int) and isinstance(forced[j], int):
                comparable[b] += 1
                if forced[i] != forced[j]:
                    discordant[b] += 1
    inf = [discordant[b] / comparable[b] for b in range(n) if comparable[b]]
    known = sum(isinstance(v, int) for v in forced)
    if any(v == "unknown" for v in forced):
        status = "partial_timeout"
    elif feas == 0:
        status = "infeasible"
    elif known == 0:
        status = "feasible_undetermined"
    else:
        status = "complete"
    return dict(n_patterns=len(pats), n_feasible=feas, n_unresolved=unres,
                n_forced=known, n_forced_one=sum(1 for v in forced if v == 1),
                determinism=(known / feas if feas else 0.0),
                influence_mean=float(np.mean(inf)) if inf else 0.0,
                influence_max=float(np.max(inf)) if inf else 0.0,
                n_influence_inputs=len(inf), status=status,
                pattern_outcomes=";".join(str(v) for v in forced))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout", type=int, default=3)
    ap.add_argument("--max-targets", type=int, default=5)
    ap.add_argument("--query-cap", type=int, default=400)
    ap.add_argument("--wall-cap", type=int, default=1800)
    ap.add_argument("--designs", default="")
    ap.add_argument("--tag", default="graded_r2")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "struct_raw").mkdir(exist_ok=True)

    split = json.loads((WORK / "views.json").read_text(encoding="utf-8"))
    role_of_view = {v: r for r in ("train", "val", "test") for v in split[f"{r}_views"]}

    # pre-registered, label-blind selection (see selection.json)
    import hashlib
    def hpick(cands):
        return sorted(cands, key=lambda s: hashlib.sha256(f"r2|{s}".encode()).hexdigest())[0]

    r2_nonctrl = ["a4ctldead_s0", "a4ctldead_s1", "a4ctlequiv_s0", "a4ctlequiv_s1",
                  "a4trojan_s0", "a4trojan_s1", "injalpha", "injdelta", "injepsilon",
                  "injgamma", "injzeta"]
    v_nonctrl = ["injalpha", "injbeta", "injepsilon", "injgamma", "injzeta"]
    plan = [
        ("rs232t1000", "ctlmatcha", "ys_abc", "normal_control"),
        ("rs232t1000", hpick(r2_nonctrl), "ys_abc", "hash_selected_noncontrol"),
        ("s38417t100", "ctlmatcha", "ys_aig", "normal_control"),
        ("s38417t100", hpick(v_nonctrl), "ys_aig", "hash_selected_noncontrol"),
        ("s38417t100", hpick(v_nonctrl), "ys_id", "recovery_noopt"),
    ]
    if a.designs:
        plan = [tuple(x.split("|")) for x in a.designs.split(",")]
    selection = dict(rule=("per host: one declared normal-control instance (ctlmatcha) + one "
                           "non-control instance chosen by sha256('r2|instance') ordering; "
                           "targets: DFF D nets ordered by structural observability, ties and "
                           "ordered positions broken by sha256('r2|target'), plus PO ports in "
                           "sha256 order; cut: 2-level fan-in, fallback 3-level, <=3 single-bit "
                           "leaf nets, all patterns enumerated; single-leaf cuts are skipped, "
                           "not padded; no name/label/risk input"),
                     hash_prefix="r2|", seed=None, timeout_s=a.timeout,
                     query_cap=a.query_cap, wall_cap_s=a.wall_cap, plan=plan,
                     no_label_inputs=True, no_trojan_name_filter=True,
                     started=time.strftime("%Y-%m-%dT%H:%M:%S%z"))
    (OUT / f"selection_{a.tag}.json").write_text(
        json.dumps(selection, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(plan), flush=True)
    import itertools
    t0 = time.time()
    qtotal = 0
    rows: list[dict] = []
    for host, inst, recipe, why in plan:
        if time.time() - t0 > a.wall_cap:
            rows.append(dict(design="", host=host, inst=inst, recipe=recipe, reason=why,
                             status="skipped_wall_cap"))
            continue
        vs = P0.find_designs("hosts_bt31", host, inst, [recipe])
        if not vs:
            rows.append(dict(design="", host=host, inst=inst, recipe=recipe, reason=why,
                             status="design_not_found"))
            continue
        v = vs[0]
        top = P0.module_name(v)
        raw = OUT / "struct_raw" / f"{v.stem}.json"
        if not raw.exists():
            s0 = "\n".join([f'read_verilog "{P0.wsl(v)}"', f"hierarchy -top {top}",
                            "flatten", "proc -noopt", f'write_json "{P0.wsl(raw)}"']) + "\n"
            P0.run_yosys(s0, OUT / "struct_raw" / f"{v.stem}.struct.log")
        mod = load_module(raw, top)
        idx = build_index(mod)
        cands = dff_d_targets(idx)
        for c in cands:
            c["reach_po"], c["reach_dff"] = reach(idx, c["bit"])
        cands.sort(key=lambda c: (-(c["reach_po"] + c["reach_dff"]),
                                  hashlib.sha256(("r2|" + c["target"]).encode()).hexdigest()))
        order = []
        if cands:
            order += [cands[0], cands[len(cands) // 2], cands[-1]]
            order += cands
        pool = [("dff_next", t) for t in order]
        po_order = sorted(out_ports(idx),
                          key=lambda s: hashlib.sha256(("r2|" + s).encode()).hexdigest())
        for p in po_order[:8]:
            bits = [b for b in idx["ports"][p].get("bits", []) if isinstance(b, int)]
            if len(bits) != 1:
                continue
            rp, rd = reach(idx, bits[0])
            pool.append(("cone", dict(kind="cone", cell=None, target=p, bit=bits[0],
                                      reach_po=rp, reach_dff=rd)))
        seen_t, accepted, rejected = set(), [], []
        for kind, t in pool:
            if len(accepted) >= a.max_targets:
                break
            if t["target"] in seen_t:
                continue
            seen_t.add(t["target"])
            cut, why_cut = cut_for(idx, t["target"], depth=2)
            depth = 2
            if why_cut:
                cut, why_cut = cut_for(idx, t["target"], depth=3)
                depth = 3 if not why_cut else 0
            if why_cut or not cut:
                rejected.append(f"{t['target']}:{why_cut}")
                continue
            accepted.append((t, cut, depth))
        print(f"[select] {v.name} accepted={len(accepted)} rejected={len(rejected)} "
              f"{rejected[:6]}", flush=True)
        cases = []
        for t, cut, depth in accepted:
            base = dict(design=v.name, top=top, host=host, inst=inst, recipe=recipe,
                        usage=why, kind=t["kind"], target=t["target"],
                        dff_cell=t.get("cell") or "",
                        driver=next(iter(idx["bit_driver"].get(t["bit"], {""}))),
                        reach_po=t["reach_po"], reach_dff=t["reach_dff"],
                        cut_nets=";".join(cut), cut_size=len(cut), cut_depth=depth,
                        role=role_of_view.get(v.stem, "unassigned"))
            base["patterns"] = list(itertools.product([0, 1], repeat=len(cut)))
            base["_cut"] = cut
            base["_qids"] = []
            cases.append(base)
        # respect the pre-declared query cap
        keep, need = [], 0
        for c in cases:
            nq = 2 * len(c["patterns"])
            if qtotal + need + nq > a.query_cap:
                rows.append({k: val for k, val in c.items() if not k.startswith("_")} |
                            dict(status="skipped_query_cap", n_patterns=len(c["patterns"])))
                continue
            keep.append(c)
            need += nq
        if not keep:
            continue
        script, nq = build_script(v, top, keep, a.timeout, set(idx["ports"]))
        print(f"[run] {v.name} targets={len(keep)} queries={nq}", flush=True)
        out = P0.run_yosys(script, OUT / f"{a.tag}__{v.stem}.sat.log", timeout=1800)
        st = parse_blocks(out)
        qtotal += nq
        for c in keep:
            s = summarize(c, st)
            row = {k: val for k, val in c.items() if not k.startswith("_")}
            row.update(s)
            row.update(query_ids=";".join(str(x) for x in c["_qids"]),
                       log=str((OUT / f"{a.tag}__{v.stem}.sat.log").relative_to(ROOT)),
                       evidence_scope=("2-level cut, all patterns enumerated; seq1 arbitrary "
                                       "state; legacy cell map; structural reach is not SAT"),
                       elapsed_s=round(time.time() - t0, 1))
            rows.append(row)
    d = pd.DataFrame(rows)
    d.to_csv(OUT / f"graded_{a.tag}.csv", index=False, encoding="utf-8-sig")
    print(d.to_string(index=False), flush=True)
    print("queries used", qtotal, "wall_s", round(time.time() - t0, 1), flush=True)
    return 0



def reach(idx: dict, bit: int, cap: int = 20000) -> tuple[int, int]:
    po_bits = {b for p in idx["ports"].values() if p.get("direction") == "output"
               for b in p.get("bits", []) if isinstance(b, int)}
    frontier, visited = [bit], {bit}
    po, dff = set(), set()
    while frontier and len(visited) < cap:
        nxt = []
        for b in frontier:
            if b in po_bits:
                po.add(b)
            for cn in idx["bit_consumer"].get(b, ()):
                if cn in idx["dff_cells"]:
                    dff.add((cn, b))
                    continue
                for ob in idx["cell_outs"].get(cn, ()):
                    if ob not in visited:
                        visited.add(ob)
                        nxt.append(ob)
        frontier = nxt
    return len(po), len(dff)


def pick_targets(idx: dict, n_dff: int = 2, n_po: int = 1) -> list[dict]:
    """Structural rule only: DFF D from top and middle observability ranks + PO at 1/3."""
    cands = dff_d_targets(idx)
    for c in cands:
        c["reach_po"], c["reach_dff"] = reach(idx, c["bit"])
    cands.sort(key=lambda c: (-(c["reach_po"] + c["reach_dff"]), c["target"]))
    picks = []
    if cands:
        picks.append(cands[0])
        if len(cands) > 2 and n_dff > 1:
            picks.append(cands[len(cands) // 2])
    pos = out_ports(idx)
    for p in pos:
        if len(picks) >= n_dff + n_po:
            break
        bits = [b for b in idx["ports"][p].get("bits", []) if isinstance(b, int)]
        if len(bits) != 1:
            continue
        if len(picks) < n_dff + n_po:
            rp, rd = reach(idx, bits[0])
            picks.append(dict(kind="cone", cell=None, target=p, bit=bits[0],
                              reach_po=rp, reach_dff=rd))
    if len(picks) > n_dff + n_po:
        picks = picks[: n_dff + n_po]
    return picks


def cut_for(idx: dict, net: str, depth: int = 2, max_cut: int = 3) -> tuple[list[str], str]:
    bits = idx["netbits"].get(net, ())
    if len(bits) != 1:
        return [], "target_not_single_bit"
    start = bits[0]
    seen = {start}
    frontier = [(start, 0)]
    leaves = []
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
                seen.add(nb)
                frontier.append((nb, d + 1))
    named = []
    for b, d in leaves:
        nm = net_of_bit(idx, b)
        if not nm or nm in ("0", "1", "x", "z") or nm.startswith("$"):
            continue
        named.append((d, nm))
    # prefer deeper leaves; ties broken by a hash, never by the name string
    named.sort(key=lambda x: (-x[0], hashlib.sha256(("r2|" + x[1]).encode()).hexdigest()))
    chosen = []
    for d, nm in named:
        if nm not in chosen:
            chosen.append(nm)
        if len(chosen) >= max_cut:
            break
    if len(chosen) < 2:
        return chosen, "cut_too_small"
    if max(d for d, _ in named[: len(chosen)]) < 2:
        return chosen, "cut_not_nonlocal"
    return chosen, ""



def dff_d_targets(idx: dict) -> list[dict]:
    """DFF D nets that have a single bit and a single combinational driver."""
    out = []
    for cn, con in idx["dff_cells"].items():
        dbits = [b for b in con.get("D", []) if isinstance(b, int)]
        if len(dbits) != 1:
            continue
        net = net_of_bit(idx, dbits[0])
        if not net:
            continue
        drv = idx["bit_driver"].get(dbits[0], set())
        if len(drv) != 1:
            continue
        dcn = next(iter(drv))
        if "DFF" in str(idx["cells"][dcn].get("type", "")).upper():
            continue
        out.append(dict(kind="dff_next", cell=cn, target=net, driver=dcn, bit=dbits[0]))
    return out


if __name__ == "__main__":
    raise SystemExit(main())
