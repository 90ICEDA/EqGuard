"""Round-3 SAT evidence state model.

Separates, for every tested cut pattern:
  query_status       : proved / refuted / timeout / error / no_result
  pattern_feasibility: feasible / infeasible / unknown
  conditional_forcing: 0 / 1 / undecided / unknown
  functional_sufficiency: proved only when every feasible pattern is forced
                          and at least one feasible pattern exists
  influence          : per-input comparable / discordant / valid mask

No labels, no Trojan names, no risk scores are inputs to this module.
"""
from __future__ import annotations

QUERY_STATES = ("proved", "refuted", "timeout", "error", "no_result")


def pattern_state(q1: str, q0: str) -> dict:
    """Interpret the two prove directions for one cut pattern.

    q1: status of `-prove target 1`; q0: status of `-prove target 0`.
    proved means no counterexample (property holds); refuted means a model exists.
    """
    base = dict(feasibility="unknown", forcing="unknown", one_sided=None,
                query="ok")
    if q1 == "proved" and q0 == "proved":
        base.update(feasibility="infeasible", forcing="not_applicable", query="ok")
        return base
    if q1 == "proved" and q0 == "refuted":
        base.update(feasibility="feasible", forcing=1)
        return base
    if q1 == "refuted" and q0 == "proved":
        base.update(feasibility="feasible", forcing=0)
        return base
    if q1 == "refuted" and q0 == "refuted":
        base.update(feasibility="feasible", forcing="undecided")
        return base
    if q1 == "proved" and q0 in ("timeout", "error", "no_result"):
        base.update(feasibility="unknown", forcing="unknown", one_sided=1, query=q0)
        return base
    if q0 == "proved" and q1 in ("timeout", "error", "no_result"):
        base.update(feasibility="unknown", forcing="unknown", one_sided=0, query=q1)
        return base
    unfinished = [q for q in (q1, q0) if q in ("timeout", "error", "no_result")]
    base.update(feasibility="unknown", forcing="unknown", query=unfinished[0])
    return base


def influence(cut: list[str], patterns: list[tuple], forcing: list) -> dict:
    """Per-input influence over pairs of feasible, forced patterns.

    An input with no comparable pair is `valid=False`, not "zero influence".
    """
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
    else:
        status, mean, mx = "valid", sum(vals) / len(vals), max(vals)
    return dict(per_input=per_input, n_inputs=n,
                n_valid_inputs=len(vals), status=status,
                mean=mean, max=mx)


def evaluate_case(cut: list[str], patterns: list[tuple], qids: list[int],
                  statuses: dict[int, str], structure: str = "unknown",
                  cut_scope: dict | None = None, enumerated: bool = True) -> dict:
    """Turn raw per-query statuses into separated evidence levels.

    `enumerated=False` means only a subset of the cut assignments was tested
    (e.g. the old all-1/all-0 probe). Such a case can never be `proved`.
    """
    qcount = {s: 0 for s in QUERY_STATES}
    states = []
    for i, _pat in enumerate(patterns):
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
    one_sided = sum(s["one_sided"] is not None for s in states)

    if qcount["timeout"] or qcount["error"] or qcount["no_result"]:
        suff = "unknown"
        reason = "query_unfinished"
    elif feas == 0 and infeas == len(patterns):
        suff = "infeasible"
        reason = "all_patterns_infeasible"
    elif feas == 0:
        suff = "unknown"
        reason = "no_feasible_pattern"
    elif forced == feas:
        suff = "proved" if enumerated else "not_enumerated"
        reason = ("all_feasible_patterns_forced" if enumerated
                  else "patterns_not_enumerated")
    else:
        suff = "not_proved"
        reason = "feasible_pattern_undecided"

    inf = influence(cut, patterns, forcing)
    return dict(
        n_patterns=len(patterns), n_feasible=feas, n_infeasible=infeas,
        n_feasibility_unknown=feas_unknown,
        n_forced=forced, n_forced_one=sum(1 for v in forcing if v == 1),
        n_undecided=undecided, n_forcing_unknown=forcing_unknown,
        n_one_sided=one_sided,
        determinism_ratio=(forced / feas) if feas else None,
        functional_sufficiency=suff, sufficiency_reason=reason,
        patterns_enumerated=enumerated,
        cut_structure=structure, cut_scope=cut_scope or {},
        query_status=";".join(f"{k}={qcount[k]}" for k in QUERY_STATES),
        forcing_patterns=";".join(str(v) for v in forcing),
        influence_per_input=";".join(
            f"{p['input']}|{p['comparable']}|{p['discordant']}|{int(p['valid'])}"
            for p in inf["per_input"]),
        influence_status=inf["status"], influence_mean=inf["mean"],
        influence_max=inf["max"], n_influence_inputs=inf["n_inputs"],
        n_valid_influence_inputs=inf["n_valid_inputs"],
    )


def classify_cut(leaf_total: int, selected: int, truncated: bool,
                 sat_sufficient: bool) -> tuple[str, str]:
    """Never call a truncated selection a complete structural boundary."""
    if sat_sufficient:
        return "sat_proven_sufficient", "sat_proved_all_feasible_forced"
    if truncated:
        return "partial_probe_of_larger_boundary", "leaf_cap_exceeded"
    if leaf_total <= selected:
        return "structural_boundary_complete", "all_leaves_included"
    return "structural_boundary_truncated", "selection_smaller_than_boundary"


def schedule(candidates: list[tuple[str, dict]], dff_budget: int,
             po_budget: int, max_scan_per_kind: int = 40) -> dict:
    """Give DFF and combinational PO independent budgets.

    PO candidates are attempted even when the DFF budget is exhausted.
    Every candidate records attempted / accepted / rejection reason.
    """
    attempts = []
    accepted = {"dff_next": 0, "cone": 0}
    for kind, budget in (("dff_next", dff_budget), ("cone", po_budget)):
        scanned = 0
        for k, item in candidates:
            if k != kind:
                continue
            if accepted[kind] >= budget:
                attempts.append(dict(kind=k, target=item.get("target", ""),
                                     attempted=False, accepted=False,
                                     reason="budget_exhausted"))
                continue
            if scanned >= max_scan_per_kind:
                attempts.append(dict(kind=k, target=item.get("target", ""),
                                     attempted=False, accepted=False,
                                     reason="scan_cap"))
                continue
            scanned += 1
            attempts.append(dict(kind=k, target=item.get("target", ""),
                                 attempted=True, accepted=True, reason="accepted"))
            accepted[kind] += 1
    return dict(attempts=attempts, accepted=accepted)


def symmetric_entropy(values: list, unknown: list[bool] | None = None) -> dict:
    """Entropy over known values, including 0. Unknown is a separate mask."""
    from collections import Counter
    import math
    known = [v for i, v in enumerate(values)
             if not (unknown[i] if unknown is not None else False)]
    n_unknown = len(values) - len(known)
    if not known:
        return dict(n_known=0, n_unknown=n_unknown, unique=0, entropy=None)
    c = Counter(known)
    p = [v / len(known) for v in c.values()]
    return dict(n_known=len(known), n_unknown=n_unknown,
                unique=len(c), entropy=-sum(x * math.log2(x) for x in p))
