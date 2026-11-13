"""Round-4 evidence model: enumeration is derived from the observed pattern set.

Fixes:
  * a caller-provided `enumerated` flag is no longer trusted;
  * patterns are validated as bit vectors (int patterns are rejected as ambiguous);
  * single-input two-pattern probes are recognised as complete enumeration;
  * one side refuted + other unfinished records premise feasibility but never
    upgrades forcing or sufficiency;
  * influence is `partial_observed` when the pattern set is incomplete.
"""
from __future__ import annotations

import itertools

QUERY_STATES = ("proved", "refuted", "timeout", "error", "no_result")


def parse_pattern(pattern, k: int) -> tuple:
    """Return a k-bit tuple. Integers are rejected because '00' vs 0 is ambiguous."""
    if isinstance(pattern, bool):
        raise ValueError("bool pattern")
    if isinstance(pattern, int):
        raise ValueError("integer pattern is ambiguous; store a fixed-width string")
    if isinstance(pattern, str):
        if len(pattern) != k or any(ch not in "01" for ch in pattern):
            raise ValueError(f"pattern {pattern!r} is not {k} bits")
        return tuple(int(ch) for ch in pattern)
    vals = list(pattern)
    if len(vals) != k or any(v not in (0, 1) for v in vals):
        raise ValueError(f"pattern {pattern!r} is not {k} binary bits")
    return tuple(int(v) for v in vals)


def enumeration_status(k: int, patterns: list, qids: list) -> dict:
    """Compute completeness from the actual pattern and qid sets."""
    expected = set(itertools.product([0, 1], repeat=k))
    try:
        parsed = [parse_pattern(p, k) for p in patterns]
    except ValueError as e:
        return dict(complete=False, reason=str(e), k=k, expected=2 ** k,
                    observed=len(patterns), duplicates=0, missing=[],
                    invalid=str(e), qid_count=len(qids))
    seen = {}
    for p in parsed:
        seen[p] = seen.get(p, 0) + 1
    duplicates = sum(v - 1 for v in seen.values() if v > 1)
    missing = sorted(expected - set(seen))
    invalid = ""
    if duplicates:
        invalid = "duplicate_pattern"
    elif missing:
        invalid = "missing_pattern"
    elif len(qids) != 2 * len(parsed) or len(set(qids)) != len(qids):
        invalid = "qid_count_or_duplicate"
    return dict(complete=(not invalid and len(seen) == 2 ** k),
                reason=invalid or "complete", k=k, expected=2 ** k,
                observed=len(parsed), duplicates=duplicates,
                missing=["".join(str(b) for b in m) for m in missing],
                invalid=invalid, qid_count=len(qids))


def pattern_state(q1: str, q0: str) -> dict:
    base = dict(feasibility="unknown", forcing="unknown", one_sided=None,
                premise_feasible_known=False)
    if q1 == "proved" and q0 == "proved":
        base.update(feasibility="infeasible", forcing="not_applicable")
        return base
    if q1 == "proved" and q0 == "refuted":
        base.update(feasibility="feasible", forcing=1, premise_feasible_known=True)
        return base
    if q1 == "refuted" and q0 == "proved":
        base.update(feasibility="feasible", forcing=0, premise_feasible_known=True)
        return base
    if q1 == "refuted" and q0 == "refuted":
        base.update(feasibility="feasible", forcing="undecided",
                    premise_feasible_known=True)
        return base
    # one side refuted + other unfinished: a model exists (premise feasible),
    # but the forcing direction is not established.
    if q1 == "refuted" and q0 in ("timeout", "error", "no_result"):
        base.update(premise_feasible_known=True, one_sided=0)
        return base
    if q0 == "refuted" and q1 in ("timeout", "error", "no_result"):
        base.update(premise_feasible_known=True, one_sided=1)
        return base
    if q1 == "proved" and q0 in ("timeout", "error", "no_result"):
        base.update(one_sided=1)
        return base
    if q0 == "proved" and q1 in ("timeout", "error", "no_result"):
        base.update(one_sided=0)
        return base
    return base


def normalize_cut(cut_names: list[str], netbits: dict, target_net: str) -> dict:
    """Deduplicate aliases by actual bit, drop constants, reject buses/missing."""
    target_bits = netbits.get(target_net, ())
    tbit = target_bits[0] if len(target_bits) == 1 else None
    canonical, seen, aliases, constants, invalid = [], {}, [], [], []
    for nm in cut_names:
        if nm in ("0", "1", "x", "z"):
            constants.append(nm)
            continue
        bits = netbits.get(nm)
        if bits is None:
            invalid.append({"name": nm, "reason": "missing_net"})
            continue
        if len(bits) != 1:
            invalid.append({"name": nm, "reason": "bus_or_empty"})
            continue
        b = bits[0]
        if tbit is not None and b == tbit:
            aliases.append({"name": nm, "alias_of": target_net,
                            "reason": "target_in_cut"})
            continue
        if b in seen:
            aliases.append({"name": nm, "alias_of": seen[b], "reason": "same_bit"})
            continue
        seen[b] = nm
        canonical.append({"name": nm, "bit": b})
    ok = bool(canonical) and not invalid and tbit is not None
    return dict(canonical=canonical, aliases=aliases, constants=constants,
                invalid=invalid, target_bit=tbit, ok=ok, k=len(canonical),
                target_in_cut=any(a["reason"] == "target_in_cut" for a in aliases))


def influence_v4(cut: list[str], patterns: list[tuple], forcing: list,
                 enumeration_complete: bool) -> dict:
    n = len(cut)
    comparable = [0] * n
    discordant = [0] * n
    for i in range(len(patterns)):
        for j in range(i + 1, len(patterns)):
            diff = [b for b in range(n) if patterns[i][b] != patterns[j][b]]
            if len(diff) != 1:
                continue
            b = diff[0]
            if isinstance(forcing[i], int) and isinstance(forcing[j], int):
                comparable[b] += 1
                if forcing[i] != forcing[j]:
                    discordant[b] += 1
    per_input = []
    for b in range(n):
        valid = comparable[b] > 0
        per_input.append(dict(input=cut[b], comparable=comparable[b],
                              discordant=discordant[b], valid=valid,
                              ratio=(discordant[b] / comparable[b]) if valid else None))
    vals = [p["ratio"] for p in per_input if p["valid"]]
    if not vals:
        status, mean, mx = "not_applicable", None, None
    elif not enumeration_complete:
        status, mean, mx = "partial_observed", sum(vals) / len(vals), max(vals)
    else:
        status, mean, mx = "valid", sum(vals) / len(vals), max(vals)
    return dict(per_input=per_input, n_inputs=n, n_valid_inputs=len(vals),
                status=status, mean=mean, max=mx)


def evaluate_case_v4(cut: list[str], patterns: list, qids: list[int],
                     statuses: dict[int, str], cut_meta: dict | None = None) -> dict:
    """Evaluate one relation. Enumeration completeness is computed, not trusted."""
    enum = enumeration_status(len(cut), patterns, qids)
    qcount = {s: 0 for s in QUERY_STATES}
    try:
        parsed = [parse_pattern(p, len(cut)) for p in patterns]
    except ValueError:
        parsed = []
    states = []
    for i, _pat in enumerate(parsed):
        q1 = statuses.get(qids[2 * i], "no_result")
        q0 = statuses.get(qids[2 * i + 1], "no_result")
        qcount[q1] = qcount.get(q1, 0) + 1
        qcount[q0] = qcount.get(q0, 0) + 1
        states.append(pattern_state(q1, q0))
    feas = sum(s["feasibility"] == "feasible" for s in states)
    infeas = sum(s["feasibility"] == "infeasible" for s in states)
    feas_unknown = sum(s["feasibility"] == "unknown" for s in states)
    forcing = [s["forcing"] for s in states]
    forced = sum(isinstance(v, int) for v in forcing)
    undecided = sum(v == "undecided" for v in forcing)
    forcing_unknown = sum(v == "unknown" for v in forcing)
    premise_known = sum(s["premise_feasible_known"] for s in states)
    one_sided = sum(s["one_sided"] is not None for s in states)

    if not enum["complete"]:
        suff, reason = "not_enumerated", enum["reason"]
    elif any(qcount[k] for k in ("timeout", "error", "no_result")):
        suff, reason = "unknown", "query_unfinished"
    elif feas == 0 and infeas == len(parsed):
        suff, reason = "infeasible", "all_patterns_infeasible"
    elif feas == 0:
        suff, reason = "unknown", "no_feasible_pattern"
    elif forced == feas:
        suff, reason = "proved", "all_feasible_patterns_forced"
    else:
        suff, reason = "not_proved", "feasible_pattern_undecided"

    inf = influence_v4(cut, parsed, forcing, enum["complete"])
    truth = ";".join(
        f"{''.join(str(b) for b in p)}:{s['feasibility']}:{s['forcing']}"
        for p, s in zip(parsed, states))
    return dict(
        enum_complete=enum["complete"], enum_reason=enum["reason"],
        enum_expected=enum["expected"], enum_observed=enum["observed"],
        enum_duplicates=enum["duplicates"], enum_missing=";".join(enum["missing"]),
        n_patterns=len(parsed), n_feasible=feas, n_infeasible=infeas,
        n_feasibility_unknown=feas_unknown, n_forced=forced,
        n_forced_one=sum(1 for v in forcing if v == 1),
        n_undecided=undecided, n_forcing_unknown=forcing_unknown,
        n_premise_feasible_known=premise_known, n_one_sided=one_sided,
        determinism_ratio=(forced / feas) if feas else None,
        functional_sufficiency=suff, sufficiency_reason=reason,
        query_status=";".join(f"{k}={qcount[k]}" for k in QUERY_STATES),
        truth_table=truth, forcing_patterns=";".join(str(v) for v in forcing),
        influence_per_input=";".join(
            f"{p['input']}|{p['comparable']}|{p['discordant']}|{int(p['valid'])}"
            for p in inf["per_input"]),
        influence_status=inf["status"], influence_mean=inf["mean"],
        influence_max=inf["max"], n_influence_inputs=inf["n_inputs"],
        n_valid_influence_inputs=inf["n_valid_inputs"],
        cut_meta=cut_meta or {})


def aggregate_records(records: list[dict]) -> dict:
    """Explicit node aggregation: masks OR, numeric max, conflict flag.

    records: one per relation attached to the same node, each with
    (cond_fact, suff_proved, influence_valid, determinism, n_inputs, truth_table).
    """
    if not records:
        return dict(cond_fact=0, suff_proved=0, influence_valid=0,
                    determinism=None, n_inputs=0, truth_tables="", conflicts=0)
    cond = int(any(r["cond_fact"] for r in records))
    suff = int(any(r["suff_proved"] for r in records))
    infl = int(any(r["influence_valid"] for r in records))
    dets = [r["determinism"] for r in records if r["determinism"] is not None]
    det = max(dets) if dets else None
    n_in = max(r["n_inputs"] for r in records)
    tts = sorted({r["truth_table"] for r in records})
    conflicts = int(len(tts) > 1 and len(records) > 1)
    return dict(cond_fact=cond, suff_proved=suff, influence_valid=infl,
                determinism=det, n_inputs=n_in,
                truth_tables=" || ".join(tts), conflicts=conflicts)

