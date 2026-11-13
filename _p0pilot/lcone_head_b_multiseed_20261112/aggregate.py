"""Audit both new B runs and aggregate paired effects with the retained seed42 run."""
import csv
import hashlib
import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch

OUT = Path(__file__).resolve().parent
P = OUT.parent
OLD = P / "lcone_head_seed42_20261112"
sys.dont_write_bytecode = True
sys.path.insert(0, str(P / "lcone_head_gate_20261112"))
from gate import TRAIN, head, sha, validation_inputs


def read(p):
    return json.loads(p.read_text(encoding="utf-8"))


def compare(rows, wanted):
    """Aggregate views within the independent source, then sources equally."""
    grouped = defaultdict(list)
    for row in rows:
        if all(row[k] == v for k, v in wanted.items()):
            grouped[row["source"]].append(row)
    return grouped


def statistic(xs):
    return dict(values=xs, mean=st.mean(xs), sd=st.stdev(xs), positive=sum(x > 1e-12 for x in xs),
                negative=sum(x < -1e-12 for x in xs), zero=sum(abs(x) <= 1e-12 for x in xs))


def main():
    steps = np.load(TRAIN / "COMMON_STEPS.npy", allow_pickle=False)
    expected = [hashlib.sha256(row.tobytes()).hexdigest() for row in steps]
    old_log = [r for r in read(OLD / "RUN_LOG.json") if r["arm"] == "B"]
    assert [r["rows_sha256"] for r in old_log] == expected
    per_seed, audit = {}, {}
    for seed in (42, 1, 2):
        folder = OLD if seed == 42 else OUT / f"seed{seed}"
        with (folder / "VAL_BY_VIEW.csv").open(encoding="utf-8-sig", newline="") as f:
            per_seed[seed] = [r for r in csv.DictReader(f) if r["kind"] == "D" and r["arm"] in ("A", "B")
                              and r["setting"] in ("gates_512", "recall_100")]
        if seed == 42:
            continue
        status = read(folder / "RUN_STATUS.json")
        logs = read(folder / "RUN_LOG.json")
        assert status["steps"] == 50 and [r["step"] for r in logs] == list(range(1, 51))
        assert [r["rows_sha256"] for r in logs] == expected and all(r["positive"] == 27 for r in logs)
        checkpoints = [r for r in logs if r["val_D_recall_512"] is not None]
        assert max(checkpoints, key=lambda r: r["val_D_recall_512"])["step"] == status["best_step"]
        assert sha(folder / "VAL_SCORES.npz") == status["val_predictions_sha256"]
        errors = {}
        with np.load(folder / "B_INPUTS.npz", allow_pickle=False) as a, np.load(folder / "VAL_SCORES.npz") as scores:
            assert np.array_equal(a["val_keys"], scores["keys"])
            for point in ("best", "last"):
                path = folder / f"{point}.pt"
                assert sha(path) == status[f"{point}_sha256"]
                ckpt = torch.load(path, weights_only=True, map_location="cuda")
                step = status["best_step"] if point == "best" else 50
                assert ckpt["step"] == step
                assert {int(x["step"]) for x in ckpt["optimizer"]["state"].values()} == {step}
                m = head().cuda().eval()
                m.load_state_dict(ckpt["state"], strict=True)
                with torch.inference_mode():
                    again = m(torch.as_tensor(a["val"], device="cuda")).flatten().cpu().numpy()
                errors[point] = float(np.max(np.abs(again - scores[point])))
                assert errors[point] <= 1e-6
        audit[str(seed)] = dict(checkpoint_replay_error=errors, steps=50, validated_schedule=True)
    output = {}
    for policy in ("endpoint", "fixed_group"):
        for point in ("best", "last"):
            for key, field in (("gates_512", "recall"), ("recall_100", "negative"), ("recall_100", "gates")):
                criteria = dict(policy=policy, setting=key)
                for rec in ("all", "abc", "aig", "id", "nand", "opt"):
                    if rec == "all":
                        criteria.pop("recipe", None)
                    else:
                        criteria["recipe"] = rec
                    a_macro, b_macro, source_data = [], [], defaultdict(lambda: {"A": [], "B": []})
                    for seed in (42, 1, 2):
                        a = compare(per_seed[seed], dict(**criteria, arm="A", point="frozen"))
                        b = compare(per_seed[seed], dict(**criteria, arm="B", point=point))
                        assert a.keys() == b.keys() and a
                        for s in a:
                            assert {r["view"] for r in a[s]} == {r["view"] for r in b[s]}
                            if key == "recall_100":
                                assert all(float(r["recall"]) == 1.0 for r in a[s]+b[s])
                            source_data[s]["A"].append(st.mean(float(r[field]) for r in a[s]))
                            source_data[s]["B"].append(st.mean(float(r[field]) for r in b[s]))
                        a_macro.append(st.mean(v["A"][-1] for v in source_data.values()))
                        b_macro.append(st.mean(v["B"][-1] for v in source_data.values()))
                    output[f"{policy}|{point}|{key}|{field}|{rec}"] = dict(
                        A=a_macro, B=b_macro, delta=statistic([b-a for a, b in zip(a_macro, b_macro)]),
                        by_source={s: dict(**v, delta=statistic([b-a for a, b in zip(v["A"], v["B"])]))
                                   for s, v in source_data.items()})
    with (OUT / "AGGREGATE.json").open("x", encoding="utf-8") as f:
        json.dump(dict(seed_order=[42, 1, 2], seed42_reused=True, audit=audit, results=output,
                       confirmation_prediction_reads=0, solver_calls=0), f, indent=2)
    print(audit)


if __name__ == "__main__":
    main()
