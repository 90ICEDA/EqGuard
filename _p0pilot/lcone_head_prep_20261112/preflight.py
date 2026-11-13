"""Frozen encoder inference and shared B/C input audit. No optimizer or backward."""
import argparse
import hashlib
import json
import math
import sys
from collections import defaultdict, deque
from pathlib import Path

import numpy as np
import torch

OUT = Path(__file__).resolve().parent
P = OUT.parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(P / "lcone_endpoint_frozen_20261112"))
from audit import S, endpoints
sys.path.insert(0, str(P / "control_best200_20261104"))
from evaluate import Model


def depths(net, start):
    distance = {start: 0}
    pending = deque([start])
    while pending:
        node = pending.popleft()
        for prev in net["pred"].get(node, set()):
            typ = net["pins"][prev][0]
            if prev not in distance and "DFF" not in typ:
                distance[prev] = distance[node] + 1
                pending.append(prev)
    return distance


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset", type=Path, default=OUT / "all_eligible")
    args = parser.parse_args()
    folder = args.asset
    budget_path = folder / "BC_BUDGET.json"
    budget = S.read(budget_path)
    _, arrays, names, views = S.load_snapshot("train")
    in_root = P / "control_boundary_v3_20261104"
    x = np.load(in_root / "inputs/trans_train/x39.npy", mmap_mode="r")
    edge = np.load(in_root / "inputs/trans_train/edge_index.npy", mmap_mode="r")
    with np.load(in_root / "normalization.npz") as z:
        mean, std = z["mean"][25:], z["std"][25:]
    checkpoint = P / "seed42_nc_ablation_20261109/N_best.pt"
    model = Model().cuda().eval()
    model.load_state_dict(torch.load(checkpoint, weights_only=True, map_location="cuda"), strict=True)
    model.requires_grad_(False)
    before = {k: v.detach().clone() for k, v in model.state_dict().items()}
    examples = defaultdict(list)
    for i, row in enumerate(budget["examples"]):
        examples[row["view"]].append((i, row))
    n = budget["count"]
    b_features = np.zeros((n, 268), np.float32)
    c_features = np.zeros_like(b_features)
    used = np.zeros(n, bool)
    captures = []
    hook = model.classifier.register_forward_pre_hook(lambda _, args: captures.append(args[0].detach()))
    for view, indexed in examples.items():
        lay = views[view]
        lo, hi = lay["start"], lay["stop"]
        assert 0 <= lo < hi <= len(x)
        src, dst = (lo <= edge[0]) & (edge[0] < hi), (lo <= edge[1]) & (edge[1] < hi)
        assert np.array_equal(src, dst), (view, "cross_view_edge")
        xv = np.array(x[lo:hi], dtype=np.float32, copy=True)
        xv[:, 25:] = np.clip((xv[:, 25:] - mean) / std, -10, 10)
        ev = np.asarray(edge[:, src] - lo)
        with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
            lg = model(torch.as_tensor(xv, device="cuda"), torch.as_tensor(ev, device="cuda", dtype=torch.long))
        assert len(captures) == 1
        h = captures.pop().float().cpu().numpy()
        margin = (lg[:, 1].float() - lg[:, 0].float()).cpu().numpy()
        assert h.shape == (hi - lo, 64) and np.isfinite(h).all() and np.isfinite(margin).all()
        net = endpoints(S.F / "trans" / f"{view}.v")[0]
        mapping = S.view_rows(views, names, view)
        reverse = {v: k for k, v in mapping.items()}
        for i, r in indexed:
            mem = np.asarray(r["member_rows"])
            local = mem - lo
            drv = r["driver_row"]
            assert drv == mapping[r["driver"]] and drv in mem
            assert np.all((local >= 0) & (local < hi - lo)) and np.all(arrays["physical"][mem])
            dist = depths(net, r["driver"])
            dd = np.array([dist[reverse[g]] for g in mem])
            m = margin[local]
            stats = [m.max(), np.quantile(m, .9), np.median(m), m.mean(), m.std(),
                     margin[drv-lo], math.log1p(len(mem)), float(r["kind"] == "PO")]
            bands = (dd == 0, dd == 1, (dd >= 2) & (dd <= 3), dd >= 4)
            assert np.all(sum(bands) == 1) and int(bands[0].sum()) == 1
            pooled = [h[local[band]].mean(0) if band.any() else np.zeros(64) for band in bands]
            b_features[i, :8] = stats
            c_features[i] = np.concatenate([stats, *pooled, [float(k.any()) for k in bands]])
            used[i] = True
    hook.remove()
    assert used.all() and np.array_equal(b_features[:, :8], c_features[:, :8])
    assert np.isfinite(b_features).all() and np.isfinite(c_features).all()
    assert all(torch.equal(before[k], v) for k, v in model.state_dict().items())
    assert all(v.grad is None for v in model.parameters())
    assert np.count_nonzero(c_features[:, 8:]) and not np.count_nonzero(b_features[:, 8:])
    # Actual matched head dimensions and shared initialization; forward only.
    torch.manual_seed(42)
    head_b = torch.nn.Sequential(torch.nn.Linear(268, 16), torch.nn.ReLU(), torch.nn.Linear(16, 1)).eval()
    head_c = torch.nn.Sequential(torch.nn.Linear(268, 16), torch.nn.ReLU(), torch.nn.Linear(16, 1)).eval()
    head_c.load_state_dict(head_b.state_dict())
    with torch.inference_mode():
        assert torch.isfinite(head_b(torch.from_numpy(b_features))).all()
        assert torch.isfinite(head_c(torch.from_numpy(c_features))).all()
    asset = folder / "BC_INPUT_SEED42_N_BEST.npz"
    with asset.open("xb") as f:
        np.savez_compressed(f, B=b_features, C=c_features,
                            keys=np.array([f"{r['view']}|{r['cone_id']}" for r in budget["examples"]]))
    report = dict(pass_seed42_N_best=True, examples=n, actual_graph_views=len(examples),
                  encoder_state_unchanged=True, feature_dim_B_active=8, feature_dim_C=268,
                  head_parameters=sum(p.numel() for p in head_b.parameters()), training_updates=0,
                  solver_calls=0, input_asset_sha256=S.sha(asset), budget_sha256=S.sha(budget_path),
                  checkpoint_sha256=S.sha(checkpoint))
    with (folder / "FEATURE_PREFLIGHT.json").open("x", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(report)


if __name__ == "__main__":
    main()
