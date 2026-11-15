"""Compare certified-negative PO queue interference on training and validation hosts."""
from collections import defaultdict
from pathlib import Path

from replay import OUT, P, OLD, csv_rows, load, np, read, write
from replay_blockers import CAP, queue, union_size


def validation_groups(views):
    path = P / 'lcone_endpoint_frozen_20261112/EVIDENCE.json'
    evidence = {(r['view'], r['cone_id']): r['status'] for r in read(path)['endpoints']
                if r['split']=='val' and r['kind']=='PO'}
    groups = defaultdict(dict)
    for r in csv_rows(P/'seed42_supervised_prep_20261109/CONE_CACHE_V2.csv'):
        key = r['view'],r['cone_id']
        if r['split']!='val' or key not in evidence:
            continue
        ids = tuple(map(int,r['phys_rows'].split('|')))
        v = views[r['view']]
        assert len(ids)==int(r['n_phys']) and min(ids)>=int(v['start']) and max(ids)<int(v['physical_stop'])
        groups[r['view']][r['cone_id']] = evidence.pop(key),ids
    assert not evidence
    return groups


def measure(group, score, meta):
    members = {c:set(a) for c,(_,a) in group.items()}
    labels = {c:l for c,(l,_) in group.items()}
    peaks = {}
    for c,(_,a) in group.items():
        ids=np.asarray(a)
        peaks[c]=set(ids[score[ids]==score[ids].max()])
    values = {c:score[min(w)] for c,w in peaks.items()}
    order = sorted(group,key=lambda c:(-values[c],c))
    hit, used, stop = queue(order,members)
    negatives = {c for c in order if labels[c]=='negative'}
    def back(remove):
        return queue([c for c in order if c not in remove]+[c for c in order if c in remove],members)
    all_hit,_,_ = back(negatives)
    single_hit,_,_ = back({stop}) if stop in negatives else (hit,used,stop)
    targets=[]
    for rank,c in enumerate(order):
        if labels[c]!='positive':
            continue
        prefix = order[:rank]
        neg = negatives.intersection(prefix)
        unknown = {x for x in prefix if labels[x]=='unknown'}
        before = union_size(prefix+[c],members)
        after = union_size([x for x in prefix if x not in neg]+[c],members)
        assert (c in all_hit)==(after<=CAP) and (c in hit)==(before<=CAP)
        # Check all individual predecessor moves, not only the first blocker.
        single_rescue = [x for x in sorted(neg) if union_size([y for y in prefix if y!=x]+[c],members)<=CAP] if c not in hit else []
        targets.append(dict(**meta,endpoint=c,rank=rank+1,size=len(members[c]),before=before,after=after,
                            hit=int(c in hit),hit_group=int(c in all_hit),hit_first=int(c in single_hit),
                            single_rescues='|'.join(single_rescue),neg_before=len(neg),unknown_before=len(unknown),
                            shared_neg=sum(bool(peaks[c]&peaks[x]) for x in neg),
                            shared_unknown=sum(bool(peaks[c]&peaks[x]) for x in unknown),
                            first_blocker=stop,first_status=labels.get(stop,'')))
    inventory=dict(**meta,positive=len(targets),negative=len(negatives),
                   unknown=sum(l=='unknown' for l in labels.values()))
    return targets,inventory


def main():
    train_views, tr=load()
    tr={v:g for (v,k),g in tr.items() if k=='PO'}
    val_views={r['view']:r for r in csv_rows(P/'control_loader_po_20261105/view_dictionary.csv')
               if r['key']=='trans_val' and r['kind']=='trojan'}
    va=validation_groups(val_views)
    results, inventory=[],[]
    def run(split,seed,path,groups,views):
        with np.load(path) as z:
            for point in ('best','last'):
                score=z[point if split=='train' else f'val_{point}']
                assert np.isfinite(score).all()
                for view,g in sorted(groups.items()):
                    v=views[view]
                    meta=dict(split=split,seed=seed,point=point,view=view,host=v['host'],
                              source=v['source'],recipe=v['recipe'])
                    rr,iv=measure(g,score,meta)
                    results.extend(rr)
                    inventory.append(iv)
    run('train',42,OLD/'TRAIN_NC_SCORES.npz',tr,train_views)
    for seed in (42,1,2):
        name='NC_scores.npz' if seed==42 else f'NC_s{seed}_scores.npz'
        run('val',seed,P/'seed42_nc_ablation_20261109'/name,va,val_views)
    write('PO_HOST_TARGETS.csv',results)
    write('PO_HOST_INVENTORY.csv',inventory)
    summary=[]
    buckets=defaultdict(list)
    for r in results:
        for source,recipe in ((r['source'],r['recipe']),('all',r['recipe']),('all','all')):
            buckets[r['split'],r['seed'],r['point'],r['host'],source,recipe].append(r)
    for (split,seed,point,host,source,recipe),rr in sorted(buckets.items()):
        missed=[r for r in rr if not r['hit'] and r['size']<=CAP]
        restored=[r for r in missed if r['hit_group']]
        summary.append(dict(split=split,seed=seed,point=point,host=host,source=source,recipe=recipe,
                            positive=len(rr),views=len({r['view'] for r in rr}),
                            independent_sources=len({r['source'] for r in rr}),
                            missed=sum(not r['hit'] for r in rr),feasible_missed=len(missed),
                            restored=len(restored),group_only=sum(not r['single_rescues'] for r in restored),
                            restored_sources=len({r['source'] for r in restored}),
                            restored_source_PO=len({(r['source'],r['endpoint']) for r in restored})))
    write('PO_HOST_SUMMARY.csv',summary)
    for r in summary:
        if r['source']==r['recipe']=='all':
            print(r)
    for r in results:
        if not r['hit'] and r['hit_group'] and (r['host']!='s35932t200' or r['split']=='val'):
            print('RESCUE',r)


if __name__=='__main__':
    main()
