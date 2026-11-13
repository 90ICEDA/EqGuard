"""Pure offline, bounded functional-boundary descriptors (no solver imports).

Canonical signatures are comparison aids, NEVER proofs of signal equivalence.
Canonical positions may be ambiguous under input symmetries; keep all ties.
"""
import hashlib
import itertools
import json

COLS = ['k_over_4', 'feasibility_known_fraction', 'feasible_fraction',
        'forced_fraction', 'undecided_fraction', 'infeasible_fraction',
        'determinism_on_feasible', 'determinism_valid', 'ones_on_forced',
        'ones_valid', 'comparable_pair_fraction', 'change_on_comparable',
        'influence_valid', 'max_input_influence', 'complete_full_domain',
        'complete_restricted_domain', 'partial_forcing', 'has_unknown']
STATES = {('feasible','0'), ('feasible','1'), ('feasible','undecided'),
          ('infeasible','not_applicable'), ('unknown','unknown')}


def parse_table(text, k):
    if not 1 <= k <= 4:
        raise ValueError('Only existing 1..4-bit evidence supported')
    rows = [x.split(':') for x in str(text).split(';')]
    expected = set(map(''.join, itertools.product('01', repeat=k)))
    if any(len(x) != 3 for x in rows) or len(rows) != len(expected):
        raise ValueError('Wrong or duplicate pattern count')
    result = {p:(f,v) for p,f,v in rows}
    if set(result) != expected or any(x not in STATES for x in result.values()):
        raise ValueError('Invalid table binding/state')
    return result


def reindex(table, order):
    """order[new_position] is its source input index."""
    k = len(order)
    if sorted(order) != list(range(k)):
        raise ValueError('Invalid input permutation')
    result = {}
    for p, value in table.items():
        result[''.join(p[i] for i in order)] = value
    return result


def canonical(table, k):
    best, orders = None, []
    for order in itertools.permutations(range(k)):
        t = reindex(table, order)
        signature = ';'.join(f'{p}:{t[p][0]}:{t[p][1]}' for p in sorted(t))
        if best is None or signature < best:
            best, orders = signature, [list(order)]
        elif signature == best:
            orders.append(list(order))
    return dict(signature=best, signature_sha=hashlib.sha256(best.encode()).hexdigest(),
                orders=orders, unique_order=len(orders)==1,
                slot_candidates=[[j for j in range(k) if any(o[j]==i for o in orders)] for i in range(k)])


def summarize(table, k):
    n = 2**k
    feasible = sum(f=='feasible' for f,v in table.values())
    forced = sum(f=='feasible' and v in ('0','1') for f,v in table.values())
    ones = sum(f=='feasible' and v=='1' for f,v in table.values())
    unknown = sum(f=='unknown' for f,v in table.values())
    undecided = sum(f=='feasible' and v=='undecided' for f,v in table.values())
    infeasible = sum(f=='infeasible' for f,v in table.values())
    inputs = []
    for b in range(k):
        comp = changed = 0
        for p,a in table.items():
            if p[b] != '0':
                continue
            q = p[:b]+'1'+p[b+1:]
            z = table[q]
            if a[0] == z[0] == 'feasible' and a[1] in ('0','1') and z[1] in ('0','1'):
                comp += 1
                changed += a[1] != z[1]
        inputs.append(dict(input_index=b, comparable=comp, changed=changed,
            pair_coverage=comp/(2**(k-1)), change_fraction=changed/comp if comp else 0.,
            influence_valid=int(comp>0)))
    comp = sum(x['comparable'] for x in inputs)
    changed = sum(x['changed'] for x in inputs)
    full = unknown==0 and forced==feasible and feasible>0
    values = [k/4, (n-unknown)/n, feasible/n, forced/n, undecided/n, infeasible/n,
        forced/feasible if feasible else 0., int(feasible>0), ones/forced if forced else 0., int(forced>0),
        comp/(k*2**(k-1)), changed/comp if comp else 0., int(comp>0),
        max(x['change_fraction'] for x in inputs), int(full and feasible==n),
        int(full and feasible<n), int(forced>0 and forced<feasible), int(unknown>0)]
    return dict(zip(COLS, values)), inputs


def comparison_gate(context_a, context_b, explicit_signal_proof=False, safety_roles_verified=False):
    """Function similarity is not a permission to build a consistency pair."""
    return dict(descriptor_comparable=context_a==context_b,
                semantic_pair_allowed=context_a==context_b and explicit_signal_proof,
                training_pair_allowed=context_a==context_b and explicit_signal_proof and safety_roles_verified)


def context_key(context):
    return hashlib.sha256(json.dumps(context,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
