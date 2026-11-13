"""Exact, rank-unread replay of the registered beta endpoint case."""
import json
import sys
from collections import Counter
from pathlib import Path

OUT = Path(__file__).resolve().parent
P = OUT.parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(P / "lcone_endpoint_frozen_20261112"))
from audit import S, Expressions, bind_lineage, binding, construct, endpoints


def main():
    previous = S.read(P / "lcone_confirmation_assets_20261112/LOAD_GATE.json")["second_source"]
    orig_path, raw_path = [S.ROOT / n for n in previous["proof_paths"]]
    converted_path = S.ROOT / previous["converted"]
    host, source = "s38584t100", previous["source"]
    base = S.ROOT / "generate_trans/hosts" / host
    clean_path = base / "base" / f"{host}_clean.v"
    prov, = [r for r in S.read(base / "provenance.json") if r["view"] == source]
    for key, path in (("original", orig_path), ("raw", raw_path), ("converted", converted_path)):
        assert S.sha(path) == previous["sha256"][key]
    a, b, c, d = [endpoints(p) for p in (clean_path, orig_path, raw_path, converted_path)]
    added, repl, missing = bind_lineage(prov, a, b)
    assert not missing and repl["TrojanBPD"]["instance"] in added
    states = binding(a, b, c, repl)[0] & binding(a, b, d, repl)[0]
    expr = Expressions()
    evaluator = [construct(n, expr, states) for n in (a, b, c, d)]
    observed = {}
    for signal, which in (("TrojanB_t2", (1, 2, 3)), ("TrojanB_p2", (1, 2, 3)), ("test_so3", (0, 1, 2, 3))):
        roots = [evaluator[i](signal)[0] for i in which]
        inputs = sorted(set().union(*(expr.inputs(root) for root in roots)))
        assert len(inputs) <= 12
        count = 1 << len(inputs)
        env = {n: sum(1 << i for i in range(count) if (i >> k) & 1) for k, n in enumerate(inputs)}
        ev = expr.evaluator(env, (1 << count) - 1)
        values = [ev(root) for root in roots]
        observed[signal] = dict(inputs=inputs, patterns=count, design_indices=which,
                                ones=[x.bit_count() for x in values],
                                difference_vs_first=[(x ^ values[0]).bit_count() for x in values])
    assert not any(observed["TrojanB_t2"]["ones"])
    assert not any(observed["test_so3"]["difference_vs_first"])
    cec = P / "heldout_composition_20261110"
    used = {r["src_view"] for r in S.read(P / "lcone_endpoint_frozen_20261112/SELECTION.json")["included"]}
    contract = S.read(S.CONTRACT)["shared_inputs"]
    training = {v["view"].split("__ys_")[0].split("__keep")[0]
                for split in ("orig_train", "trans_train") for v in contract[split]["views"]}
    refs = Counter()
    for file in ("CEC_STAGE3A.csv", "CEC_STAGE3B.csv"):
        for r in S.rows(cec / file):
            orig, = [v for v in r.values() if v.endswith(".v")]
            name = Path(orig).stem
            status = "training" if name in training else "prior_panel" if name in used else "unused"
            refs[f"{status}|{name}"] += 1
    with (OUT / "SOURCE_GATE.json").open("x", encoding="utf-8") as f:
        json.dump(dict(source=source, observation_order=["clean", "inserted_source", "raw_abc", "converted_abc"],
                       observed=observed, proven_panel_source_inventory=dict(refs),
                       verdict="observed_PO_unchanged_under_full_free_cut", predictions_read=0, solver_calls=0),
                  f, indent=2)
    print(observed)
    print({k: n for k, n in refs.items() if k.startswith("unused")})


if __name__ == "__main__":
    main()
