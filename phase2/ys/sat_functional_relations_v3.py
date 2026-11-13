"""sat_functional_relations_v3.py -- independent SAT protocol repair (new file).

Uses legacy struct export and seq1 cell mapping; this context is NOT the
native physical-Q context of rounds 10..16. Never mix their tables silently.
2026-10-26 repair: coordinate-bound input pairing, infeasible/unknown masks,
full vs sampled domain, marker-bound parser, gate-independent influence.

v3 protocol
  * gate / cone / dff_next: all 2^k patterns when within max-patterns;
    otherwise explicitly sampled patterns (never a full-function proof);
  * mux: truth table over S0/A/B, with S0 control influence reported;
  * every pattern asks target=1 and target=0;
  * decided = complete enumeration, nonempty feasible domain, all its outputs forced;
  * influence_i = actual single-coordinate pairs of feasible forced outputs;
  * q_proved / q_refuted / q_unknown are separate;
  * observability is structural (n_po/n_dff), not a SAT proof.

Output columns:
  relation_id, target, cut_nets, cut_order, n_inputs, n_patterns,
  activation_patterns, q_proved, q_refuted, q_unknown,
  decided, influence, influence_i, control_influence,
  status, reach_po, reach_dff, struct_reach, reach_status,
  runtime_s, log
"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import argparse
import hashlib
import itertools
import json
import re
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(_eqguard_path(''))
sys.path.insert(0, str(ROOT / "phase2/ys"))
import sat_functional_relations as P0  # noqa: E402
import sat_functional_relations_agnostic as AG  # noqa: E402
from sat_boundary_semantics import classify, input_influence  # noqa: E402

SAT_REF = AG._sat_ref2


def cut_order(c: dict) -> list[str]:
    return list(c["cut"].keys())


def validate_case_boundary(g: dict, c: dict) -> None:
    """Fail closed before direct '-set': aliases must not overwrite a value."""
    inverse = {name: [bit] for bit, name in g['names'].items()}
    inverse.update({name: info['bits'] for name, info in g.get('netnames', {}).items()})
    nets = list(c['cut'].values())
    bits = []
    for name in nets + [c['target']]:
        bs = inverse.get(name, [])
        if len(bs) != 1 or not isinstance(bs[0], int):
            raise ValueError('Non-scalar, missing or constant boundary: ' + name)
        bits.append(bs[0])
    if not nets or len(set(bits[:-1])) != len(nets):
        raise ValueError('Duplicate cut bit/alias needs predicate-based extraction')
    if bits[-1] in bits[:-1]:
        raise ValueError('Target is in its own cut')
    c['_cut_bits'] = bits[:-1]
    c['_target_bit'] = bits[-1]


def pattern_list(k: int, max_patterns: int) -> list[tuple[int, ...]]:
    if k <= 0:
        return []
    if max_patterns < 1:
        raise ValueError('max_patterns must be positive')
    if 2 ** k <= max_patterns:
        return list(itertools.product((0, 1), repeat=k))
    base = [(1,) * k, (0,) * k]
    for i in range(k):
        p = [1] * k
        p[i] = 0
        base.append(tuple(p))
    out, seen = [], set()
    for p in base:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out[:max_patterns]


def case_queries_v3(c: dict, timeout: int, max_patterns: int) -> list[str]:
    keys = cut_order(c)
    refs = [c["_refs"][k] for k in keys]
    po = c.get("_pref") or SAT_REF(c["target"])
    patterns = pattern_list(len(keys), max_patterns)
    c["_patterns"] = patterns
    qs: list[str] = []
    for pat in patterns:
        sets = " ".join(f"-set {ref} {bit}" for ref, bit in zip(refs, pat))
        qs.append(f"sat -seq 1 {sets} -prove {po} 1 -timeout {timeout}")
        qs.append(f"sat -seq 1 {sets} -prove {po} 0 -timeout {timeout}")
    return qs


def build_script_v3(v: Path, top: str, cases: list[dict], js: Path,
                    timeout: int, ports: set[str], max_patterns: int) -> str:
    lines = [f'read_verilog "{P0.wsl(v)}"', f"hierarchy -top {top}", "flatten", "proc",
             f"select -module {top}"]
    renamed: dict[str, str] = {}
    rlines: list[str] = []

    def add_rename(nm: str) -> str:
        if nm in renamed:
            return renamed[nm]
        safe = f"fg_{len(renamed)}"
        renamed[nm] = safe
        rlines.append(f"rename {SAT_REF(nm)} {safe}")
        return safe

    for c in cases:
        c["_refs"] = {k: add_rename(nm) for k, nm in c["cut"].items()}
        t = c["target"]
        if t in renamed:
            c["_pref"] = renamed[t]
        elif t in ports:
            c["_pref"] = None
        else:
            c["_pref"] = add_rename(t)
    lines += rlines
    if renamed:
        lines.append("setattr -set keep 1 " + " ".join(f"w:{x}" for x in renamed.values()))
    lines += [f'write_json "{P0.wsl(js)}"', f"techmap -autoproc -map {P0.CELL_MAP}", "opt -fast"]
    query_id = 0
    for c in cases:
        qs = case_queries_v3(c, timeout, max_patterns)
        c["_nq"] = len(qs)
        c['_query_ids'] = []
        for query in qs:
            c['_query_ids'].append(query_id)
            lines += [f"log SATQ{query_id:06d}", query]
            query_id += 1
    return "\n".join(lines) + "\n"


def _forced(q1: str, q0: str):
    if q1 == "proved" and q0 == "refuted":
        return 1
    if q1 == "refuted" and q0 == "proved":
        return 0
    return None


def parse_case(c: dict, got: list[str]) -> dict:
    patterns = c.get("_patterns", [])
    npat = len(patterns)
    qs = list(got[:c.get("_nq", 2 * npat)])
    qs += ["unknown"] * (2 * npat - len(qs))
    forced: list[int | None] = []
    q_proved = q_refuted = q_unknown = q_error = 0
    table = {}
    if len(set(patterns)) != npat:
        raise ValueError("Duplicate pattern binding")
    for j in range(npat):
        q1, q0 = qs[2 * j], qs[2 * j + 1]
        q_proved += int(q1 == "proved") + int(q0 == "proved")
        q_refuted += int(q1 == "refuted") + int(q0 == "refuted")
        q_unknown += int(q1 not in ("proved", "refuted")) + int(q0 not in ("proved", "refuted"))
        q_error += int(q1 == "error") + int(q0 == "error")
        forced.append(_forced(q1, q0))
        table[''.join(map(str, patterns[j]))] = classify(q1, q0)
    k = len(c.get("cut", {}))
    per_input = input_influence(table, k)
    inf = [int(x['changed'] > 0) for x in per_input]
    complete = npat == 2 ** k
    feasible = sum(f == 'feasible' for f, v in table.values())
    forced_n = sum(x is not None for x in forced)
    infeasible = sum(f == 'infeasible' for f, v in table.values())
    # No sampled table or vacuous (all-infeasible) proof is a full function.
    decided = int(complete and q_unknown == 0 and feasible > 0 and forced_n == feasible)
    influence_any = int(any(inf))

    keys = cut_order(c)
    ctrl = 0
    if c.get("kind") == "mux" and "S0" in keys:
        ctrl = inf[keys.index("S0")]
    if decided and influence_any:
        status = "proved"
    elif decided:
        if all(x['pair_coverage'] == 1 for x in per_input):
            status = "functional_no_influence"
        elif any(x['comparable'] for x in per_input):
            status = "functional_no_change_on_comparable_subset"
        else:
            status = "functional_influence_unassessed"
    elif q_error > 0:
        status = "error"
    elif q_unknown > 0:
        status = "unknown"
    elif complete and infeasible == npat:
        status = "infeasible_domain"
    elif any(x is not None for x in forced):
        status = "partial"
    else:
        status = "undetermined"

    act = ";".join(
        f"{''.join(str(b) for b in p)}:{f if f is not None else '?'}"
        for p, f in zip(patterns, forced))
    infs = ";".join(f"c{i}:{v}" for i, v in enumerate(inf))
    return dict(
        n_inputs=k,
        n_patterns=npat,
        activation_patterns=act,
        q_proved=q_proved,
        q_refuted=q_refuted,
        q_unknown=q_unknown,
        q_error=q_error,
        patterns_complete=int(complete),
        feasible_patterns=feasible,
        infeasible_patterns=infeasible,
        forced_patterns=forced_n,
        conditional_table=';'.join(f'{p}:{f}:{v}' for p, (f, v) in sorted(table.items())),
        decided=decided,
        decided_scope='all_feasible_patterns' if complete else 'not_complete_domain',
        influence=influence_any,
        influence_i=infs,
        control_influence=ctrl,
        control_influence_valid=int(c.get('kind') == 'mux' and 'S0' in keys
                                    and per_input[keys.index('S0')]['comparable'] > 0),
        influence_valid=int(any(x['comparable'] for x in per_input)),
        influence_valid_i=';'.join(str(x['influence_valid']) for x in per_input),
        influence_comparable_i=';'.join(str(x['comparable']) for x in per_input),
        influence_changed_i=';'.join(str(x['changed']) for x in per_input),
        influence_coverage_i=';'.join(str(x['pair_coverage']) for x in per_input),
        influence_fraction_i=';'.join(str(x['change_fraction']) for x in per_input),
        influence_scope='feasible_forced_single_cut_coordinate_pairs; not shared_environment_intervention',
        causal_influence_proved=0,
        semantic_version='conditional_boundary_v4',
        status=status,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fold", default="hosts_bt31")
    ap.add_argument("--host", default="s38584t100")
    ap.add_argument("--inst", default="injalpha")
    ap.add_argument("--recipes", default="ys_abc")
    ap.add_argument("--gate-cases", type=int, default=80)
    ap.add_argument("--mux-cases", type=int, default=20)
    ap.add_argument("--comb-cases", type=int, default=10)
    ap.add_argument("--dff-cases", type=int, default=5)
    ap.add_argument("--max-cases", type=int, default=115)
    ap.add_argument("--max-patterns", type=int, default=8)
    ap.add_argument("--timeout", type=int, default=20)
    ap.add_argument("--only-dff", action="store_true")
    ap.add_argument("--dff-order", choices=["name", "obs"], default="obs")
    ap.add_argument("--out", default=str(ROOT / "_p0pilot/functional_relations_v3.csv"))
    ap.add_argument("--logdir", default=str(ROOT / "_p0pilot/v3_logs"))
    ap.add_argument("--allow-overwrite", action="store_true",
                    help="Explicitly allow replacing existing v3 output/logs")
    a = ap.parse_args()

    logdir = Path(a.logdir)
    if not a.allow_overwrite and (Path(a.out).exists() or
            (logdir.exists() and any(logdir.iterdir()))):
        ap.error('Output/log directory already has evidence; choose a fresh path')
    logdir.mkdir(parents=True, exist_ok=True)
    recipes = [s.strip() for s in a.recipes.split(",") if s.strip()]
    insts = [s.strip() for s in a.inst.split(",") if s.strip()]
    rows: list[dict] = []
    rejected, ledger = [], []

    def sample(cases: list, n: int) -> list:
        if n <= 0:
            return []
        if len(cases) <= n:
            return cases
        step = len(cases) / n
        return [cases[int(i * step)] for i in range(n)]

    for inst in insts:
        vs = P0.find_designs(a.fold, a.host, inst, recipes)
        canon = [x for x in vs if "keep" not in x.name]
        if canon:
            vs = canon
        for v in vs:
            top = P0.module_name(v)
            print(f"\n=== {v.name} (top={top})")
            js_raw = logdir / f"{top}.struct_raw.json"
            js_sat = logdir / f"{top}.sat.json"
            s0 = "\n".join([
                f'read_verilog "{P0.wsl(v)}"', f"hierarchy -top {top}", "flatten", "proc",
                f'write_json "{P0.wsl(js_raw)}"',
                f"techmap -autoproc -map {P0.CELL_MAP}", "opt -fast"]) + "\n"
            # A fresh execution never trusts mtime-only snapshots.
            P0.run_yosys(s0, logdir / f"{top}.struct.log")
            g = P0.load_graph(js_raw, top)

            # all candidates, structural reach first, then sample
            mux = AG.pick_mux_agnostic(g)
            gate = AG.pick_gate_agnostic(g)
            cone = AG.pick_cone_agnostic(g)
            dff = AG.pick_dff_next_agnostic(g)
            reach_index = P0.forward_index(g)
            for c in mux + gate + cone + dff:
                net = c.get("q") if c.get("kind") == "dff_next" else c.get("target")
                if net:
                    c["n_po_reached"], c["n_dff_reached"] = P0.forward_reach(g, [net], index=reach_index)
            if a.dff_order == "obs":
                dff.sort(key=lambda c: -(c.get("n_po_reached", 0) + c.get("n_dff_reached", 0)))
            mux.sort(key=lambda c: -(c.get("n_po_reached", 0) + c.get("n_dff_reached", 0)))
            gate.sort(key=lambda c: -(c.get("n_po_reached", 0) + c.get("n_dff_reached", 0)))
            raw = (dff if a.only_dff else
                   mux + gate + sample(cone, a.comb_cases) + sample(dff, a.dff_cases))
            if not a.only_dff:
                raw = (sample(mux, a.mux_cases) + sample(gate, a.gate_cases) +
                       sample(cone, a.comb_cases) + sample(dff, a.dff_cases))
            cases, seen_t = [], set()
            for c in raw:
                if c["target"] in seen_t:
                    continue
                try:
                    validate_case_boundary(g, c)
                except ValueError as exc:
                    rejected.append(dict(design=v.name, target=c['target'], reason=str(exc)))
                    continue
                seen_t.add(c["target"])
                cases.append(c)
            cases = cases[:max(1, a.max_cases)]
            print(f"  [cases] total={len(cases)}")
            if not cases:
                continue

            t0 = time.time()
            script = build_script_v3(
                v, top, cases, js_sat, a.timeout, set(g["ports"].keys()),
                a.max_patterns)
            out = P0.run_yosys(script, logdir / f"{top}.sat.log")
            res = P0.parse_results(out)
            executed = {int(m[1]) for m in re.finditer(r'^SATQ(\d{6})\s*$', out, re.M)}
            source_sha = hashlib.sha256(v.read_bytes()).hexdigest()
            script_sha = hashlib.sha256(script.encode()).hexdigest()
            raw_sha = hashlib.sha256(js_raw.read_bytes()).hexdigest()
            log_sha = hashlib.sha256((logdir / f'{top}.sat.log').read_bytes()).hexdigest()
            dt = time.time() - t0
            k = 0
            for c in cases:
                got = res[k:k + c.get("_nq", 0)]
                k += c.get("_nq", 0)
                info = parse_case(c, got)
                npo = int(c.get("n_po_reached", 0))
                ndff = int(c.get("n_dff_reached", 0))
                rid = "|".join([a.host, inst, v.stem.split("__")[-1],
                                c["kind"], str(c["cell"]), str(c["target"])])
                for local, qid in enumerate(c['_query_ids']):
                    ledger.append(dict(relation_id=rid, query_id=qid,
                                       pattern=''.join(map(str,c['_patterns'][local//2])),
                                       prove=1 if local%2==0 else 0,
                                       executed=int(qid in executed),
                                       status=res[qid] if qid < len(res) else 'not_executed',
                                       source_sha=source_sha, raw_sha=raw_sha,
                                       script_sha=script_sha, log_sha=log_sha))
                rows.append(dict(
                    relation_id=rid, design=v.name, top=top, inst=inst,
                    recipe=v.stem.split("__")[-1], kind=c["kind"],
                    cell=c["cell"], cell_type=c["type"], target=c["target"],
                    cut_nets=";".join(c["cut"].values()),
                    cut_order=";".join(cut_order(c)),
                    cut_bits=';'.join(map(str,c['_cut_bits'])),
                    target_bit=c['_target_bit'],
                    source_sha=source_sha, raw_sha=raw_sha,
                    cell_map_sha=hashlib.sha256((ROOT/P0.CELL_MAP).read_bytes()).hexdigest(),
                    query_context='legacy_seq1_cellmap_free_initial_v1',
                    query_ids=';'.join(map(str,c['_query_ids'])),
                    script_sha=script_sha, log_sha=log_sha,
                    **info,
                    reach_po=npo, reach_dff=ndff,
                    struct_reach=int((npo + ndff) > 0),
                    reach_status="struct",
                    runtime_s=round(dt, 1),
                    log=str((logdir / f"{top}.sat.log").relative_to(ROOT)),
                ))
            print(f"  [out] rows={len(rows)} patterns={sum(x['n_patterns'] for x in rows if x['top']==top)}")

    (logdir / 'rejected_boundaries.json').write_text(
        json.dumps(rejected, ensure_ascii=False, indent=2), encoding='utf-8')
    pd.DataFrame(ledger).to_csv(logdir/'query_ledger.csv', index=False, encoding='utf-8-sig')
    if not rows:
        print("[WARN] no rows")
        return 1
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"[write] {out} rows={len(df)}")
    print(df.groupby(["kind", "status"]).size().to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


