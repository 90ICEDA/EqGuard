"""Incremental exposure: union(old, new) minus old, by role and hops."""
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
OUT = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_map_round2"


def main() -> int:
    split = json.loads((WORK / "views.json").read_text(encoding="utf-8"))
    role_of_view = {v: r for r in ("train", "val", "test") for v in split[f"{r}_views"]}
    meta = json.loads((WORK / "data/for_train/metadata_trans.json").read_text(encoding="utf-8"))
    fids = np.asarray(meta["file_ids"], dtype=object)
    vid, views = pd.factorize(fids, sort=False)
    vid = vid.astype(np.int32)
    role = np.asarray([role_of_view.get(str(v), "unassigned") for v in views])[vid]
    g = torch.load(PT / "trans_graph.pt", map_location="cpu", weights_only=False, mmap=True)
    y = g.y.numpy().reshape(-1) > 0
    edges = g.edge_index.numpy()
    old = np.asarray(np.load(PT / "satrel_node_feats_sparseR1_real.npy", mmap_mode="r")[:, 6]) > 0
    new = np.zeros(len(vid), bool)
    for t in ("new_receptive_field_main.csv", "new_receptive_field_val_ysid.csv"):
        pass
    # rebuild new support from graded target attaches via saved manifests is not enough;
    # use node ids recomputed by eval_new: read its manifest only has counts, so recompute
    # from the graded rows using the same rule.
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "ev", ROOT / "_p0pilot/round2_20261025/eval_new.py")
    # simpler: the eval script saved no ids; recompute directly here
    import hashlib
    from collections import defaultdict
    EXT = ROOT / "_p0pilot/round2_20261025/extraction"
    frames = [pd.read_csv(EXT / "graded_graded_main.csv", encoding="utf-8-sig"),
              pd.read_csv(EXT / "graded_graded_val_ysid.csv", encoding="utf-8-sig")]
    d = pd.concat(frames, ignore_index=True)
    d = d[pd.to_numeric(d["n_patterns"], errors="coerce").fillna(0) > 0]
    by_key = defaultdict(list)
    for v in views:
        p = str(v).split("__")
        by_key[(p[0], p[1], p[-1])].append(str(v))
    digest = {}

    def sha(p: Path):
        if str(p) not in digest:
            digest[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None
        return digest[str(p)]

    attach = defaultdict(set)
    for _, r in d.iterrows():
        for c in ("driver", "dff_cell"):
            if isinstance(r.get(c), str) and r[c]:
                attach[r["design"]].add(str(r[c]).lstrip("\\"))
    elig = {}
    for design in attach:
        p = Path(design).stem.split("__")
        ev = [v for v in by_key.get((p[0], p[1], p[-1]), [])
              if sha(WORK / "trans" / f"{v}.v") == sha(WORK / "trans" / design)]
        elig[design] = {i for i, v in enumerate(views) if str(v) in ev}
    desired = set().union(*attach.values())
    hits = defaultdict(list)
    with (PT / "node_names_trans.txt").open(encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= vid.size:
                break
            nm = line.strip().lstrip("\\")
            if nm in desired:
                hits[nm].append(i)
    for design, names in attach.items():
        for nm in names:
            for i in hits.get(nm, []):
                if int(vid[i]) in elig[design]:
                    new[i] = True

    def hop(support, h):
        r = support.copy()
        for _ in range(h):
            nxt = r.copy()
            nxt[edges[1, r[edges[0]]]] = True
            r = nxt
        return r

    rows = []
    for h in range(3):
        so, sn, su = hop(old, h), hop(new, h), hop(old | new, h)
        for r in ("train", "val", "test"):
            m = role == r
            rows.append(dict(hops=h, role=r,
                             old_pos=int((so & y & m).sum()),
                             new_pos=int((sn & y & m).sum()),
                             union_pos=int((su & y & m).sum()),
                             incremental_pos=int((su & y & m).sum() - (so & y & m).sum()),
                             incremental_nodes=int((su & m).sum() - (so & m).sum())))
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "incremental_exposure.csv", index=False, encoding="utf-8-sig")
    print(out.to_string(index=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
