"""Corrected 25-column round-5-only feature arrays (supersede the old 20-col)."""
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
from build_features_r6 import COLS, record  # noqa: E402


def agg(recs, rid_nodes, N, name):
    per = defaultdict(list)
    for rid, nodes in rid_nodes.items():
        if rid in recs:
            for ni in nodes:
                per[ni].append(recs[rid])
    arr = np.lib.format.open_memmap(FEAT / name, mode="w+", dtype=np.float32,
                                    shape=(N, len(COLS)))
    for ni, rs in per.items():
        for j, c in enumerate(COLS):
            if c == "multi_relation_norm":
                arr[ni, j] = min(1.0, len(rs) / 2.0)
            elif c == "covered":
                arr[ni, j] = 1.0
            else:
                arr[ni, j] = max(x[c] for x in rs)
        arr[ni, -1] = 1.0
    arr.flush()
    return arr, per


def main() -> int:
    d = pd.read_csv(TAB6 / "r6_relations_all.csv", encoding="utf-8-sig")
    d = d[d["round"] == "r5"].copy()
    nodes = pd.read_csv(TAB5 / "r5_nodes.csv", encoding="utf-8-sig")
    rid_nodes = nodes.groupby("relation_id").node_index.apply(
        lambda s: sorted(set(int(x) for x in s))).to_dict()
    g = torch.load(PT / "trans_graph.pt", map_location="cpu",
                   weights_only=False, mmap=True)
    N = g.y.size(0)
    recs = {r.relation_id: record(r) for _, r in d.iterrows()}
    real, per = agg(recs, rid_nodes, N, "r5_extra_corrected_real.npy")
    rng = np.random.default_rng(20261025)
    precs = dict(recs)
    no_perm = []
    for design, g2 in d.groupby("design", sort=False):
        if len(g2) < 2:
            no_perm.append(design)
            continue
        order = rng.permutation(len(g2))
        if np.array_equal(order, np.arange(len(g2))):
            order = np.roll(order, 1)
        for tgt, src in zip(g2.relation_id, g2.relation_id.iloc[order]):
            precs[tgt] = recs[src]
    perm, _ = agg(precs, rid_nodes, N, "r5_extra_corrected_permuted.npy")
    support = np.array(sorted(per), dtype=np.int64)
    changed = support[np.any(np.asarray(real[support]) != np.asarray(perm[support]), axis=1)]
    role = dict(zip(nodes.node_index, nodes.role))
    info = dict(relations=len(d), support=len(support), changed=len(changed),
                changed_by_role={r: int(sum(role.get(int(i)) == r for i in changed))
                                 for r in ("train", "val")},
                no_perm_designs=sorted(set(no_perm)),
                class_counts=d.function_class.value_counts().to_dict())
    (FEAT / "r5_feature_columns_corrected.json").write_text(json.dumps(dict(
        columns=COLS, n=N, last_column="covered", bounded=[0, 1],
        supersedes="r5_extra_real.npy (old 20-col constant encoding invalid)",
        class_counts=info["class_counts"], no_perm_designs=info["no_perm_designs"]),
        ensure_ascii=False, indent=2), encoding="utf-8")
    (TAB6 / "r5_feature_diff_corrected.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(info, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())