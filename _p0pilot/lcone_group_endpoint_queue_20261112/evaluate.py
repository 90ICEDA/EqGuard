"""Compare three A inspection queues on already-scored injdelta confirmation views."""
import csv
import json
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent
P = OUT.parent
SCORES = P / "lcone_injdelta_confirmation_20261112"
ASSETS = P / "lcone_confirmation_assets_20261112"
POLICIES = ("endpoint", "whole_group", "group_then_endpoint")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def walk(queue, members, labels, score, condition, cutoff=None):
    gates, labels_found = set(), Counter()
    inspected, blocker = 0, None
    for item in queue:
        if condition == "full_recall_prefix" and labels_found["positive"] == 2:
            break
        if condition == "full_recall_all_score_ties" and score[item[0]] < cutoff:
            break
        union = gates.union(*(members[i] for i in item))
        if condition == "budget_512" and len(union) > 512:
            blocker = dict(incremental_gates=len(union)-len(gates), endpoints=len(item))
            break
        gates = union
        labels_found.update(labels[i] for i in item)
        inspected += 1
    if condition != "budget_512":
        assert labels_found["positive"] == 2
    return dict(units=inspected, gates=len(gates), positive=labels_found["positive"],
                negative=labels_found["negative"], unknown=labels_found["unknown"],
                recall=labels_found["positive"]/2,
                blocked_incremental_gates=blocker["incremental_gates"] if blocker else None,
                blocked_endpoints=blocker["endpoints"] if blocker else None)


def main():
    old = {}
    with (SCORES / "BY_VIEW.csv").open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r["arm"] == "A":
                old[r["view"], int(r["seed"]), r["policy"], r["setting"]] = r
    results = []
    for view in read(ASSETS / "GRAPH_REPORT.json")["views"]:
        v = view["view"]
        folder = ASSETS / v
        rows = [r for r in read(folder / "ENDPOINTS.json") if r["rankable"] and r["kind"] == "D"]
        endpoint = [r["endpoint"] for r in rows]
        labels = [r["status"] for r in rows]
        assert Counter(labels) == {"positive": 2, "negative": 574, "unknown": 604}
        with np.load(folder / "GRAPH_ENDPOINTS.npz", allow_pickle=False) as g:
            ptr, packed = g["ptr"], g["members"]
        raw_members = [packed[ptr[r["packed_index"]]:ptr[r["packed_index"]+1]] for r in rows]
        members = [set(map(int, m)) for m in raw_members]
        for seed in (42, 1, 2):
            with np.load(SCORES / f"{v}_s{seed}_SCORES.npz", allow_pickle=False) as s:
                assert endpoint == s["endpoint"].tolist()
                score, margin = s["A"], s["margin"]
            winner = [int(m[margin[m] == margin[m].max()].min()) for m in raw_members]
            assert np.array_equal(score, margin[winner])
            order = sorted(range(len(rows)), key=lambda i: (-float(score[i]), endpoint[i]))
            groups = defaultdict(list)
            for i in order:
                groups[winner[i]].append(i)
            assert all(len({float(score[i]) for i in g}) == 1 for g in groups.values())
            queues = {"endpoint": [[i] for i in order], "whole_group": list(groups.values()),
                      "group_then_endpoint": [[i] for g in groups.values() for i in g]}
            cut = min(float(score[i]) for i, lab in enumerate(labels) if lab == "positive")
            ties = {}
            for policy, q in queues.items():
                for condition in ("budget_512", "full_recall_prefix", "full_recall_all_score_ties"):
                    out = walk(q, members, labels, score, condition, cut)
                    if condition == "full_recall_all_score_ties":
                        ties[policy] = tuple(out[k] for k in ("gates", "positive", "negative", "unknown"))
                    if policy != "group_then_endpoint" and condition != "full_recall_prefix":
                        ref = old[v, seed, "endpoint" if policy == "endpoint" else "fixed_group",
                                  "gates_512" if condition == "budget_512" else "recall_100"]
                        assert all(out[k] == int(ref[k]) for k in ("units", "gates", "positive", "negative", "unknown"))
                    results.append(dict(view=v, recipe=v.rsplit("__ys_", 1)[1],
                                        keep="keep" if "__keepcur__" in v else "no-keep",
                                        seed=seed, policy=policy, condition=condition, **out))
            assert len(set(ties.values())) == 1
    assert len(results) == 108
    with (OUT / "BY_VIEW.csv").open("x", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0]))
        w.writeheader()
        w.writerows(results)
    summary = {}
    for r in results:
        k = "|".join(r[x] for x in ("view", "condition", "policy"))
        summary.setdefault(k, []).append(r)
    fields = ("gates", "recall", "negative", "unknown", "units")
    with (OUT / "SUMMARY.json").open("x", encoding="utf-8") as f:
        json.dump(dict(seed_order=[42, 1, 2], source_count=1, baseline_checks=48,
                       training_updates=0, sat_cec_calls=0, results={
                           k: {m: dict(values=[r[m] for r in rr], mean=st.mean(r[m] for r in rr)) for m in fields}
                           for k, rr in summary.items()}), f, indent=2)
    print(len(results), "rows, 48 baseline checks")


if __name__ == "__main__":
    main()
