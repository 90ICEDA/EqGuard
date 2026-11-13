"""Analyze endpoint inspection overlap from frozen labels and saved scores."""
import csv
import json
import math
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
P = ROOT / "_p0pilot"
FROZEN = P / "lcone_endpoint_frozen_20261112"
RUN = P / "seed42_nc_ablation_20261109"
OUT = Path(__file__).parent


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def csv_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f)


def load():
    labels = {(e["view"], e["cone_id"]): e["status"]
              for e in read(FROZEN / "EVIDENCE.json")["endpoints"] if e["split"] == "test"}
    views = {r["view"]: r for r in read(P / "control_boundary_v3_20261104/input_contract.json")
             ["shared_inputs"]["trans_test"]["views"]}
    layout, panel = {}, defaultdict(dict)
    for r in csv_rows(RUN / "CONE_CACHE_TEST.csv"):
        key = r["view"], r["cone_id"]
        if key not in labels:
            continue
        v, cid = key
        layout[v] = views[v]
        a = np.fromstring(r["phys_rows"], dtype=np.int64, sep="|")
        assert len(a) == int(r["n_phys"]) and np.all((a >= views[v]["start"]) & (a < views[v]["physical_stop"]))
        panel[v, r["kind"]][cid] = (labels.pop(key), a)
    assert not labels
    return layout, panel


def snapshot(scores, view, group):
    vmax = np.sort(scores[view["start"]:view["physical_stop"]])
    values, winners = {}, {}
    for cid, (_, a) in group.items():
        score = float(scores[a].max())
        values[cid] = score
        winners[cid] = tuple(map(int, a[scores[a] == score]))
    ranks = {cid: float(np.searchsorted(vmax, value, side="left") / len(vmax))
             for cid, value in values.items()}
    return values, winners, ranks


def inspect(group, s, positive, q):
    values, _, ranks = s
    need = math.ceil(q * len(positive))
    thr = sorted((values[c] for c in positive), reverse=True)[need - 1]
    crit = sorted(c for c in positive if values[c] == thr)
    checked = {c for c, x in values.items() if x >= thr}
    rank = ranks[crit[0]]
    assert checked == {c for c, p in ranks.items() if p >= rank}
    return checked, crit, rank


def features(subset, group, winners, reference, positive, other_unknown):
    """Reference is checked endpoints retained by both arms."""
    pos_win = {g for c in positive for g in winners[c]}
    pos_members = set().union(*(set(group[c][1]) for c in positive))
    ref_win = {g for c in reference for g in winners[c]}
    ref_members = set().union(*(set(group[c][1]) for c in reference))
    usage = Counter(g for c in subset for g in winners[c])
    member_union = set()
    out = Counter()
    for cid in subset:
        mem = set(group[cid][1])
        w = set(winners[cid])
        member_union.update(mem)
        out["cones"] += 1
        out["member_occurrences"] += len(mem)
        out["overlaps_positive_members"] += bool(mem & pos_members)
        out["winner_in_positive_members"] += bool(w & pos_members)
        out["same_winner_as_positive"] += bool(w & pos_win)
        out["same_winner_as_retained"] += bool(w & ref_win)
        out["winner_shared_with_other_changed"] += any(usage[g] > 1 for g in w)
        out["multiwinner"] += len(w) > 1
    out["unique_members"] = len(member_union)
    out["new_unique_members_vs_retained"] = len(member_union - ref_members)
    out["unique_representative_winners"] = len({min(winners[c]) for c in subset})
    out["new_unique_representative_winners_vs_retained"] = len({min(winners[c]) for c in subset} - ref_win)
    out["retained_unknown"] = len(other_unknown)
    return dict(out)


def cost(checked, group, winners):
    return {"endpoints": len(checked),
            "member_occurrences": sum(len(group[c][1]) for c in checked),
            "unique_members": len(set().union(*(set(group[c][1]) for c in checked))),
            "unique_representative_winners": len({min(winners[c]) for c in checked})}


def write(path, records):
    with path.open("x", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(records[0]))
        w.writeheader()
        w.writerows(records)


def main():
    layouts, panel = load()
    prior = {(r["view"], r["kind"], int(r["seed"]), r["arm"], r["point"]): r
             for r in csv_rows(FROZEN / "METRICS.csv")
             if r["split"] == "test" and r["pool"] == "all_nonempty"}
    rows, switches, matched = [], [], []
    for seed in (42, 1, 2):
        suffix = "" if seed == 42 else f"_s{seed}"
        data = {}
        for arm in ("N", "NC"):
            with np.load(RUN / f"{arm}{suffix}_scores.npz") as z:
                for point in ("best", "last"):
                    data[arm, point] = z[f"test_{point}"]
        for point in ("best", "last"):
            saved = {}
            for (view, kind), group in sorted(panel.items()):
                pos = {c for c, (label, _) in group.items() if label == "positive"}
                if not pos:
                    continue
                source, recipe = view.rsplit("__ys_", 1)
                snaps = {arm: snapshot(data[arm, point], layouts[view], group) for arm in ("N", "NC")}
                saved[source, recipe, kind] = (group, snaps)
                for q in (0.95, 1.0):
                    sel = {a: inspect(group, s, pos, q) for a, s in snaps.items()}
                    n, c = (sel[a][0] for a in ("N", "NC"))
                    tn, tc = (sel[a][2] for a in ("N", "NC"))
                    ranks_n, ranks_c = snaps["N"][2], snaps["NC"][2]
                    t = str(round(q * 100))
                    for arm, chosen in (("N", n), ("NC", c)):
                        ref = prior[view, kind, seed, arm, point]
                        assert len(chosen) == int(ref[f"checks_{t}"])
                        assert sum(group[x][0] == "negative" for x in chosen) == int(ref[f"false_positive_{t}"])
                        assert sum(group[x][0] == "unknown" for x in chosen) == int(ref[f"unknown_checks_{t}"])
                    common = n & c
                    u_keep = {x for x in common if group[x][0] == "unknown"}
                    changes = {}
                    for tag, arm, delta in (("entered", "NC", c-n), ("exited", "N", n-c)):
                        unk = {x for x in delta if group[x][0] == "unknown"}
                        changes[tag] = features(unk, group, snaps[arm][1], common, pos, u_keep)
                        for cid in sorted(delta):
                            v = snaps[arm][1][cid]
                            # Test score movement and threshold movement separately on the view's node percentiles.
                            score_only = ranks_c[cid] >= tn
                            threshold_only = ranks_n[cid] >= tc
                            wanted = tag == "entered"
                            mode = ("both_sufficient" if score_only == threshold_only == wanted else
                                    "score_only_sufficient" if score_only == wanted else
                                    "threshold_only_sufficient" if threshold_only == wanted else
                                    "combined_required")
                            switches.append(dict(source=source, recipe=recipe, view=view, kind=kind, seed=seed, point=point,
                                                 recall=q, change=tag, cone_id=cid, status=group[cid][0],
                                                 node_count=len(group[cid][1]), max_nodes="|".join(map(str, v)),
                                                 score_pct_N=ranks_n[cid], score_pct_NC=ranks_c[cid],
                                                 cutoff_pct_N=tn, cutoff_pct_NC=tc, crossing_diagnostic=mode))
                    rows.append(dict(source=source, recipe=recipe, view=view, kind=kind, seed=seed, point=point, recall=q,
                                     pos=len(pos), negative=sum(v[0] == "negative" for v in group.values()),
                                     threshold_N=tn, threshold_NC=tc, critical_N=sel["N"][1], critical_NC=sel["NC"][1],
                                     N=dict(**cost(n, group, snaps["N"][1]), **Counter(group[x][0] for x in n)),
                                     NC=dict(**cost(c, group, snaps["NC"][1]), **Counter(group[x][0] for x in c)),
                                     changes=changes))
            # Use exactly the same certified positive IDs and functional-negative IDs in both recipes.
            for source in sorted({k[0] for k in saved}):
                for kind in ("D", "PO"):
                    if not all((source, rec, kind) in saved for rec in ("aig", "nand")):
                        continue
                    gs = {rec: saved[source, rec, kind] for rec in ("aig", "nand")}
                    intersection = {status: set.intersection(*({cid for cid, (lab, _) in g.items() if lab == status}
                                                                for g, _ in gs.values()))
                                    for status in ("positive", "negative")}
                    if not all(intersection.values()):
                        continue
                    for rec, (g, ss) in gs.items():
                        for arm, snap in ss.items():
                            checked, crit, thr = inspect(g, snap, intersection["positive"], 1.0)
                            fp = checked & intersection["negative"]
                            pos_winners = {k for c in intersection["positive"] for k in snap[1][c]}
                            matched.append(dict(source=source, recipe=rec, kind=kind, seed=seed, point=point, arm=arm,
                                                matched_positive=len(intersection["positive"]),
                                                matched_negative=len(intersection["negative"]), fp=len(fp),
                                                fp_shared_positive_winner=sum(bool(set(snap[1][c]) & pos_winners) for c in fp),
                                                fp_ids="|".join(sorted(fp)), critical_positive="|".join(crit),
                                                threshold_percentile=thr))
    with (OUT / "OVERLAP.json").open("x", encoding="utf-8") as f:
        json.dump(rows, f, indent=2)
    write(OUT / "SWITCHES.csv", switches)
    write(OUT / "AIG_NAND_MATCHED.csv", matched)
    print(len(rows), len(switches), len(matched))


if __name__ == "__main__":
    main()
