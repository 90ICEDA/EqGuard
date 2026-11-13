"""Prepare a small train-only independent endpoint panel without model updates."""
import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent
P = OUT.parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(P / "lcone_endpoint_frozen_20261112"))
from audit import S, Expressions, bind_lineage, binding, construct, endpoints, qualify, structural_cone

RECIPES = ("ys_abc", "ys_aig", "ys_nand")


def write(folder, name, value):
    path = folder / name
    if path.exists():
        assert json.loads(path.read_text(encoding="utf-8")) == value, name
        return
    with path.open("x", encoding="utf-8") as f:
        json.dump(value, f, indent=2)


class LogicOnlyPath:
    def __init__(self, path):
        self.path = path

    def read_text(self, **options):
        # The combinational evaluator consumes connectivity, not simulator timing units.
        return re.sub(r"(?m)^\s*`timescale[^\r\n]*", "", self.path.read_text(**options))


def selection(layouts, cache, all_eligible=False):
    pairs = defaultdict(dict)
    manifest = {r["view_name"]: r for r in S.rows(S.F / "view_manifest_cec.csv")}
    for v in layouts:
        m = manifest.get(v, {})
        if ("__inj" not in v or "__keep" in v or v not in cache or
                m.get("op") not in RECIPES or m.get("cec_status") != "PASS" or m.get("unproven") != "0"):
            continue
        src = m["src_view"]
        base = S.ROOT / "generate_trans/hosts" / m["host"]
        files = (base / "base" / f"{m['host']}_clean.v", S.F / "orig" / f"{src}.v",
                 S.F / "trans" / f"{v}.v", base / "provenance.json")
        if not all(x.is_file() for x in files):
            continue
        records = [r for r in S.read(files[-1]) if r["view"] == src and r["kind"] == "trojan"]
        if len(records) == 1:
            pairs[m["host"], src][m["op"]] = dict(view=v, files=[str(p) for p in files], source=src,
                                               recipe=m["op"], host=m["host"], cec=m, provenance=records[0])
    selected = []
    for host in sorted({h for h, _ in pairs}):
        eligible = sorted(s for h, s in pairs if h == host and set(pairs[h, s]) == set(RECIPES))
        for source in (eligible if all_eligible else eligible[:2]):
            selected.extend(pairs[host, source][r] for r in RECIPES)
    assert len(selected) >= 18 and len(selected) % len(RECIPES) == 0
    contract = S.read(S.CONTRACT)["shared_inputs"]
    forbidden = {v["view"].split("__ys_")[0].split("__keep")[0]
                 for split in ("val", "test") for v in contract["trans_" + split]["views"]}
    assert not forbidden & {x["source"] for x in selected}
    return selected


def assess(spec, records, mapping, physical):
    cp, op, tp, _ = map(Path, spec["files"])
    clean, orig, trans = [endpoints(LogicOnlyPath(p)) for p in (cp, op, tp)]
    inserted, replacements, missing = bind_lineage(spec["provenance"], clean, orig)
    states, restored, unresolved = binding(clean, orig, trans, replacements)
    expr = Expressions()
    evaluators = [construct(g, expr, states) for g in (clean, orig, trans)]
    unknown, results = Counter(), []
    target = trans[0]
    for r in records:
        rows = sorted(int(x) for x in r["phys_rows"].split("|") if x)
        if not rows:
            unknown["empty"] += 1
            continue
        kind, cid = r["kind"], r["cone_id"]
        identity = cid.split(":", 1)[1]
        try:
            if kind == "D":
                nets = [dict(g[0]["pins"][identity][1])["D"] for g in (clean, orig, trans)]
                assert "DFF" in target["pins"][identity][0]
            else:
                assert identity in trans[2]
                nets = [identity] * 3
            assert target["find"](nets[-1]) == target["find"](r["endpoint"])
            assert target["drivers"][target["find"](nets[-1])] == {r["driver"]}
            members, issues = structural_cone(trans, nets[-1])
            assert sorted(mapping[m] for m in members if m in mapping) == rows
            assert not (members - mapping.keys() - set(target["virtual_names"]))
            assert all(physical[i] for i in rows)
            if issues or (kind == "D" and identity not in states) or (kind == "PO" and
                    not all(identity in g[2] for g in (clean, orig))):
                raise ValueError("endpoint_or_boundary_unbound")
            values = [ev(n) for ev, n in zip(evaluators, nets)]
            assert members == values[-1][1]
            status, evidence, nvars, witness = qualify(expr, [x[0] for x in values])
            lineage = sorted(inserted & values[1][1])
            if status == "positive" and (missing or not lineage):
                status, evidence = "unknown", "unbound_manufacturing_lineage"
            if status == "unknown":
                unknown[evidence] += 1
                continue
            results.append(dict(view=spec["view"], source=spec["source"], recipe=spec["recipe"], kind=kind,
                                cone_id=cid, endpoint=identity, driver=r["driver"], driver_row=mapping.get(r["driver"]),
                                member_rows=rows, label=int(status == "positive"), evidence=evidence, inputs=nvars,
                                witness=witness, lineage=lineage if status == "positive" else []))
        except AssertionError:
            raise
        except (KeyError, ValueError, RecursionError) as ex:
            unknown[str(ex)] += 1
    expr.inputs.cache_clear()
    return results, dict(unknown), dict(restored=restored, unresolved=unresolved,
                                        bound_registers=len(states), missing_inserted=sorted(missing))


def freeze_budget(records):
    grouped = defaultdict(dict)
    for r in records:
        if r["driver_row"] is not None:
            key = (r["source"], r["kind"], r["cone_id"], r["label"])
            assert r["recipe"] not in grouped[key]
            grouped[key][r["recipe"]] = r
    matched = defaultdict(lambda: {0: [], 1: []})
    for (src, kind, cid, label), recipes in grouped.items():
        if set(recipes) == set(RECIPES):
            matched[src, kind][label].append((cid, recipes))
    chosen, budget = [], []
    for (src, kind), pool in sorted(matched.items()):
        n = min(len(pool[0]), len(pool[1]), 16)
        budget.append(dict(source=src, kind=kind, available_neg=len(pool[0]),
                           available_pos=len(pool[1]), per_class_endpoint_quota=n))
        for label in (0, 1):
            order = sorted(pool[label], key=lambda x: hashlib.sha256(f"42|{src}|{kind}|{x[0]}".encode()).digest())
            for _, recipes in order[:n]:
                chosen.extend(recipes[r] for r in RECIPES)
    assert len(chosen) == sum(x["per_class_endpoint_quota"] * 6 for x in budget)
    assert len({(x["view"], x["cone_id"]) for x in chosen}) == len(chosen)
    return chosen, budget


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--all-eligible", action="store_true")
    options = parser.parse_args()
    folder = OUT / "all_eligible" if options.all_eligible else OUT
    folder.mkdir(exist_ok=True)
    _, arrays, names, layouts = S.load_snapshot("train")
    path = P / "seed42_supervised_prep_20261109/CONE_CACHE_V2.csv"
    records = defaultdict(list)
    for r in S.rows(path):
        if r["split"] == "train" and r["kind"] in ("D", "PO"):
            records[r["view"]].append(r)
    selected = selection(layouts, records, options.all_eligible)
    rule = ("all eligible training sources, common abc/aig/nand" if options.all_eligible else
            "first two eligible source names per training host, common abc/aig/nand")
    write(folder, "SELECTION.json", dict(rule=rule,
                                 data=[dict(**x, sha256=[S.sha(p) for p in x["files"]]) for x in selected]))
    all_labels, reports = [], []
    for spec in selected:
        v = spec["view"]
        vr = S.view_rows(layouts, names, v)
        labels, unknown, q = assess(spec, records[v], vr, arrays["physical"])
        counts = Counter(f"{r['kind']}_{r['label']}" for r in labels)
        reports.append(dict(view=v, counts=dict(counts), unknown=unknown, q=q))
        all_labels.extend(labels)
        print(v, dict(counts), flush=True)
    examples, budget = freeze_budget(all_labels)
    write(folder, "TRAIN_ENDPOINTS.json", all_labels)
    write(folder, "BC_BUDGET.json", dict(count=len(examples), strata=budget, examples=examples))
    write(folder, "PREP_REPORT.json", dict(views=reports, certified=len(all_labels), shared_BC_examples=len(examples),
                                   training_updates=0, solver_calls=0))


if __name__ == "__main__":
    main()
