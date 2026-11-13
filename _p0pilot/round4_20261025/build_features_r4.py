"""Build the round-4 unified relation table and aggregated features."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import itertools
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

ROOT = Path(_eqguard_path(''))
WORK = ROOT / "generate_trans/folds/hosts_bt31"
PT = WORK / "data/processed"
R3 = ROOT / "_p0pilot/round3_20261025"
R4 = ROOT / "_p0pilot/round4_20261025"
TAB3 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_valid_round3"
TAB4 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_chain_round4"
FEAT = R4 / "features"
sys.path.insert(0, str(R4))
from sat_evidence_v4 import evaluate_case_v4, normalize_cut  # noqa: E402


def gate_type(design: str, cell: str) -> str:
    raw = R3 / "struct_raw" / (Path(design).stem + ".json")
    mods = json.loads(raw.read_text(encoding="utf-8"))["modules"]
    mod = next(iter(mods.values()))
    c = mod.get("cells", {}).get(cell)
    return str(c.get("type", "")) if c else ""


def netbits(design: str) -> dict:
    raw = R3 / "struct_raw" / (Path(design).stem + ".json")
    mods = json.loads(raw.read_text(encoding="utf-8"))["modules"]
    mod = next(iter(mods.values()))
    nb = {nm: tuple(b for b in info.get("bits", []) if isinstance(b, int))
          for nm, info in mod.get("netnames", {}).items()}
    for nm, p in mod.get("ports", {}).items():
        nb[nm] = tuple(b for b in p.get("bits", []) if isinstance(b, int))
    return nb


def main() -> int:
    FEAT.mkdir(parents=True, exist_ok=True)
    r3rel = pd.read_csv(TAB3 / "r3_recovery_relations.csv", encoding="utf-8-sig")
    drv = dict(zip(r3rel.relation_id, r3rel.driver))
    rc = pd.read_csv(TAB4 / "r4_reclassify.csv", encoding="utf-8-sig")
    cc = pd.read_csv(TAB4 / "r4_two_input_relations.csv", encoding="utf-8-sig")
    g = pd.read_csv(TAB3 / "r3_graded_relations.csv", encoding="utf-8-sig")
    gq = pd.read_csv(TAB3 / "r3_graded_queries.csv", encoding="utf-8-sig",
                     dtype={"pattern": str})

    rows = []
    # 50 single-input (already re-evaluated)
    for _, r in rc[rc.cut_size_canonical == 1].iterrows():
        rows.append(dict(relation_id=r.relation_id, design=r.design, role=r.role,
                         host=r.host, recipe=r.recipe, kind=r.kind, target=r.target,
                         driver=drv.get(r.relation_id, ""), source="recovery_single",
                         cut_size=1, enum_complete=r.enum_complete,
                         functional_sufficiency=r.functional_sufficiency,
                         influence_status=r.influence_status,
                         determinism=r.determinism_ratio, n_inputs=1,
                         n_valid_inputs=r.n_valid_influence_inputs,
                         n_forced=int(r.n_forced), truth_table=r.truth_table,
                         driver_type=gate_type(r.design, drv.get(r.relation_id, "")),
                         depth=-1, po_sat=0))
    # 29 two-input (completed)
    for _, r in cc.iterrows():
        if "functional_sufficiency" not in r:
            continue
        rows.append(dict(relation_id=r.relation_id, design=r.design, role=r.role,
                         host=r.host, recipe=r.recipe, kind=r.kind, target=r.target,
                         driver=drv.get(r.relation_id, ""), source="recovery_two",
                         cut_size=2, enum_complete=r.enum_complete,
                         functional_sufficiency=r.functional_sufficiency,
                         influence_status=r.influence_status,
                         determinism=r.determinism_ratio, n_inputs=2,
                         n_valid_inputs=r.n_valid_influence_inputs,
                         n_forced=int(r.n_forced), truth_table=r.truth_table,
                         driver_type=gate_type(r.design, drv.get(r.relation_id, "")),
                         depth=-1, po_sat=0))
    # 10 graded, re-evaluated with v4 from stored queries
    for _, r in g.iterrows():
        sub = gq[gq.relation_id == r.relation_id].reset_index(drop=True)
        k = int(r.cut_size)
        pats = ["".join(str(b) for b in p) for p in itertools.product([0, 1], repeat=k)]
        stat = {i + 1: sub.status.iloc[i] for i in range(min(2 * len(pats), len(sub)))}
        nb = netbits(r.design)
        canon = normalize_cut([c for c in str(r.cut_nets).split(";") if c],
                              nb, r.target)
        cut = [c["name"] for c in canon["canonical"]]
        ev = evaluate_case_v4(cut, pats, list(range(1, 2 * len(pats) + 1)), stat)
        rows.append(dict(relation_id=r.relation_id, design=r.design, role=r.role,
                         host=r.host, recipe=r.recipe, kind=r.kind, target=r.target,
                         driver=r.driver, source="graded",
                         cut_size=len(cut), enum_complete=ev["enum_complete"],
                         functional_sufficiency=ev["functional_sufficiency"],
                         influence_status=ev["influence_status"],
                         determinism=ev["determinism_ratio"], n_inputs=len(cut),
                         n_valid_inputs=ev["n_valid_influence_inputs"],
                         n_forced=int(ev["n_forced"]), truth_table=ev["truth_table"],
                         driver_type=gate_type(r.design, str(r.driver)),
                         depth=int(r.cut_depth), po_sat=int(r.kind == "cone")))
    d = pd.DataFrame(rows)
    d.to_csv(TAB4 / "r4_unified_relations.csv", index=False, encoding="utf-8-sig")
    print("unified", len(d), flush=True)
    print(d.groupby(["source", "cut_size", "functional_sufficiency"]).size().to_string(),
          flush=True)
    print("\ngate types:\n", d.groupby(["driver_type", "cut_size"]).size().to_string(),
          flush=True)
    print("\nPO relations:", int(d.po_sat.sum()), flush=True)

    # ---------- node mapping and aggregation ----------
    nodes = pd.concat([
        pd.read_csv(TAB3 / "r3_recovery_nodes.csv", encoding="utf-8-sig"),
        pd.read_csv(TAB3 / "r3_graded_nodes.csv", encoding="utf-8-sig")],
        ignore_index=True).drop_duplicates(["relation_id", "view", "node_index"])
    rid_nodes = nodes.groupby("relation_id").node_index.apply(
        lambda s: sorted(set(int(x) for x in s))).to_dict()
    split = json.loads((WORK / "views.json").read_text(encoding="utf-8"))
    role_of_view = {v: r for r in ("train", "val") for v in split[f"{r}_views"]}
    meta = json.loads((WORK / "data/for_train/metadata_trans.json").read_text(encoding="utf-8"))
    fids = np.asarray(meta["file_ids"], dtype=object)
    vid, views = pd.factorize(fids, sort=False)
    vid = vid.astype(np.int32)
    del fids
    role = np.asarray([role_of_view.get(str(v), "other") for v in views])[vid]
    N = len(vid)
    g = torch.load(PT / "trans_graph.pt", map_location="cpu", weights_only=False, mmap=True)
    y = g.y.numpy().reshape(-1) > 0
    trust = np.load(PT / "trust_trans.npy")
    edges = g.edge_index.numpy()
    old = np.load(PT / "satrel_node_feats_sparseR1_real.npy", mmap_mode="r")
    old_support = np.asarray(old[:, 6]) > 0

    d["cond_fact"] = (d.n_forced > 0).astype(int)
    d["suff"] = (d.functional_sufficiency == "proved").astype(int)
    d["infl"] = (d.influence_status == "valid").astype(int)
    sigs = sorted(d.truth_table.unique())
    sig_id = {s: i + 1 for i, s in enumerate(sigs)}
    d["sig_id"] = d.truth_table.map(sig_id)

    def aggregate(rel_frame: pd.DataFrame) -> dict:
        per_node = {}
        for _, r in rel_frame.iterrows():
            rec = dict(cond_fact=int(r.cond_fact), suff_proved=int(r.suff),
                       influence_valid=int(r.infl),
                       determinism=(None if pd.isna(r.determinism) else float(r.determinism)),
                       n_inputs=int(r.n_inputs),
                       nvalid=int(r.n_valid_inputs) if not pd.isna(r.n_valid_inputs) else 0,
                       truth_table=str(r.truth_table))
            for ni in rid_nodes.get(r.relation_id, []):
                per_node.setdefault(ni, []).append(rec)
        out = {}
        for ni, recs in per_node.items():
            cond = int(any(x["cond_fact"] for x in recs))
            suff = int(any(x["suff_proved"] for x in recs))
            infl = int(any(x["influence_valid"] for x in recs))
            dets = [x["determinism"] for x in recs if x["determinism"] is not None]
            det = max(dets) if dets else 0.0
            nin = max(x["n_inputs"] for x in recs)
            nvalid = max(x["nvalid"] for x in recs)
            tts = sorted({x["truth_table"] for x in recs})
            out[ni] = dict(cond=cond, suff=suff, infl=infl, det=det, nin=nin,
                           nvalid=nvalid, sig=sig_id.get(tts[0], 0),
                           multi=len(recs), conflict=int(len(tts) > 1 and len(recs) > 1))
        return out

    COLS = ["reach_po", "reach_dff", "covered", "cond_fact", "suff_proved",
            "influence_valid", "determinism", "n_inputs", "n_valid_inputs",
            "truth_sig", "multi_relation", "conflict", "det_known", "truth_known"]
    real = np.zeros((N, len(COLS)), np.float32)
    real[:, 0] = np.asarray(old[:, 0])
    real[:, 1] = np.asarray(old[:, 1])
    real[:, 2] = np.asarray(old[:, 7])
    real_agg = aggregate(d)
    for ni, a in real_agg.items():
        real[ni, 3] = a["cond"]
        real[ni, 4] = a["suff"]
        real[ni, 5] = a["infl"]
        real[ni, 6] = a["det"]
        real[ni, 7] = a["nin"]
        real[ni, 8] = a["nvalid"]
        real[ni, 9] = a["sig"]
        real[ni, 10] = a["multi"]
        real[ni, 11] = a["conflict"]
        real[ni, 12] = 1
        real[ni, 13] = 1

    rng = np.random.default_rng(20261025)
    perm_parts = []
    for design, g2 in d.groupby("design"):
        g2 = g2.sort_values("relation_id").reset_index(drop=True)
        order = rng.permutation(len(g2))
        perm_parts.append(g2.iloc[order].assign(relation_id=g2.relation_id.values))
    dp = pd.concat(perm_parts, ignore_index=True)
    perm = np.zeros_like(real)
    perm[:, :3] = real[:, :3]
    perm_agg = aggregate(dp)
    for ni, a in perm_agg.items():
        perm[ni, 3] = a["cond"]
        perm[ni, 4] = a["suff"]
        perm[ni, 5] = a["infl"]
        perm[ni, 6] = a["det"]
        perm[ni, 7] = a["nin"]
        perm[ni, 8] = a["nvalid"]
        perm[ni, 9] = a["sig"]
        perm[ni, 10] = a["multi"]
        perm[ni, 11] = a["conflict"]
        perm[ni, 12] = 1
        perm[ni, 13] = 1
    np.save(FEAT / "r4_features_real.npy", real)
    np.save(FEAT / "r4_features_permuted.npy", perm)
    (FEAT / "r4_feature_columns.json").write_text(json.dumps(
        dict(columns=COLS, N=N, truth_signatures=sigs), ensure_ascii=False, indent=2),
        encoding="utf-8")
    print("features saved", real.shape, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
