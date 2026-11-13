"""Explicit qid binding for round-5 evidence."""
from __future__ import annotations

import itertools


def validate_qid_specs(cut: list[str], specs: list[dict]) -> dict:
    k = len(cut)
    expected = {(("".join(str(b) for b in p)), prove)
                for p in itertools.product([0, 1], repeat=k) for prove in (1, 0)}
    got = {(s["pattern"], int(s["prove"])) for s in specs}
    qids = [int(s["qid"]) for s in specs]
    missing = sorted(expected - got)
    extra = sorted(got - expected)
    issues = []
    if missing:
        issues.append(f"missing={missing}")
    if extra:
        issues.append(f"extra={extra}")
    if len(qids) != len(set(qids)):
        issues.append("duplicate_qid")
    if len(specs) != 2 * (2 ** k):
        issues.append(f"count={len(specs)}_expected={2 * (2 ** k)}")
    return dict(valid=not issues, issues=";".join(issues),
                n_specs=len(specs), expected=2 * (2 ** k))


def statuses_by_qid(specs: list[dict], status_by_key: dict[str, str]) -> dict[int, str]:
    out = {}
    for s in specs:
        out[int(s["qid"])] = status_by_key.get(s["query_key"], "no_result")
    return out
