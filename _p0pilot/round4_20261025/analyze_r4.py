"""Round-4 evidence-level coverage, information content and feature permutation."""
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
WORK = ROOT / "generate_trans/folds/hosts_bt31"
PT = WORK / "data/processed"
R4 = ROOT / "_p0pilot/round4_20261025"
TAB4 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_chain_round4"
FEAT = R4 / "features"


def hops(support, edges, h):
    r = support.copy()
    for _ in range(h):
        nxt = r.copy()
        nxt[edges[1, r[edges[0]]]] = True
        r = nxt
    return r


def main() -> int:
    split = json.loads((WORK / "views.json").read_text(encoding="utf-8"))
    role_of_view = {v: r for r in ("train", "val") for v in split[f"{r}_views"]}
    meta = json.loads((WORK / "data/for_train/metadata_trans.json").read_text(encoding="utf-8"))
    fids = np.asarray(meta["file_ids"], dtype=object)
    vid, views = pd.factorize(fids, sort=False)
    vid = vid.astype(np.int32)
    del fids
    role = np.asarray([role_of_view.get(str(v), "other") for v in views])[vid]
    g = torch.load(PT / "trans_graph.pt", map_location="cpu", weights_only=False, mmap=True)
    y = g.y.numpy().reshape(-1) > 0
    trust = np.load(PT / "trust_trans.npy")
    edges = g.edge_index.numpy()
    old = np.load(PT / "satrel_node_feats_sparseR1_real.npy", mmap_mode="r")
    old_support = np.asarray(old[:, 6]) > 0

    real = np.load(FEAT / "r4_features_real.npy", mmap_mode="r")
    perm = np.load(FEAT / "r4_features_permuted.npy", mmap_mode="r")
    cols = json.loads((FEAT / "r4_feature_columns.json").read_text(encoding="utf-8"))["columns"]
    rel = pd.read_csv(TAB4 / "r4_unified_relations.csv", encoding="utf-8-sig")
    tv = np.isin(role, ["train", "val"])

    queried = (np.asarray(real[:, 3:14]) != 0).any(axis=1)
    levels = {
        "queried": queried,
        "cond_fact": np.asarray(real[:, 3]) > 0,
        "suff_proved": np.asarray(real[:, 4]) > 0,
        "influence_valid": np.asarray(real[:, 5]) > 0,
    }
    rows = []
    for name, sup in levels.items():
        for r in ("train", "val"):
            m = tv & (role == r)
            s = sup & m
            rows.append(dict(level=name, role=r, nodes=int(s.sum()),
                             positives=int((s & y).sum()),
                             trusted_pos=int((s & y & trust).sum()),
                             trusted_neg=int((s & ~y & trust).sum()),
                             old_overlap=int((s & old_support & m).sum()),
                             net_new=int((s & ~old_support & m).sum()),
                             union_with_old=int(((s | old_support) & m).sum())))
    cov = pd.DataFrame(rows)
    cov.to_csv(TAB4 / "r4_coverage_levels.csv", index=False, encoding="utf-8-sig")
    print(cov.to_string(index=False), flush=True)

    strat = []
    nodes_df = pd.concat([
        pd.read_csv(ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/"
                    "sat_valid_round3/r3_recovery_nodes.csv", encoding="utf-8-sig"),
        pd.read_csv(ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/"
                    "sat_valid_round3/r3_graded_nodes.csv", encoding="utf-8-sig")],
        ignore_index=True).drop_duplicates(["relation_id", "node_index"])
    rid_nodes = nodes_df.groupby("relation_id").node_index.apply(
        lambda s: sorted(set(int(x) for x in s))).to_dict()
    for (host, recipe, kind, source), g2 in rel.groupby(
            ["host", "recipe", "kind", "source"]):
        ids = sorted({i for rid in g2.relation_id for i in rid_nodes.get(rid, [])})
        mm = np.zeros(len(vid), bool)
        mm[ids] = True
        strat.append(dict(host=host, recipe=recipe, kind=kind, source=source,
                          relations=len(g2),
                          proved=int((g2.functional_sufficiency == "proved").sum()),
                          influence_valid=int((g2.influence_status == "valid").sum()),
                          nodes=len(ids), positives=int((mm & y).sum()),
                          trusted_pos=int((mm & y & trust).sum()),
                          trusted_neg=int((mm & ~y & trust).sum())))
    pd.DataFrame(strat).to_csv(TAB4 / "r4_strata.csv", index=False, encoding="utf-8-sig")

    # ---- feature permutation diff ----
    diff_rows = []
    for j, c in enumerate(cols):
        diff_rows.append(dict(column=c,
                              changed=int((real[:, j] != perm[:, j]).sum()),
                              changed_train_val=int(((real[:, j] != perm[:, j]) & tv).sum())))
    pd.DataFrame(diff_rows).to_csv(TAB4 / "r4_feature_diff_columns.csv", index=False,
                                   encoding="utf-8-sig")
    struct_same = all(np.array_equal(np.asarray(real[:, j]), np.asarray(perm[:, j]))
                      for j in range(3))
    sat_changed = ((real[:, 3:14] != perm[:, 3:14]).any(axis=1)) & tv
    cs = sat_changed.copy()
    diff = dict(structure_identical=bool(struct_same),
                sat_changed_nodes=int(sat_changed.sum()),
                sat_changed_1hop=int(hops(cs, edges, 1).sum()),
                sat_changed_2hop=int(hops(cs, edges, 2).sum()),
                cond_changed=int(((real[:, 3] != perm[:, 3]) & tv).sum()),
                suff_changed=int(((real[:, 4] != perm[:, 4]) & tv).sum()),
                infl_changed=int(((real[:, 5] != perm[:, 5]) & tv).sum()),
                det_changed=int(((real[:, 6] != perm[:, 6]) & tv).sum()),
                sig_changed=int(((real[:, 9] != perm[:, 9]) & tv).sum()))
    (TAB4 / "r4_feature_diff.json").write_text(
        json.dumps(diff, ensure_ascii=False, indent=2), encoding="utf-8")
    print(diff, flush=True)

    # ---- information content ----
    ev = queried & tv
    info = []
    for j, c in enumerate(cols[3:], start=3):
        vals = np.asarray(real[:, j])[ev]
        u = np.unique(vals)
        info.append(dict(column=c, n=int(len(vals)), unique=int(len(u)),
                         values=";".join(f"{x:g}" for x in u[:12])))
    idf = pd.DataFrame(info)
    idf.to_csv(TAB4 / "r4_info_columns.csv", index=False, encoding="utf-8-sig")
    print(idf.to_string(index=False), flush=True)

    mat = np.asarray(real[:, 3:12])[ev]
    dup = []
    for a in range(mat.shape[1]):
        for b in range(a + 1, mat.shape[1]):
            dup.append(dict(a=cols[3 + a], b=cols[3 + b],
                            identical=bool(np.array_equal(mat[:, a], mat[:, b]))))
    pd.DataFrame(dup).to_csv(TAB4 / "r4_info_duplicates.csv", index=False,
                             encoding="utf-8-sig")
    combos = pd.Series([tuple(r) for r in mat.astype(np.int64)]).value_counts()
    combos.rename("count").to_csv(TAB4 / "r4_info_combinations.csv", encoding="utf-8-sig")
    print("\njoint combinations top:\n", combos.head(8).to_string(), flush=True)

    def forcing(tt):
        return ";".join(x.split(":")[2] for x in str(tt).split(";"))

    def function_sig(tt):
        parts = []
        for x in str(tt).split(";"):
            p, feas, force = x.split(":")
            if feas == "feasible" and force not in ("not_applicable", "undecided", "unknown"):
                parts.append(f"{p}:{force}")
        return ";".join(parts)

    def feasibility_sig(tt):
        return ";".join(f"{x.split(':')[0]}:{x.split(':')[1]}" for x in str(tt).split(";"))

    rel["forcing_sig"] = rel.truth_table.map(forcing)
    rel["function_sig"] = rel.truth_table.map(function_sig)
    rel["feasibility_sig"] = rel.truth_table.map(feasibility_sig)
    rel[["relation_id", "design", "target", "driver_type", "cut_size",
         "truth_table", "function_sig", "feasibility_sig"]].to_csv(
        TAB4 / "r4_truth_functions.csv", index=False, encoding="utf-8-sig")
    grp = rel.groupby(["driver_type", "cut_size"]).agg(
        relations=("relation_id", "size"),
        distinct_function=("function_sig", "nunique"),
        distinct_feasibility=("feasibility_sig", "nunique"),
        distinct_truth=("truth_table", "nunique")).reset_index()
    grp.to_csv(TAB4 / "r4_truth_vs_gate.csv", index=False, encoding="utf-8-sig")
    print("\ntruth vs gate:\n", grp.to_string(index=False), flush=True)
    manifest = dict(
        evidence_levels={k: int((v & tv).sum()) for k, v in levels.items()},
        old_train_val_nodes=int((old_support & tv).sum()),
        net_new_train_val=int((levels["queried"] & ~old_support & tv).sum()),
        overlap_train_val=int((levels["queried"] & old_support & tv).sum()),
        feature_diff=diff, joint_combinations=int(len(combos)),
        top_combination_share=float(combos.iloc[0] / combos.sum()),
        gate_groups=int(len(grp)),
        gate_groups_function_determined=int((grp.distinct_function == 1).sum()),
        gate_groups_feasibility_varies=int((grp.distinct_feasibility > 1).sum()),
        po_relations=int(rel.po_sat.sum()), test_used=False)
    (TAB4 / "r4_eval_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
