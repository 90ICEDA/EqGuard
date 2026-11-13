"""Pre-register the round-3 recovery plan (no SAT queries here)."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import hashlib
import json
from pathlib import Path

import pandas as pd

ROOT = Path(_eqguard_path(''))
WORK = ROOT / "generate_trans/folds/hosts_bt31"
R3 = ROOT / "_p0pilot/round3_20261025"
TAB = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_valid_round3"


def hpick(items, prefix="r3|"):
    return sorted(items, key=lambda s: hashlib.sha256((prefix + s).encode()).hexdigest())


def main() -> int:
    split = json.loads((WORK / "views.json").read_text(encoding="utf-8"))
    allowed = {r: set(split[f"{r}_views"]) for r in ("train", "val")}
    role = {v: r for r in allowed for v in allowed[r]}
    d = pd.read_csv(ROOT / "_p0pilot/functional_relations_agnostic.csv",
                    encoding="utf-8-sig").fillna("")
    d = d[d.kind.isin(["cone", "dff_next"])].copy()
    d["role"] = d.design.map(lambda s: role.get(Path(str(s)).stem, "other"))
    unknown = d[["sat_q1", "sat_q2", "sat_q3", "sat_q4"]].isin(
        ["proved", "refuted"]).sum(axis=1) == 0
    u = d[unknown & d.role.isin(["train", "val"])].copy()
    assert len(u) == 680, len(u)

    # non-control instance pools (fold-declared control families are excluded here
    # only to build the non-control pool; no label or Trojan name is consulted)
    s15850_nonctrl = ["a4ctldead_s0", "a4ctldead_s1", "a4ctlequiv_s0", "a4ctlequiv_s1",
                      "a4trojan_s0", "a4trojan_s1", "injalpha", "injdelta",
                      "injepsilon", "injgamma", "injzeta"]
    s38417_nonctrl = ["injalpha", "injbeta", "injepsilon", "injgamma", "injzeta"]
    plan_spec = [
        ("train", "s15850t100", "ctlmatcha", "ys_id", "control_train_ysid", "unfinished"),
        ("train", "s15850t100", hpick(s15850_nonctrl)[0], "ys_id", "hash_noncontrol_train_ysid", "unfinished"),
        ("val", "s38417t100", "ctlmatcha", "ys_id", "control_val_ysid", "unfinished"),
        ("val", "s38417t100", hpick(s38417_nonctrl)[0], "ys_id", "hash_noncontrol_val_ysid", "unfinished"),
        ("val", "s38417t100", "ctlmatcha", "ys_opt", "control_val_ysopt", "unfinished"),
        ("train", "rs232t1000", "ctlmatcha", "ys_abc", "regression_accepted", "accepted"),
    ]

    def resolve(host, inst, recipe, scope):
        pool = u if scope == "unfinished" else d[d.role.isin(["train", "val"])]
        sub = pool[(pool.design.str.startswith(f"{host}__{inst}_d1_s42__")) &
                   (pool.design.str.endswith(f"{recipe}.v"))]
        if sub.empty:
            sub = pool[(pool.design.str.startswith(f"{host}__{inst}_d1_s42__")) &
                       (pool.design.str.contains(f"__{recipe}.v"))]
        return sorted(sub.design.unique())

    rows, designs = [], []
    for role_name, host, inst, recipe, purpose, scope in plan_spec:
        names = resolve(host, inst, recipe, scope)
        if len(names) != 1:
            raise SystemExit(f"cannot resolve {host}/{inst}/{recipe}: {names}")
        design = names[0]
        pool = u if scope == "unfinished" else d[d.role.isin(["train", "val"])]
        sub = pool[pool.design == design].copy()
        sub["h"] = sub.apply(lambda r: hashlib.sha256(
            f"r3|{r.target}|{r.cut_nets}".encode()).hexdigest(), axis=1)
        sub = sub.sort_values(["kind", "h"])
        cone = sub[sub.kind == "cone"].head(12)
        dff = sub[sub.kind == "dff_next"].head(8)
        chosen = pd.concat([cone, dff]).head(20)
        designs.append(dict(role=role_name, host=host, inst=inst, recipe=recipe,
                            purpose=purpose, scope=scope, design=design,
                            available_rows=len(sub), candidates=len(chosen),
                            cone=int((chosen.kind == "cone").sum()),
                            dff=int((chosen.kind == "dff_next").sum())))
        rows.append(chosen.assign(role=role_name, purpose=purpose, host=host,
                                  recipe=recipe, scope=scope))
    cand = pd.concat(rows, ignore_index=True)
    n_rec = int((cand.scope == "unfinished").sum())
    n_reg = int((cand.scope == "accepted").sum())
    plan = dict(
        rule=("allowed roles = train+val only; designs = one fold-declared normal "
              "control per gap + one non-control instance by sha256('r3|instance') + "
              "one accepted regression design; candidates = old cone/DFF rows sorted "
              "by (kind, sha256('r3|target|cut_nets')), max 12 cone + 8 DFF per design; "
              "patterns = old all-1 / all-0 probe only, so functional sufficiency is "
              "NOT_ENUMERATED and can never be 'proved'"),
        roles=sorted(allowed), budget=dict(max_designs=6, max_candidates=120,
                                           max_recovery_queries=480,
                                           max_extra_queries=320, max_total_queries=800,
                                           query_timeout_s=5, wall_cap_min=30),
        designs=designs, candidates_total=len(cand),
        recovery_candidates=n_rec, regression_candidates=n_reg,
        expected_recovery_queries=4 * n_rec,
        expected_regression_queries=4 * n_reg,
        expected_extra_nonlocal_queries=192,
        expected_total_queries=4 * len(cand) + 192,
        selection_inputs="design/instance name, target net, cut nets, structural kind",
        label_inputs=False, test_inputs=False,
        started="2026-10-25T17:05:00+08:00")
    (R3 / "recovery_plan.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    cand.to_csv(TAB / "r3_recovery_candidates.csv", index=False, encoding="utf-8-sig")
    print(json.dumps(plan, ensure_ascii=False, indent=2), flush=True)
    print("\nper design:\n", pd.DataFrame(designs).to_string(index=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
