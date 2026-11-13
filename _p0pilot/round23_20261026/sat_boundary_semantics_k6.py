"""Gate-independent, fail-closed interpretation of conditional SAT tables.

An influence witness here is a pair of feasible, forced rows differing in
exactly one cut coordinate. It is NOT a shared-environment intervention proof.
Missing rows and solver failures never count as forced values or negative
influence evidence. No solver or historical artifact is imported or modified.
"""
from __future__ import annotations

import itertools
import re

COLS = ['k_over_8', 'feasibility_known_fraction', 'feasible_fraction',
        'forced_fraction', 'undecided_fraction', 'infeasible_fraction',
        'determinism_on_feasible', 'determinism_valid', 'ones_on_forced',
        'ones_valid', 'comparable_pair_fraction', 'change_on_comparable',
        'influence_valid', 'max_input_influence', 'complete_full_domain',
        'complete_restricted_domain', 'partial_forcing', 'has_unknown']
STATES = {('feasible', '0'), ('feasible', '1'), ('feasible', 'undecided'),
          ('infeasible', 'not_applicable'), ('unknown', 'unknown')}


def classify(q1: str, q0: str) -> tuple[str, str]:
    """Each prove is universal over the SAME premise; refuted has a witness."""
    return {('proved', 'proved'): ('infeasible', 'not_applicable'),
            ('proved', 'refuted'): ('feasible', '1'),
            ('refuted', 'proved'): ('feasible', '0'),
            ('refuted', 'refuted'): ('feasible', 'undecided')}.get(
                (q1, q0), ('unknown', 'unknown'))


def summarize(table: dict, k: int):
    if not 1 <= k <= 6:
        raise ValueError('Boundary descriptor supports 1..6 inputs')
    expected = {''.join(p) for p in itertools.product('01', repeat=k)}
    if set(table) != expected or any(tuple(v) not in STATES for v in table.values()):
        raise ValueError('Complete, explicitly bound pattern table required')
    n = len(expected)
    feasible = sum(f == 'feasible' for f, v in table.values())
    forced = sum(f == 'feasible' and v in ('0', '1') for f, v in table.values())
    ones = sum(f == 'feasible' and v == '1' for f, v in table.values())
    unknown = sum(f == 'unknown' for f, v in table.values())
    undecided = sum(f == 'feasible' and v == 'undecided' for f, v in table.values())
    infeasible = sum(f == 'infeasible' for f, v in table.values())
    inputs = input_influence(table, k)
    comp = sum(x['comparable'] for x in inputs)
    changed = sum(x['changed'] for x in inputs)
    full = unknown == 0 and forced == feasible and feasible > 0
    values = [k / 8, (n - unknown) / n, feasible / n, forced / n,
              undecided / n, infeasible / n, forced / feasible if feasible else 0.,
              int(feasible > 0), ones / forced if forced else 0., int(forced > 0),
              comp / (k * 2 ** (k - 1)), changed / comp if comp else 0.,
              int(comp > 0), max(x['change_fraction'] for x in inputs),
              int(full and feasible == n), int(full and feasible < n),
              int(forced > 0 and forced < feasible), int(unknown > 0)]
    return dict(zip(COLS, values)), inputs


def input_influence(table: dict, k: int) -> list[dict]:
    """Pair by actual coordinate tuples, independent of row order/sampling."""
    if k < 1 or any(len(p) != k or set(p) - {'0', '1'} for p in table):
        raise ValueError('Malformed pattern coordinate')
    if any(tuple(v) not in STATES for v in table.values()):
        raise ValueError('Malformed pattern state')
    result = []
    for i in range(k):
        comp = changed = 0
        for p, a in table.items():
            if p[i] != '0':
                continue
            b = table.get(p[:i] + '1' + p[i + 1:])
            if (b is not None and a[0] == b[0] == 'feasible'
                    and a[1] in ('0', '1') and b[1] in ('0', '1')):
                comp += 1
                changed += a[1] != b[1]
        result.append(dict(input_index=i, comparable=comp, changed=changed,
                           pair_coverage=comp / (2 ** (k - 1)),
                           change_fraction=changed / comp if comp else 0.,
                           influence_valid=int(comp > 0)))
    return result


def parse_query_results(log: str) -> list[str]:
    """SATQ markers retain timeout/missing slots instead of shifting results.

    Unmarked legacy logs remain readable but cannot reconstruct missing slots;
    callers must not present them as marker-bound evidence.
    """
    blocks, current = {}, None
    for line in log.splitlines():
        match = re.fullmatch(r'SATQ(\d{6})', line.strip())
        if match:
            current = int(match[1])
            if current in blocks:
                raise ValueError('Duplicate SAT query marker')
            blocks[current] = []
        elif current is not None:
            blocks[current].append(line)
    if not blocks:
        return ['proved' if 'no model found: SUCCESS' in ln else 'refuted'
                for ln in log.splitlines()
                if 'no model found: SUCCESS' in ln or 'model found: FAIL' in ln]
    result = []
    for qid in range(max(blocks) + 1):
        text = '\n'.join(blocks.get(qid, []))
        proved = 'no model found: SUCCESS' in text
        refuted = 'model found: FAIL' in text
        if 'ERROR:' in text or (proved and refuted):
            result.append('error')
        else:
            result.append('proved' if proved else 'refuted' if refuted else 'unknown')
    return result
