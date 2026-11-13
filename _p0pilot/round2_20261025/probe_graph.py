"""Probe graph metadata, masks, edge direction convention, and feature shapes."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path
import json
from pathlib import Path
import numpy as np
import torch

PT = Path(_eqguard_path('generate_trans/folds/hosts_bt31/data/processed'))
g = torch.load(PT / "trans_graph.pt", map_location="cpu", weights_only=False, mmap=True)
print("type", type(g))
print("keys", list(g.keys()) if hasattr(g, "keys") else dir(g)[:30])
for k in ("x", "y", "edge_index"):
    v = getattr(g, k, None)
    if v is not None:
        print(k, type(v), tuple(v.shape), v.dtype)
ei = g.edge_index
print("edge_index min/max", int(ei.min()), int(ei.max()))
# self loops?
print("self loops", int((ei[0] == ei[1]).sum()))
y = g.y.numpy().reshape(-1)
print("y sum", int((y > 0).sum()), "n", y.size)
for k in ("train_mask", "val_mask", "test_mask"):
    v = getattr(g, k, None)
    if v is not None:
        print(k, int(v.sum()))
print("has edge_type", hasattr(g, "edge_type"))
print("num_edges", ei.shape[1])
# Check direction: how many edges src has out-degree vs in-degree
src = ei[0].numpy(); dst = ei[1].numpy()
print("unique src", np.unique(src).size, "unique dst", np.unique(dst).size)
# sample: does src or dst look like high-fanout net?
print("sample edges", ei[:, :8].numpy().tolist())
meta = json.loads((PT / "dataset_meta.json").read_text(encoding="utf-8"))
print("dataset_meta keys", list(meta.keys())[:20])
nm = json.loads((PT / "node_meta_trans.json").read_text(encoding="utf-8"))
print("node_meta_trans", nm)
t = np.load(PT / "trust_trans.npy")
print("trust", t.shape, t.dtype, float(t.mean()), int(t.sum()))
