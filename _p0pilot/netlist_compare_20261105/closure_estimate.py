"""Estimate how many equivalence-cone pairs can be added by transitive closure (no new SAT).

Every proven pair links two root endpoints (view, cell, pin) inside one context. If A~B and
B~C are proven under the same context, A~C is implied. We build the endpoint graph per
(source, context), take connected components, and count cross-view pairs not already proven.
"""
import collections
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
J = ROOT / '_p0pilot/cec_joint_expand_20261105'

pairs = json.loads((J / 'final_pairs.json').read_text(encoding='utf-8'))
cones = {c['cone_id']: c for c in json.loads((J / 'final_cones.json').read_text(encoding='utf-8'))}


def endpoint_key(ep):
    return (ep['view'], ep['cell'], ep['pin'], ep.get('bit'))


def view_recipe(view):
    return view.split('__')[-1]


def main():
    # node -> cone_id (only 'row' endpoints carry a cone via the pair; use pair cones)
    graph = collections.defaultdict(set)      # (source, context) -> set of frozenset edges
    node_cone = {}
    proven = set()
    for p in pairs:
        eps = p.get('root_endpoints') or []
        if len(eps) != 2:
            continue
        ka, kb = endpoint_key(eps[0]), endpoint_key(eps[1])
        key = (p['source_object'], p['context_id'])
        graph[key].add((ka, kb))
        node_cone[ka] = p['left_cone']; node_cone[kb] = p['right_cone']
        proven.add(frozenset([ka, kb]))

    added = collections.Counter(); added_by_split = collections.Counter()
    per_source = collections.Counter()
    for (source, ctx), edges in graph.items():
        parent = {}
        def find(x):
            parent.setdefault(x, x)
            while parent[x] != x:
                parent[x] = parent[parent[x]]; x = parent[x]
            return x
        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb
        for a, b in edges:
            union(a, b)
        comp = collections.defaultdict(list)
        for n in parent:
            comp[find(n)].append(n)
        for nodes in comp.values():
            nodes = [n for n in nodes if n in node_cone]
            for i in range(len(nodes)):
                for j in range(i + 1, len(nodes)):
                    a, b = nodes[i], nodes[j]
                    if view_recipe(a[0]) == view_recipe(b[0]):
                        continue
                    if frozenset([a, b]) in proven:
                        continue
                    rec = '|'.join(sorted([view_recipe(a[0]), view_recipe(b[0])]))
                    ca, cb = node_cone[a], node_cone[b]
                    m = min(len(cones[ca]['graph_rows']), len(cones[cb]['graph_rows']))
                    added[rec] += 1
                    per_source[source] += 1
                    split = next((p['split'] for p in pairs if p['source_object'] == source), '?')
                    added_by_split[(split, rec)] += 1

    print('implied new pairs by recipe:', dict(added.most_common()))
    print('implied total:', sum(added.values()))
    print('\nby split x recipe:')
    for (s, r), n in sorted(added_by_split.items()):
        print(f'  {s:6s} {r:14s} {n}')
    print('\nby source:')
    for s, n in sorted(per_source.items()):
        print(f'  {s:32s} {n}')
    out = dict(by_recipe=dict(added), total=sum(added.values()),
               by_split_recipe={f'{s}|{r}': n for (s, r), n in added_by_split.items()},
               by_source=dict(per_source), note='transitive closure only; no new SAT; cones reused')
    (Path(__file__).resolve().parent / 'closure_estimate.json').write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
