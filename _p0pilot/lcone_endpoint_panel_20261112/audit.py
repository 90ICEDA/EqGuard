"""Audit selected endpoint cones and build an independent free-state evaluation panel."""
import csv
import argparse
import json
import math
import random
import sys
from collections import Counter, defaultdict
from functools import cache
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
P = ROOT / "_p0pilot"
OUT = Path(__file__).parent
RUN = P / "seed42_nc_ablation_20261109"
sys.path.insert(0, str(P / "seed42_supervised_prep_20261109"))
import cone_builder as B
S = B.S

VIRTUAL = {
    "V2_ASSIGN_AND": ("&", ("A", "B")), "V2_ASSIGN_OR": ("|", ("A", "B")),
    "V2_ASSIGN_XOR": ("^", ("A", "B")), "V2_ASSIGN_NOT": ("~", ("A",)),
    "V2_ASSIGN_MUX": ("?", ("S", "A", "B")),
}


def endpoints(path):
    g = S.raw_network(path, S.lib_pins)
    pi, po = B.declared_ports(path.read_text(encoding="utf-8"))
    pis = defaultdict(set)
    for n in pi:
        pis[g["find"](n)].add(n)
    return g, pis, po


class Expressions:
    def __init__(self):
        self.nodes, self.index = [], {}

    def make(self, op, *a):
        if op in ("&", "|", "^"):
            a = tuple(sorted(a))
        key = (op, *a)
        if key not in self.index:
            self.index[key] = len(self.nodes)
            self.nodes.append(key)
        return self.index[key]

    @cache
    def inputs(self, idx):
        op, *a = self.nodes[idx]
        if op == "var":
            return frozenset(a)
        if op == "const":
            return frozenset()
        return frozenset().union(*(self.inputs(i) for i in a))

    def evaluator(self, env, mask):
        @cache
        def evaluate(i):
            op, *a = self.nodes[i]
            if op == "var":
                return env[a[0]]
            if op == "const":
                return mask if a[0] else 0
            b = [evaluate(i) for i in a]
            if op == "~":
                return b[0] ^ mask
            if op == "&":
                return b[0] & b[1]
            if op == "|":
                return b[0] | b[1]
            if op == "^":
                return b[0] ^ b[1]
            if op == "?":
                return (b[0] & b[1]) | ((b[0] ^ mask) & b[2])
            raise ValueError(op)
        return evaluate


def construct(network, expr, allowed_states):
    g, pis, _ = network
    active = set()

    def from_ast(ast, env):
        op, *a = ast
        if op == "leaf":
            if a[0] in ("0", "1", "1'b0", "1'b1"):
                return expr.make("const", int(a[0][-1]))
            return wire(env[a[0]])[0]
        return expr.make(op, *(from_ast(x, env) for x in a))

    @cache
    def cached(net):
        if net in ("#0", "#1"):
            return expr.make("const", int(net[-1])), frozenset()
        owners = g["drivers"].get(net, set())
        if net in pis:
            if len(pis[net]) != 1 or owners:
                raise ValueError("ambiguous_PI:" + net)
            return expr.make("var", "PI:" + next(iter(pis[net]))), frozenset()
        if len(owners) != 1:
            raise ValueError("driver_count:" + net)
        cell, = owners
        kind, connections = g["pins"][cell]
        ports = dict(connections)
        if "DFF" in kind:
            outputs = [p for p, n in connections if n == net and p in ("Q", "QN")]
            if cell not in allowed_states or len(outputs) != 1:
                raise ValueError("unbound_state:" + cell)
            q = expr.make("var", "Q:" + cell)
            return (expr.make("~", q) if outputs[0] == "QN" else q), frozenset()
        if kind in VIRTUAL:
            op, ins = VIRTUAL[kind]
            ast = (op, *(("leaf", p) for p in ins))
        else:
            output, = [p for p, n in connections if n == net and p in S.lib_pins[kind]["outputs"]]
            ins = S.lib_pins[kind]["inputs"]
            ast = S.LIB.ast(kind, output)
        result = from_ast(ast, ports)
        return result, frozenset({cell}).union(*(wire(ports[p])[1] for p in ins))

    def wire(raw):
        net = g["find"](raw)
        if net in active:
            raise ValueError("loop:" + net)
        active.add(net)
        try:
            return cached(net)
        finally:
            active.remove(net)
    return wire


def structural_cone(network, endpoint):
    graph, pis, _ = network
    pending = [endpoint]
    seen, members, issues = set(), set(), set()
    while pending:
        net = graph["find"](pending.pop())
        if net in seen:
            continue
        seen.add(net)
        if net in ("#0", "#1"):
            continue
        owners = graph["drivers"].get(net, set())
        if net in pis:
            if owners or len(pis[net]) != 1:
                issues.add(("ambiguous_PI", net))
            continue
        if len(owners) != 1:
            issues.add(("nonbinary_or_driver_count", net))
            continue
        cell, = owners
        kind, pins = graph["pins"][cell]
        if "DFF" in kind:
            continue
        members.add(cell)
        inputs = VIRTUAL[kind][1] if kind in VIRTUAL else S.lib_pins[kind]["inputs"]
        pending.extend(n for p, n in pins if p in inputs)
    return members, sorted(issues)


def binding(clean, orig, trans):
    def reg(g):
        return {c: (typ, dict(pins)) for c, (typ, pins) in g["pins"].items() if "DFF" in typ}
    a, b, c = [reg(x[0]) for x in (clean, orig, trans)]
    allowed = set()
    for name in a.keys() & b.keys() & c.keys():
        if a[name][0] != b[name][0] or b[name][0] != c[name][0]:
            continue
        if any(not any(pin in x[name][1] for pin in ("Q", "QN")) for x in (a, b, c)):
            continue
        # A preserved register identity requires an actual shared Q/QN pin signal or alias.
        stable = any(
            pin in a[name][1] and pin in b[name][1] and pin in c[name][1]
            and a[name][1][pin] == b[name][1][pin]
            and trans[0]["find"](b[name][1][pin]) == c[name][1][pin]
            for pin in ("Q", "QN")
        )
        if stable:
            allowed.add(name)
    return allowed


def bind_lineage(record, clean, orig):
    a, b = clean[0], orig[0]
    accepted, replacements, missing = set(), {}, set()
    for gate in record["new_gates"]:
        if gate in b["pins"] and gate not in a["pins"]:
            accepted.add(gate)
            continue
        replacement = gate[:-2] + "HJ" if gate.endswith("PD") else ""
        if replacement in b["pins"] and replacement not in a["pins"]:
            kind, connections = b["pins"][replacement]
            pins = dict(connections)
            for op in S.lib_pins[kind]["outputs"]:
                if op not in pins:
                    continue
                net = pins[op]
                old_owners = a["drivers"].get(a["find"](net), set())
                if len(old_owners) != 1:
                    continue
                for p in S.lib_pins[kind]["inputs"]:
                    if p not in pins or pins[p] == net:
                        continue
                    if b["drivers"].get(pins[p], set()) == old_owners:
                        accepted.add(replacement)
                        replacements[gate] = {"instance": replacement, "output": net,
                                              "original_driver": next(iter(old_owners)), "original_signal": pins[p]}
                        break
        if gate not in replacements:
            missing.add(gate)
    return accepted, replacements, missing


def qualify(expr, roots):
    variables = sorted(set().union(*(expr.inputs(r) for r in roots)))
    if len(variables) <= 12:
        count = 1 << len(variables)
        env = {n: sum(1 << k for k in range(count) if (k >> j) & 1) for j, n in enumerate(variables)}
        method = "exhaustive_free_PI_Q"
    else:
        count = 2048
        rng = random.Random(844321)
        env = {n: rng.getrandbits(count) for n in variables}
        method = "free_PI_Q_witness_search"
    ev = expr.evaluator(env, (1 << count) - 1)
    clean, orig, trans = (ev(r) for r in roots)
    if orig == trans and clean == orig and (method.startswith("exhaustive") or len(set(roots)) == 1):
        if len(set(roots)) == 1:
            method = "identical_boolean_expression"
        return "negative", method, len(variables), None
    # Both inserted source and target must differ from clean on the same vector.
    diff = (orig ^ clean) & (trans ^ clean)
    if diff:
        k = (diff & -diff).bit_length() - 1
        witness = {n: (env[n] >> k) & 1 for n in variables}
        observed = [expr.evaluator(witness, 1)(r) for r in roots]
        assert observed[0] != observed[1] == observed[2]
        return "positive", method, len(variables), {"assignment": witness, "clean_orig_trans": observed}
    return "unknown", "no_verified_difference_or_equality", len(variables), None


def choose():
    diffs = defaultdict(list)
    for r in S.rows(P / "lcone_endpoint_offline_20261112/POSITIVE_RANKS.csv"):
        diffs[(r["split"], r["kind"], r["view"], r["cone_id"])].append(int(r["rank_gain"]))
    result = defaultdict(set)
    for split in ("val", "test"):
        for kind in ("D", "PO"):
            rows = sorted((sum(d), v, c) for (s, k, v, c), d in diffs.items()
                          if s == split and k == kind and len(d) == 3)
            for _, v, c in (rows[0], rows[-1]):
                result[(split, v)].add(c)
    result["val", "s38417t100__injepsilon_d1_s42__ys_abc"].add("D:DFF_378_Q_reg")
    result["test", "s38584t100__injgamma_d1_s42__ys_aig"].add("D:DFF_1100_Q_reg")
    return result


def compare(panel, scores):
    result = []
    for (split, view, kind), cases in sorted(panel.items()):
        pos = sum(x["status"] == "positive" for x in cases)
        neg = sum(x["status"] == "negative" for x in cases)
        if not pos or not neg:
            continue
        for seed in (42, 1, 2):
            for arm in ("N", "NC"):
                for point in ("best", "last"):
                    m = scores[split, seed, arm, point]
                    ranked_all = sorted(((float(m[x["rows"]].max()), x["cone_id"], x["status"]) for x in cases),
                                        key=lambda x: (-x[0], x[1]))
                    for pool, ranked in (("certified", [x for x in ranked_all if x[2] != "unknown"]),
                                         ("all_nonempty", ranked_all)):
                        row = dict(split=split, view=view, kind=kind, pool=pool, seed=seed, arm=arm,
                                   point=point, positive=pos, negative=neg, unknown=len(ranked)-pos-neg)
                        for k in (1, 5, 10):
                            row[f"recall_at_{k}"] = sum(x[2] == "positive" for x in ranked[:k]) / pos
                        for q in (80, 95, 100):
                            thresh = [x[0] for x in ranked if x[2] == "positive"][math.ceil(q * pos / 100) - 1]
                            selected = [x for x in ranked if x[0] >= thresh]
                            fp = sum(x[2] == "negative" for x in selected)
                            unk = sum(x[2] == "unknown" for x in selected)
                            row[f"checks_{q}"] = len(selected)
                            row[f"recall_{q}"] = (len(selected) - fp - unk) / pos
                            row[f"false_positive_{q}"] = fp
                            row[f"fpr_{q}"] = fp / neg
                            row[f"unknown_checks_{q}"] = unk
                        result.append(row)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path, default=OUT / "PANEL_V4.json")
    parser.add_argument("--csv", type=Path, default=OUT / "METRICS_V4.csv")
    args = parser.parse_args()
    selection = choose()
    manifest = {r["view_name"]: r for r in S.rows(S.F / "view_manifest_cec.csv")}
    by_view, panel, scores, inventory = [], defaultdict(list), {}, []
    for split in ("val", "test"):
        _, arrays, names, layouts = S.load_snapshot(split)
        path = (RUN / "CONE_CACHE_TEST.csv" if split == "test" else
                P / "seed42_supervised_prep_20261109/CONE_CACHE_V2.csv")
        saved = defaultdict(list)
        for r in S.rows(path):
            if (split, r["view"]) in selection and r["split"] == split and r["kind"] in ("D", "PO"):
                saved[r["view"]].append(r)
        for seed in (42, 1, 2):
            for arm in ("N", "NC"):
                suffix = "" if seed == 42 else f"_s{seed}"
                with np.load(RUN / f"{arm}{suffix}_scores.npz") as z:
                    assert np.array_equal(z[f"y_{split}"], arrays["y"])
                    assert np.array_equal(z[f"trust_{split}"], arrays["trusted"])
                    for point in ("best", "last"):
                        scores[split, seed, arm, point] = z[f"{split}_{point}"]
        for view, records in saved.items():
            m = manifest[view]
            assert m["cec_status"] == "PASS" and m["unproven"] == "0"
            src, host = m["src_view"], m["host"]
            base = S.ROOT / "generate_trans/hosts" / host
            provenance = [x for x in S.read(base / "provenance.json") if x["view"] == src and x["kind"] == "trojan"]
            assert len(provenance) == 1
            cp, op, tp = (base / "base" / f"{host}_clean.v",
                          S.F / "orig" / f"{src}.v", S.F / "trans" / f"{view}.v")
            clean, orig, trans = [endpoints(p) for p in (cp, op, tp)]
            inserted, replacements, missing_lineage = bind_lineage(provenance[0], clean, orig)
            states = binding(clean, orig, trans)
            expr = Expressions()
            evals = [construct(n, expr, states) for n in (clean, orig, trans)]
            mapping = S.view_rows(layouts, names, view)
            view_summary = Counter()
            for r in records:
                kind, cid = r["kind"], r["cone_id"]
                priority = cid in selection[split, view]
                rid = cid.split(":", 1)[1]
                cache_rows = {int(x) for x in r["phys_rows"].split("|") if x}
                row = dict(split=split, view=view, kind=kind, cone_id=cid, priority=priority,
                           n_cached=len(cache_rows), endpoint=r["endpoint"], driver=r["driver"])
                if not cache_rows:
                    view_summary["empty_cached"] += 1
                    continue
                nets = []
                # Audit target cone first so unsupported clean/source evidence does not obscure cache defects.
                try:
                    target = trans[0]
                    if kind == "D":
                        typ, p = target["pins"][rid]
                        assert "DFF" in typ and target["find"](r["endpoint"]) == dict(p)["D"]
                        target_net = dict(p)["D"]
                    else:
                        assert rid in trans[2] and target["find"](r["endpoint"]) == target["find"](rid)
                        target_net = rid
                    canonical = target["find"](target_net)
                    assert target["drivers"][canonical] == {r["driver"]}
                    gates, structural_issues = structural_cone(trans, target_net)
                    reconstructed = {mapping[g] for g in gates if g in mapping}
                    missing = sorted(gates - mapping.keys() - set(target["virtual_names"]))
                    row.update(cache_only=len(cache_rows - reconstructed), rebuild_only=len(reconstructed - cache_rows),
                               missing_physical=len(missing))
                    assert all(arrays["physical"][i] for i in reconstructed)
                    if cache_rows != reconstructed or missing:
                        raise ValueError("cache_member_or_graph_mismatch")
                    view_summary["physical_cone_exact"] += 1
                    row["cache_exact"] = True
                    if structural_issues:
                        row["structural_issues"] = structural_issues
                        raise ValueError("structural_boundary_open")
                    trans_root, semantic_gates = evals[2](target_net)
                    assert semantic_gates == gates
                    for graph in (clean, orig):
                        if kind == "D":
                            if rid not in states:
                                raise ValueError("endpoint_register_identity_unbound")
                            nets.append(dict(graph[0]["pins"][rid][1])["D"])
                        else:
                            if rid not in graph[2]:
                                raise ValueError("endpoint_PO_identity_unbound")
                            nets.append(rid)
                    clean_result, orig_result = [ev(n) for ev, n in zip(evals[:2], nets)]
                    roots = [clean_result[0], orig_result[0], trans_root]
                    status, evidence, nvars, witness = qualify(expr, roots)
                    lineage = sorted(orig_result[1] & inserted)
                    if status == "positive" and (not lineage or missing_lineage):
                        status, evidence, witness = "unknown", "witness_without_inserted_lineage", None
                    row.update(status=status, evidence=evidence, inputs=nvars, witness=witness)
                    if status == "positive":
                        row["inserted_cells_in_source_cone"] = lineage
                except (ValueError, AssertionError, KeyError, RecursionError) as exc:
                    row.update(status="unknown", evidence=f"{type(exc).__name__}:{exc}")
                view_summary[row["status"]] += 1
                inventory.append(row)
                panel[split, view, kind].append({**row, "rows": sorted(cache_rows)})
            by_view.append(dict(split=split, view=view, bound_registers=len(states),
                                source=src, cec=m, counts=dict(view_summary),
                                provenance=provenance[0]["new_gates"],
                                missing_source_provenance=sorted(missing_lineage),
                                verified_source_replacements=replacements,
                                netlist_sha=[S.sha(p) for p in (cp, op, tp)]))
            # Drop expression cache between views.
            expr.inputs.cache_clear()
            print(split, view, dict(view_summary), flush=True)
    metrics = compare(panel, scores)
    with args.json.open("x", encoding="utf-8") as f:
        json.dump(dict(views=by_view, endpoints=inventory, metrics=metrics), f, indent=2)
    if metrics:
        with args.csv.open("x", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(metrics[0]))
            writer.writeheader()
            writer.writerows(metrics)


if __name__ == "__main__":
    main()
