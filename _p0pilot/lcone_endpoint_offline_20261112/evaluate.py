"""Compare saved N/NC margins on a shared endpoint ranking pool."""
import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
PILOT = ROOT / "_p0pilot"
RUN = PILOT / "seed42_nc_ablation_20261109"
BOUND = PILOT / "control_boundary_v3_20261104"
OUT = Path(__file__).parent


def csv_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f)


def load_panel(split):
    layout = json.loads((BOUND / "input_contract.json").read_text(encoding="utf-8"))
    views = {v["view"]: v for v in layout["shared_inputs"][f"trans_{split}"]["views"]}
    data = BOUND / "inputs" / f"trans_{split}"
    y, trusted, physical = (np.load(data / f"{k}.npy", mmap_mode="r")
                            for k in ("y", "trusted", "physical"))
    cache = (RUN / "CONE_CACHE_TEST.csv" if split == "test" else
             PILOT / "seed42_supervised_prep_20261109/CONE_CACHE_V2.csv")
    groups, eligible_groups = defaultdict(list), defaultdict(list)
    seen, counts = set(), Counter()
    for r in csv_rows(cache):
        if r["split"] != split or r["view"] not in views:
            continue
        v = r["view"]
        if "__inj" not in v or "ctl" in v:
            continue
        ident = (v, r["cone_id"])
        assert ident not in seen, ident
        seen.add(ident)
        members = np.fromstring(r["phys_rows"], dtype=np.int64, sep="|") if r["phys_rows"] else np.empty(0, np.int64)
        lay = views[v]
        assert len(members) == int(r["n_phys"]) == len(np.unique(members)), ident
        assert np.all((lay["start"] <= members) & (members < lay["physical_stop"])), ident
        assert np.all(physical[members]), ident
        known = members[trusted[members]]
        weak_label = (1 if np.any(y[known] == 1) else
                      0 if len(members) and len(known) == len(members) and np.all(y[known] == 0) else -1)
        assert weak_label == int(r["label"]), (ident, weak_label, r["label"])
        if not len(members):
            counts[f"{r['kind']}_empty"] += 1
            continue
        group = (v, r["kind"])
        groups[group].append((r["cone_id"], r["endpoint"], weak_label, members))
        if len(known) >= 2 and weak_label >= 0:
            eligible_groups[group].append((r["cone_id"], r["endpoint"], weak_label, known))
    return groups, eligible_groups, (y, trusted), counts


def report(ranked):
    n_pos = sum(r[2] == 1 for r in ranked)
    n_neg = sum(r[2] == 0 for r in ranked)
    n_unknown = len(ranked) - n_pos - n_neg
    result = {"pos": n_pos, "neg": n_neg, "unknown": n_unknown}
    for k in (1, 5, 10):
        top = ranked[:k]
        result[f"hit@{k}"] = sum(r[2] == 1 for r in top)
        result[f"recall@{k}"] = result[f"hit@{k}"] / n_pos
    for q in (0.8, 0.95, 1.0):
        need = math.ceil(q * n_pos)
        threshold = [r[3] for r in ranked if r[2] == 1][need - 1]
        checked = [r for r in ranked if r[3] >= threshold]
        tag = f"@{q:.2f}"
        result["checks" + tag] = len(checked)
        result["positive" + tag] = sum(r[2] == 1 for r in checked)
        result["known_negative" + tag] = sum(r[2] == 0 for r in checked)
        result["unknown" + tag] = sum(r[2] == -1 for r in checked)
        result["ties" + tag] = sum(r[3] == threshold for r in checked)
    return result


def main():
    rows, cases, panel_support = [], [], {}
    for split in ("val", "test"):
        full, strict, (y, trusted), counts = load_panel(split)
        for mode, groups in (("physical", full), ("trusted_ge2", strict)):
            for kind in ("D", "PO"):
                relevant = [g for (v, t), g in groups.items() if t == kind]
                eligible = [g for g in relevant if any(r[2] == 1 for r in g)]
                panel_support[f"{split}|{mode}|{kind}"] = {
                    "all_rankable_views": len(relevant), "positive_views": len(eligible),
                    "positive_views_with_known_neg": sum(any(r[2] == 0 for r in g) for g in eligible),
                    "pos": sum(r[2] == 1 for g in eligible for r in g),
                    "neg": sum(r[2] == 0 for g in eligible for r in g),
                    "unknown": sum(r[2] == -1 for g in eligible for r in g),
                    "empty_excluded": counts[f"{kind}_empty"],
                }
        for seed in (42, 1, 2):
            margins = {}
            for arm in ("N", "NC"):
                suffix = "" if seed == 42 else f"_s{seed}"
                with np.load(RUN / f"{arm}{suffix}_scores.npz") as z:
                    assert np.array_equal(z[f"y_{split}"], y)
                    assert np.array_equal(z[f"trust_{split}"], trusted)
                    for point in ("best", "last"):
                        scores = z[f"{split}_{point}"]
                        assert scores.shape == y.shape and np.isfinite(scores).all()
                        margins[arm, point] = scores
            for mode, groups in (("physical", full), ("trusted_ge2", strict)):
                for (view, kind), group in sorted(groups.items()):
                    if not any(r[2] == 1 for r in group):
                        continue
                    source = view.split("__ys_")[0]
                    for point in ("best", "last"):
                        both = {}
                        for arm in ("N", "NC"):
                            scores = margins[arm, point]
                            rank = sorted(((cid, endpoint, lab, float(scores[mem].max()))
                                           for cid, endpoint, lab, mem in group), key=lambda r: (-r[3], r[0]))
                            both[arm] = {cid: i for i, (cid, *_) in enumerate(rank, 1)}
                            rows.append(dict(split=split, mode=mode, kind=kind, view=view,
                                             source=source, seed=seed, point=point, arm=arm, **report(rank)))
                        if mode == "physical" and point == "best":
                            for cid, endpoint, lab, mem in group:
                                if lab != 1:
                                    continue
                                pos = mem[trusted[mem] & (y[mem] == 1)]
                                nr = both["N"][cid]
                                cr = both["NC"][cid]
                                cases.append(dict(split=split, view=view, kind=kind, endpoint=endpoint,
                                                  cone_id=cid, seed=seed, rank_N=nr, rank_NC=cr,
                                                  rank_gain=nr-cr, physical_members=len(mem),
                                                  weak_pos_members=len(pos)))
    assert rows and cases
    metrics = ["recall@1", "recall@5", "recall@10", "checks@0.80", "checks@0.95",
               "positive@0.80", "positive@0.95", "known_negative@0.80", "known_negative@0.95",
               "unknown@0.80", "unknown@0.95"]
    macro = defaultdict(lambda: defaultdict(list))
    for row in rows:
        key = tuple(row[k] for k in ("split", "mode", "kind", "point", "seed", "arm"))
        macro[key][row["source"]].append(row)
    result = {}
    for key, sources in macro.items():
        result["|".join(map(str, key))] = {
            "sources": len(sources), "views": sum(map(len, sources.values())),
            **{m: statistics.mean(statistics.mean(r[m] for r in rr) for rr in sources.values())
               for m in metrics},
        }
    paired = {}
    for key in macro:
        if key[-1] != "N":
            continue
        n = result["|".join(map(str, key))]
        c = result["|".join(map(str, (*key[:-1], "NC")))]
        paired["|".join(map(str, key[:-1]))] = {m: c[m] - n[m] for m in metrics}
    for filename, records in (("VIEW_METRICS.csv", rows), ("POSITIVE_RANKS.csv", cases)):
        with (OUT / filename).open("x", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)
    with (OUT / "RESULTS.json").open("x", encoding="utf-8") as f:
        json.dump(dict(support=panel_support, source_macro=result, paired_delta=paired), f, indent=2)


if __name__ == "__main__":
    main()
