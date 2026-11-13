"""Build the 11-relation offline sample contract and dry-run (no training)."""
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
    T14.mkdir(parents=True, exist_ok=True)
    pairs = json.loads((T11 / "validated_pairs_cumulative.json").read_text(
        encoding="utf-8"))
    z = np.load(T11 / "paired_features_cumulative.npz", allow_pickle=True)
    src, par = z["source"].astype(float), z["partner"].astype(float)
    rels = [str(x) for x in z["relation_id"]]
    assert [x["relation_id"] for x in pairs] == rels
    g = torch.load(PT / "trans_graph.pt", map_location="cpu",
                   weights_only=False, mmap=True)
    N = int(g.y.size(0))

    p10 = json.loads((T10 / "plan.json").read_text(encoding="utf-8"))["selected"]
    a10 = pd.read_csv(T10 / "proven_boundary_attachments.csv", encoding="utf-8-sig")
    a10["relation_id"] = a10.pair_index.map({i: x["relation_id"] for i, x in enumerate(p10)})
    a11 = pd.read_csv(T11 / "boundary_attachments.csv", encoding="utf-8-sig")
    out = pd.read_csv(T11 / "all_outcomes.csv", encoding="utf-8-sig")
    key = out[out.status == "paired_validated"][["batch_id", "pair_index", "relation_id", "role"]]
    a11 = a11.merge(key, on=["batch_id", "pair_index"], how="left")
    att = pd.concat([a10, a11], ignore_index=True, sort=False)
    att["node_index"] = pd.to_numeric(att.node_index, errors="coerce")
    att["valid_index"] = att.node_index.notna() & (att.node_index >= 0) & (att.node_index < N)
    sig = pd.read_csv(T11 / "validated_signal_pairs.csv", encoding="utf-8-sig")

    records, rows = [], []
    for i, p in enumerate(pairs):
        sub = att[att.relation_id == p["relation_id"]]
        coords = []
        for slot in range(5):
            s = sub[(sub.side == "source") & (sub.slot == slot)]
            q = sub[(sub.side == "partner") & (sub.slot == slot)]
            def one(x, name):
                if not len(x):
                    return dict(net=None, bit=None, node_index=None, valid=False,
                                pi_anchor=False)
                y = x.iloc[0]
                idx = int(y.node_index) if pd.notna(y.node_index) else None
                return dict(net=str(y.net), bit=int(y.bit), node_index=idx,
                            valid=bool(idx is not None and 0 <= idx < N),
                            pi_anchor=bool(idx is not None and idx < 0))
            coords.append(dict(slot=slot, source=one(s, "source"),
                               partner=one(q, "partner")))
        valid_nodes = sorted(set(int(x.node_index) for x in sub.itertuples()
                                 if bool(x.valid_index)))
        pi = [dict(side=x.side, slot=int(x.slot), net=str(x.net),
                   bit=int(x.bit), node_index=-1,
                   anchor=str(getattr(x, "primary_input_anchor", "") or
                              getattr(x, "PI_anchor", "")))
              for x in sub.itertuples() if pd.notna(x.node_index) and x.node_index < 0]
        role_ok = []
        for n in valid_nodes:
            if bool(g.train_mask[n]):
                role_ok.append("train")
            elif bool(g.val_mask[n]):
                role_ok.append("val")
            elif bool(g.test_mask[n]):
                role_ok.append("test")
            else:
                role_ok.append("other")
        refs = [str(T11 / "validated_pairs_cumulative.json"),
                str(T11 / "boundary_attachments.csv")]
        sp = sig[sig.relation_id == p["relation_id"]]
        if len(sp):
            refs += [f"{x.proof_folder}#q{x.query_id}" for x in sp.itertuples()]
        else:
            refs.append(f"{T10 / 'validated_pairs.json'}#pair_index={p.get('pair_index')}")
        record = dict(
            sample_id=p["relation_id"], sample_unit="functional_relation_boundary",
            relation_id=p["relation_id"], role=p["role"],
            split_use=("train" if p["role"] == "train" else "val_audit_only"),
            source_view=p["source_view"], partner_view=p["partner_view"],
            source_sha=p["source_sha"], partner_sha=p["partner_sha"],
            context_id=p["context_id"],
            cut_coordinates=coords,
            target=dict(slot=4, source=coords[4]["source"], partner=coords[4]["partner"]),
            valid_graph_landing=valid_nodes,
            valid_graph_landing_roles=dict(zip(valid_nodes, role_ok)),
            pi_anchors=pi,
            feature_18d=dict(source=[float(v) for v in src[i]],
                             partner=[float(v) for v in par[i]]),
            evidence_refs=refs,
            claim_A_sat_description=dict(
                scope="boundary slots of this relation",
                attached_to="valid graph nodes only; not whole-unit embedding",
                includes_safety_label=False),
            claim_B_boundary_equivalence=dict(
                scope="corresponding cut/target boundary under shared PI/physical-Q context",
                includes_safety_label=False,
                whole_circuit_equivalence_not_inferred=True),
            training_pair_allowed=False, training_loader_compatible=False,
            safety_role_status="not_transferred_or_certified")
        records.append(record)
        rows.append(dict(sample_id=p["relation_id"], role=p["role"],
                         source_view=p["source_view"], partner_view=p["partner_view"],
                         cut_slots=5, valid_nodes=len(valid_nodes),
                         pi_anchors=len(pi), features=len(src[i])))
    (T14 / "pair_sample_manifest.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.DataFrame(rows).to_csv(T14 / "pair_sample_index.csv", index=False,
                              encoding="utf-8-sig")

    checks = []
    def check(name, ok, detail=""):
        checks.append(dict(check=name, ok=int(bool(ok)), detail=str(detail)))
    check("records_11", len(records) == 11, len(records))
    check("unique_sample_ids", len({r["sample_id"] for r in records}) == len(records))
    check("feature_shape_11x18",
          src.shape == (11, 18) and par.shape == (11, 18), f"{src.shape}/{par.shape}")
    check("feature_finite", np.isfinite(src).all() and np.isfinite(par).all())
    check("feature_bounded_0_1", (src.min() >= 0 and src.max() <= 1
                                  and par.min() >= 0 and par.max() <= 1),
          f"{src.min()}/{src.max()}/{par.min()}/{par.max()}")
    check("five_cut_coords", all(len(r["cut_coordinates"]) == 5 for r in records))
    check("target_slot4", all(r["target"]["slot"] == 4 for r in records))
    check("index_range",
          all(0 <= n < N for r in records for n in r["valid_graph_landing"]))
    check("pi_anchor_separate",
          all(all(x["node_index"] is None or x["node_index"] < 0 for x in r["pi_anchors"])
              for r in records))
    check("training_flags_false",
          all(not r["training_pair_allowed"] and not r["training_loader_compatible"]
              for r in records))
    dup_groups = {}
    for r in records:
        for c in r["cut_coordinates"]:
            for side in ("source", "partner"):
                x = c[side]
                if x["node_index"] is not None and x["node_index"] >= 0:
                    dup_groups.setdefault((r["sample_id"], side, x["node_index"]),
                                          []).append((c["slot"], x["net"]))
    dup = [k + (v,) for k, v in dup_groups.items() if len(v) > 1]
    check("duplicate_attachment_rows", 1,
          f"{len(dup)} alias groups; same node in multiple cut slots, not dropped")
    train_nodes = {n for r in records if r["role"] == "train"
                   for n in r["valid_graph_landing"]}
    val_nodes = {n for r in records if r["role"] == "val"
                 for n in r["valid_graph_landing"]}
    check("split_relation_disjoint",
          len({r["sample_id"] for r in records if r["role"] == "train"}
              & {r["sample_id"] for r in records if r["role"] == "val"}) == 0)
    check("train_val_node_overlap", len(train_nodes & val_nodes) == 0,
          f"overlap={len(train_nodes & val_nodes)}")
    check("no_test_nodes",
          not any(x == "test" for r in records
                  for x in r["valid_graph_landing_roles"].values()))
    check("feature_order_matches_cumulative", rels == [r["sample_id"] for r in records])
    pd.DataFrame(checks).to_csv(T14 / "dry_run_checks.csv", index=False,
                                encoding="utf-8-sig")
    report = dict(records=len(records), pair_rows=len(rows),
                  checks=len(checks), passed=int(sum(c["ok"] for c in checks)),
                  failed=int(sum(1 - c["ok"] for c in checks)),
                  feature_shape=list(src.shape),
                  train_records=sum(r["role"] == "train" for r in records),
                  val_records=sum(r["role"] == "val" for r in records),
                  unique_train_nodes=len(train_nodes),
                  unique_val_nodes=len(val_nodes),
                  train_val_overlap=len(train_nodes & val_nodes),
                  duplicate_attachment_groups=len(dup),
                  training_initialized=False, training_run=False,
                  note=("dry-run only; features are read-only, training_pair_allowed "
                        "is not modified"))
    (T14 / "dry_run_report.json").write_text(json.dumps(report, ensure_ascii=False,
                                                       indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    print(pd.DataFrame(checks).to_string(index=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())