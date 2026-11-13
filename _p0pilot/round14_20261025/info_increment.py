"""Offline information-increment audit of 11 pairs vs the 40-relation metadata."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch

ROOT = Path(_eqguard_path(''))
T10 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round10"
T11 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round11"
T14 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round14"
PT = ROOT / "generate_trans/folds/hosts_bt31/data/processed"


def main() -> int:
    inv = pd.DataFrame(json.loads((T10 / "plan.json").read_text(
        encoding="utf-8"))["inventory"])
    rels = []
    for f in ("sat_nonlocal_round5/r5_nonlocal_relations.csv",
              "sat_expand_round6/r6_nonlocal_relations.csv",
              "sat_repair_round7/r7_nonlocal_relations.csv"):
        d = pd.read_csv(ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables" / f,
                        encoding="utf-8-sig")
        rels.append(d[["relation_id", "driver_type", "cut_nets", "kind", "target"]])
    meta = pd.concat(rels, ignore_index=True).drop_duplicates("relation_id")
    inv = inv.merge(meta, on="relation_id", how="left")
    inv["cut_size"] = inv.source_nets.apply(lambda x: len(x) - 1)
    inv.to_csv(T14 / "relation_metadata_40.csv", index=False, encoding="utf-8-sig")

    pairs = json.loads((T11 / "validated_pairs_cumulative.json").read_text(
        encoding="utf-8"))
    pids = {x["relation_id"] for x in pairs}
    sel = inv[inv.relation_id.isin(pids)]
    z = np.load(T11 / "paired_features_cumulative.npz", allow_pickle=True)
    src = z["source"].astype(float)
    # Corrected boundary roles from actual attachment driver types.
    chk = pd.read_csv(T14 / "attachment_validation.csv", encoding="utf-8-sig")
    v = chk[chk.valid_index == 1].copy()
    v["role_kind"] = np.where(v.driver_actual.astype(str).str.contains("DFF|LATCH"),
                              "DFF_state",
                              np.where(v.driver_actual.astype(str) == "", "logic_or_PI",
                                       "logic"))
    role_counts = v.role_kind.value_counts().to_dict()
    pi_count = int((chk.node_index == -1).sum())

    # Structural context of landing nodes, descriptive only.
    g = torch.load(PT / "trans_graph.pt", map_location="cpu",
                   weights_only=False, mmap=True)
    x = g.x.numpy()
    nodes = sorted(set(int(x) for x in v.node_index))
    sx = x[nodes]
    structural_unique = len(np.unique(np.round(sx, 4), axis=0))

    # Feature diversity and distances.
    rounded = np.round(src, 4)
    uniq, counts = np.unique(rounded, axis=0, return_counts=True)
    dist = np.abs(src[:, None, :] - src[None, :, :]).sum(axis=2)
    np.fill_diagonal(dist, np.inf)
    nearest = np.min(dist, axis=1)
    coord_range = np.stack([src.min(axis=0), src.max(axis=0)], axis=1)
    pd.DataFrame(dict(index=range(18), min=coord_range[:, 0],
                      max=coord_range[:, 1])).to_csv(
        T14 / "pair_feature_ranges.csv", index=False, encoding="utf-8-sig")

    summary = dict(
        pairs=len(pairs), train=sum(x["role"] == "train" for x in pairs),
        val=sum(x["role"] == "val" for x in pairs),
        gate_types_11=sel.driver_type.value_counts().to_dict(),
        gate_types_40=inv.driver_type.value_counts().to_dict(),
        cut_sizes_11=sel.cut_size.value_counts().to_dict(),
        cut_sizes_40=inv.cut_size.value_counts().to_dict(),
        boundary_roles_11=role_counts, pi_anchor_records=pi_count,
        unique_18d_descriptions=int(len(uniq)),
        duplicate_description_rows=int(len(src) - len(uniq)),
        max_duplicate_group=int(counts.max()),
        nearest_l1_min=float(nearest.min()),
        nearest_l1_median=float(np.median(nearest)),
        nearest_l1_max=float(nearest.max()),
        structural_dim=int(x.shape[1]),
        landing_nodes=len(nodes),
        unique_structural_vectors_at_landing=int(structural_unique),
        structural_duplicate_nodes=int(len(nodes) - structural_unique),
        nonlocal_function_evidence=("18-d boundary summary over cut+target; not a complete "
                                    "gate/function one-hot and not a whole-unit embedding"),
        description_diversity=("9 unique source descriptions among 11; duplicates exist, "
                               "so pair count is not description diversity"),
        structural_difference=("landing nodes have 39-d structural features; functional "
                               "18-d descriptions are not a subset of them"),
        predictive_gain="not_identified: no classifier, no labels, no test-set use",
        direct_positive_labels="not_transferred_or_evaluated",
        conclusion=("evidence is sufficient for a read-only sample contract and dry-run, "
                    "not for a supervised training comparison"))
    (T14 / "info_increment.json").write_text(json.dumps(summary, ensure_ascii=False,
                                                       indent=2), encoding="utf-8")
    pd.DataFrame([summary]).to_csv(T14 / "info_increment.csv", index=False,
                                   encoding="utf-8-sig")
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())