"""Freeze a common 50-step schedule with one recipe per source endpoint per step."""
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

P = Path(__file__).resolve().parent / "all_eligible"
RECIPES = ("ys_abc", "ys_aig", "ys_nand")


def main():
    budget = json.loads((P / "BC_BUDGET.json").read_text(encoding="utf-8"))
    examples = budget["examples"]
    grouped = defaultdict(dict)
    for i, r in enumerate(examples):
        key = (r["source"], r["kind"], r["label"], r["cone_id"])
        assert r["recipe"] not in grouped[key]
        grouped[key][r["recipe"]] = i
    strata = defaultdict(lambda: defaultdict(list))
    for (source, kind, label, cid), rec in grouped.items():
        assert set(rec) == set(RECIPES)
        strata[source, kind][label].append((cid, rec))
    pairs = []
    for _, sides in sorted(strata.items()):
        assert len(sides[0]) == len(sides[1])
        pairs.extend(zip(sorted(sides[0]), sorted(sides[1])))
    schedule = []
    for step in range(50):
        indices = []
        for j, (neg, pos) in enumerate(pairs):
            rec = RECIPES[(j + step) % len(RECIPES)]
            indices.extend((neg[1][rec], pos[1][rec]))
        assert len(indices) == len(set(indices)) == len(grouped)
        classes = Counter((examples[i]["recipe"], examples[i]["label"]) for i in indices)
        assert all(classes[rec, 0] == classes[rec, 1] for rec in RECIPES)
        schedule.append(indices)
    ids = np.asarray(schedule, dtype=np.int64)
    with (P / "COMMON_STEPS.npy").open("xb") as f:
        np.save(f, ids, allow_pickle=False)
    c = np.bincount(ids.ravel(), minlength=len(examples))
    with (P / "COMMON_STEPS.json").open("x", encoding="utf-8") as f:
        json.dump(dict(shape=list(ids.shape), logical_endpoints=len(grouped), row_exposure=dict(Counter(map(int, c))),
                       step_recipe_class_counts={f"{r}|{l}": sum(examples[i]["recipe"] == r and examples[i]["label"] == l
                                                                   for i in ids[0]) for r in RECIPES for l in (0, 1)},
                       sha256=hashlib.sha256(ids.tobytes()).hexdigest(), executed_steps=0), f, indent=2)


if __name__ == "__main__":
    main()
