"""Verify the shared endpoint evaluator on validation, without model updates."""
import csv
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import torch

OUT = Path(__file__).resolve().parent
P = OUT.parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(P / "lcone_head_gate_20261112"))
from gate import head, validation_inputs
sys.path.insert(0, str(P / "lcone_endpoint_dedup_20261112"))
from evaluate import prefix


def queues(values, fixed_group):
    order = sorted(values, key=lambda c: (-values[c], c))
    buckets = defaultdict(list)
    for c in order:
        buckets[fixed_group[c]].append(c)
    groups = list(buckets.values())
    assert all(len(g) for g in groups)
    return {"endpoint": [[c] for c in order], "fixed_group": groups}


def evaluate_view(group, values, fixed_group, caps):
    pos = {cid for cid, (lab, _) in group.items() if lab == "positive"}
    if not pos:
        return {}
    output = {}
    for name, items in queues(values, fixed_group).items():
        result = {}
        for cap in caps:
            budget = prefix(items, group, max_gates=cap)
            assert budget["gates"] <= cap
            result[f"gates_{cap}"] = budget
        unit_score = {c: values[item[0]] for item in items for c in item}
        for q in (80, 95, 100):
            threshold = sorted((unit_score[c] for c in pos), reverse=True)[math.ceil(q * len(pos) / 100) - 1]
            scored = prefix(items, group, threshold=threshold, values=values)
            assert scored["positive"] >= math.ceil(q * len(pos) / 100)
            result[f"recall_{q}"] = scored
        output[name] = result
    return output


def main():
    frozen = P / "lcone_endpoint_dedup_20261112/VIEW_RESULTS_V2.csv"
    old = {}
    with frozen.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r["split"] == "val" and r["seed"] == "42" and r["arm"] == "N":
                old[r["view"], r["kind"], r["point"], r["mode"], int(r["budget"])] = r
    checked, smoke = Counter(), Counter()
    with torch.random.fork_rng(devices=[torch.cuda.current_device()]):
        torch.manual_seed(42)
        h = head().cuda().eval()
        with np.load(P / "seed42_nc_ablation_20261109/N_scores.npz", allow_pickle=False) as margins:
            for point in ("best", "last"):
                val, rows = validation_inputs(point)
                anchor = margins[f"val_{point}"]
                data = defaultdict(dict)
                for r in rows:
                    assert r["feature_available"]
                    i = r["feature_row"]
                    mem = val["members"][val["ptr"][i]:val["ptr"][i+1]]
                    v = float(anchor[mem].max())
                    assert v == float(val["B"][i, 0])
                    k = int(mem[anchor[mem] == v].min())
                    data[r["view"], r["kind"]][r["cone_id"]] = (r["status"], mem, i, k)
                learned = {}
                if point == "best":
                    with torch.inference_mode():
                        for arm in ("B", "C"):
                            predicted = h(torch.as_tensor(val[arm], device="cuda")).flatten().cpu().numpy()
                            assert np.isfinite(predicted).all()
                            learned[arm] = predicted
                for (view, kind), rr in data.items():
                    caps = (128, 256, 512, 1024) if kind == "D" else (32, 64, 128, 256)
                    group = {cid: (r[0], r[1]) for cid, r in rr.items()}
                    fixed = {cid: r[3] for cid, r in rr.items()}
                    a = evaluate_view(group, {cid: float(val["B"][r[2], 0]) for cid, r in rr.items()}, fixed, caps)
                    for policy, result in a.items():
                        tag = "raw" if policy == "endpoint" else "group"
                        for mode, bs, label in (("fixed_gate_cap", caps, "gates"), ("equal_recall", (80, 95, 100), "recall")):
                            for b in bs:
                                reference = old[view, kind, point, mode, b]
                                score = result[f"{label}_{b}"]
                                for key in ("units", "endpoint_count", "gates", "positive", "negative", "unknown"):
                                    assert score[key] == int(reference[f"{tag}_{key}"]), (view, kind, point, key)
                                checked[point] += 1
                    for arm, v in learned.items():
                        r = evaluate_view(group, {cid: float(v[x[2]]) for cid, x in rr.items()}, fixed, caps)
                        assert r.keys() == a.keys()
                        smoke[arm] += len(r)
    with (OUT / "EVAL_GATE.json").open("x", encoding="utf-8") as f:
        json.dump(dict(passed=True, A_exact_against_frozen=dict(checked), untrained_head_policy_checks=dict(smoke),
                       optimizer_steps=0, confirmation_prediction_reads=0), f, indent=2)
    print(checked, smoke)


if __name__ == "__main__":
    main()
