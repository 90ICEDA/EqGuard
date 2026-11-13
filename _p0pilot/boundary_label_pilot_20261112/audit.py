"""Read-only pilot on two transformed views. Writes one new audit JSON."""
import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict, deque
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
FOLD = ROOT / "generate_trans/folds/hosts_bt31"
SOURCE = "s15850t100__injzeta_d1_s42"
NAME = r"\\?[-\w.$]+(?:\[\d+\])?"
ATOM = rf"(?:{NAME}|1'[bBhH][01])"


def read(path):
    return re.sub(r"/\*.*?\*/|//[^\n]*", "", path.read_text(encoding="utf-8-sig"), flags=re.S)


class Netlist:
    def __init__(self, path, output_pins):
        text = read(path)
        self.aliases = {}
        for lhs, rhs in re.findall(r"\bassign\s+([^;=]+?)\s*=\s*([^;]+);", text):
            lhs, rhs = lhs.strip().lstrip("\\"), rhs.strip().lstrip("\\")
            if re.fullmatch(ATOM, lhs) and re.fullmatch(ATOM, rhs):
                if lhs in self.aliases and self.aliases[lhs] != rhs:
                    raise ValueError(("conflicting_assign", lhs))
                self.aliases[lhs] = rhs
        self.gates, self.drivers, self.loads = {}, defaultdict(list), defaultdict(set)
        self.primary_inputs, self.primary_outputs = set(), set()
        for direction, declaration in re.findall(r"(?m)^\s*(input|output)\s+([^;]+);", text):
            ports = self.primary_inputs if direction == "input" else self.primary_outputs
            ports.update(self.canonical(signal.strip().lstrip("\\")) for signal in declaration.split(","))
        for kind, gate, body in re.findall(
            rf"(?m)^\s*(\w+)\s+({NAME})\s*\(\s*(\.[^;]+?)\)\s*;", text
        ):
            if kind not in output_pins:
                raise ValueError(("unknown_cell", kind, gate))
            gate = gate.lstrip("\\")
            pins = {
                pin: self.canonical(net.strip().lstrip("\\"))
                for pin, net in re.findall(r"\.(\w+)\s*\(([^()]*)\)", body)
            }
            inputs = {p: n for p, n in pins.items() if p not in output_pins[kind] and n}
            outputs = {p: n for p, n in pins.items() if p in output_pins[kind] and n}
            self.gates[gate] = kind, inputs, outputs
            for pin, net in outputs.items():
                self.drivers[net].append((gate, pin))
            for net in inputs.values():
                self.loads[net].add(gate)

    def canonical(self, signal):
        seen = set()
        while signal in self.aliases:
            if signal in seen:
                raise ValueError(("alias_cycle", signal))
            seen.add(signal)
            signal = self.aliases[signal]
        return signal


def trace(graph, roots, stops):
    members, open_leaves, used_stops, active = set(), set(), set(), set()

    def visit(net):
        if net in stops:
            used_stops.add(net)
            return
        if re.fullmatch(r"1'[bBhH][01]", net):
            return
        drivers = graph.drivers.get(net, [])
        if len(drivers) != 1:
            open_leaves.add((net, "missing_driver" if not drivers else "multiple_drivers"))
            return
        gate, _ = drivers[0]
        kind, inputs, _ = graph.gates[gate]
        if kind.startswith(("DFF", "SDFF", "DFFAR", "LATCH")):
            open_leaves.add((net, "undeclared_state_boundary"))
            return
        if gate in active:
            raise ValueError(("combinational_cycle", gate))
        if gate in members:
            return
        members.add(gate)
        active.add(gate)
        for child in inputs.values():
            visit(child)
        active.remove(gate)

    for root in roots:
        visit(root)
    return members, sorted(open_leaves), used_stops


def evaluate(graph, root, variables, formula, mask):
    values = variables.copy()
    used = set()

    def value(net):
        if net in values:
            return values[net]
        if re.fullmatch(r"1'[bBhH][01]", net):
            return mask if net[-1] == "1" else 0
        (gate, pin), = graph.drivers[net]
        kind, ins, _ = graph.gates[gate]
        expr = formula[kind, pin]
        args = {p: value(n) for p, n in ins.items()}
        used.add((kind, pin, expr))
        mux = re.fullmatch(r"(\w+)\s*\?\s*(\w+)\s*:\s*(\w+)", expr)
        if mux:
            sel, yes, no = (args[x] for x in mux.groups())
            out = (sel & yes) | (~sel & no)
        else:
            if not re.fullmatch(r"[\w()~&|^\s]+", expr) or set(re.findall(r"\w+", expr)) - args.keys():
                raise ValueError(("unsupported_formula", kind, pin, expr))
            out = eval(expr, {"__builtins__": {}}, args)
        values[net] = out & mask
        return values[net]

    result = value(root)
    return result, sorted(used)


def truth_variables(inputs):
    cases = 1 << len(inputs)
    if cases < 8:
        return cases, {n: sum(1 << k for k in range(cases) if (k >> i) & 1)
                       for i, n in enumerate(inputs)}
    nbytes = cases // 8
    values = {}
    for i, net in enumerate(inputs):
        if i < 3:
            pattern = bytes((0xAA, 0xCC, 0xF0)[i:i+1])
        else:
            block = 1 << (i - 3)
            pattern = b"\0" * block + b"\xff" * block
        values[net] = int.from_bytes(pattern * (nbytes // len(pattern)), "little")
    return cases, values


def paths_to_open_leaves(graph, roots, stops, leaves):
    remaining = {n for n, _ in leaves}
    queue = deque((n, []) for n in roots)
    seen, paths = set(), {}
    while queue and remaining:
        net, path = queue.popleft()
        if net in seen or net in stops:
            continue
        seen.add(net)
        if net in remaining:
            paths[net] = {"primary_input": net in graph.primary_inputs, "path": path}
            remaining.remove(net)
            continue
        if len(graph.drivers[net]) == 1:
            gate, pin = graph.drivers[net][0]
            for ip, child in graph.gates[gate][1].items():
                queue.append((child, path + [[net, gate, pin, ip, child]]))
    assert not remaining
    return paths


def main():
    out = Path(__file__).parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=out / "PILOT_V2.json")
    args = parser.parse_args()
    library = ROOT.parent / "GraphSAINT-train/vali/verilog_lib.v"
    output_pins, formula = {}, {}
    for kind, body in re.findall(r"\bmodule\s+(\w+)\s*\([^;]+;(.+?)\bendmodule\b", read(library), re.S):
        output_pins[kind] = {
            p.strip() for group in re.findall(r"\boutput\s+([^;]+);", body) for p in group.split(",")
        }
        formula.update({(kind, p): e.strip() for p, e in re.findall(r"\bassign\s+(\w+)\s*=\s*([^;]+);", body)})
    source_path = FOLD / "orig" / f"{SOURCE}.v"
    source = Netlist(source_path, output_pins)
    inserted = {g for g in source.gates if g.startswith("Trojan")}
    inner_nets = {n for g in inserted for n in source.gates[g][2].values()}
    inputs = sorted({n for g in inserted for n in source.gates[g][1].values()} - inner_nets)
    outputs = sorted(n for n in inner_nets if source.loads[n] - inserted or n in source.primary_outputs)
    assert len(outputs) == 1
    source_members, source_open, _ = trace(source, outputs, set(inputs))
    assert source_members == inserted and not source_open
    cases, variables = truth_variables(inputs)
    mask = (1 << cases) - 1
    reference, formulas = evaluate(source, outputs[0], variables, formula, mask)

    data = FOLD / "data/for_train"
    files = json.loads((data / "metadata_trans.json").read_text(encoding="utf-8"))["file_ids"]
    names = (FOLD / "data/processed/node_names_trans.txt").read_text(encoding="utf-8").splitlines()
    classes = json.loads((data / "class_map_trans.json").read_text(encoding="utf-8"))
    trusted = np.load(data / "trust_trans.npy", mmap_mode="r")
    assert len(files) == len(names) == len(trusted)
    with (FOLD / "view_manifest_cec.csv").open(encoding="utf-8-sig", newline="") as f:
        manifest = {next(iter(r.values())): r for r in csv.DictReader(f)}
    docs = next((ROOT / "10.15").glob("00_*"))
    results = []
    for recipe in ("ys_id", "ys_nand"):
        view = f"{SOURCE}__{recipe}"
        trans_path = FOLD / "trans" / f"{view}.v"
        graph = Netlist(trans_path, output_pins)
        pairs = json.loads((docs / f"SAT_ALL_{view}.json").read_text(encoding="utf-8"))["results"]
        boundary = {}
        for net in inputs + outputs:
            refs = {
                f"{g}.{p}"
                for g in inserted
                for pinset in source.gates[g][1:]
                for p, wire in pinset.items()
                if wire == net
            }
            pins = {graph.canonical(r) for r in refs if r in graph.aliases}
            candidate = graph.canonical(net)
            assert candidate in graph.drivers or candidate in graph.loads
            assert not pins or pins == {candidate}, (view, net, pins, candidate)
            stored = [
                p for p in pairs if p.get("orig_net") == net and p.get("status") == "success!"
                and graph.canonical(p["trans_net"]) == candidate
            ]
            boundary[net] = {"target": candidate, "matching_aliases": sorted(refs & graph.aliases.keys()),
                             "reported_sat_rows": [p["trans_node"] for p in stored]}
        roots = [boundary[n]["target"] for n in outputs]
        target_variables = {boundary[n]["target"]: variables[n] for n in inputs}
        assert len(target_variables) == len(inputs)
        region, leaves, used = trace(graph, roots, set(target_variables))
        a, b = (boundary[n]["target"] for n in ("g4193_orig", "n935"))
        _, missing_cut, _ = trace(graph, roots, set(target_variables) - {a})
        target_formulas, differences, swap_differences, extended = [], None, None, None
        if not leaves:
            observed, target_formulas = evaluate(graph, roots[0], target_variables, formula, mask)
            swap = target_variables.copy()
            swap[a], swap[b] = swap[b], swap[a]
            swapped, _ = evaluate(graph, roots[0], swap, formula, mask)
            differences = (observed ^ reference).bit_count()
            swap_differences = (swapped ^ reference).bit_count()
            assert differences == 0 and swap_differences > 0 and missing_cut
        elif len(inputs) + len(leaves) <= 22 and all(reason == "missing_driver" for _, reason in leaves):
            # Free extension is a diagnostic, not a whole-design equivalence check.
            names_ext = inputs + [f"extra:{n}" for n, _ in leaves]
            cases_ext, variables_ext = truth_variables(names_ext)
            ext_mask = (1 << cases_ext) - 1
            tv = {boundary[n]["target"]: variables_ext[n] for n in inputs}
            tv.update({n: variables_ext[f"extra:{n}"] for n, _ in leaves})
            orig_ext, _ = evaluate(source, outputs[0], {n: variables_ext[n] for n in inputs}, formula, ext_mask)
            trans_ext, target_formulas = evaluate(graph, roots[0], tv, formula, ext_mask)
            delta = orig_ext ^ trans_ext
            witness = None
            if delta:
                k = (delta & -delta).bit_length() - 1
                witness = {n: (k >> i) & 1 for i, n in enumerate(names_ext)}
            extended = {"cases": cases_ext, "differences": delta.bit_count(), "witness": witness}

        mapping = json.loads((FOLD / "mappings" / f"{view}.json").read_text(encoding="utf-8"))["node_alignment"]
        candidates = {t for s in inserted for t in mapping.get(s, [])}
        reverse = defaultdict(set)
        for s, targets in mapping.items():
            for t in targets:
                reverse[t].add(s)
        rows = {n: i for i, (v, n) in enumerate(zip(files, names)) if v == view}
        assert rows.keys() == graph.gates.keys()
        counts = {}
        for tag, group in (("region", region), ("outside", rows.keys() - region)):
            counts[tag] = dict(Counter(
                ("trusted_" if trusted[rows[g]] else "untrusted_") + str(classes[str(rows[g])])
                for g in group
            ))
        leakage = {
            gate: sorted(net for net in graph.gates[gate][2].values()
                         if net not in roots and (graph.loads[net] - region or net in graph.primary_outputs))
            for gate in sorted(region)
        }
        results.append({
            "view": view, "cec_manifest": manifest.get(view), "graph_nodes": len(rows),
            "boundary": boundary, "region": sorted(region), "open_leaves": leaves,
            "open_leaf_paths": paths_to_open_leaves(graph, roots, set(target_variables), leaves),
            "unused_boundaries": sorted(target_variables.keys() - used),
            "target_sha256": hashlib.sha256(trans_path.read_bytes()).hexdigest(),
            "candidate_inside": sorted(candidates & region), "candidate_outside": sorted(candidates - region),
            "recovered_inside": sorted(region - candidates),
            "mixed_origin": {g: sorted(reverse[g]) for g in sorted(region) if reverse[g] & inserted and reverse[g] - inserted},
            "internal_outputs_shared_outside": {g: n for g, n in leakage.items() if n},
            "old_label_counts": counts,
            "outside_old_trusted_positive": sorted(g for g in rows.keys() - region
                                                   if trusted[rows[g]] and classes[str(rows[g])] == 1),
            "boundary_truth_cases": cases if not leaves else None, "truth_differences": differences,
            "swapped_boundary_truth_differences": swap_differences, "free_extension": extended,
            "missing_boundary_open_leaves": missing_cut, "target_formulas": target_formulas,
        })
    result = {"source": SOURCE, "source_members": sorted(inserted), "inputs": inputs,
              "source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
              "library_sha256": hashlib.sha256(library.read_bytes()).hexdigest(),
              "outputs": outputs, "source_formulas": formulas, "views": results}
    with args.output.open("x", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
