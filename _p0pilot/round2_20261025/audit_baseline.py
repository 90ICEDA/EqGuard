"""Train/val/test baseline for sparse_sat_round1, with role-consistent denominators.

Reads only existing artefacts (no SAT search, no label-based candidate selection).
Outputs go to tables/sat_map_round2/ (new versioned dir).
"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import json
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import torch

ROOT = Path(_eqguard_path(''))
WORK = ROOT / "generate_trans/folds/hosts_bt31"
PT = WORK / "data/processed"
OLD = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sparse_sat_round1"
OUT = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_map_round2"
NAMES = ["reach_po_log", "reach_dff_log", "forced_pattern_fraction",
         "feasible_pattern_fraction", "tested_joint_change_ratio",
         "forced_one_fraction", "evaluated_case", "covered"]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    split = json.loads((WORK / "views.json").read_text(encoding="utf-8"))
    role_of_view = {}
    for role in ("train", "val", "test"):
        for v in split[f"{role}_views"]:
            role_of_view[v] = role

    # ---------- node -> view -> role ----------
    meta = json.loads((WORK / "data/for_train/metadata_trans.json").read_text(encoding="utf-8"))
    file_ids = np.asarray(meta["file_ids"], dtype=object)
    vid, views = pd.factorize(file_ids, sort=False)
    vid = vid.astype(np.int32)
    n = len(vid)
    assert n == 3220146, n
    role_code = np.zeros(len(views), dtype=np.int8)
    for i, v in enumerate(views):
        role_code[i] = {"train": 1, "val": 2, "test": 3}.get(role_of_view.get(str(v), ""), 0)
    node_role = role_code[vid]
    del file_ids
    print("views", len(views), Counter(role_code.tolist()), flush=True)

    graph = torch.load(PT / "trans_graph.pt", map_location="cpu", weights_only=False, mmap=True)
    y = graph.y.numpy().reshape(-1) > 0
    edges = graph.edge_index.numpy()
    masks = {k: getattr(graph, f"{k}_mask").numpy().reshape(-1).astype(bool)
             for k in ("train", "val", "test")}
    trust = np.load(PT / "trust_trans.npy")
    print("nodes by mask", {k: int(v.sum()) for k, v in masks.items()}, flush=True)
    print("node_role counts", {k: int((node_role == c).sum())
                               for k, c in (("train", 1), ("val", 2), ("test", 3))}, flush=True)
    for k, c in (("train", 1), ("val", 2), ("test", 3)):
        print(f"mask[{k}] vs view_role: inter={int((masks[k] & (node_role == c)).sum())} "
              f"mask={int(masks[k].sum())} role={int((node_role == c).sum())}", flush=True)

    # ---------- candidates / queries ----------
    rel = pd.read_csv(ROOT / "_p0pilot/functional_relations_agnostic.csv",
                      encoding="utf-8-sig").fillna("")
    rel["role"] = rel["design"].map(
        lambda d: role_of_view.get(Path(str(d)).stem, "unassigned"))
    rel["is_complex"] = rel["kind"].isin(["cone", "dff_next"])
    cand_rows = []
    for (role, kind), g in rel.groupby(["role", "kind"], sort=True):
        q = g[["sat_q1", "sat_q2", "sat_q3", "sat_q4"]].to_numpy().reshape(-1)
        known = np.isin(q, ["proved", "refuted"])
        determined = g[["sat_q1", "sat_q2", "sat_q3", "sat_q4"]].isin(
            ["proved", "refuted"]).all(axis=1)
        cand_rows.append(dict(role=role, kind=kind, rows=len(g), queries=len(q),
                              definite_values=int(known.sum()),
                              unknown_values=int((~known).sum()),
                              rows_all4_definite=int(determined.sum()),
                              rows_any_unknown=int((~determined).sum()),
                              declared_proved=int((g["status"] == "proved").sum()),
                              declared_partial=int((g["status"] == "partial").sum())))
    cand = pd.DataFrame(cand_rows)
    cand.to_csv(OUT / "baseline_candidates.csv", index=False, encoding="utf-8-sig")
    print("\n[candidates]\n", cand.to_string(index=False), flush=True)

    # ---------- log qualification by role ----------
    qual = pd.read_csv(OLD / "log_qualification.csv", encoding="utf-8-sig").fillna("")
    design_of_log = rel.groupby("log")["design"].first()
    log_role = design_of_log.map(lambda d: role_of_view.get(Path(str(d)).stem, "unassigned"))
    qual["role"] = qual["log"].map(log_role).fillna("unassigned")
    by_role = qual.groupby(["role", "accepted"]).agg(
        logs=("log", "size"), queries=("queries", "sum"),
        complex_rows=("complex_rows", "sum"), qualified_rows=("qualified_rows", "sum")).reset_index()
    by_role.to_csv(OUT / "baseline_log_qualification.csv", index=False, encoding="utf-8-sig")
    print("\n[log qualification]\n", by_role.to_string(index=False), flush=True)

    # ---------- qualified relations / mapped nodes ----------
    ev = pd.read_csv(OLD / "conditional_evidence.csv", encoding="utf-8-sig").fillna("")
    ev["role"] = ev["source"].map(
        lambda s: role_of_view.get(str(s).replace(".v", ""), "unassigned"))
    ev["host"] = ev["source"].map(lambda s: str(s).split("__")[0])
    ev["recipe"] = ev["source"].map(lambda s: str(s).split("__")[-1].replace(".v", ""))
    x = np.load(PT / "satrel_node_feats_sparseR1_real.npy", mmap_mode="r")
    eval_mask = np.asarray(x[:, 6]) > 0
    print("\nqualified relations", len(ev), "unique sources", ev["source"].nunique(),
          "unique targets", ev["target"].nunique(),
          "unique drivers", ev["driver"].nunique(), flush=True)
    strat = []
    for keys, g in ev.groupby(["role", "host", "recipe", "kind"], sort=True):
        role, host, recipe, kind = keys
        strat.append(dict(role=role, host=host, recipe=recipe, kind=kind,
                          relations=len(g),
                          unique_targets=g["target"].nunique(),
                          unique_drivers=g["driver"].nunique(),
                          forced_patterns_gt0=int((g["forced_patterns"].astype(int) > 0).sum()),
                          both_patterns=int((g["feasible_patterns"].astype(int) > 1).sum()),
                          joint_change=int((g["tested_joint_change"].astype(int) > 0).sum()),
                          forced_one=int((g["forced_ones"].astype(int) > 0).sum())))
    strat_df = pd.DataFrame(strat)
    strat_df.to_csv(OUT / "baseline_qualified_by_stratum.csv", index=False,
                    encoding="utf-8-sig")
    print("\n[qualified by role]\n",
          strat_df.groupby("role")[["relations", "unique_targets", "unique_drivers"]]
          .sum().to_string(), flush=True)

    node_host = np.asarray([str(v).split("__")[0] for v in views], dtype=object)
    node_recipe = np.asarray([str(v).split("__")[-1] for v in views], dtype=object)
    map_rows = []
    for k, c in (("train", 1), ("val", 2), ("test", 3), ("all_assigned", -1)):
        m = eval_mask if c < 0 else (eval_mask & (node_role == c))
        map_rows.append(dict(scope=k, evaluated_nodes=int(m.sum()),
                             unique_views=int(len(np.unique(vid[m]))) if m.any() else 0,
                             positives=int((m & y).sum())))
    pd.DataFrame(map_rows).to_csv(OUT / "baseline_mapped_nodes.csv", index=False,
                                  encoding="utf-8-sig")
    print("\n[mapped nodes]\n", pd.DataFrame(map_rows).to_string(index=False), flush=True)

    # ---------- coverage: direct / 1 / 2 hop, per role ----------
    support = (np.asarray(x[:, 2:6]) != 0).any(axis=1)
    cov_rows = []
    for role, c in (("train", 1), ("val", 2), ("test", 3)):
        rm = node_role == c
        reached = support & rm
        for h in range(3):
            cov_rows.append(dict(role=role, hops=h, nodes=int(reached.sum()),
                                 positives=int((reached & y & rm).sum()),
                                 trusted_positives=int((reached & y & trust & rm).sum()),
                                 trusted_negatives=int((reached & ~y & trust & rm).sum()),
                                 denominator_nodes=int(rm.sum()),
                                 denominator_positives=int((y & rm).sum()),
                                 denominator_trusted_positives=int((y & trust & rm).sum()),
                                 denominator_trusted_negatives=int((~y & trust & rm).sum())))
            if h < 2:
                nxt = reached.copy()
                nxt[edges[1, reached[edges[0]]]] = True
                reached = nxt
    pd.DataFrame(cov_rows).to_csv(OUT / "baseline_receptive_field.csv", index=False,
                                  encoding="utf-8-sig")
    print("\n[receptive field]\n", pd.DataFrame(cov_rows).to_string(index=False), flush=True)

    # per-column coverage by role
    colcov = []
    for j, name in enumerate(NAMES):
        nz = np.asarray(x[:, j]) != 0
        for role, c in (("train", 1), ("val", 2), ("test", 3)):
            m = nz & (node_role == c)
            colcov.append(dict(column=name, role=role, nonzero=int(m.sum()),
                               positives=int((m & y).sum()),
                               trusted_positives=int((m & y & trust).sum()),
                               trusted_negatives=int((m & ~y & trust).sum()),
                               denominator=int((node_role == c).sum())))
    pd.DataFrame(colcov).to_csv(OUT / "baseline_column_coverage.csv", index=False,
                                encoding="utf-8-sig")

    # per-host / recipe stratified coverage (train/val only)
    strat_cov = []
    for host in sorted(set(node_host)):
        for recipe in sorted(set(node_recipe)):
            vm = (node_host[vid] == host) & (node_recipe[vid] == recipe)
            for role, c in (("train", 1), ("val", 2), ("test", 3)):
                m = vm & (node_role == c)
                if not m.any():
                    continue
                d = support & m
                strat_cov.append(dict(role=role, host=host, recipe=recipe,
                                      nodes=int(m.sum()), positives=int((m & y).sum()),
                                      sat_nodes=int(d.sum()),
                                      sat_positives=int((d & y).sum()),
                                      sat_trusted_positives=int((d & y & trust).sum()),
                                      sat_trusted_negatives=int((d & ~y & trust).sum())))
    pd.DataFrame(strat_cov).to_csv(OUT / "baseline_stratified_coverage.csv", index=False,
                                   encoding="utf-8-sig")

    # ---------- column statistics ----------
    stats = []
    cols = np.asarray(x, dtype=np.float32)
    for j, name in enumerate(NAMES):
        col = cols[:, j]
        for role, c in (("train", 1), ("val", 2), ("test", 3)):
            v = col[node_role == c]
            nzv = v[v != 0]
            uniq = np.unique(v)
            idx = np.searchsorted(uniq, v)
            modal_share = float(np.max(np.bincount(idx)) / v.size) if v.size else 0.0
            stats.append(dict(column=name, role=role, mean=float(v.mean()),
                              std=float(v.std()), min=float(v.min()), max=float(v.max()),
                              nonzero_rate=float((v != 0).mean()),
                              unique_all=int(uniq.size),
                              unique_nonzero=int(np.unique(nzv).size),
                              nonzero_p50=float(np.percentile(nzv, 50)) if nzv.size else 0.0,
                              nonzero_p95=float(np.percentile(nzv, 95)) if nzv.size else 0.0,
                              modal_value_share=modal_share))
    stats_df = pd.DataFrame(stats)
    stats_df.to_csv(OUT / "baseline_column_stats.csv", index=False, encoding="utf-8-sig")
    print("\n[column stats: train]\n",
          stats_df[stats_df.role == "train"].to_string(index=False), flush=True)

    dup = []
    for a in range(len(NAMES)):
        for b in range(a + 1, len(NAMES)):
            dup.append(dict(a=NAMES[a], b=NAMES[b],
                            identical=bool(np.array_equal(cols[:, a], cols[:, b])),
                            equal_fraction=float(np.mean(cols[:, a] == cols[:, b]))))
    pd.DataFrame(dup).to_csv(OUT / "baseline_duplicate_columns.csv", index=False,
                             encoding="utf-8-sig")

    info = dict(views=len(views), role_view_counts={
        "train": len(split["train_views"]), "val": len(split["val_views"]),
        "test": len(split["test_views"])},
        node_counts={k: int(v.sum()) for k, v in masks.items()},
        node_role_counts={k: int((node_role == c).sum())
                          for k, c in (("train", 1), ("val", 2), ("test", 3), ("unassigned", 0))},
        positives=int(y.sum()), trusted=int(trust.sum()),
        support_nodes=int(support.sum()), evaluated_nodes=int(eval_mask.sum()),
        denominator_note="role masks from trans_graph.pt; per-host strata use view file_ids")
    (OUT / "baseline_manifest.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n", json.dumps(info, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
