"""Prepare a broader, capped, within-view replacement schedule without training."""
from audit import OUT, P, candidates, digest, inputs, norm, np, read, rows, write
from collections import Counter, defaultdict
from types import SimpleNamespace
import json


def main():
    data = inputs('train')
    with np.load(OUT / 'SCHEDULE.npz') as old, np.load(OUT / 'TRAIN_NC_SCORES.npz') as saved:
        base, orig = old['g0_trans'], old['orig_shared']
        scores = {k:saved[k] for k in saved.files}
    pos_n = 829
    common = base[:,pos_n:pos_n+8192]
    exp = np.bincount(base[:,pos_n:].ravel(), minlength=len(data['y']))
    with np.load(P / 'control_boundary_v3_20261104/normalization.npz') as z:
        normalization = {k:z[k] for k in ('mean','std')}
    mined, _, donor_sets, stats = candidates(SimpleNamespace(normalization=normalization), data, scores, exp)
    assert {r['row'] for r in mined} == {int(r['row']) for r in rows(OUT / 'CANDIDATES.csv')}
    slots = {}
    for r in mined:
        if r['exposure'] > 5:
            continue
        i = r['row']
        ids, kk, hard, b95, l95 = donor_sets[r['vi']]
        use = ((kk==r['stratum']) & ~hard & (exp[ids]>0)
               & (scores['best'][ids]<b95) & (scores['last'][ids]<l95))
        ids = ids[use]
        if not len(ids):
            continue
        dd = np.sqrt(np.mean((norm(data, ids, stats)-norm(data, [i], stats))**2, axis=1))
        order = np.lexsort((ids,dd))
        slots[i] = [(int(ids[j]), float(dd[j])) for j in order if dd[j]<=2]
    by_group = defaultdict(list)
    for r in mined:
        if slots.get(r['row']):
            by_group[r['source'],r['recipe']].append(r)
    new = base.copy()
    use_node, use_src, use_group = Counter(), Counter(), Counter()
    ledger = []
    for step in range(200):
        where = {int(i):j+pos_n for j,i in enumerate(common[step])}
        present = set(base[step])
        src_step = Counter()
        for source, recipe in sorted(by_group, key=lambda k:(use_group[k],use_src[k[0]],k)):
            if sum(src_step.values()) >= 8:
                break
            if src_step[source] >= 2 or use_src[source] >= 160:
                continue
            group = source,recipe
            for r in sorted(by_group[group], key=lambda a: (
                    a['exposure']+use_node[a['row']], -a['ahead_best_both'], -a['margin_advantage'], a['row'])):
                node = r['row']
                if node in present or use_node[node] >= 8:
                    continue
                donor = next(((d,dist) for d,dist in slots[node] if d in where),None)
                if donor is None:
                    continue
                d, dist = donor
                new[step,where.pop(d)] = node
                present.add(node)
                use_node[node] += 1
                use_src[source] += 1
                use_group[group] += 1
                src_step[source] += 1
                ledger.append(dict(step=step+1, donor=d, donor_rms=dist, **r))
                break
    for a,z in zip(base,new):
        assert len(np.unique(z))==len(z)
        assert (data['trusted'][z] & data['physical'][z]).all()
        assert np.array_equal(data['y'][a],data['y'][z])
    assert np.array_equal(new[:,:pos_n],base[:,:pos_n])
    assert np.array_equal(new[:,pos_n+8192:],base[:,pos_n+8192:])
    new_exp = np.bincount(new[:,pos_n:].ravel(), minlength=len(exp))
    assert max(new_exp)<=128 and max(use_node.values())<=8 and max(use_src.values())<=160
    per_step = np.count_nonzero(new!=base,axis=1)
    assert per_step.max()<=8 and per_step.sum()==len(ledger)
    write('STEP_SWAPS.csv',ledger)
    np.savez_compressed(OUT/'STEP_SCHEDULE.npz',g0_trans=base,native_trans=new,orig_shared=orig)
    summary = dict(exposures=len(ledger), unique_nodes=len(use_node), sources=len(use_src),
                   recipes=dict(Counter(r['recipe'] for r in ledger)),
                   nonempty_steps=int((per_step>0).sum()), min_per_step=int(per_step.min()),
                   max_per_step=int(per_step.max()), max_added_per_node=max(use_node.values()),
                   max_source=max(use_src.values()), max_negative_exposure=int(max(new_exp)),
                   old_unique_negative=int((exp>0).sum()), new_unique_negative=int((new_exp>0).sum()),
                   schedule_sha=digest(OUT/'STEP_SCHEDULE.npz'))
    (OUT/'STEP_AUDIT.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(summary)


if __name__=='__main__':
    main()
