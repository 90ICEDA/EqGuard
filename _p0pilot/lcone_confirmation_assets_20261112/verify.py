"""Load confirmation assets with graph/endpoint checks, without scoring."""
import json
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent
P = OUT.parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(P / "lcone_head_gate_20261112"))
from register_confirmation import S, assess, endpoints


def load_one(record):
    folder = OUT / record["view"]
    graph, meta = folder / "GRAPH_ENDPOINTS.npz", folder / "ENDPOINTS.json"
    if S.sha(graph) != record["graph_sha256"] or S.sha(meta) != record["endpoint_sha256"]:
        raise ValueError("confirmation_asset_hash_mismatch")
    with np.load(graph, allow_pickle=False) as f:
        z = {k: f[k] for k in f.files}
    x, edge, physical = z["x39"], z["edge_index"], z["physical"]
    assert x.shape == (len(physical), 39) and np.isfinite(x).all()
    assert edge.shape == (2, record["edges"]) and len(z["edge_roles"]) == edge.shape[1]
    assert np.all((edge >= 0) & (edge < len(x)))
    assert np.array_equal(physical, np.arange(len(x)) < record["physical"])
    assert len(np.unique(z["names"])) == len(x)
    assert np.all(physical[z["members"]])
    assert np.all(np.diff(z["ptr"]) > 0) and z["ptr"][-1] == len(z["members"])
    rows = S.read(meta)
    rankable = [r for r in rows if r["rankable"]]
    assert len(rankable) == len(z["ptr"]) - 1 == record["rankable"]
    assert [r["packed_index"] for r in rankable] == list(range(len(rankable)))
    assert len({(r["kind"], r["endpoint"]) for r in rows}) == len(rows)
    for r in rankable:
        i = r["packed_index"]
        mem = z["members"][z["ptr"][i]:z["ptr"][i+1]]
        assert len(mem) == len(np.unique(mem))
        assert 0 <= r["driver_row"] < len(x)
        if physical[r["driver_row"]]:
            assert r["driver_row"] in mem
    return z, rows


def second_source():
    root = S.ROOT
    host, source = "s38584t100", "s38584t100__injbeta_d1_s42"
    log = root / f"generate_trans/yskeep_abc_s38584t100/logs/cec_{source}__ys_abc.log"
    text = log.read_text(encoding="utf-8")
    assert "Equivalence successfully proven!" in text and "5224 are proven and 0 are unproven" in text
    proof_paths = re.findall(r"^[23]. Executing Verilog-2005 frontend: .*?/(generate_trans/[^\r\n]+)", text, re.M)
    assert len(proof_paths) == 2 and all(source in x for x in proof_paths)
    orig, raw = (root / p for p in proof_paths)
    converted = root / f"generate_trans/yslib_keep_abc/{host}/{source}__ys_abc.v"
    clean = root / f"generate_trans/hosts/{host}/base/{host}_clean.v"
    prov, = [r for r in S.read(root / f"generate_trans/hosts/{host}/provenance.json") if r["view"] == source]
    a = assess(clean, orig, raw, prov)
    b = assess(clean, orig, converted, prov)
    net = endpoints(raw)[0]
    typ = Counter(t for t, _ in net["pins"].values() if not t.startswith("V2_ASSIGN"))
    return dict(source=source, raw_cec_bound=True, proof_paths=proof_paths, raw_cec_log=str(log.relative_to(root)),
                raw_physical_types=dict(typ), raw_virtual=len(net["virtual_names"]), raw_support=a["support"],
                converted=str(converted.relative_to(root)), converted_support=b["support"],
                converted_has_exact_log=False, qualified_for_primary_panel=False,
                sha256={k: S.sha(p) for k, p in dict(log=log, original=orig, raw=raw, converted=converted).items()})


def main():
    manifest = S.read(OUT / "GRAPH_REPORT.json")
    reports = []
    for record in manifest["views"]:
        z, rows = load_one(record)
        support = Counter(f"{r['kind']}|{r['status']}" for r in rows if r["rankable"])
        assert dict(support) == record["counts"]
        reports.append(dict(view=record["view"], loaded=len(rows), rankable=record["rankable"],
                            positive_ids=sorted(f"{r['kind']}:{r['endpoint']}" for r in rows
                                                if r["rankable"] and r["status"] == "positive")))
    assert all(x["positive_ids"] == reports[0]["positive_ids"] for x in reports)
    # Exercise the same public loading path with an incorrect graph digest.
    try:
        load_one(dict(manifest["views"][0], graph_sha256="0" * 64))
    except ValueError as e:
        assert str(e) == "confirmation_asset_hash_mismatch"
    else:
        raise AssertionError("tampered digest accepted")
    beta = second_source()
    report = dict(loaded=reports, second_source=beta, hash_rejection=True, independent_panel_ready=False,
                  model_forwards=0, predictions_read=0, optimizer_steps=0, solver_calls=0)
    with (OUT / "LOAD_GATE.json").open("x", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(reports)
    print(beta)


if __name__ == "__main__":
    main()
