"""First A/B scoring of the frozen, single-source injdelta confirmation panel."""
import csv
import importlib.util
import json
import math
import statistics as st
import sys
from pathlib import Path

import numpy as np
import torch

OUT = Path(__file__).resolve().parent
P = OUT.parent
ASSETS = P / "lcone_confirmation_assets_20261112"
sys.dont_write_bytecode = True
sys.path.insert(0, str(P / "lcone_head_protocol_20261112"))
from eval_gate import evaluate_view, head
from gate import sha

spec = importlib.util.spec_from_file_location("frozen_encoder", P / "control_best200_20261104/evaluate.py")
encoder_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(encoder_module)
Model = encoder_module.Model


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    with path.open("x", encoding="utf-8") as f:
        json.dump(value, f, indent=2, allow_nan=False)


def models(seed):
    historical = P / "lcone_head_seed42_20261112"
    base = P / "seed42_nc_ablation_20261109"
    if seed == 42:
        enc = base / "N_best.pt"
        cfg = read(historical / "RUN_CONTRACT.json")
        enc_hash = next(v for k, v in cfg["assets"].items() if Path(k).name == enc.name)
        folder = historical / "B"
        b = read(historical / "RUN_STATUS.json")["checkpoints"]["B"]
    else:
        enc = base / f"N_s{seed}_best.pt"
        folder = P / "lcone_head_b_multiseed_20261112" / f"seed{seed}"
        enc_hash = read(folder / "RUN_CONTRACT.json")["frozen_encoder_sha256"]
        b = read(folder / "RUN_STATUS.json")
    assert sha(enc) == enc_hash
    for point in ("best", "last"):
        assert sha(folder / f"{point}.pt") == b[f"{point}_sha256"]
    return enc, folder, b


def load_view(r):
    folder = ASSETS / r["view"]
    a, m = folder / "GRAPH_ENDPOINTS.npz", folder / "ENDPOINTS.json"
    assert sha(a) == r["graph_sha256"] and sha(m) == r["endpoint_sha256"]
    with np.load(a, allow_pickle=False) as f:
        graph = {k: f[k] for k in f.files}
    meta = [x for x in read(m) if x["rankable"] and x["kind"] == "D"]
    assert len(meta) == 1180 and len({x["endpoint"] for x in meta}) == len(meta)
    assert sorted(x["endpoint"] for x in meta if x["status"] == "positive") == ["DFF_18_Q_reg", "DFF_19_Q_reg"]
    return graph, meta


def aggregate(rows):
    by_view = {}
    for v in sorted({r["view"] for r in rows}):
        for policy in ("endpoint", "fixed_group"):
            for point in ("best", "last"):
                for setting in ("gates_512", "recall_100"):
                    a, b = [], []
                    for seed in (42, 1, 2):
                        def one(arm, stage):
                            r, = [r for r in rows if r["view"] == v and r["policy"] == policy and r["point"] == stage
                                  and r["arm"] == arm and r["seed"] == seed and r["setting"] == setting]
                            return r
                        a.append(one("A", "frozen"))
                        b.append(one("B", point))
                    columns = ("recall", "negative", "gates", "unknown", "units")
                    by_view["|".join((v, policy, point, setting))] = {
                        k: dict(A=[r[k] for r in a], B=[r[k] for r in b],
                                delta=[rb[k]-ra[k] for ra, rb in zip(a, b)],
                                A_mean=st.mean(r[k] for r in a), B_mean=st.mean(r[k] for r in b))
                        for k in columns
                    }
    return by_view


def main():
    assert torch.cuda.is_available() and "ginvenv_gpu" in sys.executable.lower()
    graph_manifest = ASSETS / "GRAPH_REPORT.json"
    meta = read(graph_manifest)
    gate = read(ASSETS / "LOAD_GATE.json")
    assert len(meta["views"]) == len(gate["loaded"]) == 4
    assert gate["predictions_read"] == 0 and len({r["source"] for r in meta["views"]}) == 1
    norm = P / "control_boundary_v3_20261104/normalization.npz"
    with np.load(norm) as f:
        mean, std = f["mean"][25:], f["std"][25:]
    ckpts = {s: models(s) for s in (42, 1, 2)}
    write(OUT / "CONTRACT.json", dict(seed_order=[42, 1, 2], encoder="N_best per seed", head_selection="saved validation selection",
                                     group="A argmax physical node per seed and view; min row on ties",
                                     scope="one independent source; D-only; no further model selection",
                                     budget_512="physical gate union of score-ordered prefix; no skipping",
                                     equal_recall="all certified D positives, include score ties",
                                     manifest_sha256=sha(graph_manifest), normalization_sha256=sha(norm),
                                     checkpoints={str(s): {str(p.relative_to(P)): sha(p) for p in
                                                           (enc, folder / "best.pt", folder / "last.pt")}
                                                  for s, (enc, folder, _) in ckpts.items()}))
    rows = []
    for seed, (enc, folder, binfo) in ckpts.items():
        encoder = Model().cuda().eval().requires_grad_(False)
        encoder.load_state_dict(torch.load(enc, map_location="cuda", weights_only=True), strict=True)
        bh = {}
        for point in ("best", "last"):
            m = head().cuda().eval().requires_grad_(False)
            saved = torch.load(folder / f"{point}.pt", map_location="cuda", weights_only=True)
            assert saved["step"] == (binfo["best_step"] if point == "best" else 50)
            m.load_state_dict(saved["state"], strict=True)
            bh[point] = m
        for record in meta["views"]:
            view = record["view"]
            graph, entries = load_view(record)
            x = graph["x39"].copy()
            x[:, 25:] = np.clip((x[:, 25:] - mean) / std, -10, 10)
            with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
                lg = encoder(torch.as_tensor(x, device="cuda"),
                             torch.as_tensor(graph["edge_index"], device="cuda", dtype=torch.long)).float()
            margin = (lg[:, 1] - lg[:, 0]).cpu().numpy()
            assert len(margin) == len(x) and np.isfinite(margin).all()
            group, anchor = {}, {}
            features = np.zeros((len(entries), 268), np.float32)
            for i, row in enumerate(entries):
                j = row["packed_index"]
                mem = graph["members"][graph["ptr"][j]:graph["ptr"][j+1]]
                assert np.all(graph["physical"][mem])
                driver = row["driver_row"]
                assert driver in mem
                values = margin[mem]
                top = float(values.max())
                anchor[row["endpoint"]] = int(mem[values == top].min())
                group[row["endpoint"]] = row["status"], mem
                features[i, :8] = (top, np.quantile(values, .9), np.median(values), values.mean(), values.std(),
                                    margin[driver], math.log1p(len(mem)), 0)
            logits = {("A", "frozen"): features[:, 0]}
            with torch.inference_mode():
                xx = torch.as_tensor(features, device="cuda")
                for point, model in bh.items():
                    logits["B", point] = model(xx).flatten().cpu().numpy()
            assert all(np.isfinite(v).all() for v in logits.values())
            path = OUT / f"{view}_s{seed}_SCORES.npz"
            with path.open("xb") as f:
                np.savez_compressed(f, endpoint=np.array(list(group)), margin=margin,
                                    A=logits["A", "frozen"], B_best=logits["B", "best"], B_last=logits["B", "last"])
            for (arm, point), logit in logits.items():
                values = dict(zip(group, map(float, logit)))
                result = evaluate_view(group, values, anchor, (512,))
                for policy, metrics in result.items():
                    for setting in ("gates_512", "recall_100"):
                        c = metrics[setting]
                        rows.append(dict(seed=seed, view=view, recipe=view.split("__ys_")[-1],
                                         keep="keepcur" if "__keepcur__" in view else "keepnone",
                                         arm=arm, point=point, policy=policy, setting=setting,
                                         recall=c["positive"]/2, fpr=c["negative"]/574, **c))
            print(seed, view, "evaluated", flush=True)
    with (OUT / "BY_VIEW.csv").open("x", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    assert len(rows) == 144
    write(OUT / "SUMMARY.json", dict(results=aggregate(rows), seeds=[42, 1, 2], views=4, independent_sources=1,
                                    optimizer_steps=0, solver_calls=0))


if __name__ == "__main__":
    main()
