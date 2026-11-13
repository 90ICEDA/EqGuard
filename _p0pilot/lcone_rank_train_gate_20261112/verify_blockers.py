"""Check only the frozen unknown training blockers with exact Boolean evaluation."""
import argparse
import csv
import re
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

from audit import CACHE, OUT, P, load_module, read, sha, write_json

panel = load_module('frozen_endpoint_proofs', P / 'lcone_endpoint_frozen_20261112/audit.py')
S = panel.S
Expressions = panel.Expressions

NODE_LIMIT = 80_000


class LogicOnlyPath:
    def __init__(self, path):
        self.path = path

    def read_text(self, **options):
        return re.sub(r'(?m)^\s*`timescale[^\r\n]*', '', self.path.read_text(**options))


def exact_roots(expr, roots, variables):
    """Return canonical BDD roots using a shared variable order and bounded workspace."""
    nodes = [(len(variables), 0, 0), (len(variables), 1, 1)]
    interned = {}
    positions = {name: i for i, name in enumerate(variables)}

    def node(level, lo, hi):
        if lo == hi:
            return lo
        key = level, lo, hi
        if key not in interned:
            if len(nodes) == NODE_LIMIT:
                raise OverflowError('bdd_node_limit')
            interned[key] = len(nodes)
            nodes.append(key)
        return interned[key]

    @lru_cache(maxsize=4 * NODE_LIMIT)
    def apply(op, a, b):
        if a > b:
            return apply(op, b, a)
        if op == '&':
            if a == 0 or a == b:
                return a
            if a == 1:
                return b
        elif op == '|':
            if a == 0 or a == b:
                return b
            if a == 1:
                return 1
        elif op == '^':
            if a == 0:
                return b
            if a == b:
                return 0
        level = min(nodes[a][0], nodes[b][0])
        _, al, ah = nodes[a] if nodes[a][0] == level else (level, a, a)
        _, bl, bh = nodes[b] if nodes[b][0] == level else (level, b, b)
        return node(level, apply(op, al, bl), apply(op, ah, bh))

    @lru_cache(maxsize=None)
    def convert(idx):
        op, *args = expr.nodes[idx]
        if op == 'const':
            return args[0]
        if op == 'var':
            return node(positions[args[0]], 0, 1)
        args = [convert(i) for i in args]
        if op == '~':
            return apply('^', 1, args[0])
        if op == '?':
            s, yes, no = args
            return apply('|', apply('&', s, yes), apply('&', apply('^', 1, s), no))
        return apply(op, *args)

    try:
        return [convert(r) for r in roots], len(nodes)
    finally:
        apply.cache_clear()
        convert.cache_clear()


def check_bdd():
    e = Expressions()
    x, y, s = (e.make('var', v) for v in ('x', 'y', 's'))
    nx = e.make('~', x)
    xor = e.make('^', x, y)
    mux = e.make('?', x, e.make('~', y), y)
    zero = e.make('^', s, s)
    one = e.make('|', x, nx)
    roots, _ = exact_roots(e, (xor, mux, zero, one, x, nx), ['y', 'x', 's'])
    assert roots[0] == roots[1] and roots[2:4] == [0, 1] and roots[4] != roots[5]


def exhaustive_check(expr, roots, variables):
    count = 1 << len(variables)
    mask = (1 << count) - 1
    env = {name: sum(1 << i for i in range(count) if (i >> j) & 1)
           for j, name in enumerate(variables)}
    run = expr.evaluator(env, mask)
    assert len({run(r) for r in roots}) == 1
    return count


def assess(spec, records, mapping, physical):
    assert spec['cec']['cec_status'] == 'PASS' and spec['cec']['unproven'] == '0'
    files = [Path(p) for p in spec['files']]
    assert [sha(p) for p in files] == spec['sha256']
    clean, orig, trans = [panel.endpoints(LogicOnlyPath(p)) for p in files[:3]]
    inserted, replacements, missing = panel.bind_lineage(spec['provenance'], clean, orig)
    states, _, _ = panel.binding(clean, orig, trans, replacements)
    expr = Expressions()
    evaluators = [panel.construct(g, expr, states) for g in (clean, orig, trans)]
    target = trans[0]
    output = []
    for r in records:
        cid = r['cone_id']
        identity = cid.split(':', 1)[1]
        detail = dict(view=spec['view'], source=spec['source'], cone_id=cid, status='unknown')
        try:
            nets = [dict(g[0]['pins'][identity][1])['D'] for g in (clean, orig, trans)]
            assert 'DFF' in target['pins'][identity][0]
            assert target['find'](nets[-1]) == target['find'](r['endpoint'])
            assert target['drivers'][target['find'](nets[-1])] == {r['driver']}
            members, issues = panel.structural_cone(trans, nets[-1])
            rows = sorted(int(x) for x in r['phys_rows'].split('|') if x)
            assert sorted(mapping[m] for m in members if m in mapping) == rows
            assert not (members - mapping.keys() - set(target['virtual_names']))
            assert all(physical[i] for i in rows)
            if issues or identity not in states:
                raise ValueError('endpoint_or_boundary_unbound')
            values = [ev(net) for ev, net in zip(evaluators, nets)]
            assert members == values[-1][1]
            roots = [v[0] for v in values]
            status, reason, nvars, witness = panel.qualify(expr, roots)
            variables = sorted(set().union(*(expr.inputs(r) for r in roots)))
            assert nvars == len(variables)
            detail.update(inputs=nvars, status=status, evidence=reason, witness=witness,
                          member_rows=rows, original_structural_equality=roots[0] == roots[1])
            if status == 'positive' and (missing or not inserted.intersection(values[1][1])):
                detail.update(status='unknown', evidence='unbound_manufacturing_lineage')
            elif status == 'unknown':
                for direction in ('sorted', 'reversed'):
                    try:
                        ids, count = exact_roots(expr, roots, variables if direction == 'sorted' else variables[::-1])
                        detail.update(bdd_nodes=count, bdd_order=direction, bdd_roots=ids)
                        if len(set(ids)) == 1:
                            detail.update(status='negative', evidence='canonical_bdd_three_way_equality')
                            if len(variables) <= 16:
                                detail['independent_exhaustive_assignments'] = exhaustive_check(expr, roots, variables)
                        else:
                            detail['evidence'] = 'exact_roots_differ_without_confirmed_influence_witness'
                        break
                    except (OverflowError, RecursionError) as exc:
                        detail.setdefault('bdd_limits', {})[direction] = type(exc).__name__
        except (KeyError, ValueError, RecursionError) as exc:
            detail.update(status='unknown', evidence=str(exc))
        output.append(detail)
    expr.inputs.cache_clear()
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--verified', action='store_true')
    args = parser.parse_args()
    check_bdd()
    blockers = OUT / 'BLOCKERS.csv'
    with blockers.open(encoding='utf-8-sig', newline='') as f:
        selected = {(r['view'], r['blocker']) for r in csv.DictReader(f)}
    selection = P / 'lcone_head_prep_20261112/all_eligible/SELECTION.json'
    specs = {r['view']: r for r in read(selection)['data']}
    _, arrays, names, layouts = S.load_snapshot('train')
    cache = defaultdict(list)
    with CACHE.open(encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            if r['split'] == 'train' and (r['view'], r['cone_id']) in selected:
                cache[r['view']].append(r)
    assert sum(map(len, cache.values())) == len(selected)
    output = []
    for view, records in sorted(cache.items()):
        mapping = S.view_rows(layouts, names, view)
        res = assess(specs[view], records, mapping, arrays['physical'])
        for r in res:
            print(view, r['cone_id'], r['status'], r.get('inputs'), r['evidence'], r.get('bdd_nodes'), flush=True)
        output.extend(res)
    assert len({(r['source'], r['cone_id']) for r in output}) == 6
    if args.verified:
        old = read(OUT / 'BLOCKER_PROOFS.json')['records']
        assert [{k: v for k, v in r.items() if k != 'independent_exhaustive_assignments'} for r in output] == old
    name = 'BLOCKER_PROOFS_VERIFIED.json' if args.verified else 'BLOCKER_PROOFS.json'
    write_json(OUT / name, dict(records=output, source_sha256=sha(blockers),
               selection_sha256=sha(selection), node_limit=NODE_LIMIT, optimizer_steps=0, sat_cec_calls=0))


if __name__ == '__main__':
    main()
