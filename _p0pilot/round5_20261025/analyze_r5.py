"""Round-5 coverage, information and real/permuted feature diff."""
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


def hops(s, e, h):
    r = s.copy()
    for _ in range(h):
        n = r.copy()
        n[e[1, r[e[0]]]] = True
        r = n
    return r


def main() -> int:
    split = json.loads((WORK / "views.json").read_text(encoding="utf-8"))
    role_of_view = {v: r for r in ("train", "val") for v in split[f"{r}_views"]}
    meta = json.loads((WORK / "data/for_train/metadata_trans.json").read_text(encoding="utf-8"))
    fids = np.asarray(meta["file_ids"], dtype=object)
    vid, views = pd.factorize(fids, sort=False)
    role = np.asarray([role_of_view.get(str(v), "other") for v in views])[vid]
    g = torch.load(PT / "trans_graph.pt", map_location="cpu", weights_only=False, mmap=True)
    y = g.y.numpy().reshape(-1) > 0
    trust = np.load(PT / "trust_trans.npy")
    edges = g.edge_index.numpy()
    old = np.asarray(np.load(PT / "satrel_node_feats_sparseR1_real.npy", mmap_mode="r")[:, 6]) > 0

    nodes = pd.read_csv(TAB5 / "r5_nodes.csv", encoding="utf-8-sig")
    node_idx = np.unique(nodes.node_index.to_numpy())
    support = np.zeros(len(vid), bool)
    support[node_idx] = True
    tv = np.isin(role, ["train", "val"])
    rows = []
    for r in ("train", "val"):
        m = tv & (role == r)
        s = support & m
        rows.append(dict(role=r, nodes=int(s.sum()), positives=int((s & y).sum()),
                         trusted_pos=int((s & y & trust).sum()),
                         trusted_neg=int((s & ~y & trust).sum()),
                         old_overlap=int((s & old & m).sum()),
                         net_new=int((s & ~old & m).sum()),
                         union_with_old=int(((s | old) & m).sum())))
    cov = pd.DataFrame(rows)
    cov.to_csv(TAB5 / "r5_coverage.csv", index=False, encoding="utf-8-sig")
    print(cov.to_string(index=False), flush=True)
    inc = []
    for h in range(3):
        su, so = hops(support & tv, edges, h), hops(old & tv, edges, h)
        for r in ("train", "val"):
            m = tv & (role == r)
            inc.append(dict(hops=h, role=r,
                            new_pos=int((su & y & m).sum()),
                            old_pos=int((so & y & m).sum()),
                            incremental=int(((su | so) & y & m).sum() - (so & y & m).sum())))
    pdf = pd.DataFrame(inc)
    pdf.to_csv(TAB5 / "r5_receptive_field.csv", index=False, encoding="utf-8-sig")
    print(pdf.to_string(index=False), flush=True)

    real = np.load(FEAT / "r5_extra_real.npy", mmap_mode="r")
    perm = np.load(FEAT / "r5_extra_permuted.npy", mmap_mode="r")
    cols = json.loads((FEAT / "r5_feature_columns.json").read_text(encoding="utf-8"))["columns"]
    ev = support & tv
    dcols = []
    for j, c in enumerate(cols):
        dcols.append(dict(column=c, changed=int(((real[:, j] != perm[:, j]) & ev).sum())))
    pd.DataFrame(dcols).to_csv(TAB5 / "r5_feature_diff_columns.csv", index=False,
                               encoding="utf-8-sig")
    changed = ((real[:, 3:18] != perm[:, 3:18]).any(axis=1)) & ev
    cs = changed.copy()
    diff = dict(changed_nodes=int(changed.sum()),
                changed_1hop=int(hops(cs, edges, 1).sum()),
                changed_2hop=int(hops(cs, edges, 2).sum()),
                covered_last_column=int(real[:, -1].sum()),
                shape=list(real.shape), min=float(real.min()), max=float(real.max()),
                structure_columns_in_base="unchanged (extra array only)")
    (TAB5 / "r5_feature_diff.json").write_text(
        json.dumps(diff, ensure_ascii=False, indent=2), encoding="utf-8")
    print(diff, flush=True)

    info = []
    for j, c in enumerate(cols):
        v = np.asarray(real[:, j])[ev]
        u = np.unique(v)
        info.append(dict(column=c, n=int(len(v)), unique=int(len(u)),
                         values=";".join(f"{x:g}" for x in u[:10])))
    idf = pd.DataFrame(info)
    idf.to_csv(TAB5 / "r5_info_columns.csv", index=False, encoding="utf-8-sig")
    print(idf.to_string(index=False), flush=True)
    mat = np.asarray(real[:, :19])[ev]
    combos = pd.Series([tuple(r) for r in mat]).value_counts()
    info2 = dict(evidence_nodes=int(ev.sum()),
                 positives=int((support & y & tv).sum()),
                 net_new=int((support & ~old & tv).sum()),
                 overlap=int((support & old & tv).sum()),
                 joint_combinations=int(len(combos)),
                 top_combination_share=float(combos.iloc[0] / combos.sum()),
                 feature_diff=diff,
                 no_permutation_designs=json.loads(
                     (FEAT / "r5_feature_columns.json").read_text(
                         encoding="utf-8"))["no_valid_permutation_designs"])
    (TAB5 / "r5_eval_manifest.json").write_text(
        json.dumps(info2, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(info2, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
