"""Shared training/validation loading and one real no-update head gradient check."""
import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

OUT = Path(__file__).resolve().parent
VAL = OUT / "aux_driver_v2"
TRAIN = OUT.parent / "lcone_head_prep_20261112" / "all_eligible"


def read(p):
    return json.loads(p.read_text(encoding="utf-8"))


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def input_pair(path, expected):
    if sha(path) != expected:
        raise ValueError("asset_hash_mismatch")
    with np.load(path, allow_pickle=False) as z:
        result = {k: z[k] for k in z.files}
    b, c = result["B"], result["C"]
    assert b.shape == c.shape == (len(result["keys"]), 268)
    assert len(np.unique(result["keys"])) == len(result["keys"])
    assert np.isfinite(b).all() and np.isfinite(c).all()
    assert np.array_equal(b[:, :8], c[:, :8]) and not b[:, 8:].any()
    return result


def training_inputs():
    assets = read(TRAIN / "FEATURE_PREFLIGHT.json")
    data = input_pair(TRAIN / "BC_INPUT_SEED42_N_BEST.npz", assets["input_asset_sha256"])
    budget_path = TRAIN / "BC_BUDGET.json"
    assert sha(budget_path) == assets["budget_sha256"]
    budget = read(budget_path)["examples"]
    assert data["keys"].tolist() == [f"{r['view']}|{r['cone_id']}" for r in budget]
    y = np.array([r["label"] for r in budget], np.float32)
    assert set(np.unique(y)) == {0.0, 1.0}
    schedule = np.load(TRAIN / "COMMON_STEPS.npy", allow_pickle=False)
    frozen = read(TRAIN / "COMMON_STEPS.json")
    assert list(schedule.shape) == frozen["shape"]
    assert hashlib.sha256(schedule.tobytes()).hexdigest() == frozen["sha256"]
    for ids in schedule:
        selected = [budget[i] for i in ids]
        assert len({(r["source"], r["cone_id"]) for r in selected}) == len(ids)
        assert set(Counter((r["recipe"], r["label"]) for r in selected).values()) == {9}
    return data, y, schedule


def validation_inputs(point):
    reports = read(VAL / "VAL_PREFLIGHT.json")
    ref, = (r for r in reports["checkpoints"] if r["point"] == point)
    asset = input_pair(VAL / f"VAL_BC_SEED42_N_{point.upper()}.npz", ref["asset_sha256"])
    rows = read(VAL / "VAL_INVENTORY.json")
    known = [r for r in rows if r["feature_available"]]
    assert asset["keys"].tolist() == [f"{r['view']}|{r['cone_id']}" for r in known]
    assert np.all(np.diff(asset["ptr"]) > 0) and asset["ptr"][-1] == len(asset["members"])
    assert len(asset["ptr"]) == len(known) + 1
    return asset, rows


def head():
    return nn.Sequential(nn.Linear(268, 16), nn.ReLU(), nn.Linear(16, 1))


def main():
    training, labels, schedule = training_inputs()
    val = {p: validation_inputs(p) for p in ("best", "last")}
    assert set(training["keys"]).isdisjoint(val["best"][0]["keys"])
    assert np.array_equal(val["best"][0]["keys"], val["last"][0]["keys"])
    assert all(r["feature_available"] for r in val["best"][1])
    # Validate a rejection using the actual asset loader.
    try:
        input_pair(TRAIN / "BC_INPUT_SEED42_N_BEST.npz", "0" * 64)
    except ValueError as exc:
        assert str(exc) == "asset_hash_mismatch"
    else:
        raise AssertionError("hash mismatch accepted")
    ids = schedule[0]
    y = torch.as_tensor(labels[ids], device="cuda")
    by_arm = {}
    with torch.random.fork_rng(devices=[torch.cuda.current_device()]):
        torch.manual_seed(42)
        first = head().cuda().train()
        initial = {k: v.detach().clone() for k, v in first.state_dict().items()}
        for arm in ("B", "C"):
            h = head().cuda().train()
            h.load_state_dict(initial, strict=True)
            x = torch.as_tensor(training[arm][ids], device="cuda")
            logits = h(x).flatten()
            loss = F.binary_cross_entropy_with_logits(logits, y)
            grads = torch.autograd.grad(loss, tuple(h.parameters()))
            assert torch.isfinite(loss) and all(torch.isfinite(g).all() for g in grads)
            norm = float(torch.sqrt(sum(g.square().sum() for g in grads)))
            context_norm = float(torch.linalg.vector_norm(grads[0][:, 8:]))
            assert norm > 0 and (context_norm > 0 if arm == "C" else context_norm == 0)
            assert all(torch.equal(initial[k], v) for k, v in h.state_dict().items())
            assert all(p.grad is None for p in h.parameters())
            h.eval()
            with torch.inference_mode():
                assert torch.isfinite(h(torch.as_tensor(val["best"][0][arm], device="cuda"))).all()
            by_arm[arm] = dict(loss=float(loss.detach()), gradient_norm=norm, context_gradient_norm=context_norm,
                               state_unchanged=True, head_parameters=sum(p.numel() for p in h.parameters()))
    report = dict(passed=True, seed=42, encoder_snapshot="N_best", batch_size=len(ids), positives=int(y.sum()),
                  shared_rows_sha256=hashlib.sha256(ids.tobytes()).hexdigest(), arm=by_arm, optimizer_steps=0,
                  validation_rankable=len(val["best"][0]["keys"]), rejected_invalid_hash=True)
    with (VAL / "NO_UPDATE_GATE.json").open("x", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(report)


if __name__ == "__main__":
    main()
