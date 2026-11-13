"""Post-freeze diagnostic: label coverage of the frozen round-5 candidates."""
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
PT = ROOT / "generate_trans/folds/hosts_bt31/data/processed"
TAB5 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_nonlocal_round5"


def main() -> int:
    plan = json.loads((TAB5 / "r5_candidate_plan.json").read_text(encoding="utf-8"))
    nodes = pd.read_csv(TAB5 / "r5_nodes.csv", encoding="utf-8-sig")
    g = torch.load(PT / "trans_graph.pt", map_location="cpu",
                   weights_only=False, mmap=True)
    y = g.y.numpy().reshape(-1) > 0
    trust = np.load(PT / "trust_trans.npy")
    rid_nodes = nodes.groupby("relation_id").node_index.apply(
        lambda s: sorted(set(int(x) for x in s))).to_dict()
    rows = []
    for r in plan["frozen"]:
        rid = f"r5|{r['design']}|{r['target']}"
        ids = rid_nodes.get(rid, [])
        rows.append(dict(relation_id=rid, design=r["design"], host=r["host"],
                         role=r["role"], usage=r["usage"], kind=r["kind"],
                         target=r["target"], cut_size=len(r["cut"]),
                         nodes=len(ids),
                         positives=int(sum(y[i] for i in ids)),
                         trusted_pos=int(sum(y[i] and trust[i] for i in ids)),
                         trusted_neg=int(sum((not y[i]) and trust[i] for i in ids))))
    d = pd.DataFrame(rows)
    d.to_csv(TAB5 / "r5_candidate_coverage.csv", index=False, encoding="utf-8-sig")
    print(d.groupby(["role", "usage"]).agg(
        relations=("relation_id", "size"), nodes=("nodes", "sum"),
        positives=("positives", "sum")).to_string(), flush=True)
    print("total nodes", int(d.nodes.sum()), "positives", int(d.positives.sum()),
          flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
