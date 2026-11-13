"""Replay frozen A queues on the fixed 49-view endpoint panel."""
import csv
import json
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent
P = OUT.parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(P / "lcone_endpoint_dedup_20261112"))
from evaluate import load

def walk(queue, members, labels, score, condition, n_positive, cutoff=None):
    gates, found, order, inspected = set(), Counter(), [], 0
    blocker = 0
    for item in queue:
        if condition == "full_recall_prefix" and found["positive"] == n_positive:
            break
        if condition == "full_recall_all_score_ties" and score[item[0]] < cutoff:
            break
        union = gates.union(*(members[i] for i in item))
        if condition == "budget_512" and len(union) > 512:
            blocker = len(union) - len(gates)
            break
        gates = union
        found.update(labels[i] for i in item)
        order.extend(item)
        inspected += 1
    if condition != "budget_512":
        assert found["positive"] == n_positive
    return dict(units=inspected, gates=len(gates), positive=found["positive"], negative=found["negative"],
                unknown=found["unknown"], recall=found["positive"]/n_positive if n_positive else None,
                blocked_incremental_gates=blocker), order


def summarize(rows):
    summary = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if r["recall"] is None:
            continue
        for recipe in ("all", r["recipe"]):
            key = tuple(str(x) for x in (r["split"], r["point"], r["seed"], recipe, r["condition"], r["policy"]))
            summary[key][r["source"]].append(r)
    fields = ("recall", "gates", "negative", "unknown", "units")
    out = {}
    for k, src in summary.items():
        by_source = {s: {m: st.mean(r[m] for r in rr) for m in fields} for s, rr in src.items()}
        out["|".join(k)] = dict(sources=len(src), views=sum(map(len, src.values())), by_source=by_source,
                                macro={m: st.mean(d[m] for d in by_source.values()) for m in fields})
    return out


def main():
    _, panel = load()
    base = P / "seed42_nc_ablation_20261109"
    old = {}
    p = P / "lcone_endpoint_dedup_20261112/VIEW_RESULTS_V2.csv"
    with p.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r["arm"] == "N" and r["kind"] == "D":
                old[r["split"], r["view"], int(r["seed"]), r["point"], r["mode"], int(r["budget"])] = r
    results, cross, n_verified = [], [], 0
    no_positive = set()
    for seed in (42, 1, 2):
        suffix = "" if seed == 42 else f"_s{seed}"
        with np.load(base / f"N{suffix}_scores.npz", allow_pickle=False) as z:
            for split in ("val", "test"):
                for point in ("best", "last"):
                    margin = z[f"{split}_{point}"]
                    for (s, view, kind), group in sorted(panel.items()):
                        if s != split or kind != "D":
                            continue
                        source, recipe = view.rsplit("__ys_", 1)
                        names, data = list(group), list(group.values())
                        labels = [lab for lab, _ in data]
                        positive = [i for i, l in enumerate(labels) if l == "positive"]
                        if not positive:
                            no_positive.add((s, view))
                        arrays = [a for _, a in data]
                        members = [set(a.tolist()) for a in arrays]
                        winner = [int(a[margin[a] == margin[a].max()].min()) for a in arrays]
                        score = margin[winner]
                        order = sorted(range(len(names)), key=lambda i: (-float(score[i]), names[i]))
                        grouped = defaultdict(list)
                        for i in order:
                            grouped[winner[i]].append(i)
                        assert all(np.all(score[g] == score[g[0]]) for g in grouped.values())
                        queues = {"endpoint": [[i] for i in order], "whole_group": list(grouped.values()),
                                  "group_then_endpoint": [[i] for g in grouped.values() for i in g]}
                        cut = min((float(score[i]) for i in positive), default=None)
                        options = ("budget_512", "full_recall_prefix", "full_recall_all_score_ties") if positive else ("budget_512",)
                        for condition in options:
                            policies, inspected = {}, {}
                            for policy, queue in queues.items():
                                result, seq = walk(queue, members, labels, score, condition, len(positive), cut)
                                policies[policy], inspected[policy] = result, seq
                                if positive and policy != "group_then_endpoint" and condition != "full_recall_prefix":
                                    mode, budget = (("fixed_gate_cap", 512) if condition == "budget_512" else ("equal_recall", 100))
                                    ref = old[s, view, seed, point, mode, budget]
                                    tag = "raw" if policy == "endpoint" else "group"
                                    assert all(int(ref[tag+"_"+k]) == result[k] for k in ("gates", "positive", "negative", "unknown", "units"))
                                    n_verified += 1
                                results.append(dict(split=s, view=view, source=source, recipe=recipe, seed=seed, point=point,
                                                    condition=condition, policy=policy, positive_support=len(positive),
                                                    negative_support=labels.count("negative"), **result))
                            if condition == "full_recall_all_score_ties":
                                assert len({frozenset(a) for a in inspected.values()}) == 1
                            ep, gp = inspected["endpoint"], inspected["group_then_endpoint"]
                            cross.append(dict(split=s, view=view, seed=seed, point=point, condition=condition,
                                              same_set=set(ep)==set(gp), same_order=ep==gp,
                                              delta_positive=policies["group_then_endpoint"]["positive"]-policies["endpoint"]["positive"],
                                              delta_gates=policies["group_then_endpoint"]["gates"]-policies["endpoint"]["gates"],
                                              delta_negative=policies["group_then_endpoint"]["negative"]-policies["endpoint"]["negative"]))
    with (OUT / "BY_VIEW.csv").open("x", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0]))
        w.writeheader()
        w.writerows(results)
    with (OUT / "SUMMARY.json").open("x", encoding="utf-8") as f:
        json.dump(dict(results=summarize(results), comparisons=cross, old_baseline_checks=n_verified,
                       no_positive_views=sorted(no_positive), optimizer_steps=0, sat_cec_calls=0), f, indent=2)
    print(len(results), n_verified, sorted(no_positive))


if __name__ == "__main__":
    main()
