"""Explain seed1 confirmation results using only saved scores and fixed graph assets."""
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent
P = OUT.parent
CONFIRM = P / "lcone_injdelta_confirmation_20261112"
GRAPHS = P / "lcone_confirmation_assets_20261112"


def read(p):
    return json.loads(p.read_text(encoding="utf-8"))


def cost(groups, members, labels):
    ids = [i for group in groups for i in group]
    counts = Counter(labels[i] for i in ids)
    return set().union(*(members[i] for i in ids)), counts


def inspect(queues, members, labels, cap=None):
    taken, gates = [], set()
    for q in queues:
        candidate = gates | set().union(*(members[i] for i in q))
        if cap is not None and len(candidate) > cap:
            return taken, gates, len(candidate) - len(gates)
        taken.append(q)
        gates = candidate
    return taken, gates, None


def metrics(q, members, labels, cap=512):
    done, _, next_size = inspect(q, members, labels, cap)
    gates, count = cost(done, members, labels)
    return dict(groups=len(done), gates=len(gates), positive=count["positive"], negative=count["negative"],
                unknown=count["unknown"], next_incremental_gates=next_size)


def analyze(name, scores, members, labels, endpoint, winner, physical_names, reference):
    bkt = defaultdict(list)
    for i, w in enumerate(winner):
        bkt[int(w)].append(i)
    pos = {i for i, lab in enumerate(labels) if lab == "positive"}
    assert len(pos) == 2
    group_gates = {w: set().union(*(members[i] for i in ids)) for w, ids in bkt.items()}
    group_size = {w: len(m) for w, m in group_gates.items()}
    positive_winners = {int(winner[i]) for i in pos}

    def ranking(s):
        ordered = sorted(range(len(s)), key=lambda i: (-float(s[i]), endpoint[i]))
        groups = defaultdict(list)
        for i in ordered:
            groups[int(winner[i])].append(i)
        return ordered, dict(groups)

    def describe(w, queue, s):
        g = queue[w]
        count = Counter(labels[i] for i in g)
        return dict(winner=physical_names[w], gates=group_size[w], endpoints=len(g),
                    positive=count["positive"], negative=count["negative"], unknown=count["unknown"],
                    score=float(s[g[0]]), lead_endpoint=endpoint[g[0]], lead_status=labels[g[0]])

    def one(s, stage):
        order, groups = ranking(s)
        seq = list(groups.values())
        high = min(float(s[q[0]]) for q in seq if pos & set(q))
        selected = {w for w, q in groups.items() if s[q[0]] >= high}
        chosen = [q for w, q in groups.items() if w in selected]
        gates, count = cost(chosen, members, labels)
        ref = reference["A" if stage == "A" else "B", "frozen" if stage == "A" else stage]
        assert len(gates) == int(ref["recall_100"]["gates"])
        assert count["negative"] == int(ref["recall_100"]["negative"])
        budget = metrics(seq, members, labels)
        assert budget["positive"] == int(ref["gates_512"]["positive"])
        assert budget["gates"] == int(ref["gates_512"]["gates"])
        prior_gate = set()
        ranks = {}
        for j, (w, q) in enumerate(groups.items(), 1):
            delta = group_gates[w] - prior_gate
            prior_gate |= delta
            if w in positive_winners:
                ranks[physical_names[w]] = dict(rank=j, gates_before=len(prior_gate)-len(delta),
                                                incremental_gates=len(delta), gates_through=len(prior_gate),
                                                **describe(w, groups, s))
        raw_rank = {endpoint[i]: order.index(i)+1 for i in sorted(pos)}
        return dict(group_order=list(groups), queue=groups, selected=selected, selected_gates=gates,
                    recall100=dict(groups=len(selected), gates=len(gates), **dict(count)),
                    budget512=budget, positive_groups=ranks, positive_raw_rank=raw_rank, threshold=high)

    a = one(scores["A"], "A")
    result = {}
    for stage in ("best", "last"):
        s = scores[stage]
        b = one(s, stage)
        n, c = a["selected"], b["selected"]
        entering, exiting = c-n, n-c
        kept = n & c
        retained_gates = set().union(*(group_gates[w] for w in kept))
        detail = {}
        for tag, wins, obj, sc in (("entered", entering, b, s), ("exited", exiting, a, scores["A"])):
            gates, counts = cost([obj["queue"][w] for w in obj["group_order"] if w in wins], members, labels)
            detail[tag] = dict(groups=len(wins), gates=len(gates), gates_outside_retained=len(gates-retained_gates),
                               labels=dict(counts), detail=[describe(w, obj["queue"], sc) for w in obj["group_order"] if w in wins])
        outside = len(b["selected_gates"]-a["selected_gates"])
        removed = len(a["selected_gates"]-b["selected_gates"])
        assert outside-removed == b["recall100"]["gates"]-a["recall100"]["gates"]
        within_p = {}
        for gn, obj in (("A", a), ("B", b)):
            for wn, ws in (("A", scores["A"]), ("B", s)):
                seq = [[i] for w in obj["group_order"] for i in sorted(bkt[w], key=lambda x: (-ws[x], endpoint[x]))]
                within_p[f"{gn}_group_{wn}_within"] = metrics(seq, members, labels)
        bins = (32, 64, 128, 256, 512)
        bins_of = {w: int(np.searchsorted(bins, len(g), side="left")) for w, g in group_gates.items()}
        buckets = defaultdict(list)
        for w in b["group_order"]:
            buckets[bins_of[w]].append(w)
        it = {k: iter(q) for k, q in buckets.items()}
        sz = [next(it[bins_of[w]]) for w in a["group_order"]]
        within_p["B_rank_with_A_size_bin_sequence"] = metrics([bkt[w] for w in sz], members, labels)

        def brief(obj):
            return {k: obj[k] for k in ("recall100", "budget512", "positive_groups", "positive_raw_rank", "threshold")}

        result[stage] = dict(A=brief(a), B=brief(b), changed=detail, retained_groups=len(kept), shared_gates=len(retained_gates),
                             added_distinct_gates=outside, removed_distinct_gates=removed, counterfactual_budget512=within_p)
    return dict(view=name, total_fixed_groups=len(bkt), positive_groups=len(positive_winners), results=result)


def main():
    with (CONFIRM / "BY_VIEW.csv").open(encoding="utf-8-sig", newline="") as f:
        ref = defaultdict(lambda: defaultdict(dict))
        for r in csv.DictReader(f):
            if r["seed"] == "1" and r["policy"] == "fixed_group":
                ref[r["view"]][r["arm"], r["point"]][r["setting"]] = r
    results = []
    for r in read(GRAPHS / "GRAPH_REPORT.json")["views"]:
        name = r["view"]
        folder = GRAPHS / name
        rows = [r for r in read(folder / "ENDPOINTS.json") if r["kind"] == "D" and r["rankable"]]
        with np.load(folder / "GRAPH_ENDPOINTS.npz", allow_pickle=False) as z:
            ptr, pack, names = z["ptr"], z["members"], z["names"].tolist()
        raw_members = [pack[ptr[r["packed_index"]]:ptr[r["packed_index"]+1]] for r in rows]
        endpoint = [r["endpoint"] for r in rows]
        labels = [r["status"] for r in rows]
        with np.load(CONFIRM / f"{name}_s1_SCORES.npz", allow_pickle=False) as z:
            assert endpoint == z["endpoint"].tolist()
            scores = {"A": z["A"], "best": z["B_best"], "last": z["B_last"]}
            margin = z["margin"]
        winner = [int(m[margin[m] == margin[m].max()].min()) for m in raw_members]
        assert np.array_equal(scores["A"], margin[winner])
        results.append(analyze(name, scores, [set(m.tolist()) for m in raw_members], labels, endpoint, winner, names, ref[name]))
    assert len(results) == 4
    with (OUT / "DIAGNOSIS.json").open("x", encoding="utf-8") as f:
        json.dump(dict(results=results, seed=1, source_count=1, training_updates=0, solver_calls=0), f, indent=2)
    print("recomputed", len(results), "views")


if __name__ == "__main__":
    main()
