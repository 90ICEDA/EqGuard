"""Audit supports and pair N/NC results before averaging by source."""
import csv
import json
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

OUT = Path(__file__).resolve().parent


def main():
    evidence = json.loads((OUT / "EVIDENCE.json").read_text(encoding="utf-8"))
    support, views = defaultdict(Counter), defaultdict(set)
    for e in evidence["endpoints"]:
        recipe = e["view"].rsplit("__ys_", 1)[1]
        key = (e["split"], recipe, e["kind"])
        support[key][e["status"]] += 1
        support[key]["cache_exact"] += bool(e.get("cache_exact"))
        if e["status"] == "positive":
            views[key].add(e["view"])
            obs = e["witness"]["clean_orig_trans"]
            assert obs[0] != obs[1] == obs[2] and e["inserted_cells_in_source_cone"]

    with (OUT / "METRICS.csv").open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    pairs = defaultdict(dict)
    for r in rows:
        for q in (80, 95, 100):
            found = round(float(r[f"recall_{q}"]) * int(r["positive"]))
            assert int(r[f"checks_{q}"]) == found + int(r[f"false_positive_{q}"]) + int(r[f"unknown_checks_{q}"])
        key = tuple(r[k] for k in ("split", "view", "kind", "pool", "seed", "point"))
        assert r["arm"] not in pairs[key]
        pairs[key][r["arm"]] = r
    per_source = defaultdict(lambda: defaultdict(list))
    metrics = ("recall_at_1", "recall_at_5", "recall_at_10", "checks_95", "false_positive_95",
               "unknown_checks_95", "fpr_95", "recall_95", "checks_100", "false_positive_100", "fpr_100")
    for (split, view, kind, pool, seed, point), rr in pairs.items():
        n, c = rr["N"], rr["NC"]
        assert all(n[m] == c[m] for m in ("positive", "negative", "unknown"))
        source, recipe = view.rsplit("__ys_", 1)
        for axis in (recipe, "all"):
            key = (split, axis, kind, pool, point, seed)
            per_source[key][source].append(
                dict(view=view, exact_95=float(n["recall_95"]) == float(c["recall_95"]),
                     N={m: float(n[m]) for m in metrics}, NC={m: float(c[m]) for m in metrics}))

    result = {}
    for key, data in per_source.items():
        summary = {m: {} for m in metrics}
        for m in metrics:
            for arm in ("N", "NC"):
                summary[m][arm] = st.mean(st.mean(r[arm][m] for r in rr) for rr in data.values())
            summary[m]["delta"] = summary[m]["NC"] - summary[m]["N"]
        result["|".join(key)] = dict(n_sources=len(data), n_views=sum(map(len, data.values())),
                                    n_exact_95=sum(r["exact_95"] for rr in data.values() for r in rr),
                                    source_rows=dict(data), metrics=summary)

    with (OUT / "SUMMARY.json").open("x", encoding="utf-8") as f:
        json.dump(dict(support={"|".join(k): dict(**v, positive_views=sorted(views[k]))
                                for k, v in support.items()}, paired=result), f, indent=2)


if __name__ == "__main__":
    main()
