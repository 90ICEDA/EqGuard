"""Execute the pre-registered round-3 recovery (train/val only, bounded)."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import hashlib
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
from r3_nets import build_index, load_module  # noqa: E402
from r3_sat import run_cases  # noqa: E402
from sat_evidence import evaluate_case  # noqa: E402


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
    plan = json.loads((R3 / "recovery_plan.json").read_text(encoding="utf-8"))
    cand = pd.read_csv(TAB / "r3_recovery_candidates.csv", encoding="utf-8-sig").fillna("")
    split = json.loads((WORK / "views.json").read_text(encoding="utf-8"))
    allowed = {r: set(split[f"{r}_views"]) for r in ("train", "val")}
    role_of_view = {v: r for r in allowed for v in allowed[r]}

    prepared, rejections = [], []
    for _, drow in pd.DataFrame(plan["designs"]).iterrows():
        v = WORK / "trans" / drow["design"]
        top = P0.module_name(v)
        raw = ensure_struct(v, top)
        idx = build_index(load_module(raw, top))
        sub = cand[cand.design == drow["design"]]
        cases = []
        for _, r in sub.iterrows():
            cut = [x for x in str(r["cut_nets"]).split(";") if x]
            target = str(r["target"])
            bits = idx["netbits"].get(target, ())
            if not cut:
                rejections.append(dict(design=drow["design"], target=target,
                                       kind=r["kind"], reason="empty_cut"))
                continue
            if len(bits) != 1:
                rejections.append(dict(design=drow["design"], target=target,
                                       kind=r["kind"], reason="target_not_single_bit"))
                continue
            if any(len(idx["netbits"].get(n, ())) != 1 for n in cut):
                rejections.append(dict(design=drow["design"], target=target,
                                       kind=r["kind"], reason="cut_net_missing_or_bus"))
                continue
            drv = idx["bit_driver"].get(bits[0], set())
            if len(drv) != 1:
                rejections.append(dict(design=drow["design"], target=target,
                                       kind=r["kind"], reason="driver_not_unique"))
                continue
            driver = next(iter(drv))
            dff = str(r["cell"]) if r["kind"] == "dff_next" else ""
            if dff and dff not in idx["cells"]:
                rejections.append(dict(design=drow["design"], target=target,
                                       kind=r["kind"], reason="dff_cell_missing"))
                continue
            k = len(cut)
            cases.append(dict(design=drow["design"], role=drow["role"],
                              purpose=drow["purpose"], scope=drow["scope"],
                              host=drow["host"], recipe=drow["recipe"],
                              kind=r["kind"], target=target,
                              target_id=f"{drow['design']}|{bits[0]}|{target}",
                              cut=cut, patterns=[(1,) * k, (0,) * k],
                              driver=driver, dff_cell=dff,
                              saved=[r[f"sat_q{i}"] for i in range(1, 5)]))
        prepared.append(dict(meta=drow.to_dict(), v=v, top=top, idx=idx, cases=cases))
        print(f"[prep] {drow['design']} cases={len(cases)}", flush=True)

    # one pass over node names for all attach names, restricted to allowed views
    meta = json.loads((WORK / "data/for_train/metadata_trans.json").read_text(encoding="utf-8"))
    fids = np.asarray(meta["file_ids"], dtype=object)
    vid, views = pd.factorize(fids, sort=False)
    vid = vid.astype(np.int32)
    del fids
    view_role = np.asarray([role_of_view.get(str(v), "other") for v in views])
    view_ok = np.isin(view_role, ["train", "val"])
    desired = set()
    for p in prepared:
        for c in p["cases"]:
            desired.add(c["driver"].lstrip("\\"))
            if c["dff_cell"]:
                desired.add(c["dff_cell"].lstrip("\\"))
    hits = defaultdict(list)
    with (PT / "node_names_trans.txt").open(encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= vid.size:
                break
            vidx = int(vid[i])
            if not view_ok[vidx]:
                continue
            nm = line.strip().lstrip("\\")
            if nm in desired:
                hits[nm].append((i, vidx))
    print(f"[nodes] desired={len(desired)} names_with_hits={len(hits)}", flush=True)

    by_key = defaultdict(list)
    for i, v in enumerate(views):
        if view_role[i] not in ("train", "val"):
            continue
        p = str(v).split("__")
        by_key[(p[0], p[1], p[-1])].append(i)
    digest = {}

    def sha(p: Path) -> str:
        if str(p) not in digest:
            digest[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else ""
        return digest[str(p)]

    rel_rows, q_rows, node_rows, map_rows = [], [], [], []
    q_used = 0
    wall_cap = 30 * 60
    for p in prepared:
        if time.perf_counter() - t0 > wall_cap:
            rel_rows.append(dict(design=p["meta"]["design"], status="skipped_wall_cap"))
            continue
        d = p["meta"]
        v = p["v"]
        cases = p["cases"]
        if not cases:
            continue
        res = run_cases(v, p["top"], cases, timeout=5, ports=set(p["idx"]["ports"]),
                        log=R3 / "logs" / f"{v.stem}.sat.log",
                        dump_dir=R3 / "witness" / v.stem,
                        cache_path=R3 / "cache" / f"{v.stem}.json")
        q_used += res["n_queries"]
        print(f"[sat] {v.name} queries={res['n_queries']} new={res['n_new']} "
              f"cached={res['n_cached']}", flush=True)
        for c in cases:
            int_status = {i + 1: res["statuses"][k] for i, k in enumerate(c["_keys"])}
            ev = evaluate_case(c["cut"], c["patterns"], [1, 2, 3, 4], int_status,
                               structure="old_cutset_two_pattern_probe",
                               cut_scope=dict(kind="old_all1_all0_probe",
                                              cut_size=len(c["cut"])),
                               enumerated=False)
            got = [int_status[i] for i in range(1, 5)]
            same = sum(a == b for a, b in zip(got, c["saved"]))
            rid = hashlib.sha1(f"{c['design']}|{c['target']}|{c['cut']}|{c['kind']}"
                               .encode()).hexdigest()[:16]
            row = dict(relation_id=rid, design=c["design"], role=c["role"],
                       host=c["host"], recipe=c["recipe"], purpose=c["purpose"],
                       scope=c["scope"], kind=c["kind"], target=c["target"],
                       target_id=c["target_id"], driver=c["driver"],
                       dff_cell=c["dff_cell"], cut_nets=";".join(c["cut"]),
                       cut_size=len(c["cut"]), saved=";".join(c["saved"]),
                       replayed=";".join(got), saved_equal=int(same),
                       saved_equal_all=int(got == c["saved"]),
                       log=str((R3 / "logs" / f"{v.stem}.sat.log").relative_to(ROOT)))
            row.update({k: ev[k] for k in (
                "n_patterns", "n_feasible", "n_infeasible",
                "n_feasibility_unknown", "n_forced", "n_forced_one",
                "n_undecided", "n_one_sided", "determinism_ratio",
                "functional_sufficiency", "sufficiency_reason",
                "patterns_enumerated", "cut_structure", "query_status",
                "forcing_patterns", "influence_per_input",
                "influence_status", "influence_mean", "influence_max",
                "n_influence_inputs", "n_valid_influence_inputs")})
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
            attach = {c["driver"].lstrip("\\")}
            if c["dff_cell"]:
                attach.add(c["dff_cell"].lstrip("\\"))
            parts = Path(c["design"]).stem.split("__")
            elig = [i for i in by_key.get((parts[0], parts[1], parts[-1]), [])
                    if sha(WORK / "trans" / f"{views[i]}.v") == sha(v)]
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
    rel.to_csv(TAB / "r3_recovery_relations.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(q_rows).to_csv(TAB / "r3_recovery_queries.csv", index=False,
                                encoding="utf-8-sig")
    pd.DataFrame(node_rows).to_csv(TAB / "r3_recovery_nodes.csv", index=False,
                                   encoding="utf-8-sig")
    pd.DataFrame(map_rows).to_csv(TAB / "r3_recovery_mapping_by_view.csv",
                                  index=False, encoding="utf-8-sig")
    reg = rel[rel.scope == "accepted"]
    mdf = pd.DataFrame(map_rows)
    info = dict(planned=plan["candidates_total"],
                executed_relations=int(len(rel)),
                executed_queries=int(q_used),
                plan_expected_queries=plan["expected_total_queries"],
                wall_s=round(time.perf_counter() - t0, 1),
                rejections=len(rejections),
                rejection_reasons=(pd.Series([r["reason"] for r in rejections])
                                   .value_counts().to_dict() if rejections else {}),
                regression_cases=int(len(reg)),
                regression_query_matches=int(reg.saved_equal.sum()) if len(reg) else 0,
                regression_query_total=int(4 * len(reg)),
                sufficiency_counts=rel.functional_sufficiency.value_counts().to_dict(),
                mapping_views=int(len(map_rows)),
                mapping_views_all_mapped=int((mdf.missing == 0).sum()) if len(mdf) else 0,
                allowed_roles=sorted(allowed), test_used=False)
    pd.DataFrame(rejections).to_csv(TAB / "r3_recovery_rejections.csv", index=False,
                                    encoding="utf-8-sig")
    (TAB / "r3_recovery_manifest.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(info, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
