"""Trace all tied maxima of the already-audited training competitors."""
import sys
from collections import defaultdict
from types import SimpleNamespace

from replay import OUT, P, OLD, csv_rows, load, read, write, np

sys.path.insert(0, str(P/'native_hard_fpr_20261113'))
from freeze import cKDTree, digest, inputs, key, norm, view_ids
sys.path.insert(0, str(OLD))
from audit import candidates


def joined(values):
    return '|'.join(map(str, sorted(values)))


def main():
    views, groups = load()
    data = inputs('train')
    path = OLD/'TRAIN_NC_SCORES.npz'
    assert digest(path) == read(OLD/'AUDIT.json')['score_sha']
    with np.load(path) as z, np.load(OLD/'STEP_SCHEDULE.npz') as schedule:
        scores = {p:z[p] for p in ('best','last')}
        exp = np.bincount(schedule['g0_trans'][:,829:].ravel(), minlength=len(data['y']))
    with np.load(P/'control_boundary_v3_20261104/normalization.npz') as z:
        stats = {k:z[k] for k in ('mean','std')}
    mined, population, native_sets, _ = candidates(SimpleNamespace(normalization=stats),data,scores,exp)
    candidates_by_row = {r['row'] for r in mined}
    assert candidates_by_row == {int(r['row']) for r in csv_rows(OLD/'CANDIDATES.csv')}
    templates = defaultdict(list)
    limits = read(P/'native_hard_fpr_20261113/FROZEN.json')['cutoff']
    ns = stats['mean'][25:], stats['std'][25:]
    for v in views.values():
        a = view_ids(v)
        a = a[data['trusted'][a] & (data['y'][a]==1)]
        strata = key(v,data,a)
        for st in np.unique(strata):
            templates[v['recipe'],int(st)].append(a[strata==st])
    with np.load(P/'control_overall_contract_20261105/trojan_host_trans_train.npz') as z:
        reason = dict(zip(z['rows'].tolist(),z['reason'].tolist()))
        eligible = set(z['rows'][z['eligible']].tolist())
    names = (OUT.parents[1]/'generate_trans/folds/hosts_bt31/data/processed/node_names_trans.txt'
             ).read_text(encoding='utf-8').splitlines()
    by_case = defaultdict(list)
    for r in csv_rows(OUT/'COMPETITORS.csv'):
        if r['reached_or_blocker']=='1':
            by_case[r['view'],r['kind'],r['point'],r['competitor']].append(r)
    rows = []
    for (view,kind,point,cid), links in sorted(by_case.items()):
        v, group, margin = views[view],groups[view,kind],scores[point]
        label, members = group[cid]
        assert label == links[0]['status']
        pos = {c: set(a) for c,(l,a) in group.items() if l=='positive'}

        def winners(a):
            ids = np.asarray(sorted(a))
            return set(ids[margin[ids]==margin[ids].max()].tolist())

        peak = winners(members)
        pos_peak = {c:winners(a) for c,a in pos.items()}
        for link in links:
            assert bool(peak & pos_peak[link['positive']]) == (link['shares_positive_peak']=='1')
        native, kk, hard, b95, l95 = native_sets[int(v['view_id'])]
        hard_nodes = set(native[hard].tolist())
        for n in sorted(peak):
            assert data['physical'][n]
            trust, y = bool(data['trusted'][n]), int(data['y'][n])
            is_native = n in eligible
            st = int(key(v,data,[n])[0])
            sample = templates.get((v['recipe'],st))
            distance = float(cKDTree(norm(data,np.concatenate(sample),ns)).query(
                norm(data,[n],ns))[0][0]/np.sqrt(14)) if is_native and sample else None
            b, l = float(scores['best'][n]-b95),float(scores['last'][n]-l95)
            if not trust:
                why = 'untrusted'
            elif y != 0:
                why = 'trusted_nonnegative'
            elif not is_native:
                why = {11:'nonhost_or_mixed',12:'incomplete_view_trace'}[reason[n]]
            elif not sample:
                why = 'no_same_recipe_gate_PO_template'
            elif n not in hard_nodes:
                why = 'outside_structure_radius'
            elif not np.isfinite(b):
                why = 'no_view_positive'
            elif min(b,l)<=0:
                why = 'not_strictly_above_95_both'
            else:
                why = 'in_pool'
            assert (why=='in_pool') == (n in candidates_by_row)
            if distance is not None:
                assert (distance<=limits[v['recipe']]) == (n in hard_nodes)
            shared_target = {r['positive'] for r in links if n in pos_peak[r['positive']]}
            shared_positive = {c for c,a in pos_peak.items() if n in a}
            row = int(v['old_start']) + n-int(v['start'])
            rows.append(dict(source=v['source'],recipe=v['recipe'],view=view,kind=kind,point=point,
                             cone=cid,status=label,node=n,name=names[row].strip().lstrip('\\'),
                             trusted=int(trust),label=y,native=int(is_native),why=why,
                             stratum=st,structure_pass=int(n in hard_nodes),distance=distance,
                             radius=limits[v['recipe']],
                             best_gap=b,last_gap=l,exposure=int(exp[n]),tied_peaks=len(peak),
                             shared_target=joined(shared_target),shared_positive=joined(shared_positive),
                             targets=joined({r['positive'] for r in links}),
                             restored=joined({r['positive'] for r in links if r['restores']=='1'})))
    write('WINNERS.csv',rows)
    buckets = defaultdict(list)
    for r in rows:
        for source,recipe in [(r['source'],r['recipe']),('all',r['recipe']),('all','all')]:
            for status in (r['status'],'all'):
                buckets[source,recipe,status,r['why']].append(r)
    summary = []
    for (source,recipe,status,why),rr in sorted(buckets.items()):
        summary.append(dict(source=source,recipe=recipe,status=status,why=why,records=len(rr),
                            nodes=len({r['node'] for r in rr}),sources=len({r['source'] for r in rr}),
                            shared_target=len({r['node'] for r in rr if r['shared_target']}),
                            shared_positive=len({r['node'] for r in rr if r['shared_positive']}),
                            low_exposure=len({r['node'] for r in rr if r['exposure']<=5}),
                            both_above95=len({r['node'] for r in rr if min(r['best_gap'],r['last_gap'])>0})))
    write('WINNER_BY_SOURCE_RECIPE.csv',summary)
    print('records',len(rows),'nodes',len({r['node'] for r in rows}))
    for r in summary:
        if r['source']==r['recipe']=='all':
            print(r)


if __name__=='__main__':
    main()
