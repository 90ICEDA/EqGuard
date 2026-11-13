"""Register all source-disjoint, training-host cases in the exact CEC panels."""
import json
import re
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent
P = OUT.parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(P / "lcone_head_gate_20261112"))
from register_confirmation import S, assess
sys.path.insert(0, str(P / "lcone_head_prep_20261112"))
from build_train_panel import LogicOnlyPath


def main():
    layouts = S.read(S.CONTRACT)["shared_inputs"]
    training = {v["view"].split("__ys_")[0].split("__keep")[0]
                for k in ("orig_train", "trans_train") for v in layouts[k]["views"]}
    train_hosts = {v.split("__", 1)[0] for v in training}
    ranked = {r["src_view"] for r in S.read(P / "lcone_endpoint_frozen_20261112/SELECTION.json")["included"]}
    selection = []
    for p in sorted((P / "heldout_composition_20261110").glob("CEC_STAGE3[AB].csv")):
        for r in S.rows(p):
            src, = (s.lstrip("\ufeff") for s in r.values() if s.endswith(".v"))
            source = Path(src).stem
            host = source.split("__", 1)[0]
            if source in training | ranked or host not in train_hosts or "PASS" not in r.values():
                continue
            log, = (s for s in r.values() if s.endswith(".log"))
            text = (S.ROOT / log).read_text(encoding="utf-8")
            assert "Equivalence successfully proven!" in text
            src_target = re.findall(r"^[23]\. Executing Verilog-2005 frontend: (generate_trans/[^\r\n]+)", text, re.M)
            assert len(src_target) == 2 and Path(src_target[0]).stem == source
            selection.append(dict(source=source, host=host, original=src_target[0], target=src_target[1], log=log))
    assert selection
    with (OUT / "SOURCE_ONLY_SELECTION.json").open("x", encoding="utf-8") as f:
        json.dump(selection, f, indent=2)
    results = []
    for r in selection:
        base = S.ROOT / "generate_trans/hosts" / r["host"]
        clean = base / "base" / (r["host"] + "_clean.v")
        prov, = [p for p in S.read(base / "provenance.json") if p["view"] == r["source"]]
        orig, target, log = [S.ROOT / r[k] for k in ("original", "target", "log")]
        item = assess(*map(LogicOnlyPath, (clean, orig, target)), prov)
        results.append(dict(**r, **item, sha256={k: S.sha(v) for k, v in dict(
            clean=clean, original=orig, target=target, log=log).items()}))
        print(r["target"], item["support"], flush=True)
    with (OUT / "SOURCE_ONLY_EVIDENCE.json").open("x", encoding="utf-8") as f:
        json.dump(dict(results=results, prediction_reads=0, solver_calls=0,
                       independence="source-only; host used for training"), f, indent=2)


if __name__ == "__main__":
    main()
