"""Recompute the panel from saved margins with an independent queue walk."""
import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent
ASSETS = OUT.parent / "lcone_confirmation_assets_20261112"


def read(p):
    return json.loads(p.read_text(encoding="utf-8"))


def main():
    with (OUT / "BY_VIEW.csv").open(encoding="utf-8-sig", newline="") as f:
        table = {(int(r["seed"]), r["view"], r["arm"], r["point"], r["policy"], r["setting"]): r
                 for r in csv.DictReader(f)}
    checked = 0
    for v in read(ASSETS / "GRAPH_REPORT.json")["views"]:
        name = v["view"]
        p = ASSETS / name
        rows = [r for r in read(p / "ENDPOINTS.json") if r["kind"] == "D" and r["rankable"]]
        with np.load(p / "GRAPH_ENDPOINTS.npz", allow_pickle=False) as f:
            ptr, members = f["ptr"], f["members"]
        ends = [r["endpoint"] for r in rows]
        mm = [members[ptr[r["packed_index"]]:ptr[r["packed_index"]+1]] for r in rows]
        ls = [r["status"] for r in rows]
        assert ls.count("positive") == 2 and ls.count("negative") == 574 and ls.count("unknown") == 604
        for seed in (42, 1, 2):
            with np.load(OUT / f"{name}_s{seed}_SCORES.npz", allow_pickle=False) as f:
                assert f["endpoint"].tolist() == ends
                margin = f["margin"]
                scored = [("A", "frozen", f["A"]), ("B", "best", f["B_best"]), ("B", "last", f["B_last"])]
            winner = [int(m[np.argmax(margin[m])]) for m in mm]
            assert np.array_equal(scored[0][2], [margin[w] for w in winner])
            for arm, point, score in scored:
                order = sorted(range(len(score)), key=lambda i: (-score[i], ends[i]))
                fixed = defaultdict(list)
                for i in order:
                    fixed[winner[i]].append(i)
                for policy, seq in (("endpoint", [[i] for i in order]), ("fixed_group", list(fixed.values()))):
                    cutoff = min(score[q[0]] for q in seq if any(ls[i] == "positive" for i in q))
                    for setting in ("gates_512", "recall_100"):
                        gates, idx, units = set(), [], 0
                        for q in seq:
                            new = set().union(*(set(mm[i]) for i in q))
                            if setting == "gates_512" and len(gates | new) > 512:
                                break
                            if setting == "recall_100" and score[q[0]] < cutoff:
                                break
                            units += 1
                            gates.update(new)
                            idx.extend(q)
                        r = table[seed, name, arm, point, policy, setting]
                        for k, x in dict(gates=len(gates), units=units, endpoint_count=len(idx),
                                         **{lab: sum(ls[i] == lab for i in idx) for lab in ("positive", "negative", "unknown")}).items():
                            assert int(r[k]) == x, (seed, name, arm, point, policy, setting, k)
                        checked += 1
    assert checked == len(table) == 144
    with (OUT / "REPLAY.json").open("x", encoding="utf-8") as f:
        json.dump(dict(passed=True, rows=checked, independent_sources=1), f, indent=2)
    print(checked)


if __name__ == "__main__":
    main()
