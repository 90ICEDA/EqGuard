"""Build a training-format candidate extra-feature array for round-5 evidence.

Last column is the coverage mask; every other column is bounded in [0,1].
Truth classes are one-hot, never an ordinal signature id. No training.
"""
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
R5 = ROOT / "_p0pilot/round5_20261025"
TAB5 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_nonlocal_round5"
FEAT = R5 / "features"

COLS = ["queried", "forced_fraction", "feasible_fraction", "determinism",
        "infeasible_fraction", "undecided_fraction", "influence_mean",
        "influence_max", "n_inputs_norm", "n_valid_inputs_norm",
        "is_constant0", "is_constant1", "is_identity", "is_inverter",
        "is_and", "is_or", "is_xor", "is_other_function",
        "multi_relation_norm", "covered"]


def truth_class(tt: str, k: int) -> str:
    d = {}
    for item in str(tt).split(";"):
        p, feas, force = item.split(":")
        d[p] = (feas, force)
    vals = {p: int(f) for p, (fe, f) in d.items()
            if fe == "feasible" and f in ("0", "1")}
    if not vals:
        return "other"
    if all(v == 0 for v in vals.values()):
        return "constant0"
    if all(v == 1 for v in vals.values()):
        return "constant1"
    if k == 1:
        if vals.get("0") == 0 and vals.get("1") == 1:
            return "identity"
        if vals.get("0") == 1 and vals.get("1") == 0:
            return "inverter"
    if k == 2:
        def ok(fn):
            return all(fn(p) == v for p, v in vals.items())
        if ok(lambda p: int(all(c == "1" for c in p))):
            return "and"
        if ok(lambda p: int(any(c == "1" for c in p))):
            return "or"
        if ok(lambda p: int(p[0] != p[1])):
            return "xor"
    return "other"


def main() -> int:
    FEAT.mkdir(parents=True, exist_ok=True)
    rel = pd.read_csv(TAB5 / "r5_nonlocal_relations.csv", encoding="utf-8-sig")
    nodes = pd.read_csv(TAB5 / "r5_nodes.csv", encoding="utf-8-sig")
    rid_nodes = nodes.groupby("relation_id").node_index.apply(
        lambda s: sorted(set(int(x) for x in s))).to_dict()
    g = torch.load(PT / "trans_graph.pt", map_location="cpu", weights_only=False, mmap=True)
    N = g.y.size(0)

    def rel_record(r) -> dict:
        k = int(str(r.cut_nets).count(";") + 1)
        npat = int(r.n_patterns)
        det = 0.0 if pd.isna(r.determinism_ratio) else float(r.determinism_ratio)
        inf_mean = 0.0 if pd.isna(r.influence_mean) else float(r.influence_mean)
        inf_max = 0.0 if pd.isna(r.influence_max) else float(r.influence_max)
        tc = truth_class(r.truth_table, k)
        ones = {c: 0.0 for c in COLS[10:18]}
        ones[{"constant0": "is_constant0", "constant1": "is_constant1",
              "identity": "is_identity", "inverter": "is_inverter",
              "and": "is_and", "or": "is_or", "xor": "is_xor",
              "other": "is_other_function"}[tc]] = 1.0
        return dict(queried=1.0, forced_fraction=int(r.n_forced) / npat,
                    feasible_fraction=int(r.n_feasible) / npat, determinism=det,
                    infeasible_fraction=int(r.n_infeasible) / npat,
                    undecided_fraction=int(r.n_undecided) / npat,
                    influence_mean=inf_mean, influence_max=inf_max,
                    n_inputs_norm=k / 4.0,
                    n_valid_inputs_norm=float(r.n_valid_influence_inputs) / 4.0,
                    **ones, multi_relation_norm=0.0, covered=1.0)

    def aggregate(frame: pd.DataFrame) -> np.ndarray:
        arr = np.zeros((N, len(COLS)), np.float32)
        per = {}
        for _, r in frame.iterrows():
            rec = rel_record(r)
            for ni in rid_nodes.get(r.relation_id, []):
                per.setdefault(ni, []).append(rec)
        for ni, recs in per.items():
            for j, c in enumerate(COLS):
                if c == "multi_relation_norm":
                    arr[ni, j] = min(1.0, len(recs) / 2.0)
                elif c == "covered":
                    arr[ni, j] = 1.0
                else:
                    arr[ni, j] = max(x[c] for x in recs)
            arr[ni, len(COLS) - 1] = 1.0
        return arr

    real = aggregate(rel)
    rng = np.random.default_rng(20261025)
    parts, no_perm = [], []
    key = rel.assign(k=rel.cut_nets.str.count(";") + 1)
    for (design, k), g2 in key.groupby(["design", "k"]):
        if len(g2) < 2:
            no_perm.append(design)
            parts.append(g2)
            continue
        order = rng.permutation(len(g2))
        if len(g2) > 1 and np.array_equal(order, np.arange(len(g2))):
            order = np.roll(order, 1)   # avoid an identity permutation for n=2
        parts.append(g2.iloc[order].assign(relation_id=g2.relation_id.values))
    perm = aggregate(pd.concat(parts, ignore_index=True))
    np.save(FEAT / "r5_extra_real.npy", real)
    np.save(FEAT / "r5_extra_permuted.npy", perm)
    (FEAT / "r5_feature_columns.json").write_text(json.dumps(dict(
        columns=COLS, n=N, last_column="covered", bounded=[0, 1],
        truth_encoding="one-hot over 8 truth classes; no ordinal signature id",
        aggregation="max per numeric column; one-hot OR; multi_relation=count/2 capped 1",
        permutation="within design and cut size; designs with <2 relations unchanged",
        no_valid_permutation_designs=sorted(set(no_perm))), ensure_ascii=False, indent=2),
        encoding="utf-8")
    print(json.dumps(dict(shape=list(real.shape), min=float(real.min()),
                          max=float(real.max()), covered=int(real[:, -1].sum()),
                          no_perm=len(set(no_perm))), ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
