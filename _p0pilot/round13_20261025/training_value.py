"""Offline training-value audit of the 11 validated pairs (no SAT)."""
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
T13 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round13"
PT = ROOT / "generate_trans/folds/hosts_bt31/data/processed"


def main() -> int:
    vp = json.loads((T11 / "validated_pairs_cumulative.json").read_text(
        encoding="utf-8"))
    feat = np.load(T11 / "paired_features_cumulative.npz", allow_pickle=True)
    src = feat["source"].astype(np.float64)
    par = feat["partner"].astype(np.float64)
    relations = [str(x) for x in feat["relation_id"]]

    # Graph attachments: six round-10 pairs + five round-11 pairs.
    a10 = pd.read_csv(T10 / "proven_boundary_attachments.csv", encoding="utf-8-sig")
    a10 = a10[a10.node_index.notna()].copy()
    p10 = json.loads((T10 / "plan.json").read_text(encoding="utf-8"))["selected"]
    a10["relation_id"] = a10.pair_index.map(
        {i: x["relation_id"] for i, x in enumerate(p10)})
    a10["role"] = a10.relation_id.map({x["relation_id"]: x["role"] for x in p10})
    a11 = pd.read_csv(T11 / "boundary_attachments.csv", encoding="utf-8-sig")
    a11 = a11[a11.node_index.notna()].copy()
    out = pd.read_csv(T11 / "all_outcomes.csv", encoding="utf-8-sig")
    key = out[out.status == "paired_validated"][["batch_id", "pair_index", "relation_id", "role"]]
    a11 = a11.merge(key, on=["batch_id", "pair_index"], how="left")
    nodes = pd.concat([
        a10[["relation_id", "side", "view", "net", "node_index"]].assign(role="unknown"),
        a11[["relation_id", "side", "view", "net", "node_index", "role"]]],
        ignore_index=True)
    nodes = nodes.dropna(subset=["node_index"]).drop_duplicates(
        ["relation_id", "side", "node_index"])
    g = torch.load(PT / "trans_graph.pt", map_location="cpu",
                   weights_only=False, mmap=True)
    idx = torch.tensor(nodes.node_index.astype(int).values, dtype=torch.long)
    nodes["role_graph"] = np.where(g.train_mask[idx].numpy(), "train",
                                   np.where(g.val_mask[idx].numpy(), "val", "other"))
    # Prior SAT evidence nodes (r3/r5/r6/r7) for overlap, not for labels.
    prior = set()
    for p in [ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_valid_round3/r3_recovery_nodes.csv",
              ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_valid_round3/r3_graded_nodes.csv",
              ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_nonlocal_round5/r5_nodes.csv",
              ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_expand_round6/r6_nodes.csv",
              ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_repair_round7/r7_nodes.csv"]:
        if p.exists():
            prior |= set(int(x) for x in pd.read_csv(p, encoding="utf-8-sig").node_index)
    uniq_nodes = sorted(set(int(x) for x in nodes.node_index))
    overlap = sorted(set(uniq_nodes) & prior)

    # Functional-description duplicates and distances.
    rounded = np.round(src, 4)
    uniq_desc, counts = np.unique(rounded, axis=0, return_counts=True)
    dist = np.abs(src[:, None, :] - src[None, :, :]).sum(axis=2)
    np.fill_diagonal(dist, np.inf)
    diff = np.abs(src - par)
    rows = []
    for i, rel in enumerate(relations):
        rows.append(dict(relation_id=rel,
                         source_view=vp[i]["source_view"],
                         partner_view=vp[i]["partner_view"],
                         role=vp[i]["role"],
                         feature_max_abs_diff=float(diff[i].max()),
                         nearest_source_l1=float(dist[i].min()),
                         node_rows=int((nodes.relation_id == rel).sum())))
    pd.DataFrame(rows).to_csv(T13 / "training_value_pairs.csv", index=False,
                              encoding="utf-8-sig")
    summary = dict(
        pairs=len(vp), train=int(sum(x["role"] == "train" for x in vp)),
        val=int(sum(x["role"] == "val" for x in vp)),
        hosts=sorted({x["source_view"].split("__")[0] for x in vp}
                     | {x["partner_view"].split("__")[0] for x in vp}),
        unique_source_views=len({x["source_view"] for x in vp}),
        unique_partner_views=len({x["partner_view"] for x in vp}),
        unique_node_indices=len(uniq_nodes),
        node_role_counts=pd.Series(nodes.role_graph).value_counts().to_dict(),
        overlap_prior_evidence=len(overlap),
        unique_18d_source_descriptions=int(len(uniq_desc)),
        duplicate_description_rows=int(len(src) - len(uniq_desc)),
        max_duplicate_group=int(counts.max()),
        source_feature_max_abs_diff=float(diff.max()),
        nearest_source_l1_min=float(np.nanmin(np.where(np.isfinite(dist), dist, np.nan))),
        nearest_source_l1_median=float(np.nanmedian(dist)),
        training_pair_allowed=sum(bool(x.get("training_pair_allowed")) for x in vp),
        training_loader_compatible=sum(bool(x.get("training_loader_compatible")) for x in vp),
        direct_positive_labels="not_transferred_or_evaluated",
        missing_interface=[
            "no pair-to-graph loader; 18-d pair features are separate from 39-d node features",
            "no pair labels/roles transferred; all training_pair_allowed=false",
            "29/40 relations remain blocked; val only 2 pairs",
            "no temporal/reachability context; local boundary only",
            "feature equality is a validation check, not predictive information"],
    )
    (T13 / "training_value.json").write_text(json.dumps(summary, ensure_ascii=False,
                                                       indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())