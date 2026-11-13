"""Recompute the main validation metrics and verify saved step contracts."""
import csv
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch

OUT = Path(__file__).resolve().parent
P = OUT.parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(P / "lcone_head_gate_20261112"))
from gate import TRAIN, head, sha, training_inputs, validation_inputs


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    contract, status, logs = (read(OUT / name) for name in ("RUN_CONTRACT.json", "RUN_STATUS.json", "RUN_LOG.json"))
    assert all(sha(P / name) == digest for name, digest in contract["assets"].items())
    train, y, steps = training_inputs()
    val, inventory = validation_inputs("best")
    rows = defaultdict(list)
    for r in inventory:
        i = r["feature_row"]
        mem = val["members"][val["ptr"][i]:val["ptr"][i+1]]
        rows[r["view"], r["kind"]].append((r["cone_id"], r["status"], mem, i))
    with np.load(P / "seed42_nc_ablation_20261109/N_scores.npz") as z:
        anchor = z["val_best"]
    scores = {("A", "frozen"): val["B"][:, 0]}
    replay_errors = {}
    for arm in ("B", "C"):
        hist = [r for r in logs if r["arm"] == arm]
        assert [r["step"] for r in hist] == list(range(1, 51))
        for r, indices in zip(hist, steps):
            assert r["rows_sha256"] == hashlib.sha256(indices.tobytes()).hexdigest()
            assert int(y[indices].sum()) == r["positive"] == 27
        evaluated = [r for r in hist if r["val_D_recall_512"] is not None]
        chosen = max(evaluated, key=lambda r: r["val_D_recall_512"])
        assert chosen["step"] == status["checkpoints"][arm]["best_step"]
        with np.load(OUT / arm / "VAL_SCORES.npz") as z:
            assert np.array_equal(z["keys"], val["keys"])
            for point, step in (("best", chosen["step"]), ("last", 50)):
                path = OUT / arm / f"{point}.pt"
                assert sha(path) == status["checkpoints"][arm][f"{point}_sha256"]
                checkpoint = torch.load(path, weights_only=True, map_location="cuda")
                assert checkpoint["step"] == step
                assert {int(x["step"]) for x in checkpoint["optimizer"]["state"].values()} == {step}
                model = head().cuda().eval()
                model.load_state_dict(checkpoint["state"], strict=True)
                with torch.inference_mode():
                    again = model(torch.as_tensor(val[arm], device="cuda")).flatten().cpu().numpy()
                scores[arm, point] = z[point]
                replay_errors[f"{arm}_{point}"] = float(np.max(np.abs(again - z[point])))
                assert replay_errors[f"{arm}_{point}"] <= 1e-6
    with (OUT / "VAL_BY_VIEW.csv").open(encoding="utf-8-sig", newline="") as f:
        csv_map = {(r["arm"], r["point"], r["view"], r["kind"], r["policy"], r["setting"]): r
                   for r in csv.DictReader(f)}
    checked = 0
    for (view, kind), rr in rows.items():
        label = {c: l for c, l, _, _ in rr}
        members = {c: set(mem.tolist()) for c, _, mem, _ in rr}
        fixed = {c: int(mem[np.argmax(anchor[mem])]) for c, _, mem, _ in rr}
        positive = {c for c in label if label[c] == "positive"}
        if not positive:
            continue
        for (arm, point), s in scores.items():
            order = sorted(rr, key=lambda r: (-float(s[r[3]]), r[0]))
            grouped = defaultdict(list)
            for c, _, _, i in order:
                grouped[fixed[c]].append((c, float(s[i])))
            for policy, units in (("endpoint", [[(c, float(s[i]))] for c, _, _, i in order]),
                                  ("fixed_group", list(grouped.values()))):
                cap = 512 if kind == "D" else 128
                for setting in (f"gates_{cap}", "recall_100"):
                    cutoff = min(u[0][1] for u in units if any(c in positive for c, _ in u))
                    included, gates, n = [], set(), 0
                    for u in units:
                        cells = {g for c, _ in u for g in members[c]}
                        if setting == "recall_100" and u[0][1] < cutoff:
                            break
                        if setting.startswith("gates_") and len(cells | gates) > cap:
                            break
                        n += 1
                        included.extend(c for c, _ in u)
                        gates.update(cells)
                    row = csv_map[arm, point, view, kind, policy, setting]
                    expected = dict(gates=len(gates), units=n, endpoint_count=len(included),
                                    **{lab: sum(label[c] == lab for c in included) for lab in ("positive", "negative", "unknown")})
                    assert all(int(row[k]) == v for k, v in expected.items())
                    checked += 1
    with (OUT / "AUDIT.json").open("x", encoding="utf-8") as f:
        json.dump(dict(passed=True, independent_metrics_recomputed=checked, checkpoint_replay_max_errors=replay_errors,
                       optimizer_step_state_checked=True, paired_steps=50, confirmation_prediction_reads=0), f, indent=2)
    print(checked, replay_errors)


if __name__ == "__main__":
    main()
