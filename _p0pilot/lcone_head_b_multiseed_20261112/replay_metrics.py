"""Independent replay of both new seeds' main metrics from saved scores."""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent
P = OUT.parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(P / "lcone_head_gate_20261112"))
from gate import validation_inputs


def main():
    val, meta = validation_inputs("best")
    by_view = defaultdict(list)
    for r in meta:
        if r["kind"] != "D":
            continue
        i = r["feature_row"]
        mem = val["members"][val["ptr"][i]:val["ptr"][i+1]]
        by_view[r["view"]].append((r["cone_id"], r["status"], i, mem))
    checked = {}
    for seed in (1, 2):
        folder = OUT / f"seed{seed}"
        with (folder / "VAL_BY_VIEW.csv").open(encoding="utf-8-sig", newline="") as f:
            ref = {(r["arm"], r["point"], r["view"], r["policy"], r["setting"]): r
                   for r in csv.DictReader(f) if r["kind"] == "D"}
        with np.load(P / f"seed42_nc_ablation_20261109/N_s{seed}_scores.npz") as z:
            anchor = z["val_best"]
        with np.load(folder / "VAL_SCORES.npz") as z:
            assert np.array_equal(z["keys"], val["keys"])
            heads = {("B", p): z[p] for p in ("best", "last")}
        n = 0
        for view, rows in by_view.items():
            fixed = {i: int(mem[np.argmax(anchor[mem])]) for _, _, i, mem in rows}
            point_a = {i: float(anchor[mem].max()) for _, _, i, mem in rows}
            for (arm, point), score in {("A", "frozen"): point_a, **heads}.items():
                ordered = sorted(rows, key=lambda r: (-score[r[2]], r[0]))
                buckets = defaultdict(list)
                for r in ordered:
                    buckets[fixed[r[2]]].append(r)
                for policy, units in (("endpoint", [[r] for r in ordered]), ("fixed_group", list(buckets.values()))):
                    threshold = min(score[u[0][2]] for u in units if any(r[1] == "positive" for r in u))
                    for setting in ("gates_512", "recall_100"):
                        used, labels, opened = set(), [], 0
                        for u in units:
                            cells = {int(i) for r in u for i in r[3]}
                            if setting == "gates_512" and len(used | cells) > 512:
                                break
                            if setting == "recall_100" and score[u[0][2]] < threshold:
                                break
                            used |= cells
                            labels.extend(r[1] for r in u)
                            opened += 1
                        expected = {"gates": len(used), "units": opened, "positive": labels.count("positive"),
                                    "negative": labels.count("negative"), "unknown": labels.count("unknown")}
                        actual = ref[arm, point, view, policy, setting]
                        assert all(int(actual[k]) == v for k, v in expected.items())
                        n += 1
        checked[str(seed)] = n
    with (OUT / "METRIC_REPLAY.json").open("x", encoding="utf-8") as f:
        json.dump(dict(passed=True, recomputed_rows=checked, confirmation_prediction_reads=0), f, indent=2)
    print(checked)


if __name__ == "__main__":
    main()
