"""Audit genuinely competing training D cones outside the pilot host."""
import csv
from collections import Counter, defaultdict

import numpy as np
import torch

from audit import CACHE, EVIDENCE, OUT, P, V5, load_module, read, read_panel, sha, write_csv, write_json
from run_pilot import FOLDS, RUNS
from verify_blockers import S, assess, check_bdd


def rank_candidates(view, group, margin, mapping):
    labels, scores, peaks, members = {}, {}, {}, {}
    for cid, (label, rows) in group.items():
        ids = mapping[rows]
        assert (ids >= 0).all()
        values = margin[ids]
        labels[cid], scores[cid], members[cid] = label, float(values.max()), set(rows.tolist())
        peaks[cid] = set(rows[values == scores[cid]].tolist())
    order = sorted(scores, key=lambda cid: (-scores[cid], cid))
    index = {cid: i for i, cid in enumerate(order, 1)}
    seen, incremental, used = set(), {}, {}
    for cid in order:
        incremental[cid] = len(members[cid]-seen)
        seen.update(members[cid])
        used[cid] = len(seen)
    inventory, candidates = [], []
    for p in (c for c in order if labels[c] == 'positive'):
        source = view.rsplit('__ys_', 1)[0]
        inventory.append(dict(view=view, source=source, positive=p, positive_rank=index[p],
                              positive_size=len(members[p]), positive_prefix=used[p], hit=used[p] <= 512))
        for n in order[:index[p]-1]:
            if labels[n] == 'positive' or not incremental[n]:
                continue
            tie = scores[p] == scores[n]
            shared = bool(peaks[p] & peaks[n])
            candidates.append(dict(view=view, source=source, positive=p, negative=n,
                        status=labels[n], positive_rank=index[p], negative_rank=index[n],
                        positive_size=len(members[p]), positive_prefix=used[p],
                        incremental_gates=incremental[n], gap=scores[n]-scores[p],
                        same_score=tie, shared_max=shared, eligible=not shared,
                        negative_max=min(peaks[n])))
    return inventory, candidates


def verify(candidates):
    check_bdd()
    # Each checkpoint may nominate at most two distinct winner groups per view.
    groups = defaultdict(dict)
    for r in candidates:
        if r['status'] == 'unknown' and r['eligible'] and not r['same_score']:
            groups[r['fold'], r['reference'], r['view']].setdefault(r['negative_max'], r)
    chosen = {(r['view'], r['negative']) for group in groups.values()
              for r in sorted(group.values(), key=lambda x: (x['negative_rank'], -x['incremental_gates']))[:2]}
    if not chosen:
        return []
    old = read(OUT / 'BLOCKER_PROOFS_VERIFIED.json')['records']
    results = [dict(r, reused=True) for r in old if (r['view'], r['cone_id']) in chosen]
    pending = chosen - {(r['view'], r['cone_id']) for r in results}
    if not pending:
        return results
    selection = P / 'lcone_head_prep_20261112/all_eligible/SELECTION.json'
    specs = {r['view']: r for r in read(selection)['data']}
    _, arrays, names, layouts = S.load_snapshot('train')
    found = defaultdict(list)
    with CACHE.open(encoding='utf-8-sig', newline='') as f:
        for row in csv.DictReader(f):
            if row['split'] == 'train' and (row['view'], row['cone_id']) in pending:
                found[row['view']].append(row)
    assert sum(map(len, found.values())) == len(pending)
    for view, records in found.items():
        results.extend(dict(r, reused=False) for r in assess(specs[view], records, S.view_rows(layouts, names, view), arrays['physical']))
    return results


def metrics(positive, candidates, proofs):
    evidence = {(r['view'], r['cone_id']): r for r in proofs}
    results = []
    for r in candidates:
        proof = evidence.get((r['view'], r['negative']), {})
        admitted = (proof.get('status') == 'negative' and (proof.get('independent_exhaustive_assignments')
                    or proof.get('evidence') in ('exhaustive_free_PI_Q', 'identical_boolean_expression')))
        results.append(dict(r, verified_negative=r['status'] == 'negative' or bool(admitted),
                            extra_evidence=proof.get('evidence')))
    summary = {}
    for fold in FOLDS:
        summary[fold] = {}
        for ref in ('v5_best', 'pilot_last'):
            pr = [r for r in positive if (r['fold'], r['reference']) == (fold, ref)]
            rows = [r for r in results if (r['fold'], r['reference']) == (fold, ref)]
            hard = [r for r in rows if r['eligible'] and not r['same_score'] and r['verified_negative']]
            tied = [r for r in rows if r['eligible'] and r['same_score'] and r['verified_negative']]
            unknown = [r for r in rows if r['eligible'] and not r['same_score'] and not r['verified_negative']]
            summary[fold][ref] = dict(positive_records=len(pr), positives=len({(r['source'], r['positive']) for r in pr}),
                 sources=sorted({r['source'] for r in pr}), misses=sum(not r['hit'] for r in pr),
                 misses_positive_alone_over_budget=sum(r['positive_size'] > 512 and not r['hit'] for r in pr),
                 strict_pairs=len(hard), strict_positive_identities=len({(r['source'], r['positive']) for r in hard}),
                 strict_sources=sorted({r['source'] for r in hard}),
                 strict_pairs_for_misses=sum(r['positive_prefix'] > 512 for r in hard),
                 strict_pairs_for_feasible_misses=sum(r['positive_prefix'] > 512 and r['positive_size'] <= 512 for r in hard),
                 strict_unknown_pair_records=len(unknown), strict_unknown_endpoints=len({(r['view'], r['negative']) for r in unknown}),
                 tied_separate_winner_pairs=len(tied), shared_max_pair_records=sum(r['shared_max'] for r in rows))
    return summary, results


def main():
    layouts, panel = read_panel(verified=True)
    io = load_module('v5_io', V5 / 'fold_io.py')
    model_type = load_module('v5_model', P / 'control_best200_20261104/evaluate.py').Model
    model = model_type().cuda().eval().requires_grad_(False)
    positives, candidates, bindings = [], [], {}
    for fold in FOLDS:
        train = io.load_trans(fold)
        views = {v: g for v, g in panel.items() if not v.startswith('s35932') and not v.endswith('__'+fold)
                 and any(lab == 'positive' for lab, _ in g.values())}
        assert views and all(np.all(train['old2new'][layouts[v]['start']:layouts[v]['stop']] >= 0) for v in views)
        x, edge = (torch.as_tensor(train[k], device='cuda') for k in ('x', 'edge'))
        for ref, path in (('v5_best', V5 / fold / 'N/best.pt'), ('pilot_last', RUNS / fold / 'N/last.pt')):
            state = torch.load(path, map_location='cpu', weights_only=True)
            model.load_state_dict(state, strict=True)
            with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
                lg = model(x, edge).float()
                margin = (lg[:, 1]-lg[:, 0]).cpu().numpy()
            assert np.isfinite(margin).all() and all(torch.equal(v.cpu(), state[k]) for k, v in model.state_dict().items())
            bindings[f'{fold}/{ref}'] = sha(path)
            for view, group in sorted(views.items()):
                a, b = rank_candidates(view, group, margin, train['old2new'])
                positives.extend(dict(fold=fold, reference=ref, **r) for r in a)
                candidates.extend(dict(fold=fold, reference=ref, **r) for r in b)
    proof = verify(candidates)
    summary, pairs = metrics(positives, candidates, proof)
    source_only = read(P / 'lcone_head_protocol_20261112/SOURCE_ONLY_EVIDENCE.json')['results']
    other = Counter(r['source'] for r in source_only if any(e['kind'] == 'D' and e['status'] == 'positive' for e in r['endpoints']))
    write_csv(OUT / 'CROSS_HOST_POSITIVE_AUDIT.csv', positives)
    write_csv(OUT / 'CROSS_HOST_COMPETITORS.csv', pairs)
    write_json(OUT / 'CROSS_HOST_PAIR_AUDIT.json', dict(folds=summary, proofs=proof,
               extra_source_only_d_positive=dict(other), checkpoint_sha256=bindings, original_evidence_sha256=sha(EVIDENCE),
               optimizer_steps=0, sat_cec_calls=0, labels_modified=False, test_predictions_read=False))
    print(summary, flush=True)
    for r in proof:
        print(r['view'], r['cone_id'], r['status'], r.get('inputs'), r['evidence'], flush=True)


if __name__ == '__main__':
    main()
