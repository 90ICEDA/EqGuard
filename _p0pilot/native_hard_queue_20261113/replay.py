"""Replay the frozen endpoint queues and retain per-positive prefix evidence."""
import csv
import importlib.util
from collections import Counter
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent
P = OUT.parent
BASE = P / 'native_hard_control_20261113'


def read(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def write(name, rows):
    with (OUT / name).open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def trace(group, score):
    members = {cid: set(a.tolist()) for cid, (_, a) in group.items()}
    winners = {cid: set(a[score[a] == score[a].max()].tolist()) for cid, (_, a) in group.items()}
    values = {cid: float(score[min(w)]) for cid, w in winners.items()}
    order = sorted(group, key=lambda cid: (-values[cid], cid))
    gates, prefix, blocked, checked, positive = set(), [], None, Counter(), []
    used = 0
    for rank, cid in enumerate(order, 1):
        fresh = members[cid] - gates
        if blocked is None and len(gates) + len(fresh) > 512:
            blocked = (rank, cid, len(fresh), len(gates) + len(fresh))
        hit = blocked is None
        status = group[cid][0]
        if hit:
            checked[status] += 1
            used = len(gates) + len(fresh)
        if status == 'positive':
            tied = [c for c in prefix if values[c] == values[cid]]
            shared = [c for c in prefix if winners[cid] & winners[c]]
            counts = Counter(group[c][0] for c in prefix)
            positive.append(dict(endpoint=cid, hit=int(hit), rank=rank, score=values[cid],
                                 gates=len(members[cid]), prefix_gates=len(gates), added_gates=len(fresh),
                                 through_gates=len(gates)+len(fresh),
                                 prev_negative=counts['negative'], prev_unknown=counts['unknown'],
                                 prev_tied=len(tied), prev_shared_max=len(shared),
                                 shared_ids='|'.join(shared), max_nodes='|'.join(map(str,sorted(winners[cid]))),
                                 prefix_ids='|'.join(prefix),
                                 blocker_rank=blocked[0] if blocked else '',
                                 blocker=blocked[1] if blocked else '',
                                 blocker_status=group[blocked[1]][0] if blocked else '',
                                 blocker_added=blocked[2] if blocked else '',
                                 blocker_total=blocked[3] if blocked else '',
                                 blocker_shares_max=int(bool(winners[blocked[1]] & winners[cid])) if blocked else ''))
        gates.update(fresh)
        prefix.append(cid)
    return positive, used, checked, blocked


def main():
    spec = importlib.util.spec_from_file_location('fixed_panel', P / 'lcone_endpoint_overlap_20261112/audit.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _, panel = mod.load()
    refs = {(r['arm'],r['point'],r['view'],r['kind']):r for r in read(BASE/'ENDPOINT_BY_VIEW.csv')}
    detail, checks = [], []
    for arm in ('G0','high','low'):
        path = (P / 'seed42_nc_ablation_20261109/NC_scores.npz' if arm=='G0'
                else BASE / arm / 'NC_s42_scores.npz')
        with np.load(path) as saved:
            for point in ('best','last'):
                score = saved[f'test_{point}']
                assert np.isfinite(score).all()
                for (view,kind), group in panel.items():
                    source,recipe = view.rsplit('__ys_',1)
                    positive, used, checked, blocked = trace(group,score)
                    ref = refs[arm,point,view,kind]
                    assert len(positive)==int(ref['positive']) and used==int(ref['gates_512'])
                    assert checked['positive']==sum(r['hit'] for r in positive)
                    assert (checked['positive']/len(positive)==float(ref['recall_512'])
                            if positive else ref['recall_512']=='')
                    k = dict(arm=arm,point=point,source=source,recipe=recipe,view=view,kind=kind)
                    detail.extend(dict(**k,**r) for r in positive)
                    checks.append(dict(**k,positive=len(positive),found=checked['positive'],
                                       checked_negative=checked['negative'],checked_unknown=checked['unknown'],
                                       used=used,blocker=blocked[1] if blocked else ''))
    assert len(checks)==len(refs)
    write('POSITIVE_TRACE.csv',detail)
    write('BY_SOURCE_RECIPE.csv',checks)
    lookup = {(r['arm'],r['point'],r['view'],r['kind'],r['endpoint']):r for r in detail}
    changes = []
    for r in detail:
        if r['arm']!='low':
            continue
        key = tuple(r[k] for k in ('point','view','kind','endpoint'))
        g,h = (lookup[a,*key] for a in ('G0','high'))
        d = dict(point=r['point'],source=r['source'],recipe=r['recipe'],kind=r['kind'],endpoint=r['endpoint'])
        for arm, rr in [('g0',g),('high',h),('low',r)]:
            d.update({f'{arm}_{k}':rr[k] for k in ('hit','rank','gates','prefix_gates','added_gates','through_gates',
                                                  'prev_tied','prev_shared_max','blocker','blocker_total',
                                                  'blocker_status','blocker_shares_max','max_nodes')})
        changes.append(d)
    write('PAIRED_POSITIVES.csv',changes)
    displaced = []
    for r in changes:
        if r['g0_hit']!=r['low_hit']:
            print(r)
            view = r['source'] + '__ys_' + r['recipe']
            key = r['point'], view, r['kind'], r['endpoint']
            g, l = (lookup[a,*key] for a in ('G0','low'))
            removed = set(g['prefix_ids'].split('|')) - set(l['prefix_ids'].split('|'))
            for cid in g['prefix_ids'].split('|'):
                if cid in removed and cid:
                    status, members = panel[view,r['kind']][cid]
                    displaced.append(dict(view=view,kind=r['kind'],positive=r['endpoint'],removed=cid,
                                          status=status,gates=len(members)))
    write('DISPLACED_PREFIX.csv',displaced)


if __name__=='__main__':
    main()
