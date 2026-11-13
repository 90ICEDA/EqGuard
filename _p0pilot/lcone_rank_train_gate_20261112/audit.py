"""Audit train-only functional D pairs and budget competitors in v5 folds."""
import argparse
import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import torch

OUT = Path(__file__).resolve().parent
P = OUT.parent
sys.path.insert(0, str(P / 'c2_endpoint_replay_20261112'))
from replay import BOUNDARY, load_module, read, sha, write_csv, write_json

V5 = P / 'heldout_recipe_v5_20261109'
EVIDENCE = P / 'lcone_head_prep_20261112/all_eligible/TRAIN_ENDPOINTS.json'
CACHE = P / 'seed42_supervised_prep_20261109/CONE_CACHE_V2.csv'
CAP = 512


def read_panel(verified=False):
    shared = read(BOUNDARY / 'input_contract.json')['shared_inputs']
    layouts = {v['view']: v for v in shared['trans_train']['views']}
    held = {v['view'].split('__')[0] for split in ('val', 'test') for v in shared[f'trans_{split}']['views']}
    evidence = defaultdict(dict)
    for row in read(EVIDENCE):
        if row['kind'] != 'D':
            continue
        v, cid = row['view'], row['cone_id']
        assert v in layouts and v.split('__')[0] not in held and cid not in evidence[v]
        assert row['source'] == v.rsplit('__ys_', 1)[0]
        if row['label'] == 1:
            assert row['witness'] and row['lineage']
        else:
            assert row['label'] == 0 and row['evidence'] in ('exhaustive_free_PI_Q', 'identical_boolean_expression')
        evidence[v][cid] = row
    if verified:
        proof = read(OUT / 'BLOCKER_PROOFS_VERIFIED.json')
        assert proof['source_sha256'] == sha(OUT / 'BLOCKERS.csv')
        for row in proof['records']:
            v, cid = row['view'], row['cone_id']
            if row['status'] == 'negative':
                assert v in evidence and cid not in evidence[v] and row['independent_exhaustive_assignments'] == 1 << row['inputs']
                evidence[v][cid] = dict(row, label=0)
    candidates = defaultdict(dict)
    with CACHE.open(encoding='utf-8-sig', newline='') as f:
        for row in csv.DictReader(f):
            v, cid = row['view'], row['cone_id']
            if row['split'] != 'train' or row['kind'] != 'D' or v not in evidence or not int(row['n_phys']):
                continue
            arr = np.fromstring(row['phys_rows'], dtype=np.int64, sep='|')
            lay = layouts[v]
            assert len(arr) == int(row['n_phys']) and np.all((arr >= lay['start']) & (arr < lay['physical_stop']))
            proof = evidence[v].get(cid)
            label = 'unknown'
            if proof:
                assert np.array_equal(arr, proof['member_rows'])
                label = 'positive' if proof['label'] else 'negative'
            assert cid not in candidates[v]
            candidates[v][cid] = (label, arr)
    assert all(evidence[v].keys() <= candidates[v].keys() for v in evidence)
    return layouts, candidates


def audit_view(view, group, margin, mapping, physical):
    labels, members, winners, scores = {}, {}, {}, {}
    for cid, (label, glob) in group.items():
        loc = mapping[glob]
        assert np.all(loc >= 0) and physical[loc].all()
        vals = margin[loc]
        score = float(vals.max())
        labels[cid] = label
        members[cid] = set(glob.tolist())
        winners[cid] = int(glob[vals == score].min())
        scores[cid] = score
    order = sorted(group, key=lambda c: (-scores[c], c))
    seen, before, incremental, position, cutoff = set(), {}, {}, {}, len(order)
    for i, c in enumerate(order):
        before[c] = len(seen)
        incremental[c] = len(members[c] - seen)
        position[c] = i
        seen.update(members[c])
        if len(seen) > CAP and cutoff == len(order):
            cutoff = i
    source, recipe = view.rsplit('__ys_', 1)
    results, pairs = [], []
    for p in (c for c in order if labels[c] == 'positive'):
        strictly_higher = [c for c in order[:position[p]] if scores[c] > scores[p] and incremental[c]]
        ahead_counts = Counter(labels[c] for c in strictly_higher)
        competing = [c for c in strictly_higher if labels[c] == 'negative']
        # Select at most one candidate per representative max row; this is a diagnostic cap.
        candidates = sorted(competing, key=lambda c: (-incremental[c], position[c], c))
        shortlist = {}
        for c in candidates:
            shortlist.setdefault(winners[c], c)
        for c in list(shortlist.values())[:4]:
            pairs.append(dict(view=view, source=source, recipe=recipe, positive=p, negative=c,
                              positive_score=scores[p], negative_score=scores[c], positive_rank=position[p]+1,
                              negative_rank=position[c]+1, negative_incremental_gates=incremental[c],
                              negative_max_global=winners[c]))
        results.append(dict(view=view, source=source, recipe=recipe, positive=p, positive_rank=position[p]+1,
                            known_negative_in_view=sum(l == 'negative' for l in labels.values()),
                            positive_gate_size=len(members[p]), positive_prefix_gates=before[p]+incremental[p],
                            hit_512=position[p] < cutoff, strictly_higher_cost_negative=ahead_counts['negative'],
                            strictly_higher_cost_unknown=ahead_counts['unknown'],
                            distinct_max_hard_negatives=len(shortlist),
                            first_blocker_label=labels[order[cutoff]] if cutoff < len(order) else None,
                            first_blocker_id=order[cutoff] if cutoff < len(order) else None,
                            first_blocker_size=len(members[order[cutoff]]) if cutoff < len(order) else None,
                            first_blocker_incremental=incremental[order[cutoff]] if cutoff < len(order) else None))
    return results, pairs


def summarize(rows, inventory):
    positive = {(r['source'], r['positive']) for r in rows}
    hard = [r for r in rows if r['strictly_higher_cost_negative']]
    missed = [r for r in rows if not r['hit_512']]
    return dict(views=inventory['views'], views_with_both=inventory['views_with_both'],
                function_positive_records=len(rows), positive_identities=len(positive),
                positive_sources=len({r['source'] for r in rows}),
                function_negative_records=inventory['negative'], unknown_records=inventory['unknown'],
                hard_positive_records=len(hard), hard_positive_sources=len({r['source'] for r in hard}),
                hard_positive_identities=len({(r['source'], r['positive']) for r in hard}),
                missed_records=len(missed), missed_with_hard_negative=sum(bool(r['strictly_higher_cost_negative']) for r in missed),
                missed_first_blocker=dict(Counter(r['first_blocker_label'] for r in missed)),
                cost_competitors=dict(negative=sum(r['strictly_higher_cost_negative'] for r in rows),
                                      unknown=sum(r['strictly_higher_cost_unknown'] for r in rows)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--blockers', action='store_true', help='write the follow-up blocker evidence only')
    parser.add_argument('--verified', action='store_true', help='apply separately verified negative evidence for this audit')
    args = parser.parse_args()
    layouts, panel = read_panel(args.verified)
    Model = load_module('v5_model', P / 'control_best200_20261104/evaluate.py').Model
    fold_io = load_module('v5_io', V5 / 'fold_io.py')
    model = Model().cuda().eval().requires_grad_(False)
    audit, rows, candidates = {}, [], []
    for fold in fold_io.RECIPES:
        data = fold_io.load_trans(fold)
        eligible = {v: g for v, g in panel.items() if not v.endswith('__' + fold)}
        assert all(np.all(data['old2new'][layouts[v]['start']:layouts[v]['stop']] >= 0) for v in eligible)
        assert all(np.all(data['old2new'][layouts[v]['start']:layouts[v]['stop']] == -1) for v in panel.keys()-eligible.keys())
        ckpt = V5 / fold / 'N/best.pt'
        state = torch.load(ckpt, map_location='cpu', weights_only=True)
        model.load_state_dict(state, strict=True)
        x = torch.as_tensor(data['x'], device='cuda')
        edge = torch.as_tensor(data['edge'], device='cuda')
        with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
            logits = model(x, edge).float()
            margin = (logits[:, 1] - logits[:, 0]).cpu().numpy()
        assert np.isfinite(margin).all() and all(torch.equal(v.cpu(), state[k]) for k, v in model.state_dict().items())
        inventory, results = Counter(views=len(eligible)), []
        for v, g in sorted(eligible.items()):
            counts = Counter(label for label, _ in g.values())
            inventory.update(counts)
            inventory['views_with_both'] += bool(counts['positive'] and counts['negative'])
            details, pairs = audit_view(v, g, margin, data['old2new'], data['physical'])
            results.extend(dict(fold=fold, **r) for r in details)
            candidates.extend(dict(fold=fold, **r) for r in pairs)
        rows.extend(results)
        summary = summarize(results, inventory)
        audit[fold] = dict(**summary, checkpoint_sha256=sha(ckpt),
                           train_map_sha256=sha(fold_io.V4 / f'{fold}_train_map.npz'))
        print(fold, summary, flush=True)
        del x, edge, logits
    if args.blockers:
        blockers = {}
        for r in rows:
            if r['hit_512'] or r['first_blocker_label'] != 'unknown':
                continue
            view, source, fold, cid = (r[k] for k in ('view', 'source', 'fold', 'first_blocker_id'))
            key = (fold, view, cid)
            if key not in blockers:
                other_proofs = []
                for other, group in panel.items():
                    if (other == view or other.endswith('__' + fold) or
                            other.rsplit('__ys_', 1)[0] != source or cid not in group):
                        continue
                    label, _ = group[cid]
                    if label != 'unknown':
                        other_proofs.append(f'{other.rsplit("__ys_", 1)[1]}:{label}')
                blockers[key] = dict(fold=fold, view=view, source=source, blocker=cid,
                                     gate_size=r['first_blocker_size'], incremental_gates=r['first_blocker_incremental'],
                                     other_fold_training_view_evidence='|'.join(sorted(other_proofs)),
                                     missed_positive_ids=[])
            blockers[key]['missed_positive_ids'].append(r['positive'])
        table = [dict(r, missed_positive_ids='|'.join(r['missed_positive_ids'])) for r in blockers.values()]
        write_csv(OUT / 'BLOCKERS.csv', table)
        print('distinct within-fold unknown blockers', len(table),
              'with same-endpoint evidence in another eligible view',
              sum(bool(r['other_fold_training_view_evidence']) for r in table), flush=True)
        return
    prefix = 'VERIFIED_' if args.verified else ''
    write_csv(OUT / f'{prefix}POSITIVE_AUDIT.csv', rows)
    if candidates:
        write_csv(OUT / f'{prefix}HARD_PAIR_CANDIDATES.csv', candidates)
    write_json(OUT / f'{prefix}SUMMARY.json', dict(folds=audit, evidence_sha256=sha(EVIDENCE), cache_sha256=sha(CACHE),
                                         optimizer_steps=0, sat_cec_calls=0, labels_modified=False))


if __name__ == '__main__':
    main()
