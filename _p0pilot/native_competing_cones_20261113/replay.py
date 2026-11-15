"""Join training-only native negative scores to certified endpoint queues."""
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent
P = OUT.parent
OLD = P / 'native_hard_swap_20261113'
GATE = P / 'lcone_rank_train_gate_20261112'
HEAD = P / 'lcone_head_prep_20261112'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def csv_rows(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        yield from csv.DictReader(f)


def write(name, rows):
    with (OUT / name).open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def load():
    views = {r['view']: r for r in csv_rows(P/'control_loader_po_20261105/view_dictionary.csv')
             if r['key'] == 'trans_train' and r['kind'] == 'trojan'}
    proof = {}
    for file in (HEAD/'all_eligible/TRAIN_ENDPOINTS.json', HEAD/'TRAIN_ENDPOINTS.json'):
        for r in read(file):
            if r['view'] not in views:
                continue
            if r['label'] == 1:
                assert r['witness'] and r['lineage']
            else:
                assert r['label'] == 0 and r['evidence'] in ('exhaustive_free_PI_Q','identical_boolean_expression')
            key = r['view'],r['cone_id']
            val = ('positive' if r['label'] else 'negative', tuple(r['member_rows']))
            assert key not in proof or proof[key] == val
            proof[key] = val
    for r in read(GATE/'BLOCKER_PROOFS_VERIFIED.json')['records']:
        if r['status'] == 'negative' and r['view'] in views:
            assert r['independent_exhaustive_assignments'] == 1 << r['inputs']
            key = r['view'],r['cone_id']
            val = ('negative',tuple(r['member_rows']))
            assert key not in proof or proof[key] == val
            proof[key] = val
    d92 = read(GATE/'D92_PROOF_REPLAY.json')
    assert d92['status'] == 'functional_negative_free_PI_Q'
    assert any(r['status']=='replayed' for r in d92['replays'])
    d92key = d92['view'],d92['endpoint']
    prior = GATE/'CROSS_HOST_PAIR_AUDIT.json'
    assert hashlib.sha256(prior.read_bytes()).hexdigest() == d92['prior_sha256']
    previous, = read(prior)['proofs']
    assert (previous['view'], previous['cone_id']) == d92key
    proof[d92key] = ('negative',tuple(previous['member_rows']))
    positive_views = {v for (v,c),(label,_) in proof.items() if label=='positive'}
    groups = defaultdict(dict)
    for r in csv_rows(P/'seed42_supervised_prep_20261109/CONE_CACHE_V2.csv'):
        v,c = r['view'],r['cone_id']
        if r['split'] != 'train' or v not in positive_views or not int(r['n_phys']):
            continue
        a = tuple(map(int,r['phys_rows'].split('|')))
        assert len(a)==int(r['n_phys']) and len(set(a))==len(a)
        assert min(a)>=int(views[v]['start']) and max(a)<int(views[v]['physical_stop'])
        ev = proof.get((v,c))
        if ev:
            assert ev[1] == a
        label = ev[0] if ev else 'unknown'
        assert c not in groups[v,r['kind']]
        groups[v,r['kind']][c] = (label,a)
    assert all(c in groups[v,c.split(':',1)[0]] for (v,c),(lab,_) in proof.items() if lab=='positive')
    return views, groups


def replay(v,kind,group,score,point,meta,hard):
    if not any(l=='positive' for l,_ in group.values()):
        return [],[]
    members = {c:set(a) for c,(_,a) in group.items()}
    winners = {}
    for c,(_,a) in group.items():
        ids = np.asarray(a)
        winners[c]=set(ids[score[ids]==score[ids].max()].tolist())
    value = {c:float(score[min(w)]) for c,w in winners.items()}
    order = sorted(group,key=lambda c:(-value[c],c))
    inv = Counter(n for w in winners.values() for n in w)
    seen, trace, pairs, targets = set(), [], [], []
    next_total, rank_of, first_blocker = {}, {}, None
    for rank,c in enumerate(order,1):
        new = members[c]-seen
        seen.update(new)
        label = group[c][0]
        if label=='positive':
            feasible_miss = len(seen)>512>=len(members[c])
            targets.append(dict(view=v,source=meta['source'],recipe=meta['recipe'],kind=kind,point=point,
                                positive=c,rank=rank,gates=len(members[c]),through=len(seen),
                                hit=int(len(seen)<=512),feasible_miss=int(feasible_miss)))
            if feasible_miss:
                # A leave-one-out prefix union measures exclusive cost after deduplication.
                prefix_count = Counter(n for d,_ in trace for n in members[d])
                prefix_count.update(members[c])
                for d, incremental in trace:
                    if group[d][0]=='positive' or not incremental:
                        continue
                    exclusive = sum(prefix_count[n]==1 for n in members[d])
                    peak_hard = winners[d]&hard
                    inside = members[d]&hard
                    pairs.append(dict(view=v,source=meta['source'],recipe=meta['recipe'],kind=kind,point=point,
                                      positive=c,competitor=d,status=group[d][0],incremental=incremental,
                                      exclusive=exclusive,restores=int(len(seen)-exclusive<=512),
                                      before_stop=int(next_total[d]<=512),
                                      reached_or_blocker=int(first_blocker is None or rank_of[d]<=first_blocker),
                                      strict=int(value[d]>value[c]),shares_positive_peak=int(bool(winners[d]&winners[c])),
                                      shares_any_peak=int(any(inv[n]>1 for n in winners[d])),
                                      member_hard='|'.join(map(str,sorted(inside))),
                                      peak_hard='|'.join(map(str,sorted(peak_hard)))))
        trace.append((c,len(new)))
        next_total[c]=len(seen)
        rank_of[c]=rank
        if first_blocker is None and len(seen)>512:
            first_blocker=rank
    return targets,pairs


def main():
    views, groups = load()
    hard = defaultdict(set)
    for r in csv_rows(OLD/'CANDIDATES.csv'):
        hard[r['view']].add(int(r['row']))
    t, p = [], []
    with np.load(OLD/'TRAIN_NC_SCORES.npz') as z:
        for point in ('best','last'):
            s = z[point]
            for (v,k),g in groups.items():
                a,b = replay(v,k,g,s,point,views[v],hard[v])
                t.extend(a)
                p.extend(b)
    write('TARGETS.csv',t)
    write('COMPETITORS.csv',p)
    source_rows = []
    grouped = defaultdict(list)
    for r in p:
        if r['reached_or_blocker']:
            grouped[r['source'],r['recipe'],r['kind'],r['status']].append(r)
    for (source,recipe,kind,status), rr in sorted(grouped.items()):
        source_rows.append(dict(source=source,recipe=recipe,kind=kind,status=status,
                                pair_records=len(rr), distinct_view_cones=len({(r['view'],r['competitor']) for r in rr}),
                                member_nodes=len({n for r in rr for n in r['member_hard'].split('|') if n}),
                                highest_nodes=len({n for r in rr for n in r['peak_hard'].split('|') if n}),
                                shared_positive_cones=len({(r['view'],r['competitor']) for r in rr if r['shares_positive_peak']}),
                                restored_targets=len({(r['view'],r['positive']) for r in rr if r['restores']})))
    write('BY_SOURCE_RECIPE.csv',source_rows)
    summary=[]
    for point in ('best','last','both'):
        for kind in ('D','PO','all'):
            for recipe in sorted({r['recipe'] for r in t}|{'all'}):
                tt=[r for r in t if point in ('both',r['point']) and kind in ('all',r['kind'])
                    and recipe in ('all',r['recipe'])]
                if not tt:
                    continue
                pp=[r for r in p if point in ('both',r['point']) and kind in ('all',r['kind'])
                    and recipe in ('all',r['recipe'])]
                out=dict(point=point,kind=kind,recipe=recipe,targets=len(tt),
                         sources=len({r['source'] for r in tt}),miss=sum(not r['hit'] for r in tt),
                         feasible_miss=sum(r['feasible_miss'] for r in tt))
                for status in ('negative','unknown'):
                    rr=[r for r in pp if r['status']==status]
                    for tag, selected in [('actual',[r for r in rr if r['reached_or_blocker']]),
                                          ('restore',[r for r in rr if r['restores']]),
                                          ('peak',[r for r in rr if r['reached_or_blocker'] and r['peak_hard']]),
                                          ('member',[r for r in rr if r['reached_or_blocker'] and r['member_hard']]),
                                          ('shared',[r for r in rr if r['reached_or_blocker'] and r['shares_positive_peak']]),
                                          ('rank_ready',[r for r in rr if r['restores'] and r['strict'] and not r['shares_positive_peak']])]:
                        out[status+'_'+tag]=len(selected)
                        out[status+'_'+tag+'_sources']=len({r['source'] for r in selected})
                summary.append(out)
    write('SUMMARY.csv',summary)
    print('targets',len(t),'pairs',len(p))
    for r in summary:
        if r['recipe']=='all':
            print(r)


if __name__=='__main__':
    main()
