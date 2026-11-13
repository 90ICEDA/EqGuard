"""Offline diagnosis of the seed42 head pilot on its validation panel."""
import csv
import hashlib
import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import average_precision_score, roc_auc_score

OUT = Path(__file__).resolve().parent
P = OUT.parent
RUN = P / "lcone_head_seed42_20261112"
sys.dont_write_bytecode = True
sys.path.insert(0, str(P / "lcone_head_protocol_20261112"))
from eval_gate import evaluate_view, head, prefix, validation_inputs
from gate import TRAIN, sha, training_inputs


def read(p):
    return json.loads(p.read_text(encoding="utf-8"))


def write_csv(name, data):
    with (OUT / name).open("x", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(data[0]))
        w.writeheader()
        w.writerows(data)


def load_views(asset, rows, anchor):
    data = defaultdict(dict)
    for r in rows:
        i = r["feature_row"]
        mem = asset["members"][asset["ptr"][i]:asset["ptr"][i+1]]
        top = float(anchor[mem].max())
        assert top == float(asset["B"][i, 0])
        data[r["view"], r["kind"]][r["cone_id"]] = (r["status"], mem, i, int(mem[anchor[mem] == top].min()))
    return data


def checkpoint(arm, point, expected):
    path = RUN / arm / f"{point}.pt"
    assert sha(path) == expected
    m = head().cuda().eval().requires_grad_(False)
    m.load_state_dict(torch.load(path, weights_only=True, map_location="cuda")["state"], strict=True)
    return m


def predict(m, x):
    with torch.inference_mode():
        y = m(torch.as_tensor(x, device="cuda")).flatten().cpu().numpy()
    assert np.isfinite(y).all()
    return y


def readouts(rr, a, b):
    labels = {c: row[0] for c, row in rr.items()}
    group = {c: (row[0], row[1]) for c, row in rr.items()}
    pos = sum(l == "positive" for l in labels.values())
    by_winner = defaultdict(list)
    for c, row in rr.items():
        by_winner[row[3]].append(c)
    members = {w: set().union(*(set(rr[c][1]) for c in cs)) for w, cs in by_winner.items()}

    def order(scores):
        return sorted(by_winner, key=lambda w: min((-scores[c], c) for c in by_winner[w]))

    aa, bb = order(a), order(b)
    bins = (32, 64, 128, 256, 512)
    bins_of = {w: int(np.searchsorted(bins, len(members[w]), side="left")) for w in aa}
    buckets = defaultdict(list)
    for w in bb:
        buckets[bins_of[w]].append(w)
    seq = {k: iter(v) for k, v in buckets.items()}
    size_order_b = [next(seq[bins_of[w]]) for w in aa]
    assert [bins_of[w] for w in size_order_b] == [bins_of[w] for w in aa]
    result = []

    def measure(mode, groups, units):
        q = prefix(units, group, max_gates=512)
        selected = units[:q["units"]]
        used = set().union(*(set(rr[c][1]) for u in selected for c in u))
        first = units[q["units"]] if q["units"] < len(units) else []
        spill = set().union(*(set(rr[c][1]) for c in first)) - used
        assert len(used) == q["gates"]
        d = dict(mode=mode, recall=q["positive"] / pos, negative=q["negative"], used_gates=q["gates"],
                 units=q["units"], endpoint_count=q["endpoint_count"], next_increment=len(spill),
                 next_over_cap=bool(first and len(spill)+len(used) > 512),
                 head_group_gates=len(members[groups[0]]) if groups else None,
                 head_group_endpoints=len(by_winner[groups[0]]) if groups else None,
                 first_positive_group=next((j for j, w in enumerate(groups, 1)
                                            if any(labels[c] == "positive" for c in by_winner[w])), None))
        result.append(d)

    for name, scores in (("A", a), ("B", b)):
        measure(name+"_endpoint", [], [[c] for c in sorted(scores, key=lambda c: (-scores[c], c))])
    for name, group_order in (("A", aa), ("B", bb), ("B_size_bins_from_A", size_order_b)):
        measure(name+"_atomic", group_order, [by_winner[w] for w in group_order])
        if name != "B_size_bins_from_A":
            for within_name, scores in (("A", a), ("B", b)):
                measure(f"{name}_groups_{within_name}_within", group_order,
                        [[c] for w in group_order for c in sorted(by_winner[w], key=lambda c: (-scores[c], c))])
    return result


def discrimination(score, y):
    p = score[y == 1]
    n = score[y == 0]
    return dict(ap=float(average_precision_score(y, score)), auc=float(roc_auc_score(y, score)),
                balanced_bce=float((np.logaddexp(0, -p).mean() + np.logaddexp(0, n).mean()) / 2))


def main():
    status = read(RUN / "RUN_STATUS.json")
    asset, inventory = validation_inputs("best")
    train, labels, _ = training_inputs()
    train_rows = read(TRAIN / "BC_BUDGET.json")["examples"]
    with np.load(P / "seed42_nc_ablation_20261109/N_scores.npz") as z:
        data = load_views(asset, inventory, z["val_best"])
    a = asset["B"][:, 0]
    policy_rows, mask_rows, fit = [], [], []
    for point in ("best", "last"):
        saved, masked = {}, {}
        for arm in ("B", "C"):
            m = checkpoint(arm, point, status["checkpoints"][arm][point+"_sha256"])
            with np.load(RUN / arm / "VAL_SCORES.npz") as z:
                assert np.array_equal(z["keys"], asset["keys"])
                saved[arm] = z[point]
            assert np.allclose(saved[arm], predict(m, asset[arm]), rtol=0, atol=1e-6)
            tr = predict(m, train[arm])
            for rec in ("all", "ys_abc", "ys_aig", "ys_nand"):
                take = np.array([rec == "all" or x["recipe"] == rec for x in train_rows])
                fit.append(dict(arm=arm, point=point, recipe=rec, **discrimination(tr[take], labels[take])))
            if arm == "C":
                masked["C_zero"] = predict(m, asset["B"])
                # Preserve within-view context distributions while breaking endpoint identity.
                permutation = np.arange(len(a))
                for (view, kind), rr in data.items():
                    by_size = defaultdict(list)
                    for _, mem, i, _ in rr.values():
                        by_size[len(mem).bit_length()].append(i)
                    for size, rr_ids in sorted(by_size.items()):
                        seed = int.from_bytes(hashlib.sha256(f"{view}|{kind}|{size}".encode()).digest()[:8], "little")
                        permutation[rr_ids] = np.random.default_rng(seed).permutation(rr_ids)
                x = np.array(asset["C"], copy=True)
                x[:, 8:] = x[permutation, 8:]
                masked["C_permuted"] = predict(m, x)
                fit.append(dict(arm="C_context_shuffle", point=point, recipe="validation_context_identity",
                                ap=None, auc=None, balanced_bce=None,
                                unchanged_context_rows=int((permutation == np.arange(len(a))).sum()),
                                total_rows=len(a)))
        for (view, kind), rr in sorted(data.items()):
            if kind != "D":
                continue
            source, recipe = view.rsplit("__ys_", 1)
            pos = sum(r[0] == "positive" for r in rr.values())
            if not pos:
                continue
            base = dict(view=view, source=source, recipe=recipe, point=point)
            av = {c: float(a[r[2]]) for c, r in rr.items()}
            bv = {c: float(saved["B"][r[2]]) for c, r in rr.items()}
            policy_rows.extend(dict(**base, **r) for r in readouts(rr, av, bv))
            g = {c: (r[0], r[1]) for c, r in rr.items()}
            fixed = {c: r[3] for c, r in rr.items()}
            for name, scores in {"A": a, **saved, **masked}.items():
                v = {c: float(scores[r[2]]) for c, r in rr.items()}
                ii = [r[2] for r in rr.values() if r[0] != "unknown"]
                y = np.array([r[0] == "positive" for r in rr.values() if r[0] != "unknown"], np.int32)
                metrics = discrimination(scores[ii], y)
                er = evaluate_view(g, v, fixed, (512,))
                for policy, result in er.items():
                    q, c = result["gates_512"], result["recall_100"]
                    mask_rows.append(dict(**base, arm=name, policy=policy, recall_512=q["positive"]/pos,
                                          neg_at_full_recall=c["negative"], gates_at_full_recall=c["gates"], **metrics))
    write_csv("GROUP_DIAGNOSTICS.csv", policy_rows)
    write_csv("CONTEXT_DIAGNOSTICS.csv", mask_rows)
    with (OUT / "FIT.json").open("x", encoding="utf-8") as f:
        json.dump(fit, f, indent=2)
    print(len(policy_rows), len(mask_rows))


if __name__ == "__main__":
    main()
