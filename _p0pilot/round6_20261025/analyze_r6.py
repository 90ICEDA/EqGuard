"""Round-6 unified classification, coverage baselines, propagation and info."""
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

ROOT = Path(_eqguard_path(''))
PT = ROOT / "generate_trans/folds/hosts_bt31/data/processed"
R3 = ROOT / "_p0pilot/round3_20261025"
R5 = ROOT / "_p0pilot/round5_20261025"
R6 = ROOT / "_p0pilot/round6_20261025"
TAB3 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_valid_round3"
TAB5 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_nonlocal_round5"
TAB6 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_expand_round6"
sys.path.insert(0, str(R6))
from r6_truth import classify, influence_from_tt  # noqa: E402


def unified() -> pd.DataFrame:
    rows = []
    r5 = pd.read_csv(TAB6 / "r6_r5_corrected_relations.csv", encoding="utf-8-sig")
    r5raw = pd.read_csv(TAB5 / "r5_nonlocal_relations.csv", encoding="utf-8-sig")
    r5suf = dict(zip(r5raw.relation_id, r5raw.functional_sufficiency))
    r5max = dict(zip(r5raw.relation_id, r5raw.influence_max))
    for _, r in r5.iterrows():
        rows.append(dict(round="r5", relation_id=r.relation_id, design=r.design,
                         role=r.role, host=(r.host if "host" in r.index else ""), recipe="", usage=r.usage,
                         kind="", target=r.target, k=int(r.k),
                         enum_complete=int(r.enum_complete),
                         query_status=r.query_status,
                         function_status=r.new_status, function_class=r.new_class,
                         domain_restricted=int(r.domain_restricted),
                         n_feasible=int(r.n_feasible), n_forced=int(r.n_forced),
                         n_undecided=int(r.n_undecided), n_infeasible=int(r.n_infeasible),
                         influence_comparable_pairs=int(r.influence_comparable_pairs),
                         influence_possible_pairs=int(r.influence_possible_pairs),
                         influence_pair_coverage=float(r.influence_pair_coverage),
                         influence_observed_change=int(r.influence_observed_change),
                         influence_mean=r.influence_mean,
                         influence_max=float(r5max.get(r.relation_id, 0) or 0),
                         influence_valid_inputs=int(r.influence_valid_inputs),
                         influence_scope=r.influence_scope,
                         cut_kind="partial_probe", selected_ratio=np.nan,
                         cut_leaf_total=np.nan, cut_distances="",
                         functional_sufficiency=r5suf.get(r.relation_id, "")))
    r6 = pd.read_csv(TAB6 / "r6_nonlocal_relations.csv", encoding="utf-8-sig")
    for _, r in r6.iterrows():
        k = int(str(r.cut_nets).count(";") + 1)
        c = classify(r.truth_table, k, bool(r.enum_complete), r.query_status)
        inf = influence_from_tt(r.truth_table, k, str(r.cut_nets).split(";"))
        rows.append(dict(round="r6", relation_id=r.relation_id, design=r.design,
                         role=r.role, host=r.host, recipe=r.recipe, usage=r.usage,
                         kind=r.kind, target=r.target, k=k,
                         enum_complete=int(r.enum_complete),
                         query_status=r.query_status,
                         function_status=c["function_status"],
                         function_class=c["function_class"],
                         domain_restricted=c["domain_restricted"],
                         n_feasible=c["n_feasible"], n_forced=c["n_forced"],
                         n_undecided=c["n_undecided"], n_infeasible=c["n_infeasible"],
                         influence_comparable_pairs=inf["influence_comparable_pairs"],
                         influence_possible_pairs=inf["influence_possible_pairs"],
                         influence_pair_coverage=inf["influence_pair_coverage"],
                         influence_observed_change=inf["influence_observed_change"],
                         influence_mean=inf["influence_mean"],
                         influence_max=float(r.influence_max) if pd.notna(r.influence_max) else 0.0,
                         influence_valid_inputs=inf["influence_valid_inputs"],
                         influence_scope=inf["influence_scope"],
                         cut_kind=r.cut_kind, selected_ratio=float(r.selected_ratio),
                         cut_leaf_total=int(r.cut_leaf_total),
                         cut_distances=r.cut_depths,
                         truth_table=r.truth_table,
                         functional_sufficiency=r.functional_sufficiency))
    d = pd.DataFrame(rows)
    d["undecided_ratio"] = d.n_undecided / (2 ** d.k)
    d["feasible_ratio"] = d.n_feasible / (2 ** d.k)
    d["forced_ratio"] = d.n_forced / (2 ** d.k)
    d["infeasible_ratio"] = d.n_infeasible / (2 ** d.k)
    d.to_csv(TAB6 / "r6_relations_all.csv", index=False, encoding="utf-8-sig")
    return d


def graph_sets():
    g = torch.load(PT / "trans_graph.pt", map_location="cpu",
                   weights_only=False, mmap=True)
    y = g.y.numpy().reshape(-1) > 0
    trust = np.load(PT / "trust_trans.npy")
    ei = g.edge_index.numpy()
    src = np.concatenate([ei[0], ei[1]])
    dst = np.concatenate([ei[1], ei[0]])
    order = np.argsort(src, kind="stable")
    src, dst = src[order], dst[order]
    indptr = np.concatenate([[0], np.cumsum(np.bincount(src, minlength=len(y)))])
    return y, trust, indptr, dst


def nbrs(nodes, indptr, dst):
    nodes = np.asarray(sorted(set(int(x) for x in nodes)), dtype=np.int64)
    if not len(nodes):
        return np.array([], dtype=np.int64)
    parts = [dst[indptr[n]:indptr[n + 1]] for n in nodes]
    return np.unique(np.concatenate(parts))


def hops(seed, indptr, dst):
    one = np.setdiff1d(nbrs(seed, indptr, dst), seed)
    two = np.setdiff1d(nbrs(one, indptr, dst), np.union1d(seed, one))
    return one, two


def frames():
    r4 = pd.concat([pd.read_csv(TAB3 / "r3_recovery_nodes.csv", encoding="utf-8-sig"),
                    pd.read_csv(TAB3 / "r3_graded_nodes.csv", encoding="utf-8-sig")])
    r5 = pd.read_csv(TAB5 / "r5_nodes.csv", encoding="utf-8-sig")
    r6 = pd.read_csv(TAB6 / "r6_nodes.csv", encoding="utf-8-sig")
    return {"r4": r4, "r5": r5, "r6": r6}


def node_set(basis, f):
    if basis == "r4":
        return set(int(x) for x in f["r4"].node_index)
    if basis == "r5":
        return set(int(x) for x in f["r5"].node_index)
    if basis == "r6":
        return set(int(x) for x in f["r6"].node_index)
    if basis == "cum5":
        return node_set("r4", f) | node_set("r5", f)
    if basis == "r5r6":
        return node_set("r5", f) | node_set("r6", f)
    if basis == "cum6":
        return node_set("r4", f) | node_set("r5", f) | node_set("r6", f)
    raise ValueError(basis)


def coverage(d: pd.DataFrame) -> dict:
    y, trust, indptr, dst = graph_sets()
    f = frames()
    role_map = {}
    for frame in f.values():
        role_map.update({int(n): str(r) for n, r in zip(frame.node_index, frame.role)})
    old = {"train": dict(nodes=3231, positives=46, h1_nodes=11530, h1_positives=114,
                         h2_nodes=37384, h2_positives=197),
           "val": dict(nodes=780, positives=3, h1_nodes=4468, h1_positives=4,
                       h2_nodes=21180, h2_positives=7)}
    sets = {b: node_set(b, f) for b in ("r4", "r5", "r6", "cum5", "r5r6", "cum6")}
    rows = []
    for role, o in old.items():
        rows.append(dict(basis="old", role=role, level="queried",
                         relations=None, nodes=o["nodes"],
                         positives=o["positives"], trusted_pos=o["positives"],
                         trusted_neg=o["nodes"] - o["positives"],
                         h1_nodes=o["h1_nodes"], h1_positives=o["h1_positives"],
                         h2_nodes=o["h2_nodes"], h2_positives=o["h2_positives"],
                         h1_incremental=None, h2_incremental=None,
                         exact_set="documented_denominator_only"))
    for basis, ids in sets.items():
        for role in ("train", "val"):
            role_ids = np.array(sorted(i for i in ids if role_map.get(i) == role),
                                dtype=np.int64)
            one, two = hops(role_ids, indptr, dst)
            if basis in ("r6", "r5r6", "cum6"):
                base = sets["cum5"]
            elif basis == "r5":
                base = sets["r4"]
            else:
                base = set()
            b1, b2 = hops(np.array(sorted(base), dtype=np.int64), indptr, dst) \
                if base else (np.array([], dtype=np.int64), np.array([], dtype=np.int64))
            rows.append(dict(basis=basis, role=role, level="queried",
                             relations=None, nodes=len(role_ids),
                             positives=int(y[role_ids].sum()) if len(role_ids) else 0,
                             trusted_pos=int((y[role_ids] & trust[role_ids]).sum()) if len(role_ids) else 0,
                             trusted_neg=int((~y[role_ids] & trust[role_ids]).sum()) if len(role_ids) else 0,
                             h1_nodes=len(one), h1_positives=int(y[one].sum()) if len(one) else 0,
                             h2_nodes=len(two), h2_positives=int(y[two].sum()) if len(two) else 0,
                             h1_incremental=int(y[np.setdiff1d(one, b1)].sum()) if len(one) else 0,
                             h2_incremental=int(y[np.setdiff1d(two, b2)].sum()) if len(two) else 0,
                             exact_set="node_index"))
    cov = pd.DataFrame(rows)
    cov.to_csv(TAB6 / "r6_coverage.csv", index=False, encoding="utf-8-sig")

    lrows = []
    for basis in ("r5", "r6", "r5r6"):
        for role in ("train", "val"):
            rel_ids = set()
            for rnd, frame in (("r5", f["r5"]), ("r6", f["r6"])):
                if basis == "r5" and rnd != "r5":
                    continue
                if basis == "r6" and rnd != "r6":
                    continue
                if basis == "r5r6" and rnd not in ("r5", "r6"):
                    continue
                rel_ids |= set(frame[frame.role == role].relation_id)
            for level in ("cond_fact", "suff_proved", "influence_valid"):
                sel = d[d.role == role]
                if level == "cond_fact":
                    sel = sel[sel.enum_complete.eq(1) & (sel.n_feasible > 0) & (sel.n_forced > 0)]
                elif level == "suff_proved":
                    sel = sel[sel.functional_sufficiency == "proved"]
                else:
                    sel = sel[sel.influence_comparable_pairs > 0]
                keep = sel[sel.relation_id.isin(rel_ids)].relation_id
                nids = set()
                for frame in (f["r5"], f["r6"]):
                    nids |= set(int(x) for x in
                                frame[frame.relation_id.isin(keep)].node_index)
                nids = np.array(sorted(nids), dtype=np.int64)
                lrows.append(dict(basis=basis, role=role, level=level,
                                  relations=len(set(keep)), nodes=len(nids),
                                  positives=int(y[nids].sum()) if len(nids) else 0))
    pd.DataFrame(lrows).to_csv(TAB6 / "r6_coverage_levels.csv", index=False,
                               encoding="utf-8-sig")
    manifest = dict(old_baseline=old,
                    node_counts={k: len(v) for k, v in sets.items()},
                    overlaps={k: {b: len(sets[k] & sets[b])
                                  for b in ("r4", "r5", "r6")} for k in sets},
                    old_exact_node_set="not persisted; counts from r3_coverage.csv")
    (TAB6 / "r6_coverage_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def propagation(d: pd.DataFrame) -> dict:
    sources = [
        ("r5", pd.read_csv(TAB5 / "r5_nonlocal_relations.csv", encoding="utf-8-sig")),
        ("r6", pd.read_csv(TAB6 / "r6_nonlocal_relations.csv", encoding="utf-8-sig"))]
    rows, edges = [], []
    for rnd, rels in sources:
        for _, r in rels.iterrows():
            k = int(str(r.cut_nets).count(";") + 1)
            tt = {}
            for item in str(r.truth_table).split(";"):
                p, fe, fo = item.split(":")
                tt[p] = (fe, fo)
            edge = blocked = undet = 0
            for p in sorted(tt):
                for b in range(k):
                    q = p[:b] + ("1" if p[b] == "0" else "0") + p[b + 1:]
                    if q < p:
                        continue
                    f0, f1 = tt[p], tt[q]
                    if f0[0] == "feasible" and f1[0] == "feasible" \
                            and f0[1] in ("0", "1") and f1[1] in ("0", "1"):
                        if f0[1] != f1[1]:
                            edge += 1
                            cut = str(r.cut_nets).split(";")
                            edges.append(dict(round=rnd, relation_id=r.relation_id,
                                              design=r.design, role=r.role,
                                              target=r.target, input=cut[b],
                                              context=p[:b] + "*" + p[b + 1:],
                                              pattern0=p, value0=f0[1],
                                              pattern1=q, value1=f1[1]))
                        else:
                            blocked += 1
                    else:
                        undet += 1
            rows.append(dict(round=rnd, relation_id=r.relation_id, design=r.design,
                             role=r.role, target=r.target, k=k, edges=edge,
                             blocked=blocked, undetermined=undet,
                             total_pairs=k * (2 ** (k - 1))))
    pr = pd.DataFrame(rows)
    pr.to_csv(TAB6 / "r6_propagation.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(edges).to_csv(TAB6 / "r6_propagation_edges.csv", index=False,
                               encoding="utf-8-sig")
    info = dict(edges=int(pr.edges.sum()), blocked=int(pr.blocked.sum()),
                undetermined=int(pr.undetermined.sum()),
                relations_with_edges=int((pr.edges > 0).sum()),
                by_round=pr.groupby("round").edges.sum().to_dict(),
                by_role=pr.groupby("role").edges.sum().to_dict())
    (TAB6 / "r6_propagation_manifest.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    return info


def info(d: pd.DataFrame) -> dict:
    rows = []
    for (rnd, status, cls), g in d.groupby(["round", "function_status", "function_class"]):
        rows.append(dict(round=rnd, function_status=status, function_class=cls,
                         relations=len(g),
                         train=int((g.role == "train").sum()),
                         val=int((g.role == "val").sum()),
                         mean_undecided=float(g.undecided_ratio.mean()),
                         mean_feasible=float(g.feasible_ratio.mean()),
                         mean_influence_coverage=float(g.influence_pair_coverage.mean())))
    pd.DataFrame(rows).to_csv(TAB6 / "r6_info_columns.csv", index=False,
                              encoding="utf-8-sig")
    d["stratum"] = d.design + "|" + d.kind.fillna("")
    d["profile"] = (d.function_status.astype(str) + "|"
                    + d.undecided_ratio.round(3).astype(str) + "|"
                    + d.influence_pair_coverage.round(3).astype(str) + "|"
                    + d.forced_ratio.round(3).astype(str))
    differing = []
    for s, g in d.groupby("stratum"):
        if len(g) > 1 and (g.function_status.nunique() > 1 or g.profile.nunique() > 1):
            differing.append(dict(stratum=s, relations=len(g),
                                  statuses=";".join(sorted(g.function_status.unique())),
                                  classes=";".join(sorted(g.function_class.unique())),
                                  distinct_profiles=int(g.profile.nunique())))
    pd.DataFrame(differing).to_csv(TAB6 / "r6_info_strata.csv", index=False,
                                   encoding="utf-8-sig")
    summary = dict(
        relations=len(d), by_round=d["round"].value_counts().to_dict(),
        status_counts=d.function_status.value_counts().to_dict(),
        class_counts=d.function_class.value_counts().to_dict(),
        by_role_status={f"{a}|{b}": int(v) for (a, b), v in
                        d.groupby(["role", "function_status"]).size().items()},
        undecided_ratio=dict(mean=float(d.undecided_ratio.mean()),
                             max=float(d.undecided_ratio.max())),
        influence_coverage=dict(mean=float(d.influence_pair_coverage.mean()),
                                min=float(d.influence_pair_coverage.min()),
                                max=float(d.influence_pair_coverage.max()),
                                subset=int((d.influence_pair_coverage < 1).sum())),
        structural_strata_differing=len(differing))
    (TAB6 / "r6_info_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> int:
    d = unified()
    cov = coverage(d)
    prop = propagation(d)
    inf = info(d)
    print(json.dumps(dict(coverage=cov, propagation=prop, info=inf),
                     ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    if "--allow-legacy-ring-report" not in sys.argv:
        raise SystemExit("Historical exact-ring coverage omits the old support set. Use round7_20261025/audit_repair.py for current coverage; --allow-legacy-ring-report is archival only.")
    raise SystemExit(main())
