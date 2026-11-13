"""Replicate the frozen B score head for seeds 1 and 2, validation only."""
import copy
import csv
import hashlib
import importlib.util
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
from torch.nn import functional as F

OUT = Path(__file__).resolve().parent
P = OUT.parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(P / "lcone_head_seed42_20261112"))
from run import full_results, macro, save_checkpoint, state_digest, validation_selection, views
from eval_gate import head, validation_inputs
from gate import TRAIN, VAL, sha, training_inputs
sys.path.insert(0, str(P / "control_signed_carrier_20261109_v3"))
import Signed_common as S
spec = importlib.util.spec_from_file_location("frozen_encoder", P / "control_best200_20261104/evaluate.py")
encoder_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(encoder_module)
Model = encoder_module.Model

BASE = P / "seed42_nc_ablation_20261109"
INPUT = P / "control_boundary_v3_20261104"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, obj):
    with path.open("x", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, allow_nan=False)


def stats(margin, members, driver, kind):
    m = margin[members]
    return (m.max(), np.quantile(m, .9), np.median(m), m.mean(), m.std(),
            margin[driver], math.log1p(len(members)), float(kind == "PO"))


def val_coordinates(meta):
    _, arrays, names, layouts = S.load_snapshot("val")
    keys = {(r["view"], r["cone_id"]) for r in meta}
    mappings = {v: S.view_rows(layouts, names, v) for v in {r["view"] for r in meta}}
    aux = defaultdict(dict)
    vmap = S.F / "data/derived_v2/bitwise_alias_20261029_v2/virtual_node_map.jsonl"
    with vmap.open(encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r["view"] in mappings:
                aux[r["view"]][r["name"]] = r["global_node"]
    indices = {}
    src = P / "seed42_supervised_prep_20261109/CONE_CACHE_V2.csv"
    with src.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            v = r["view"]
            key = v, r["cone_id"]
            if r["split"] != "val" or key not in keys:
                continue
            driver = mappings[v].get(r["driver"])
            is_aux = driver is None
            if is_aux:
                a = sorted(aux[v], key=aux[v].get)
                assert aux[v][r["driver"]] in {int(x) for x in r["aux_globals"].split("|") if x}
                driver = layouts[v]["physical_stop"] + a.index(r["driver"])
                assert driver < layouts[v]["stop"] and not arrays["physical"][driver]
            else:
                assert arrays["physical"][driver]
            indices[key] = driver, is_aux
    assert indices.keys() == keys
    assert all(indices[r["view"], r["cone_id"]][1] == r["auxiliary_driver"] for r in meta)
    return [indices[r["view"], r["cone_id"]][0] for r in meta], arrays


def val_features(asset, meta, drivers, margin):
    out = np.zeros((len(meta), 268), np.float32)
    for i, r in enumerate(meta):
        assert r["feature_row"] == i
        mem = asset["members"][asset["ptr"][i]:asset["ptr"][i+1]]
        out[i, :8] = stats(margin, mem, drivers[i], r["kind"])
    return out


def train_features(checkpoint, budget):
    _, _, _, layouts = S.load_snapshot("train")
    x = np.load(INPUT / "inputs/trans_train/x39.npy", mmap_mode="r")
    edge = np.load(INPUT / "inputs/trans_train/edge_index.npy", mmap_mode="r")
    with np.load(INPUT / "normalization.npz") as z:
        mean, std = z["mean"][25:], z["std"][25:]
    by_view = defaultdict(list)
    for i, r in enumerate(budget):
        by_view[r["view"]].append((i, r))
    encoder = Model().cuda().eval().requires_grad_(False)
    encoder.load_state_dict(torch.load(checkpoint, map_location="cuda", weights_only=True), strict=True)
    initial = state_digest(encoder.state_dict())
    result = np.zeros((len(budget), 268), np.float32)
    for v, rows in by_view.items():
        lo, hi = (layouts[v][k] for k in ("start", "stop"))
        ms = (lo <= edge[0]) & (edge[0] < hi)
        md = (lo <= edge[1]) & (edge[1] < hi)
        assert np.array_equal(ms, md)
        xv = np.array(x[lo:hi], dtype=np.float32, copy=True)
        xv[:, 25:] = np.clip((xv[:, 25:] - mean) / std, -10, 10)
        ev = np.asarray(edge[:, ms] - lo)
        with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
            lg = encoder(torch.as_tensor(xv, device="cuda"), torch.as_tensor(ev, device="cuda", dtype=torch.long))
        margin = (lg[:, 1].float() - lg[:, 0].float()).cpu().numpy()
        for i, r in rows:
            mem = np.asarray(r["member_rows"]) - lo
            assert np.all((mem >= 0) & (mem < layouts[v]["physical_stop"] - lo))
            drv = r["driver_row"] - lo
            assert drv in mem
            result[i, :8] = stats(margin, mem, drv, r["kind"])
    assert state_digest(encoder.state_dict()) == initial and np.isfinite(result).all()
    return result


def verify_baseline(rows, seed):
    old = {}
    path = P / "lcone_endpoint_dedup_20261112/VIEW_RESULTS_V2.csv"
    with path.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r["split"] == "val" and r["seed"] == str(seed) and r["arm"] == "N" and r["point"] == "best":
                old[r["view"], r["kind"], r["mode"], int(r["budget"])] = r
    n = 0
    for r in rows:
        stem, budget = r["setting"].rsplit("_", 1)
        mode = {"gates": "fixed_gate_cap", "recall": "equal_recall", "top": "same_units"}[stem]
        ref = old[r["view"], r["kind"], mode, int(budget)]
        tag = "raw" if r["policy"] == "endpoint" else "group"
        for k in ("gates", "units", "positive", "negative", "unknown"):
            assert int(ref[tag + "_" + k]) == r[k], (seed, r["view"], r["setting"], k)
        n += 1
    return n


def run_seed(seed, label, schedule, budget, val, meta, drivers, arrays, c42):
    folder = OUT / f"seed{seed}"
    folder.mkdir(exist_ok=False)
    ckpt = BASE / f"N_s{seed}_best.pt"
    scores_path = BASE / f"N_s{seed}_scores.npz"
    with np.load(scores_path, allow_pickle=False) as f:
        assert np.array_equal(f["y_val"], arrays["y"])
        assert np.array_equal(f["trust_val"], arrays["trusted"])
        margin = f["val_best"]
    vx_np = val_features(val, meta, drivers, margin)
    tx_np = train_features(ckpt, budget)
    assert np.isfinite(vx_np).all() and not tx_np[:, 8:].any() and not vx_np[:, 8:].any()
    bound = dict(val, B=vx_np)
    data = views(bound, meta, margin)
    a = full_results(data, vx_np[:, 0], "A", "frozen", 0)
    baseline_checks = verify_baseline(a, seed)
    asset_path = folder / "B_INPUTS.npz"
    with asset_path.open("xb") as f:
        np.savez_compressed(f, train=tx_np, val=vx_np, val_keys=val["keys"],
                            train_keys=np.array([f"{r['view']}|{r['cone_id']}" for r in budget]))
    contract = {k: c42[k] for k in ("updates_per_arm", "optimization_dtype", "optimizer",
                                    "lr", "weight_decay", "loss", "selection", "arm_B")}
    contract.update(seed=seed, frozen_encoder_sha256=sha(ckpt), frozen_A_predictions_sha256=sha(scores_path),
                    input_sha256=sha(asset_path), schedule_sha256=sha(TRAIN / "COMMON_STEPS.npy"),
                    labels_sha256=sha(TRAIN / "BC_BUDGET.json"), baseline_checks=baseline_checks,
                    confirmation_prediction_reads=0, solver_calls=0)
    write(folder / "RUN_CONTRACT.json", contract)
    torch.manual_seed(seed)
    model = head().cuda()
    init = state_digest(model.state_dict())
    opt = torch.optim.Adam(model.parameters(), lr=c42["lr"], weight_decay=c42["weight_decay"])
    tx = torch.as_tensor(tx_np, device="cuda")
    vx = torch.as_tensor(vx_np, device="cuda")
    y = torch.as_tensor(label, device="cuda")
    logs, high = [], -1.0
    for step, ids_np in enumerate(schedule, 1):
        model.train()
        opt.zero_grad(set_to_none=True)
        ids = torch.as_tensor(ids_np, device="cuda")
        loss = F.binary_cross_entropy_with_logits(model(tx[ids]).flatten(), y[ids])
        assert torch.isfinite(loss)
        loss.backward()
        grads = [p.grad for p in model.parameters()]
        assert all(g is not None and torch.isfinite(g).all() for g in grads)
        assert not grads[0][:, 8:].count_nonzero()
        gn = float(torch.sqrt(sum(g.square().sum() for g in grads)))
        assert gn > 0
        opt.step()
        assert all(torch.isfinite(p).all() for p in model.parameters())
        row = dict(step=step, loss=float(loss.detach()), grad_norm=gn, positive=int(y[ids].sum()),
                   rows_sha256=hashlib.sha256(ids_np.tobytes()).hexdigest(), val_D_recall_512=None)
        if step % 5 == 0:
            model.eval()
            with torch.inference_mode():
                pred = model(vx).flatten().cpu().numpy()
            assert np.isfinite(pred).all()
            selection = validation_selection(data, pred)
            row["val_D_recall_512"] = selection
            if selection > high:
                high, best_step, best_pred = selection, step, pred.copy()
                best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
                best_opt = copy.deepcopy(opt.state_dict())
                best_rng = dict(cpu=torch.get_rng_state(), cuda=torch.cuda.get_rng_state())
            print(f"B seed{seed} step={step} val_D_512={selection:.6f}", flush=True)
        logs.append(row)
    assert step == 50 and len(logs) == 50
    rng = dict(cpu=torch.get_rng_state(), cuda=torch.cuda.get_rng_state())
    save_checkpoint(folder / "last.pt", model, opt, 50, selection, rng)
    model.load_state_dict(best_state, strict=True)
    opt.load_state_dict(best_opt)
    save_checkpoint(folder / "best.pt", model, opt, best_step, high, best_rng)
    with (folder / "VAL_SCORES.npz").open("xb") as f:
        np.savez_compressed(f, keys=val["keys"], best=best_pred, last=pred)
    results = a + full_results(data, best_pred, "B", "best", best_step) + full_results(data, pred, "B", "last", 50)
    with (folder / "VAL_BY_VIEW.csv").open("x", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0]))
        w.writeheader()
        w.writerows(results)
    write(folder / "VAL_SUMMARY.json", macro(results))
    write(folder / "RUN_LOG.json", logs)
    write(folder / "RUN_STATUS.json", dict(seed=seed, steps=50, init_sha256=init,
                                         best_step=best_step, best_D_recall_512=high, last_D_recall_512=selection,
                                         best_sha256=sha(folder / "best.pt"), last_sha256=sha(folder / "last.pt"),
                                         val_predictions_sha256=sha(folder / "VAL_SCORES.npz"),
                                         confirmation_prediction_reads=0, solver_calls=0))


def main():
    assert torch.cuda.is_available() and "ginvenv_gpu" in sys.executable.lower()
    frozen_train, labels, schedule = training_inputs()
    val, meta = validation_inputs("best")
    drivers, arrays = val_coordinates(meta)
    c42 = read(P / "lcone_head_seed42_20261112/RUN_CONTRACT.json")
    budget = read(TRAIN / "BC_BUDGET.json")["examples"]
    assert schedule.shape == (50, 54) and len(budget) == len(frozen_train["B"])
    with np.load(BASE / "N_scores.npz") as z:
        assert np.array_equal(val_features(val, meta, drivers, z["val_best"]), val["B"])
    for seed in (1, 2):
        run_seed(seed, labels, schedule, budget, val, meta, drivers, arrays, c42)


if __name__ == "__main__":
    main()
