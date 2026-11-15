"""Replay existing certified blockers with frozen scores and physical gate unions."""
from collections import Counter, defaultdict

from replay import OUT, OLD, csv_rows, load, np, write

CAP = 512


def queue(order, members):
    used, reached = set(), set()
    for c in order:
        union = used | members[c]
        if len(union) > CAP:
            return reached, len(used), c
        used = union
        reached.add(c)
    return reached, len(used), ''


def union_size(ids, members):
    return len(set().union(*(members[c] for c in ids)))


def main():
    views, groups = load()
    blockers = defaultdict(set)
    for r in csv_rows(OUT/'UNTRUSTED_LINEAGE.csv'):
        if r['recipe'] in ('ys_aig','ys_nand') and r['first_blocker']=='1' and r['status']=='negative':
            blockers[r['view'],r['kind'],r['point']].add(r['cone'])
    assert len(blockers)==16 and len({(v,k,c) for (v,k,p),cs in blockers.items() for c in cs})==8
    refs = {(r['view'],r['kind'],r['point'],r['positive']):r for r in csv_rows(OUT/'TARGETS.csv')}
    cases, details, witnesses = [], [], []
    with np.load(OLD/'TRAIN_NC_SCORES.npz') as z:
        for (view,kind,point), blocked in sorted(blockers.items()):
            s = z[point]
            labels = {c:l for c,(l,_) in groups[view,kind].items()}
            members = {c:set(a) for c,(_,a) in groups[view,kind].items()}
            peaks, values = {}, {}
            for c,a in members.items():
                ids = np.array(sorted(a))
                values[c] = float(s[ids].max())
                peaks[c] = set(ids[s[ids]==values[c]])
            order = sorted(labels,key=lambda c:(-values[c],c))
            reached, used, first = queue(order,members)
            assert blocked=={first} and labels[first]=='negative'
            targets = [c for c in order if labels[c]=='positive']
            for c in targets:
                assert (c in reached)==(refs[view,kind,point,c]['hit']=='1')
            base = dict(view=view,source=views[view]['source'],recipe=views[view]['recipe'],
                        kind=kind,point=point,blocker=first)
            q_moves = {'single':{first},'all_proved_negative':{c for c in order if labels[c]=='negative'}}
            for policy, move in q_moves.items():
                reranked = [c for c in order if c not in move]+[c for c in order if c in move]
                hit,gates,stop = queue(reranked,members)
                cases.append(dict(**base,policy=policy,moved=len(move),baseline_gates=used,gates=gates,
                                  hit_before=len(set(targets)&reached),hit_after=len(set(targets)&hit),
                                  new_hits='|'.join(c for c in targets if c in hit and c not in reached),
                                  lost_hits='|'.join(c for c in targets if c in reached and c not in hit),
                                  next_blocker=stop,next_status=labels.get(stop,'')))
            for c in targets:
                if c in reached or len(members[c])>CAP:
                    continue
                prefix = order[:order.index(c)]
                neg = {x for x in prefix if labels[x]=='negative'}
                unknown = {x for x in prefix if labels[x]=='unknown'}
                shared = {x for x in prefix if peaks[x]&peaks[c]}
                same_blocker = {x for x in prefix if peaks[x]&peaks[first]}
                policies = {
                    'base':set(), 'single':{first},'all_neg':neg,
                    'blocker_shared_neg':same_blocker&neg,
                    'blocker_shared_nonpositive':same_blocker&(neg|unknown),
                    'unknown_only':unknown,'target_shared_unknown':shared&unknown,
                    'all_nonpositive':neg|unknown,
                }
                row = dict(**base,target=c,target_gates=len(members[c]),rank=order.index(c)+1,
                           negatives=len(neg),unknowns=len(unknown),shared_neg=len(shared&neg),
                           shared_unknown=len(shared&unknown),blocker_shares_target=int(bool(peaks[first]&peaks[c])),
                           blocker_shared_neg_count=len(same_blocker&neg),
                           blocker_shared_unknown_count=len(same_blocker&unknown),
                           blocker_shared_pos_count=sum(labels[x]=='positive' for x in same_blocker))
                for name, move in policies.items():
                    active = [x for x in prefix if x not in move]+[c]
                    row[name] = union_size(active,members)
                    hit,_,_ = queue(active,members)
                    assert (c in hit)==(row[name]<=CAP)
                assert row['base']==int(refs[view,kind,point,c]['through'])
                details.append(row)
                if row['all_neg'] <= CAP:
                    # Add back negatives in original order where they still fit.
                    kept = {x for x in prefix if x not in neg}
                    moved = set(neg)
                    for x in prefix:
                        if x in moved and union_size(kept | {x,c},members) <= CAP:
                            kept.add(x)
                            moved.remove(x)
                    retained = union_size(kept | {c},members)
                    assert all(union_size(kept|{x,c},members)>CAP for x in moved)
                    order_after = [x for x in order if x not in moved]+[x for x in order if x in moved]
                    reached_after,_,_ = queue(order_after,members)
                    assert c in reached_after
                    witnesses.append(dict(**base,target=c,moved=len(moved),through=retained,
                                          cones='|'.join(x for x in prefix if x in moved)))
    write('BLOCKER_POLICY.csv',cases)
    write('BLOCKER_TARGETS.csv',details)
    write('BLOCKER_GROUP_WITNESSES.csv',witnesses)
    for r in details:
        if r['point']=='best':
            print(*(r[k] for k in ('source','recipe','kind','blocker','target','base','single','all_neg',
                                   'blocker_shared_neg','unknown_only','all_nonpositive','shared_unknown')))
    print('cases',len(cases),'targets',len(details))


if __name__=='__main__':
    main()
