"""Round-3 non-local supplement with independent DFF / PO budgets.

Full enumeration of the selected cut (k<=3), never calls a truncated cut
complete unless SAT proves sufficiency. No labels or Trojan names are read.
"""
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
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(_eqguard_path(''))
WORK = ROOT / "generate_trans/folds/hosts_bt31"
PT = WORK / "data/processed"
R3 = ROOT / "_p0pilot/round3_20261025"
TAB = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_valid_round3"
sys.path.insert(0, str(R3))
sys.path.insert(0, str(ROOT / "phase2/ys"))
import sat_functional_relations as P0  # noqa: E402
from r3_nets import build_index, cut_for, dff_d_targets, load_module, out_ports, reach  # noqa: E402
from r3_sat import run_cases  # noqa: E402
from sat_evidence import classify_cut, evaluate_case, schedule  # noqa: E402


def hkey(s: str) -> str:
    return hashlib.sha256(("r3|" + s).encode()).hexdigest()


def ensure_struct(v: Path, top: str) -> Path:
    raw = R3 / "struct_raw" / f"{v.stem}.json"
    if raw.exists():
        return raw
    raw.parent.mkdir(parents=True, exist_ok=True)
    s0 = "\n".join([f'read_verilog "{P0.wsl(v)}"', f"hierarchy -top {top}",
                    "flatten", "proc -noopt", f'write_json "{P0.wsl(raw)}"']) + "\n"
    P0.run_yosys(s0, R3 / "struct_raw" / f"{v.stem}.struct.log")
    return raw


def main() -> int:
    t0 = time.perf_counter()
    split = json.loads((WORK / "views.json").read_text(encoding="utf-8"))
    allowed = {r: set(split[f"{r}_views"]) for r in ("train", "val")}
    role_of_view = {v: r for r in allowed for v in allowed[r]}
    plan = [
        ("train", "rs232t1000", "ctlmatcha", "ys_abc", "normal_control"),
        ("train", "rs232t1000", "injzeta", "ys_abc", "hash_noncontrol"),
        ("val", "s38417t100", "ctlmatcha", "ys_aig", "normal_control"),
        ("val", "s38417t100", "injzeta", "ys_aig", "hash_noncontrol"),
    ]
    budget = dict(max_designs=4, dff_per_design=2, po_per_design=1,
                  max_patterns_per_target=8, query_timeout_s=3,
                  extra_query_cap=192, used_by_resolve=24, wall_cap_min=15)
    (TAB / "r3_graded_plan.json").write_text(json.dumps(dict(
        designs=plan, budget=budget,
        rule=("DFF D targets ordered by structural observability with sha256 tie-break, "
              "first 6 kept as a fallback pool; PO: ALL single-bit output ports in hash "
              "order, DFF-driven ports skipped, up to 8 combinational ports kept, with an "
              "independent budget; cut = 2-level fan-in (fallback 3), <=3 single-bit "
              "leaves; all 2^k patterns enumerated; truncated cuts are partial probes "
              "unless SAT proves sufficiency"),
        label_inputs=False, test_inputs=False), ensure_ascii=False, indent=2),
        encoding="utf-8")
    print(json.dumps(budget), flush=True)

    # unique target names per design are derived later; first prepare designs
    prepared = []
    for role, host, inst, recipe, usage in plan:
        v = WORK / "trans" / f"{host}__{inst}_d1_s42__{recipe}.v"
        if not v.exists():
            print("[skip] missing", v.name, flush=True)
            continue
        top = P0.module_name(v)
        idx = build_index(load_module(ensure_struct(v, top), top))
        cands = dff_d_targets(idx)
        for c in cands:
            c["reach_po"], c["reach_dff"] = reach(idx, c["bit"])
        cands.sort(key=lambda c: (-(c["reach_po"] + c["reach_dff"]), hkey(c["target"])))
        dff_order, seen_t = [], set()
        for c in cands:
            if c["target"] in seen_t:
                continue
            seen_t.add(c["target"])
            dff_order.append(c)
            if len(dff_order) >= 6:
                break
        po_items = []
        for p in sorted(out_ports(idx), key=hkey):
            bits = [b for b in idx["ports"][p].get("bits", []) if isinstance(b, int)]
            if len(bits) != 1:
                continue
            if all(c in idx["dff_cells"] for c in idx["bit_driver"].get(bits[0], set())):
                continue
            rp, rd = reach(idx, bits[0])
            po_items.append(dict(kind="cone", cell=None, target=p, bit=bits[0],
                                 reach_po=rp, reach_dff=rd))
            if len(po_items) >= 8:
                break
        prepared.append(dict(role=role, host=host, inst=inst, recipe=recipe,
                             usage=usage, v=v, top=top, idx=idx,
                             dff=dff_order, po=po_items))
        print(f"[prep] {v.name} dff={len(dff_order)} po_pool={len(po_items)}", flush=True)

    meta = json.loads((WORK / "data/for_train/metadata_trans.json").read_text(encoding="utf-8"))
    fids = np.asarray(meta["file_ids"], dtype=object)
    vid, views = pd.factorize(fids, sort=False)
    vid = vid.astype(np.int32)
    del fids
    view_role = np.asarray([role_of_view.get(str(v), "other") for v in views])
    view_ok = np.isin(view_role, ["train", "val"])
    desired = set()
    for p in prepared:
        for t in p["dff"] + p["po"]:
            d = p["idx"]["bit_driver"].get(t["bit"], set())
            if len(d) == 1:
                desired.add(next(iter(d)).lstrip("\\"))
            if t.get("cell"):
                desired.add(str(t["cell"]).lstrip("\\"))
    hits = defaultdict(list)
    with (PT / "node_names_trans.txt").open(encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= vid.size:
                break
            vi = int(vid[i])
            if not view_ok[vi]:
                continue
            nm = line.strip().lstrip("\\")
            if nm in desired:
                hits[nm].append((i, vi))
    by_key = defaultdict(list)
    for i, v in enumerate(views):
        if view_role[i] in ("train", "val"):
            p = str(v).split("__")
            by_key[(p[0], p[1], p[-1])].append(i)
    digest = {}

    def sha(p: Path) -> str:
        if str(p) not in digest:
            digest[str(p)] = (hashlib.sha256(p.read_bytes()).hexdigest()
                              if p.exists() else "")
        return digest[str(p)]

    rel_rows, q_rows, node_rows, map_rows, attempt_rows = [], [], [], [], []
    q_used, rejections = 0, []
    for p in prepared:
        if time.perf_counter() - t0 > budget["wall_cap_min"] * 60:
            attempt_rows.append(dict(design=p["v"].name, reason="skipped_wall_cap"))
            continue
        feasible = []
        for kind, items in (("dff_next", p["dff"]), ("cone", p["po"])):
            for t in items:
                cut = cut_for(p["idx"], t["target"], depth=2)
                depth = 2
                if cut["reason"]:
                    cut = cut_for(p["idx"], t["target"], depth=3)
                    depth = 3
                if cut["reason"]:
                    rejections.append(dict(design=p["v"].name, kind=kind,
                                           target=t["target"], reason=cut["reason"],
                                           leaf_total=cut["leaf_total"]))
                    attempt_rows.append(dict(design=p["v"].name, kind=kind,
                                             target=t["target"], accepted=False,
                                             reason=cut["reason"]))
                    continue
                feasible.append((kind, dict(target=t, cut=cut, depth=depth)))
        sch = schedule(feasible, dff_budget=budget["dff_per_design"],
                       po_budget=budget["po_per_design"], max_scan_per_kind=8)
        for a in sch["attempts"]:
            attempt_rows.append(dict(design=p["v"].name, **a))
        chosen = [it for (kind, it), a in zip(feasible, sch["attempts"])
                  if a.get("accepted")]
        cases = []
        for it in chosen:
            t, cut = it["target"], it["cut"]
            nq = 2 * (2 ** len(cut["leaves"]))
            if q_used + nq > budget["extra_query_cap"]:
                attempt_rows.append(dict(design=p["v"].name, kind=t["kind"],
                                         target=t["target"], accepted=False,
                                         reason="query_cap"))
                continue
            drv = p["idx"]["bit_driver"].get(t["bit"], set())
            cases.append(dict(design=p["v"].name, role=p["role"], host=p["host"],
                              recipe=p["recipe"], usage=p["usage"],
                              kind=t["kind"], target=t["target"],
                              target_id=f"{p['v'].name}|{t['bit']}|{t['target']}",
                              cut=cut["leaves"], patterns=list(
                                  itertools.product([0, 1], repeat=len(cut["leaves"]))),
                              driver=next(iter(drv)) if len(drv) == 1 else "",
                              dff_cell=str(t.get("cell") or ""),
                              cut_meta=cut, depth=it["depth"],
                              reach_po=t["reach_po"], reach_dff=t["reach_dff"]))
            q_used += nq
        if not cases:
            continue
        res = run_cases(p["v"], p["top"], cases, timeout=budget["query_timeout_s"],
                        ports=set(p["idx"]["ports"]),
                        log=R3 / "logs" / f"graded_{p['v'].stem}.sat.log",
                        dump_dir=R3 / "witness" / f"graded_{p['v'].stem}",
                        cache_path=R3 / "cache" / f"graded_{p['v'].stem}.json")
        print(f"[sat] {p['v'].name} targets={len(cases)} queries={res['n_queries']} "
              f"new={res['n_new']}", flush=True)
        for c in cases:
            int_status = {i + 1: res["statuses"][k]
                          for i, k in enumerate(c["_keys"])}
            ev = evaluate_case(c["cut"], c["patterns"],
                               list(range(1, 2 * len(c["patterns"]) + 1)),
                               int_status, structure="pending", enumerated=True)
            st, why = classify_cut(c["cut_meta"]["leaf_total"],
                                   c["cut_meta"]["selected"],
                                   c["cut_meta"]["truncated"],
                                   ev["functional_sufficiency"] == "proved")
            ev["cut_structure"] = st
            ev["cut_scope"] = dict(kind=why, leaf_total=c["cut_meta"]["leaf_total"],
                                   selected=c["cut_meta"]["selected"],
                                   truncated=c["cut_meta"]["truncated"],
                                   depth=c["depth"])
            rid = hashlib.sha1(f"{c['design']}|{c['target']}|{c['cut']}|{c['kind']}"
                               .encode()).hexdigest()[:16]
            row = dict(relation_id=rid, design=c["design"], role=c["role"],
                       host=c["host"], recipe=c["recipe"], usage=c["usage"],
                       kind=c["kind"], target=c["target"], target_id=c["target_id"],
                       driver=c["driver"], dff_cell=c["dff_cell"],
                       cut_nets=";".join(c["cut"]), cut_size=len(c["cut"]),
                       cut_leaf_total=c["cut_meta"]["leaf_total"],
                       cut_truncated=int(c["cut_meta"]["truncated"]),
                       cut_depth=c["depth"], reach_po=c["reach_po"],
                       reach_dff=c["reach_dff"],
                       log=str((R3 / "logs" / f"graded_{p['v'].stem}.sat.log")
                               .relative_to(ROOT)))
            row.update({k: ev[k] for k in (
                "n_patterns", "n_feasible", "n_infeasible", "n_feasibility_unknown",
                "n_forced", "n_forced_one", "n_undecided", "n_one_sided",
                "determinism_ratio", "functional_sufficiency", "sufficiency_reason",
                "patterns_enumerated", "cut_structure", "query_status",
                "forcing_patterns", "influence_per_input", "influence_status",
                "influence_mean", "influence_max", "n_influence_inputs",
                "n_valid_influence_inputs")})
            rel_rows.append(row)
            for i, pat in enumerate(c["patterns"]):
                for j, prove in enumerate((1, 0)):
                    key = c["_keys"][2 * i + j]
                    q_rows.append(dict(relation_id=rid, design=c["design"],
                                       target=c["target"],
                                       pattern="".join(str(x) for x in pat),
                                       prove=prove, query_key=key,
                                       status=res["statuses"][key],
                                       witness=res["witnesses"][key][:4000]))
            attach = {c["driver"].lstrip("\\")} if c["driver"] else set()
            if c["dff_cell"]:
                attach.add(c["dff_cell"].lstrip("\\"))
            parts = Path(c["design"]).stem.split("__")
            elig = [i for i in by_key.get((parts[0], parts[1], parts[-1]), [])
                    if sha(WORK / "trans" / f"{views[i]}.v") ==
                    sha(WORK / "trans" / c["design"])]
            for vi in elig:
                mapped = []
                for nm in sorted(attach):
                    ids = [i for i, vv in hits.get(nm, []) if vv == vi]
                    if ids:
                        mapped.append(nm)
                        for ni in ids:
                            node_rows.append(dict(relation_id=rid,
                                                  design=c["design"],
                                                  view=str(views[vi]),
                                                  role=view_role[vi], name=nm,
                                                  node_index=int(ni),
                                                  target_id=c["target_id"]))
                map_rows.append(dict(relation_id=rid, design=c["design"],
                                     view=str(views[vi]), role=view_role[vi],
                                     attach=len(attach), mapped=len(mapped),
                                     missing=len(attach) - len(mapped),
                                     missing_names=";".join(sorted(attach - set(mapped)))))
    rel = pd.DataFrame(rel_rows)
    rel.to_csv(TAB / "r3_graded_relations.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(q_rows).to_csv(TAB / "r3_graded_queries.csv", index=False,
                                encoding="utf-8-sig")
    pd.DataFrame(node_rows).to_csv(TAB / "r3_graded_nodes.csv", index=False,
                                   encoding="utf-8-sig")
    pd.DataFrame(map_rows).to_csv(TAB / "r3_graded_mapping_by_view.csv", index=False,
                                  encoding="utf-8-sig")
    pd.DataFrame(attempt_rows).to_csv(TAB / "r3_graded_attempts.csv", index=False,
                                      encoding="utf-8-sig")
    pd.DataFrame(rejections).to_csv(TAB / "r3_graded_rejections.csv", index=False,
                                    encoding="utf-8-sig")
    mdf = pd.DataFrame(map_rows)
    info = dict(designs=[p["v"].name for p in prepared], relations=len(rel),
                queries=len(q_rows), wall_s=round(time.perf_counter() - t0, 1),
                dff_targets=int((rel.kind == "dff_next").sum()) if len(rel) else 0,
                po_targets=int((rel.kind == "cone").sum()) if len(rel) else 0,
                sufficiency=rel.functional_sufficiency.value_counts().to_dict()
                if len(rel) else {},
                cut_structure=rel.cut_structure.value_counts().to_dict()
                if len(rel) else {},
                influence_status=rel.influence_status.value_counts().to_dict()
                if len(rel) else {},
                attempts=len(attempt_rows), rejections=len(rejections),
                mapping_views=int(len(map_rows)),
                mapping_views_all_mapped=int((mdf.missing == 0).sum()) if len(mdf) else 0,
                allowed_roles=sorted(allowed), test_used=False)
    (TAB / "r3_graded_manifest.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(info, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
