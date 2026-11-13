"""Build rank-unread confirmation graphs and endpoint coordinates."""
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent
P = OUT.parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(P / "lcone_endpoint_frozen_20261112"))
from audit import S, endpoints, structural_cone
sys.path.insert(0, str(P / "control_boundary_v3_20261104"))
import feature_encoding_v3_po as V


def graph(path, physical, lib, mapping, order):
    net = endpoints(path)[0]
    assert set(physical) == net["cells"].keys() - set(net["virtual_names"])
    parsed = V.parse(path, physical, lib)
    aux = [r["name"] for r in parsed["virtual_nodes"]]
    assert aux == net["virtual_names"]
    names = physical + aux
    rows = {n: i for i, n in enumerate(names)}
    assert len(rows) == len(names)
    expected = {(rows[a], rows[b]) for a, succ in net["succ"].items() for b in succ}
    assert expected == set(map(tuple, parsed["edge_index"].T))
    raw = V.features(parsed, mapping, order)
    assert raw.shape == (len(names), 39) and np.isfinite(raw).all()
    assert {names[i] for i in np.flatnonzero(raw[:, 30] == 0)} == net["pocells"]
    return net, parsed, raw, names, rows


def control(lib, mapping, order):
    _, _, names, layouts = S.load_snapshot("val")
    view = "s38417t100__injepsilon_d1_s42__ys_abc"
    q = layouts[view]
    physical = names[q["old_start"]:q["old_stop"]]
    _, parsed, x, _, _ = graph(S.F / "trans" / f"{view}.v", physical, lib, mapping, order)
    folder = P / "control_boundary_v3_20261104/inputs/trans_val"
    lo, hi = q["start"], q["stop"]
    xv = np.load(folder / "x39.npy", mmap_mode="r")[lo:hi]
    edge = np.load(folder / "edge_index.npy", mmap_mode="r")
    keep = (lo <= edge[0]) & (edge[0] < hi)
    assert np.array_equal(parsed["edge_index"], edge[:, keep] - lo)
    assert np.array_equal(parsed["edge_roles"], np.load(folder / "edge_roles.npy", mmap_mode="r")[keep])
    assert np.array_equal(x, xv)
    return dict(view=view, nodes=len(x), features_equal=True, directed_edges_equal=True, edge_roles_equal=True)


def main():
    registry = P / "lcone_head_gate_20261112/CONFIRMATION_REGISTRY.json"
    records = [r for r in S.read(registry)["registered"] if r["status"] == "registered_evidence_only"]
    assert len(records) == 4
    lib = V.load_library(S.F / "verilog_lib.v")
    mapping = {r["full_gate_name"]: r["simplified_gate_type"]
               for r in S.read(S.F / "gate_full_to_simplified_mapping.json")}
    order = S.read(S.F / "gatelookup_recommended.json")["simplified_gate_type_order"]
    assert V.COLS[:25] == ["gate_" + n for n in order]
    c = control(lib, mapping, order)
    reports = []
    for r in records:
        path = S.ROOT / r["target"]
        assert S.sha(path) == r["sha256"]["target"]
        first = endpoints(path)
        physical = [n for n in first[0]["cells"] if n not in set(first[0]["virtual_names"])]
        net, parsed, x, names, rows = graph(path, physical, lib, mapping, order)
        targets = [("D", n, dict(pins)["D"]) for n, (kind, pins) in net["pins"].items()
                   if "DFF" in kind and "D" in dict(pins)]
        targets += [("PO", po, po) for po in sorted(first[2])]
        truth = {(e["kind"], e["endpoint"]): e["status"] for e in r["endpoints"]}
        meta, members, ptr = [], [], [0]
        verified = set()
        for kind, name, endpoint in targets:
            key = kind, name
            status = truth.get(key, "unknown")
            cells, issues = structural_cone(first, endpoint)
            owners = net["drivers"].get(net["find"](endpoint), set())
            mem = sorted(rows[g] for g in cells if rows[g] < len(physical))
            item = dict(kind=kind, endpoint=name, status=status)
            if len(owners) != 1 or issues or not mem:
                assert status != "positive", (path, item)
                item.update(rankable=False, reason="empty_or_open")
            else:
                driver, = owners
                assert driver in cells
                item.update(rankable=True, driver_row=rows[driver], packed_index=len(ptr)-1)
                members.extend(mem)
                ptr.append(len(members))
                if status != "unknown":
                    verified.add(key)
            meta.append(item)
        assert verified == truth.keys(), (path, truth.keys()-verified)
        folder = OUT / path.stem
        folder.mkdir(exist_ok=False)
        a = folder / "GRAPH_ENDPOINTS.npz"
        with a.open("xb") as f:
            np.savez_compressed(f, x39=x, edge_index=parsed["edge_index"], edge_roles=parsed["edge_roles"],
                                names=np.asarray(names), physical=np.arange(len(names)) < len(physical),
                                members=np.asarray(members, np.int64), ptr=np.asarray(ptr, np.int64))
        with (folder / "ENDPOINTS.json").open("x", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
        counts = Counter(f"{x['kind']}|{x['status']}" for x in meta if x["rankable"])
        reports.append(dict(view=path.stem, source=r["source"], physical=len(physical), auxiliary=len(names)-len(physical),
                            edges=parsed["edge_index"].shape[1], endpoints=len(meta), rankable=len(ptr)-1,
                            counts=dict(counts), target_sha256=r["sha256"]["target"], graph_sha256=S.sha(a),
                            endpoint_sha256=S.sha(folder / "ENDPOINTS.json")))
        print(path.stem, len(names), dict(counts), flush=True)
    with (OUT / "GRAPH_REPORT.json").open("x", encoding="utf-8") as f:
        json.dump(dict(control=c, views=reports, registry_sha256=S.sha(registry), predictions_read=0,
                       model_forwards=0, solver_calls=0, optimizer_steps=0), f, indent=2)


if __name__ == "__main__":
    main()
