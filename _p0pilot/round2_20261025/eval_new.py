"""Map round-2 graded targets to graph nodes and compare coverage/information."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import torch

ROOT = Path(_eqguard_path(''))
WORK = ROOT / "generate_trans/folds/hosts_bt31"
PT = WORK / "data/processed"
OUT = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_map_round2"
EXT = ROOT / "_p0pilot/round2_20261025/extraction"


def entropy(x: np.ndarray) -> float:
    v = x[x != 0]
    if v.size == 0:
        return 0.0
    _, c = np.unique(v, return_counts=True)
    p = c / c.sum()
    return float(-(p * np.log2(p)).sum())


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="graded_graded_main.csv")
    ap.add_argument("--tag", default="main")
    args = ap.parse_args()
    split = json.loads((WORK / "views.json").read_text(encoding="utf-8"))
    role_of_view = {v: r for r in ("train", "val", "test") for v in split[f"{r}_views"]}
    views = [v for r in ("train", "val", "test") for v in split[f"{r}_views"]]
    by_key = defaultdict(list)
    for v in views:
        p = v.split("__")
        by_key[(p[0], p[1], p[-1])].append(v)
    digest = {}

    def sha(p: Path):
        if str(p) not in digest:
            digest[str(p)] = (hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None)
        return digest[str(p)]

    meta = json.loads((WORK / "data/for_train/metadata_trans.json").read_text(encoding="utf-8"))
    fids = np.asarray(meta["file_ids"], dtype=object)
    vid, uniq_views = pd.factorize(fids, sort=False)
    vid = vid.astype(np.int32)
    del fids
    graph = torch.load(PT / "trans_graph.pt", map_location="cpu", weights_only=False, mmap=True)
    y = graph.y.numpy().reshape(-1) > 0
    trust = np.load(PT / "trust_trans.npy")
    edges = graph.edge_index.numpy()

    new = pd.read_csv(EXT / args.file, encoding="utf-8-sig")
    new = new[pd.to_numeric(new.get("n_patterns"), errors="coerce").fillna(0) > 0].copy()
    designs = sorted(new.design.dropna().unique())
    print("designs", designs, flush=True)

    attach = {}
    for d in designs:
        s = set()
        for _, r in new[new.design == d].iterrows():
            if isinstance(r.get("driver"), str) and r["driver"]:
                s.add(str(r["driver"]).lstrip("\\"))
            if isinstance(r.get("dff_cell"), str) and r["dff_cell"]:
                s.add(str(r["dff_cell"]).lstrip("\\"))
        attach[d] = s
    elig_idx = {}
    for d in designs:
        parts = Path(d).stem.split("__")
        ev = [v for v in by_key.get((parts[0], parts[1], parts[-1]), [])
              if sha(WORK / "trans" / f"{v}.v") == sha(WORK / "trans" / d)
              and sha(WORK / "trans" / d) is not None]
        elig_idx[d] = {i for i, v in enumerate(uniq_views) if str(v) in ev}
    node_hits = defaultdict(list)
    desired = set().union(*attach.values())
    with (PT / "node_names_trans.txt").open(encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= vid.size:
                break
            nm = line.strip().lstrip("\\")
            if nm in desired:
                node_hits[nm].append(i)
    hits = []
    for d in designs:
        for nm in attach[d]:
            for i in node_hits.get(nm, []):
                if int(vid[i]) in elig_idx[d]:
                    hits.append((d, i))
    hit_nodes = sorted({i for _, i in hits})
    print("mapped node count", len(hit_nodes), flush=True)

    support = np.zeros(len(vid), bool)
    support[hit_nodes] = True
    role = np.asarray([role_of_view.get(str(v), "unassigned") for v in uniq_views])
    rows, reached = [], support.copy()
    for h in range(3):
        for r in ("train", "val", "test"):
            m = role[vid] == r
            rows.append(dict(hops=h, role=r, nodes=int((reached & m).sum()),
                             positives=int((reached & y & m).sum()),
                             trusted_positives=int((reached & y & trust & m).sum()),
                             trusted_negatives=int((reached & ~y & trust & m).sum()),
                             denominator_positives=int((y & m).sum())))
        if h < 2:
            nxt = reached.copy()
            nxt[edges[1, reached[edges[0]]]] = True
            reached = nxt
    cov = pd.DataFrame(rows)
    cov.to_csv(OUT / f"new_receptive_field_{args.tag}.csv", index=False, encoding="utf-8-sig")
    print(cov.to_string(index=False), flush=True)

    old = pd.read_csv(ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sparse_sat_round1/"
                      "conditional_evidence.csv", encoding="utf-8-sig")
    comp = []
    for d in designs:
        o = old[old.source == Path(d).name]
        n = new[new.design == d]
        comp.append(dict(design=d, old_relations=len(o), new_relations=len(n),
                         old_targets=o.target.nunique(), new_targets=n.target.nunique(),
                         old_kinds=";".join(sorted(o.kind.unique())) if len(o) else "",
                         new_kinds=";".join(sorted(n.kind.unique())) if len(n) else "",
                         new_graded_pairs=len(n[["determinism", "influence_mean"]]
                                              .drop_duplicates()) if len(n) else 0))
    compdf = pd.DataFrame(comp)
    compdf.to_csv(OUT / f"new_vs_old_by_design_{args.tag}.csv", index=False, encoding="utf-8-sig")
    print(compdf.to_string(index=False), flush=True)

    stats = []
    for col in ("n_patterns", "n_feasible", "n_forced", "determinism",
                "influence_mean", "influence_max", "reach_po", "reach_dff"):
        v = pd.to_numeric(new[col], errors="coerce").dropna().to_numpy(float)
        stats.append(dict(column=col, n=len(v), unique=len(np.unique(v)), mean=v.mean(),
                          min=v.min(), max=v.max(), entropy=entropy(v)))
    pd.DataFrame(stats).to_csv(OUT / f"new_value_diversity_{args.tag}.csv", index=False,
                               encoding="utf-8-sig")
    print(pd.DataFrame(stats).to_string(index=False), flush=True)
    x = np.load(PT / "satrel_node_feats_sparseR1_real.npy", mmap_mode="r")
    info = dict(designs=designs, mapped_nodes=len(hit_nodes),
                mapped_by_role={r: int((support & (role[vid] == r)).sum())
                                for r in ("train", "val", "test")},
                overlap_with_old=int((support & (np.asarray(x[:, 6]) > 0)).sum()),
                n_targets=len(new), queries_used=144, wall_s=38.1)
    (OUT / f"new_manifest_{args.tag}.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(info, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
