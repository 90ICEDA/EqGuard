"""Corrected function classification and influence coverage (round 6).

A function class is only assigned when enumeration is complete, all queries
finished, at least one feasible pattern exists, and every feasible pattern is
forced. Partial / unknown / infeasible are separate categories. A class found
only on a restricted feasible domain is marked domain_restricted.
"""
from __future__ import annotations


def parse_tt(tt: str, k: int) -> dict:
    out = {}
    for item in str(tt).split(";"):
        p, feas, force = item.split(":")
        out[p] = (feas, force)
    if len(out) != 2 ** k:
        raise ValueError(f"truth table has {len(out)} patterns, expected {2 ** k}")
    return out


def _function_name(vals: dict, k: int) -> str:
    if not vals:
        return "no_feasible"
    if all(v == 0 for v in vals.values()):
        return "constant0"
    if all(v == 1 for v in vals.values()):
        return "constant1"
    if k == 1:
        if vals.get("0") == 0 and vals.get("1") == 1:
            return "identity"
        if vals.get("0") == 1 and vals.get("1") == 0:
            return "inverter"
    if k >= 2:
        def ok(fn):
            return all(fn(p) == v for p, v in vals.items())
        if ok(lambda p: int(all(c == "1" for c in p))):
            return "and"
        if ok(lambda p: int(any(c == "1" for c in p))):
            return "or"
        if ok(lambda p: int(sum(int(c) for c in p) % 2 == 1)):
            return "xor"
    return "other"


def classify(tt: str, k: int, enum_complete: bool, query_status: str) -> dict:
    d = parse_tt(tt, k)
    feasible = [p for p, (fe, f) in d.items() if fe == "feasible"]
    forced = [p for p in feasible if d[p][1] in ("0", "1")]
    unresolved = [p for p in feasible if d[p][1] == "undecided"]
    q = dict(kv.split("=") for kv in str(query_status).split(";") if "=" in kv)
    q_unfinished = any(int(q.get(x, 0)) > 0 for x in ("timeout", "error", "no_result"))
    if not enum_complete:
        status, cls, restricted = "not_enumerated", "not_enumerated", False
    elif q_unfinished:
        status, cls, restricted = "unknown", "unknown", False
    elif not feasible:
        status, cls, restricted = "infeasible", "infeasible", False
    elif unresolved:
        status, cls, restricted = "partial_forced", "partial_forced", False
    else:
        vals = {p: int(d[p][1]) for p in forced}
        name = _function_name(vals, k)
        full_domain = len(feasible) == 2 ** k
        status = "complete_function" if full_domain else "domain_restricted_function"
        cls = name if full_domain else f"domain_restricted_{name}"
        restricted = not full_domain
    return dict(function_status=status, function_class=cls,
                domain_restricted=int(restricted), n_feasible=len(feasible),
                n_forced=len(forced), n_undecided=len(unresolved),
                n_infeasible=sum(1 for fe, _ in d.values() if fe == "infeasible"))


def influence_from_tt(tt: str, k: int, cut: list[str] | None = None) -> dict:
    """Comparable/discordant pairs computed from the truth table itself."""
    d = parse_tt(tt, k)
    comp = [0] * k
    disc = [0] * k
    pats = sorted(d)
    for i in range(len(pats)):
        for j in range(i + 1, len(pats)):
            diff = [b for b in range(k) if pats[i][b] != pats[j][b]]
            if len(diff) != 1:
                continue
            b = diff[0]
            f0, f1 = d[pats[i]], d[pats[j]]
            if f0[0] == "feasible" and f1[0] == "feasible" \
                    and f0[1] in ("0", "1") and f1[1] in ("0", "1"):
                comp[b] += 1
                if f0[1] != f1[1]:
                    disc[b] += 1
    possible = k * (2 ** (k - 1))
    comp_total, disc_total = sum(comp), sum(disc)
    valid = [b for b in range(k) if comp[b] > 0]
    mean = (sum(disc[b] / comp[b] for b in valid) / len(valid)) if valid else None
    return dict(influence_comparable_pairs=comp_total,
                influence_possible_pairs=possible,
                influence_pair_coverage=(comp_total / possible if possible else 0.0),
                influence_observed_change=int(disc_total > 0),
                influence_mean=mean, influence_valid_inputs=len(valid),
                influence_scope=("subset_of_pairs" if comp_total < possible else "all_pairs"),
                influence_per_input=";".join(
                    f"{(cut[b] if cut else str(b))}|{comp[b]}|{disc[b]}|{int(comp[b] > 0)}"
                    for b in range(k)))


def influence_stats(text: str, k: int) -> dict:
    """Comparable/discordant counts plus pair coverage, never a bare zero."""
    per = []
    for item in str(text).split(";"):
        if not item:
            continue
        name, comp, disc, valid = item.split("|")
        per.append(dict(input=name, comparable=int(comp), discordant=int(disc),
                        valid=int(valid)))
    possible = k * (2 ** (k - 1))  # single-bit-neighbour pairs, per input: 2^(k-1)
    comp_total = sum(p["comparable"] for p in per)
    disc_total = sum(p["discordant"] for p in per)
    coverage = comp_total / possible if possible else 0.0
    valid_inputs = [p for p in per if p["valid"]]
    mean = (sum(p["discordant"] / p["comparable"] for p in valid_inputs)
            / len(valid_inputs)) if valid_inputs else None
    return dict(influence_comparable_pairs=comp_total,
                influence_possible_pairs=possible,
                influence_pair_coverage=coverage,
                influence_observed_change=int(disc_total > 0),
                influence_mean=mean,
                influence_valid_inputs=len(valid_inputs),
                influence_scope=("subset_of_pairs" if coverage < 1.0 else "all_pairs"))
