"""Register rank-unread confirmation candidates and replay existing netlist evidence."""
import json
import re
import sys
from collections import Counter
from pathlib import Path

OUT = Path(__file__).resolve().parent
P = OUT.parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(P / "lcone_endpoint_frozen_20261112"))
from audit import S, Expressions, bind_lineage, binding, construct, endpoints, qualify, structural_cone


def assess(clean_path, source_path, target_path, provenance):
    clean, orig, trans = [endpoints(p) for p in (clean_path, source_path, target_path)]
    inserted, replacements, missing = bind_lineage(provenance, clean, orig)
    states, restored, unresolved = binding(clean, orig, trans, replacements)
    expr = Expressions()
    evaluate = [construct(g, expr, states) for g in (clean, orig, trans)]
    candidates = [("D", n) for n, (kind, pins) in trans[0]["pins"].items()
                  if "DFF" in kind and "D" in dict(pins)]
    candidates += [("PO", n) for n in sorted(trans[2])]
    rows, counts = [], Counter()
    for kind, name in candidates:
        try:
            if kind == "D":
                if name not in states:
                    raise ValueError("unbound_DFF")
                nets = [dict(g[0]["pins"][name][1])["D"] for g in (clean, orig, trans)]
            else:
                if not all(name in g[2] for g in (clean, orig, trans)):
                    raise ValueError("unbound_PO")
                nets = [name] * 3
            gates, issues = structural_cone(trans, nets[-1])
            if not gates or issues:
                raise ValueError("empty_or_open")
            outputs = [ev(n) for ev, n in zip(evaluate, nets)]
            assert outputs[-1][1] == gates
            lab, proof, n, witness = qualify(expr, [v[0] for v in outputs])
            lineage = sorted(inserted & outputs[1][1])
            if lab == "positive" and (missing or not lineage):
                lab, proof, witness = "unknown", "unbound_manufacturing_lineage", None
            if lab != "unknown":
                rows.append(dict(kind=kind, endpoint=name, status=lab, proof=proof, inputs=n,
                                 witness=witness, inserted_source_cells=lineage if lab == "positive" else []))
            counts[f"{kind}_{lab}"] += 1
        except (ValueError, KeyError, RecursionError) as exc:
            counts[f"{kind}_unscored"] += 1
            counts["reason:" + str(exc).split(":")[0]] += 1
    expr.inputs.cache_clear()
    return dict(support=dict(counts), endpoints=rows, restored_q=restored, unresolved_q=unresolved)


def main():
    root = S.ROOT
    c = S.read(S.CONTRACT)["shared_inputs"]
    used = {r["src_view"] for r in S.read(P / "lcone_endpoint_frozen_20261112/SELECTION.json")["included"]}
    train = {r["view"].split("__ys_")[0].split("__keep")[0]
             for k in ("orig_train", "trans_train") for r in c[k]["views"]}
    records = S.rows(P / "heldout_composition_20261110/CEC_STAGE3B.csv")
    output = []
    host, source = "s38417t100", "s38417t100__injdelta_d1_s42"
    assert source not in used | train
    prov, = [r for r in S.read(root / f"generate_trans/hosts/{host}/provenance.json") if r["view"] == source]
    clean = root / f"generate_trans/hosts/{host}/base/{host}_clean.v"
    for row in [r for r in records if source in " ".join(r.values())]:
        log_rel, = [v for v in row.values() if v.endswith(".log")]
        log = root / log_rel
        text = log.read_text(encoding="utf-8")
        assert "Equivalence successfully proven!" in text
        ports = re.findall(r"^[23]\. Executing Verilog-2005 frontend: (generate_trans/[^\r\n]+)", text, re.M)
        assert len(ports) == 2 and source in ports[0] and source in ports[1]
        source_path, target = [root / v for v in ports]
        output.append(dict(source=source, target=str(target.relative_to(root)), status="registered_evidence_only",
                           log=str(log.relative_to(root)), source_path=str(source_path.relative_to(root)),
                           sha256={k: S.sha(p) for k, p in dict(clean=clean, source=source_path, target=target, log=log).items()},
                           **assess(clean, source_path, target, prov)))
    assert len(output) == 4
    beta = "s38584t100__injbeta_d1_s42"
    assert beta not in used | train
    beta_target = root / f"generate_trans/yslib_keep_abc/s38584t100/{beta}__ys_abc.v"
    beta_record, = [r for r in S.rows(root / "generate_trans/yslib_keep_abc/cec_tolib.csv") if r["stem"] == beta]
    assert beta_target.is_file() and "unproven=0 PASS" in beta_record["cec"]
    output.append(dict(source=beta, target=str(beta_target.relative_to(root)), status="pending_raw_CEC_binding",
                       sha256={"target": S.sha(beta_target)}, historical_cec_summary=beta_record,
                       reason="raw source/target CEC invocation not located for this candidate"))
    with (OUT / "CONFIRMATION_REGISTRY.json").open("x", encoding="utf-8") as f:
        json.dump(dict(prediction_reads=0, selected_by="source eligibility and exact historical CEC logs",
                       registered=output, independent_panel_ready=False), f, indent=2)
    for row in output:
        print(row["target"], row["status"], row.get("support"))


if __name__ == "__main__":
    main()
