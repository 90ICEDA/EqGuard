"""Corrected round-6 feature array: 25 columns, last column covered.

A function class is one-hot only when complete; partial/unknown/infeasible and
domain-restricted flags are separate. Influence carries its pair coverage.
"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import torch

ROOT = Path(_eqguard_path(''))
PT = ROOT / "generate_trans/folds/hosts_bt31/data/processed"
R6 = ROOT / "_p0pilot/round6_20261025"
TAB5 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_nonlocal_round5"
TAB6 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_expand_round6"
FEAT = R6 / "features"
sys.path.insert(0, str(R6))
from analyze_r6 import graph_sets, hops  # noqa: E402

COLS = ["queried", "forced_fraction", "feasible_fraction", "determinism",
        "infeasible_fraction", "undecided_fraction", "influence_mean",
        "influence_max", "influence_pair_coverage", "n_inputs_norm",
        "n_valid_inputs_norm", "complete_constant0", "complete_constant1",
        "complete_identity", "complete_inverter", "complete_and",
        "complete_or", "complete_xor", "complete_other",
        "domain_restricted", "partial_forced", "unknown", "infeasible",
        "multi_relation_norm", "covered"]


def record(r) -> dict:
    rec = {c: 0.0 for c in COLS}
    rec["queried"] = 1.0
    rec["forced_fraction"] = float(r.n_forced) / (2 ** int(r.k))
    rec["feasible_fraction"] = float(r.n_feasible) / (2 ** int(r.k))
    rec["infeasible_fraction"] = float(r.n_infeasible) / (2 ** int(r.k))
    rec["undecided_fraction"] = float(r.n_undecided) / (2 ** int(r.k))
    rec["determinism"] = (float(r.n_forced) / float(r.n_feasible)
                          if r.n_feasible else 0.0)
    rec["influence_mean"] = float(r.influence_mean) if pd.notna(r.influence_mean) else 0.0
    rec["influence_max"] = float(r.influence_max) if pd.notna(r.influence_max) else 0.0
    rec["influence_pair_coverage"] = float(r.influence_pair_coverage)
    rec["n_inputs_norm"] = int(r.k) / 4.0
    rec["n_valid_inputs_norm"] = float(r.influence_valid_inputs) / 4.0
    status = str(r.function_status)
    cls = str(r.function_class)
    if status == "complete_function":
        key = {"constant0": "complete_constant0", "constant1": "complete_constant1",
               "identity": "complete_identity", "inverter": "complete_inverter",
               "and": "complete_and", "or": "complete_or", "xor": "complete_xor",
               "other": "complete_other"}.get(cls)
        if key:
            rec[key] = 1.0
    rec["domain_restricted"] = 1.0 if status == "domain_restricted_function" else 0.0
    rec["partial_forced"] = 1.0 if status == "partial_forced" else 0.0
    rec["unknown"] = 1.0 if status == "unknown" else 0.0
    rec["infeasible"] = 1.0 if status == "infeasible" else 0.0
    return rec


def main() -> int:
    FEAT.mkdir(parents=True, exist_ok=True)
    d = pd.read_csv(TAB6 / "r6_relations_all.csv", encoding="utf-8-sig")
    r5n = pd.read_csv(TAB5 / "r5_nodes.csv", encoding="utf-8-sig")
    r6n = pd.read_csv(TAB6 / "r6_nodes.csv", encoding="utf-8-sig")
    rid_nodes = {}
    for frame in (r5n, r6n):
        rid_nodes.update(frame.groupby("relation_id").node_index.apply(
            lambda s: sorted(set(int(x) for x in s))).to_dict())
    g = torch.load(PT / "trans_graph.pt", map_location="cpu",
                   weights_only=False, mmap=True)
    N = g.y.size(0)
    recs = {r.relation_id: record(r) for _, r in d.iterrows()}
    return _build(d, recs, rid_nodes, N)



def _aggregate(recs, rid_nodes, N, name):
    per = defaultdict(list)
    for rid, nodes in rid_nodes.items():
        if rid in recs:
            for ni in nodes:
                per[ni].append(recs[rid])
    arr = np.lib.format.open_memmap(FEAT / name, mode="w+",
                                    dtype=np.float32, shape=(N, len(COLS)))
    for ni, rs in per.items():
        for j, c in enumerate(COLS):
            if c == "multi_relation_norm":
                arr[ni, j] = min(1.0, len(rs) / 2.0)
            elif c == "covered":
                arr[ni, j] = 1.0
            else:
                arr[ni, j] = max(x[c] for x in rs)
        arr[ni, len(COLS) - 1] = 1.0
    arr.flush()
    return arr, per


def _build(d, recs, rid_nodes, N):
    real, per = _aggregate(recs, rid_nodes, N, "r6_extra_real.npy")
    rng = np.random.default_rng(20261025)
    perm_recs = dict(recs)
    no_perm = []
    for design, g2 in d.groupby("design", sort=False):
        if len(g2) < 2:
            no_perm.append(design)
            continue
        order = rng.permutation(len(g2))
        if len(g2) > 1 and np.array_equal(order, np.arange(len(g2))):
            order = np.roll(order, 1)
        for tgt, src in zip(g2.relation_id, g2.relation_id.iloc[order]):
            perm_recs[tgt] = recs[src]
    perm, _ = _aggregate(perm_recs, rid_nodes, N, "r6_extra_permuted.npy")
    support = np.array(sorted(per), dtype=np.int64)
    changed = support[np.any(np.asarray(real[support]) != np.asarray(perm[support]),
                             axis=1)]
    role_map = {}
    for frame in (pd.read_csv(TAB5 / "r5_nodes.csv", encoding="utf-8-sig"),
                  pd.read_csv(TAB6 / "r6_nodes.csv", encoding="utf-8-sig")):
        role_map.update({int(n): str(r) for n, r in zip(frame.node_index, frame.role)})
    y, trust, indptr, dst = graph_sets()
    groups = dict(determinism=[3, 11, 12, 13, 14, 15, 16, 17, 18],
                  feasibility=[1, 2, 4, 5, 19, 20, 21, 22],
                  influence=[6, 7, 8, 10],
                  structure=[0, 9, 23, 24])
    rows, diff_cols = [], []
    for j, c in enumerate(COLS):
        n = int(np.any(np.asarray(real[support, j]) != np.asarray(perm[support, j])))
        diff_cols.append(dict(column=c, index=j, changed=int(n)))
    for role in ("train", "val"):
        ids = changed[[role_map.get(int(i)) == role for i in changed]]
        one, two = hops(ids, indptr, dst)
        rows.append(dict(role=role, support=int(sum(role_map.get(int(i)) == role
                                                    for i in support)),
                         changed_nodes=len(ids),
                         changed_positives=int(y[ids].sum()) if len(ids) else 0,
                         h1_nodes=len(one), h1_positives=int(y[one].sum()) if len(one) else 0,
                         h2_nodes=len(two), h2_positives=int(y[two].sum()) if len(two) else 0,
                         **{f"{k}_changed": int(any(
                             np.any(np.asarray(real[ids, j]) != np.asarray(perm[ids, j]))
                             for j in idxs)) if len(ids) else 0
                            for k, idxs in groups.items()}))
    pd.DataFrame(rows).to_csv(TAB6 / "r6_feature_diff_columns.csv", index=False,
                              encoding="utf-8-sig")
    pd.DataFrame(diff_cols).to_csv(TAB6 / "r6_feature_diff_by_column.csv",
                                   index=False, encoding="utf-8-sig")
    info = dict(n=N, support=len(support), changed_nodes=len(changed),
                changed_by_role={r["role"]: r["changed_nodes"] for r in rows},
                no_perm_designs=sorted(set(no_perm)),
                group_changed={r["role"]: {k: r[f"{k}_changed"] for k in groups}
                               for r in rows})
    (TAB6 / "r6_feature_diff.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    (FEAT / "r6_feature_columns.json").write_text(json.dumps(dict(
        columns=COLS, n=N, last_column="covered", bounded=[0, 1],
        truth_encoding=("one-hot only for complete functions; domain_restricted/"
                        "partial_forced/unknown/infeasible are separate flags"),
        influence="mean/max plus comparable-pair coverage; no bare zero claim",
        aggregation="max per numeric column; one-hot OR; multi_relation=count/2",
        permutation=("within design, all k=4 relations (rounds 5+6); nodes, cuts, "
                     "query availability and structure held fixed"),
        no_valid_permutation_designs=sorted(set(no_perm))), ensure_ascii=False,
        indent=2), encoding="utf-8")
    print(json.dumps(info, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

