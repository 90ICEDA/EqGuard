"""Final numbers for the round-2 report."""
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

ROOT = Path(_eqguard_path(''))
PT = ROOT / "generate_trans/folds/hosts_bt31/data/processed"
OLD = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sparse_sat_round1"
OUT = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_map_round2"


def main() -> int:
    ev = pd.read_csv(OLD / "conditional_evidence.csv", encoding="utf-8-sig")
    split = json.loads((ROOT / "generate_trans/folds/hosts_bt31/views.json")
                       .read_text(encoding="utf-8"))
    role = {v: r for r in ("train", "val", "test") for v in split[f"{r}_views"]}
    ev["role"] = ev.source.map(lambda s: role.get(s.replace(".v", ""), "unassigned"))
    g = ev.groupby("role").agg(relations=("target", "size"),
                               unique_targets=("target", "nunique"),
                               unique_drivers=("driver", "nunique"))
    print(g.to_string(), flush=True)

    x = np.load(PT / "satrel_node_feats_sparseR1_real.npy", mmap_mode="r")
    meta = json.loads((ROOT / "generate_trans/folds/hosts_bt31/data/for_train/"
                       "metadata_trans.json").read_text(encoding="utf-8"))
    fids = np.asarray(meta["file_ids"], dtype=object)
    vid, views = pd.factorize(fids, sort=False)
    nrole = np.asarray([role.get(str(v), "unassigned") for v in views])
    nr = nrole[vid]
    ev_mask = np.asarray(x[:, 6]) > 0
    rows = []
    for r in ("train", "val", "test"):
        m = ev_mask & (nr == r)
        sub = np.asarray(x[m][:, 2:6])
        if len(sub) == 0:
            continue
        pat, cnt = np.unique(sub, axis=0, return_counts=True)
        top = np.argsort(-cnt)[:4]
        rows.append(dict(role=r, nodes=int(m.sum()),
                         distinct_patterns=int(len(pat)),
                         modal_pattern=";".join(f"{v:g}" for v in pat[top[0]]),
                         modal_share=float(cnt[top[0]] / cnt.sum()),
                         second_pattern=";".join(f"{v:g}" for v in pat[top[1]])
                         if len(top) > 1 else "",
                         second_share=float(cnt[top[1]] / cnt.sum()) if len(top) > 1 else 0.0))
    print(pd.DataFrame(rows).to_string(index=False), flush=True)

    # strong evidence: both patterns forced and different (joint change = 1)
    for r in ("train", "val", "test"):
        m = ev_mask & (nr == r)
        sub = np.asarray(x[m][:, 2:6])
        jc = int((sub[:, 2] > 0).sum()) if len(sub) else 0
        print(r, "nodes", int(m.sum()), "joint_change", jc,
              "forced_one_gt0", int((sub[:, 3] > 0).sum()) if len(sub) else 0, flush=True)

    # old feature columns: value distributions (train mapped nodes)
    for j, name in enumerate(["forced_pattern_fraction", "feasible_pattern_fraction",
                              "tested_joint_change_ratio", "forced_one_fraction"]):
        v = np.asarray(x[:, 2 + j])[ev_mask & (nr == "train")]
        u, c = np.unique(v, return_counts=True)
        print(name, dict(zip([f"{z:g}" for z in u], c.tolist())), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
