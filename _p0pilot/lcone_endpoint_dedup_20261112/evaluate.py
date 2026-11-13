"""Label-blind grouping of fixed endpoint candidates by their top-scoring node."""
import csv
import json
import math
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent
P = OUT.parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(P / "lcone_endpoint_overlap_20261112"))
from audit import FROZEN, RUN, csv_rows, read, snapshot


def load():
    rows = read(FROZEN / "EVIDENCE.json")["endpoints"]
    labels = {(r["split"], r["view"], r["cone_id"]): r["status"] for r in rows}
    root = P / "control_boundary_v3_20261104"
    c = read(root / "input_contract.json")["shared_inputs"]
    layouts, panel = {}, defaultdict(dict)
    for split, path in (("val", P / "seed42_supervised_prep_20261109/CONE_CACHE_V2.csv"),
                        ("test", RUN / "CONE_CACHE_TEST.csv")):
        views = {v["view"]: v for v in c["trans_" + split]["views"]}
        for r in csv_rows(path):
            key = r["split"], r["view"], r["cone_id"]
            if key not in labels or r["split"] != split:
                continue
            v, cid = r["view"], r["cone_id"]
            layout = layouts[split, v] = views[v]
            a = np.fromstring(r["phys_rows"], dtype=np.int64, sep="|")
            assert len(a) == int(r["n_phys"]) and np.all((a >= layout["start"]) & (a < layout["physical_stop"]))
            panel[split, v, r["kind"]][cid] = (labels.pop(key), a)
    assert not labels
    return layouts, panel


def queue(group, values, winners):
    order = sorted(group, key=lambda cid: (-values[cid], cid))
    buckets = defaultdict(list)
    for cid in order:
        buckets[min(winners[cid])].append(cid)
    # First endpoint in the original order is also the deterministic tie break between groups.
    groups = list(buckets.values())
    assert all(len({values[c] for c in g}) == 1 for g in groups)
    return [[c] for c in order], groups


def prefix(items, group, max_units=None, max_gates=None, threshold=None, values=None):
    chosen, gates, support, labels = [], set(), Counter(), Counter()
    for item in items:
        if max_units is not None and len(chosen) == max_units:
            break
        if threshold is not None and values[item[0]] < threshold:
            break
        members = set().union(*(set(group[c][1]) for c in item))
        if max_gates is not None and len(gates | members) > max_gates:
            break
        gates.update(members)
        chosen.append(item)
        types = {group[c][0] for c in item}
        labels.update(group[c][0] for c in item)
        support["positive_groups"] += "positive" in types
        support["pure_negative_groups"] += types == {"negative"}
        support["unknown_without_positive_groups"] += "unknown" in types and "positive" not in types
        support["mixed_positive_negative_groups"] += "positive" in types and "negative" in types
    return dict(units=len(chosen), endpoint_count=sum(labels.values()), gates=len(gates),
                positive=labels["positive"], negative=labels["negative"], unknown=labels["unknown"],
                **{k: support[k] for k in ("positive_groups", "pure_negative_groups",
                                           "unknown_without_positive_groups", "mixed_positive_negative_groups")})


def main():
    layouts, panel = load()
    prior = {(r["split"], r["view"], r["kind"], r["seed"], r["arm"], r["point"]): r
             for r in csv_rows(FROZEN / "METRICS.csv") if r["pool"] == "all_nonempty"}
    rows = []
    for seed in (42, 1, 2):
        suffix = "" if seed == 42 else f"_s{seed}"
        for arm in ("N", "NC"):
            with np.load(RUN / f"{arm}{suffix}_scores.npz") as z:
                for split in ("val", "test"):
                    for point in ("best", "last"):
                        margin = z[f"{split}_{point}"]
                        for (s, v, kind), group in panel.items():
                            if s != split:
                                continue
                            pos = [c for c, (lab, _) in group.items() if lab == "positive"]
                            if not pos:
                                continue
                            source, recipe = v.rsplit("__ys_", 1)
                            values, winners, _ = snapshot(margin, layouts[s, v], group)
                            baseline, dedup = queue(group, values, winners)
                            details = dict(split=s, source=source, recipe=recipe, view=v, kind=kind,
                                           seed=seed, arm=arm, point=point, positives=len(pos),
                                           negatives=sum(lab == "negative" for lab, _ in group.values()),
                                           available_endpoints=len(baseline), available_groups=len(dedup))

                            def record(mode, k, b, d, gate_cap=None):
                                rows.append(dict(**details, mode=mode, budget=k, gate_cap=gate_cap,
                                                 **{f"raw_{n}": x for n, x in b.items()},
                                                 **{f"group_{n}": x for n, x in d.items()},
                                                 raw_recall=b["positive"] / len(pos), group_recall=d["positive"] / len(pos)))

                            for k in (1, 5, 10):
                                b = prefix(baseline, group, max_units=k)
                                d = prefix(dedup, group, max_units=k)
                                assert d["positive"] >= b["positive"]
                                record("same_units", k, b, d)
                                d = prefix(dedup, group, max_gates=b["gates"])
                                assert d["gates"] <= b["gates"]
                                record("same_gate_cap", k, b, d, b["gates"])
                            for cap in ((128, 256, 512, 1024) if kind == "D" else (32, 64, 128, 256)):
                                b = prefix(baseline, group, max_gates=cap)
                                d = prefix(dedup, group, max_gates=cap)
                                assert max(b["gates"], d["gates"]) <= cap
                                record("fixed_gate_cap", cap, b, d, cap)
                            for q in (80, 95, 100):
                                thr = sorted((values[c] for c in pos), reverse=True)[math.ceil(q * len(pos) / 100) - 1]
                                b = prefix(baseline, group, threshold=thr, values=values)
                                d = prefix(dedup, group, threshold=thr, values=values)
                                ref = prior[s, v, kind, str(seed), arm, point]
                                assert b["endpoint_count"] == int(ref[f"checks_{q}"])
                                assert b["negative"] == int(ref[f"false_positive_{q}"])
                                assert b["unknown"] == int(ref[f"unknown_checks_{q}"])
                                assert all(b[x] == d[x] for x in ("endpoint_count", "gates", "positive", "negative", "unknown"))
                                record("equal_recall", q, b, d)
    assert rows
    with (OUT / "VIEW_RESULTS_V2.csv").open("x", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    summary = defaultdict(lambda: defaultdict(list))
    for r in rows:
        for recipe in (r["recipe"], "all"):
            key = tuple(str(x) for x in (r["split"], recipe, r["kind"], r["seed"], r["arm"], r["point"], r["mode"], r["budget"]))
            summary[key][r["source"]].append(r)
    metrics = ("units", "endpoint_count", "gates", "negative", "unknown", "recall",
               "pure_negative_groups", "unknown_without_positive_groups", "mixed_positive_negative_groups")
    result = {}
    for k, src in summary.items():
        per_source = {s: {f"{a}_{m}": st.mean(x[f"{a}_{m}"] for x in rr)
                          for a in ("raw", "group") for m in metrics} for s, rr in src.items()}
        macro = {m: st.mean(r[m] for r in per_source.values()) for m in next(iter(per_source.values()))}
        result["|".join(k)] = dict(sources=len(src), views=sum(map(len, src.values())),
                                  macro=macro, per_source=per_source)
    with (OUT / "SUMMARY_V2.json").open("x", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"{len(rows)} comparison rows, {len(result)} recipe/source summaries")


if __name__ == "__main__":
    main()
