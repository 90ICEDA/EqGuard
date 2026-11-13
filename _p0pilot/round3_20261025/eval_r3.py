"""Round-3 evaluation: same train/val denominators, per-view mapping, permutation."""
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
TAB = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_valid_round3"
OLD = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sparse_sat_round1"


def hops(support: np.ndarray, edges: np.ndarray, h: int) -> np.ndarray:
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
    old = np.asarray(np.load(PT / "satrel_node_feats_sparseR1_real.npy", mmap_mode="r")[:, 6]) > 0

    rel = pd.concat([
        pd.read_csv(TAB / "r3_recovery_relations.csv", encoding="utf-8-sig")
        .assign(source="recovery"),
        pd.read_csv(TAB / "r3_graded_relations.csv", encoding="utf-8-sig")
        .assign(source="graded")], ignore_index=True)
    nodes = pd.concat([
        pd.read_csv(TAB / "r3_recovery_nodes.csv", encoding="utf-8-sig")
        .assign(source="recovery"),
        pd.read_csv(TAB / "r3_graded_nodes.csv", encoding="utf-8-sig")
        .assign(source="graded")], ignore_index=True)
    nodes = nodes.drop_duplicates(["relation_id", "view", "node_index"])
    node_idx = np.unique(nodes.node_index.to_numpy())
    support = np.zeros(len(vid), bool)
    support[node_idx] = True
    print("relations", len(rel), "unique nodes", len(node_idx), flush=True)

    rows = []
    for h in range(3):
        su, so = hops(support, edges, h), hops(old, edges, h)
        for r in ("train", "val"):
            m = role == r
            rows.append(dict(hops=h, role=r,
                             new_nodes=int((su & m).sum()),
                             new_positives=int((su & y & m).sum()),
                             new_trusted_pos=int((su & y & trust & m).sum()),
                             new_trusted_neg=int((su & ~y & trust & m).sum()),
                             old_positives=int((so & y & m).sum()),
                             union_positives=int(((su | so) & y & m).sum()),
                             incremental_positives=int(((su | so) & y & m).sum()
                                                       - (so & y & m).sum()),
                             denominator_positives=int((y & m).sum())))
    cov = pd.DataFrame(rows)
    cov.to_csv(TAB / "r3_coverage.csv", index=False, encoding="utf-8-sig")
    print(cov.to_string(index=False), flush=True)

    # per host / recipe / kind
    strat = []
    for keys, g2 in rel.groupby(["source", "role", "host", "recipe", "kind"]):
        n = nodes[nodes.relation_id.isin(g2.relation_id)].node_index.to_numpy()
        nn = np.unique(n)
        mm = np.zeros(len(vid), bool)
        mm[nn] = True
        strat.append(dict(source=keys[0], role=keys[1], host=keys[2], recipe=keys[3],
                          kind=keys[4], relations=len(g2), nodes=int(mm.sum()),
                          positives=int((mm & y).sum()),
                          sufficiency=";".join(sorted(g2.functional_sufficiency.unique()))))
    pd.DataFrame(strat).to_csv(TAB / "r3_stratified.csv", index=False, encoding="utf-8-sig")

    # value information (unknown is a mask; zero is a value)
    info = []
    for src, g2 in rel.groupby("source"):
        for col in ("n_forced", "n_feasible", "determinism_ratio", "influence_mean"):
            vals = pd.to_numeric(g2[col], errors="coerce").to_numpy(float)
            known = ~np.isnan(vals)
            u, c = np.unique(vals[known], return_counts=True)
            p = c / c.sum() if len(c) else np.array([])
            info.append(dict(source=src, column=col, n=len(vals),
                             n_known=int(known.sum()), n_unknown=int((~known).sum()),
                             unique=int(len(u)), entropy=float(-(p * np.log2(p)).sum())
                             if len(p) else None,
                             values=";".join(f"{a:g}" for a in u)))
    pd.DataFrame(info).to_csv(TAB / "r3_value_info.csv", index=False, encoding="utf-8-sig")
    print(pd.DataFrame(info).to_string(index=False), flush=True)

    # joint permutation of the graded tuple within each design; measure changed content
    rng = np.random.default_rng(20261025)
    perm_rows = []
    for (src, design), g2 in rel.groupby(["source", "design"]):
        g2 = g2.sort_values("relation_id").reset_index(drop=True)
        base = list(zip(g2.functional_sufficiency, g2.n_forced,
                        g2.determinism_ratio.fillna(-1),
                        g2.influence_status, g2.influence_mean.fillna(-1)))
        order = rng.permutation(len(base))
        changed_rels = {g2.relation_id.iloc[i] for i in range(len(base))
                        if base[i] != base[order[i]]}
        nset = {}
        for rid in g2.relation_id:
            nset[rid] = set(nodes[nodes.relation_id == rid].node_index.tolist())
        changed_nodes = sorted({i for rid in changed_rels for i in nset[rid]})
        cs = np.zeros(len(vid), bool)
        cs[changed_nodes] = True
        perm_rows.append(dict(source=src, design=design, relations=len(g2),
                              changed_relations=len(changed_rels),
                              changed_nodes=len(changed_nodes),
                              changed_1hop=int(hops(cs, edges, 1).sum()),
                              changed_2hop=int(hops(cs, edges, 2).sum())))
    pdf = pd.DataFrame(perm_rows)
    pdf.to_csv(TAB / "r3_permutation.csv", index=False, encoding="utf-8-sig")
    print(pdf.to_string(index=False), flush=True)
    info2 = dict(relations=len(rel), nodes=len(node_idx),
                 mapped_views=int(len(nodes[["relation_id", "view"]].drop_duplicates())),
                 permutation_changed_nodes=int(pdf.changed_nodes.sum()),
                 permutation_changed_2hop=int(pdf.changed_2hop.sum()),
                 roles=sorted(set(rel.role)), test_used=False)
    (TAB / "r3_eval_manifest.json").write_text(
        json.dumps(info2, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(info2, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
