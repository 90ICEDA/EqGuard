"""Reconstruct cumulative coverage and audit relation participants; no SAT/training.

Only writes versioned round7 artifacts. Historical solver evidence is immutable.
Neighbourhoods include seeds and follow source-to-target message flow.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parents[2]
TABLES = ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables'
OUT = TABLES / 'sat_repair_round7'
WORK = ROOT / 'generate_trans/folds/hosts_bt31'
PT = WORK / 'data/processed'
sys.path.insert(0, str(ROOT / '_p0pilot/round3_20261025'))
from r3_nets import build_index


def write(name, frame):
    pd.DataFrame(frame).to_csv(OUT / name, index=False, encoding='utf-8-sig')


def inclusive_hops(seed, edges, max_hops):
    result = [seed.copy()]
    for _ in range(max_hops):
        q = result[-1].copy()
        q[edges[1, result[-1][edges[0]]]] = True
        result.append(q)
    return result


def table_pairs(tt, k):
    d = {p: (f, v) for p, f, v in (x.split(':') for x in tt.split(';'))}
    expected = set(map(''.join, itertools.product('01', repeat=k)))
    if set(d) != expected:
        raise ValueError('Invalid pattern set')
    counts = [[0, 0] for _ in range(k)]
    for p in sorted(d):
        for b in range(k):
            if p[b] != '0':
                continue
            q = p[:b] + '1' + p[b + 1:]
            a, z = d[p], d[q]
            if a[0] == z[0] == 'feasible' and a[1] in ('0', '1') and z[1] in ('0', '1'):
                counts[b][0] += 1
                counts[b][1] += int(a[1] != z[1])
    return d, counts


def boundary_check(idx, target_bit, cut):
    """Does every nonconstant combinational dependency hit a selected cut bit?"""
    todo, seen, leaks = [target_bit], set(), []
    while todo:
        bit = todo.pop()
        if bit in cut or bit in seen:
            continue
        seen.add(bit)
        drivers = idx['bit_driver'].get(bit, set())
        if len(drivers) != 1:
            leaks.append((bit, 'primary_or_missing_driver' if not drivers else 'multi_driver'))
            continue
        cell = next(iter(drivers))
        if cell in idx['dff_cells']:
            leaks.append((bit, 'state_boundary'))
            continue
        inputs = [x for _, bits in idx['cell_inputs'].get(cell, [])
                  for x in bits if isinstance(x, int)]
        todo.extend(inputs)
    return dict(boundary_closed=int(not leaks), escape_count=len(leaks),
                escape_bits=';'.join(str(x[0]) for x in leaks),
                escape_reasons=';'.join(sorted(set(x[1] for x in leaks))))


def main():
    t0 = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    n4 = pd.concat([pd.read_csv(TABLES / 'sat_valid_round3' / n)
                    for n in ('r3_recovery_nodes.csv', 'r3_graded_nodes.csv')])
    n5 = pd.read_csv(TABLES / 'sat_nonlocal_round5/r5_nodes.csv')
    n6 = pd.read_csv(TABLES / 'sat_expand_round6/r6_nodes.csv')
    r5 = pd.read_csv(TABLES / 'sat_nonlocal_round5/r5_nonlocal_relations.csv')
    r6 = pd.read_csv(TABLES / 'sat_expand_round6/r6_nonlocal_relations.csv')
    raw = pd.concat([r5.assign(round='r5'), r6.assign(round='r6')], ignore_index=True)
    allnodes = pd.concat([n5, n6], ignore_index=True)
    n7 = None
    if (OUT / 'r7_nodes.csv').exists():
        n7 = pd.read_csv(OUT / 'r7_nodes.csv')
        r7 = pd.read_csv(OUT / 'r7_nonlocal_relations.csv')
        raw = pd.concat([raw, r7.assign(round='r7')], ignore_index=True)
        allnodes = pd.concat([allnodes, n7], ignore_index=True)

    # These are interpreted source records; never copy target output values to inputs.
    participants, boundaries, semantics = [], [], []
    indices = {}
    for row in raw.itertuples():
        index_key = (row.round, row.design)
        if index_key not in indices:
            # Numeric Yosys bit ids are local to a JSON export, not stable across runs.
            rd = {'r5': 'round3', 'r6': 'round6', 'r7': 'round7'}[row.round]
            files = [ROOT / f'_p0pilot/{rd}_20261025/struct_raw/{Path(row.design).stem}.json']
            path = next(x for x in files if x.exists())
            mod = next(iter(json.loads(path.read_text(encoding='utf-8'))['modules'].values()))
            indices[index_key] = build_index(mod)
        idx = indices[index_key]
        cut = str(row.cut_nets).split(';')
        bits = list(map(int, str(row.cut_bits).split(';')))
        tt, counts = table_pairs(row.truth_table, len(cut))
        target = idx['netbits'][row.target]
        assert len(target) == 1 and target[0] not in bits and len(set(bits)) == len(bits)
        bc = boundary_check(idx, target[0], set(bits))
        boundaries.append(dict(relation_id=row.relation_id, round=row.round,
                               claimed_kind=getattr(row, 'cut_kind', 'not_declared'), **bc))
        semantics.append(dict(relation_id=row.relation_id, role=row.role,
            has_feasibility_evidence=int(any(f == 'feasible' for f, v in tt.values())),
            has_conditional_forcing=int(any(f == 'feasible' and v in ('0', '1') for f, v in tt.values())),
            has_comparable_influence=int(any(c for c, d in counts)),
            has_observed_change=int(any(d for c, d in counts))))
        views = allnodes.loc[allnodes.relation_id == row.relation_id, ['view', 'role']].drop_duplicates()
        for j, (name, bit) in enumerate(zip(cut, bits)):
            assert idx['netbits'][name] == (bit,)
            drivers = idx['bit_driver'].get(bit, set())
            cell = next(iter(drivers)) if len(drivers) == 1 else ''
            c, d = counts[j]
            for vr in views.itertuples():
                participants.append(dict(relation_id=row.relation_id, design=row.design,
                    view=vr.view, role=vr.role, input_index=j, input_net=name,
                    input_bit=bit, driver=cell, comparable_pairs=c, changed_pairs=d,
                    possible_pairs=2 ** (len(cut) - 1), pair_coverage=c / 2 ** (len(cut) - 1),
                    conditional_change_fraction=(d / c if c else None),
                    source_kind=('unique_driver' if cell else 'primary_or_ambiguous'),
                    boundary_closed=bc['boundary_closed']))
    part = pd.DataFrame(participants)
    write('boundary_audit.csv', boundaries)
    write('relation_evidence_levels.csv', semantics)

    # One metadata parse and one node-name scan; lookup is (view, cell), never bare name.
    meta_path = WORK / 'data/for_train/metadata_trans.json'
    fids = json.loads(meta_path.read_text(encoding='utf-8'))['file_ids']
    split = json.loads((WORK / 'views.json').read_text(encoding='utf-8'))
    role_of = {v: i for i, r in enumerate(('train', 'val'), 1) for v in split[r + '_views']}
    role = np.fromiter((role_of.get(v, 0) for v in fids), dtype=np.uint8, count=len(fids))
    wanted = set(zip(part.view, part.driver))
    hits = defaultdict(list)
    with (PT / 'node_names_trans.txt').open(encoding='utf-8') as stream:
        for ni, line in enumerate(stream):
            if ni >= len(fids):
                raise ValueError('node names longer than metadata')
            key = (fids[ni], line.strip().lstrip('\\'))
            if key in wanted:
                hits[key].append(ni)
    mapped = []
    for row in part.to_dict('records'):
        ids = hits.get((row['view'], row['driver'].lstrip('\\')), []) if row['driver'] else []
        # Ambiguous graph-name duplicates are not accepted as a unique mapping.
        row['mapping_status'] = 'mapped' if len(ids) == 1 else ('ambiguous' if ids else 'unmapped')
        row['node_index'] = ids[0] if len(ids) == 1 else -1
        mapped.append(row)
    part = pd.DataFrame(mapped)
    write('input_participants.csv', part)
    del fids

    g = torch.load(PT / 'trans_graph.pt', map_location='cpu', weights_only=False, mmap=True)
    y = g.y.numpy().reshape(-1) > 0
    e = g.edge_index.numpy()
    assert len(y) == len(role)
    oldfile = PT / 'satrel_node_feats_sparseR1_real.npy'
    old = np.asarray(np.load(oldfile, mmap_mode='r')[:, 6]) > 0
    old &= role > 0
    np.savez_compressed(OUT / 'old_support_indices.npz',
                        train=np.flatnonzero(old & (role == 1)), val=np.flatnonzero(old & (role == 2)))
    def mask(ids):
        z = np.zeros(len(y), bool)
        z[np.asarray(list(ids), dtype=np.int64)] = True
        return z
    sets = dict(old=old, r4=mask(n4.node_index), r5=mask(n5.node_index), r6=mask(n6.node_index))
    sets['cum4'] = old | sets['r4']
    sets['cum5'] = sets['cum4'] | sets['r5']
    sets['cum6'] = sets['cum5'] | sets['r6']
    if n7 is not None:
        sets['r7'] = mask(n7.node_index)
        sets['cum7'] = sets['cum6'] | sets['r7']
    valid_part = part[(part.mapping_status == 'mapped') & (part.comparable_pairs > 0)]
    sets['input_comparable'] = mask(valid_part.node_index)
    sets['input_changed'] = mask(part[(part.mapping_status == 'mapped') & (part.changed_pairs > 0)].node_index)
    sets['endpoints_inputs'] = sets['r5'] | sets['r6'] | sets.get('r7', np.zeros(len(y), bool)) | sets['input_comparable']
    latest = 'cum7' if n7 is not None else 'cum6'
    parent = dict(r4='old', r5='cum4', r6='cum5', r7='cum6', input_comparable=latest,
                  input_changed=latest, endpoints_inputs=latest)
    neighborhoods = {k: inclusive_hops(v, e, 2) for k, v in sets.items()}
    coverage = []
    for name, hs in neighborhoods.items():
        for code, r in ((1, 'train'), (2, 'val')):
            for h, z in enumerate(hs):
                m = z & (role == code)
                base = neighborhoods[parent[name]][h] if name in parent else np.zeros(len(y), bool)
                coverage.append(dict(basis=name, role=r, max_hops=h, nodes=int(m.sum()),
                    positives=int(y[m].sum()), parent=parent.get(name, ''),
                    incremental_nodes=int((m & ~base).sum()) if name in parent else None,
                    incremental_positives=int(y[m & ~base].sum()) if name in parent else None))
    write('cumulative_coverage.csv', coverage)
    # Strictly evidence-bearing participant statistics; no dense training feature is written.
    info = dict(relations=len(raw), participants=len(part),
        participant_mapping=part.mapping_status.value_counts().to_dict(),
        comparable_input_nodes=int(sets['input_comparable'].sum()),
        changed_input_nodes=int(sets['input_changed'].sum()),
        false_full_boundary=[r['relation_id'] for r in boundaries
                             if r['claimed_kind'] == 'full_boundary' and not r['boundary_closed']],
        no_conditional_forcing=[r['relation_id'] for r in semantics if not r['has_conditional_forcing']],
        old_nodes={r: int((old & (role == code)).sum()) for code, r in ((1, 'train'), (2, 'val'))},
        neighborhood='source-to-target, inclusive distance <= h; role restricted; includes seeds',
        test_evaluated=False, sat_queries=0, training_runs=0,
        elapsed_s=round(time.perf_counter() - t0, 2))
    (OUT / 'audit_manifest.json').write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(info, ensure_ascii=False, indent=2), flush=True)
    print(pd.DataFrame(coverage).query("basis in ['r6','r7','input_comparable','input_changed']").to_string(index=False), flush=True)


if __name__ == '__main__':
    main()
