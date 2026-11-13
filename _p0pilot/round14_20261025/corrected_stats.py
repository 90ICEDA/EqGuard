"""Round-14 corrected attachment statistics and L1 distances (offline)."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_p0pilot/round12_20261025"))
from audit_blockers import NetIndex, load_raw  # noqa: E402

ROOT = Path(_eqguard_path(''))
T10 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round10"
T11 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round11"
T14 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round14"
PT = ROOT / "generate_trans/folds/hosts_bt31/data/processed"
WORK = ROOT / "generate_trans/folds/hosts_bt31"


def main() -> int:
    T14.mkdir(parents=True, exist_ok=True)
    p10 = json.loads((T10 / "plan.json").read_text(encoding="utf-8"))["selected"]
    a10 = pd.read_csv(T10 / "proven_boundary_attachments.csv", encoding="utf-8-sig")
    a10["relation_id"] = a10.pair_index.map({i: x["relation_id"] for i, x in enumerate(p10)})
    a10["role"] = a10.relation_id.map({x["relation_id"]: x["role"] for x in p10})
    a11 = pd.read_csv(T11 / "boundary_attachments.csv", encoding="utf-8-sig")
    out = pd.read_csv(T11 / "all_outcomes.csv", encoding="utf-8-sig")
    key = out[out.status == "paired_validated"][["batch_id", "pair_index",
                                                 "relation_id", "role"]]
    a11 = a11.merge(key, on=["batch_id", "pair_index"], how="left")
    rec = pd.concat([a10, a11], ignore_index=True, sort=False)
    rec["node_index"] = pd.to_numeric(rec.node_index, errors="coerce")
    pa = rec["primary_input_anchor"] if "primary_input_anchor" in rec.columns else pd.Series(
        [None] * len(rec))
    pb = rec["PI_anchor"] if "PI_anchor" in rec.columns else pd.Series(
        [None] * len(rec))
    rec["pi_anchor"] = rec.node_index.eq(-1) | pa.notna() | pb.notna()

    g = torch.load(PT / "trans_graph.pt", map_location="cpu",
                   weights_only=False, mmap=True)
    N = int(g.y.size(0))
    meta = json.loads((WORK / "data/for_train/metadata_trans.json").read_text(
        encoding="utf-8"))
    fids = np.asarray(meta["file_ids"], dtype=object)
    vid, views = pd.factorize(fids, sort=False)
    view_of_node = {i: str(views[int(vid[i])]) for i in range(len(vid))}
    names = (PT / "node_names_trans.txt").read_text(
        encoding="utf-8", errors="replace").splitlines()
    rec["valid_index"] = rec.node_index.notna() & (rec.node_index >= 0) & (rec.node_index < N)
    rec["unmapped"] = rec.node_index.isna() | ((~rec.valid_index) & (~rec.pi_anchor))

    checks = []
    raw_cache = {}
    for r in rec.itertuples():
        idx = int(r.node_index) if pd.notna(r.node_index) else None
        ok_view = bool(idx is not None and 0 <= idx < N
                       and view_of_node.get(idx) == str(r.view))
        nm = names[idx].strip().lstrip("\\") if ok_view else ""
        drv_ok = 0
        drv_actual = ""
        if ok_view:
            if r.view not in raw_cache:
                m, _, _ = load_raw(str(r.view))
                raw_cache[r.view] = NetIndex(m)
            drv_actual = raw_cache[r.view].driver(str(r.net))
            if pd.isna(r.driver):
                drv_ok = int(not drv_actual)
            else:
                drv_ok = int(drv_actual.split("|")[0] == str(r.driver).lstrip("\\"))
        checks.append(dict(relation_id=r.relation_id, side=r.side, slot=r.slot,
                           net=r.net, bit=r.bit, node_index=idx,
                           valid_index=int(ok_view), view=str(r.view),
                           node_name=nm, meta_view_ok=int(ok_view),
                           driver_expected=r.driver, driver_actual=drv_actual,
                           driver_ok=drv_ok, pi_anchor=int(bool(r.pi_anchor)),
                           unmapped=int(bool(r.unmapped))))
    chk = pd.DataFrame(checks)
    chk.to_csv(T14 / "attachment_validation.csv", index=False, encoding="utf-8-sig")

    slot_records = len(rec)
    relation_attachment_rows = len(rec.drop_duplicates(
        ["relation_id", "side", "slot", "net", "bit"]))
    unique_valid = set(int(x) for x in rec.loc[rec.valid_index, "node_index"])
    pi_rows = rec[rec.pi_anchor]
    pi_unique = pi_rows.drop_duplicates(["relation_id", "side", "net", "bit"])
    idx = torch.tensor(sorted(unique_valid), dtype=torch.long)
    role_counts = {
        "train": int(g.train_mask[idx].sum()),
        "val": int(g.val_mask[idx].sum()),
        "test": int(g.test_mask[idx].sum()),
        "other": int((~g.train_mask[idx] & ~g.val_mask[idx] & ~g.test_mask[idx]).sum())}
    prior_files = [
        "sat_valid_round3/r3_recovery_nodes.csv",
        "sat_valid_round3/r3_graded_nodes.csv",
        "sat_nonlocal_round5/r5_nodes.csv",
        "sat_expand_round6/r6_nodes.csv",
        "sat_repair_round7/r7_nodes.csv"]
    prior = set()
    for f in prior_files:
        p = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables" / f
        if p.exists():
            prior |= set(int(x) for x in pd.read_csv(p, encoding="utf-8-sig").node_index)
    overlap = sorted(unique_valid & prior)
    legacy_path = (ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/"
                   "satrel_node_sat_covered.legacy.csv")
    legacy = set()
    if legacy_path.exists():
        legacy = set(int(x) for x in pd.read_csv(
            legacy_path, encoding="utf-8-sig", usecols=["node"]).node)
    legacy_overlap = sorted(unique_valid & legacy)

    z = np.load(T11 / "paired_features_cumulative.npz", allow_pickle=True)
    src = z["source"].astype(float)
    rels = [str(x) for x in z["relation_id"]]
    dist = np.abs(src[:, None, :] - src[None, :, :]).sum(axis=2)
    np.fill_diagonal(dist, np.inf)
    nearest = np.min(dist, axis=1)
    nearest_idx = np.argmin(dist, axis=1)
    l1 = pd.DataFrame(dict(relation_id=rels, nearest_l1=nearest,
                           nearest_relation=[rels[i] for i in nearest_idx]))
    l1.to_csv(T14 / "pair_l1_distances.csv", index=False, encoding="utf-8-sig")

    summary = dict(
        boundary_slot_records=slot_records,
        relation_side_slot_attachment_rows=relation_attachment_rows,
        relation_side_dedup_rows=int(len(rec[rec.valid_index].drop_duplicates(
            ["relation_id", "side", "node_index"]))),
        relation_rows=len(set(rec.relation_id)),
        valid_attachment_records=int(rec.valid_index.sum()),
        valid_unique_node_indices=len(unique_valid),
        valid_unique_by_role=role_counts,
        pi_anchor_records=len(pi_rows),
        pi_anchor_unique=len(pi_unique),
        unmapped_records=int(rec.unmapped.sum()),
        negative_index_records=int((rec.node_index < 0).sum()),
        duplicate_relation_side_node_rows=int(
            len(rec[rec.valid_index]) - len(rec[rec.valid_index].drop_duplicates(
                ["relation_id", "side", "node_index"]))),
        metadata_view_mismatch=int((~chk[chk.valid_index == 1].meta_view_ok
                                    .astype(bool)).sum()),
        driver_mismatch=int((chk[chk.valid_index == 1].driver_ok == 0).sum()),
        feature_relation_order_ok=int(
            [x["relation_id"] for x in json.loads(
                (T11 / "validated_pairs_cumulative.json").read_text(
                    encoding="utf-8"))] == rels),
        prior_evidence_union_nodes=len(prior),
        overlap_prior_evidence=len(overlap),
        overlap_prior_evidence_relations=sorted(set(
            rec[rec.node_index.isin(overlap)].relation_id)),
        legacy_partial_nodes=len(legacy),
        overlap_legacy_partial=len(legacy_overlap),
        nearest_l1_min=float(np.min(nearest)),
        nearest_l1_median=float(np.median(nearest)),
        nearest_l1_max=float(np.max(nearest)),
        nearest_l1_scope="per-row nearest source description (self excluded)",
        all_pairwise_median=float(np.median(dist[np.isfinite(dist)])),
        baseline_note=("17 is against the explicitly listed r3/r5/r6/r7 union only; "
                       "not a net-new claim against all old SAT support"))
    (T14 / "corrected_training_stats.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.DataFrame([summary]).to_csv(T14 / "corrected_training_stats.csv", index=False,
                                   encoding="utf-8-sig")
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())