"""Replay the fixed native-negative and independent endpoint evaluation."""
import importlib.util
import sys
import os
from collections import defaultdict
from statistics import mean

from prepare import BASE, OUT, P, digest, inputs, np, read, rows
from freeze import DICT, view_ids


def write(name, records):
    import csv
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        w = csv.DictWriter(f,fieldnames=list(records[0]))
        w.writeheader()
        w.writerows(records)


def main():
    from sklearn.metrics import average_precision_score
    spec = importlib.util.spec_from_file_location('fixed_endpoint_panel',
        P/'lcone_endpoint_overlap_20261112/audit.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _, endpoints = module.load()
    sys.path.insert(0,str(P/'c2_endpoint_replay_20261112'))
    from replay import endpoint_metrics

    prior = P/'native_hard_fpr_20261113'
    assert digest(prior/'PANEL.npz') == read(prior/'FROZEN.json')['panel']
    views = [v for v in rows(DICT) if v['kind']=='trojan' and v['key'] in ('trans_val','trans_test')]
    data = {s:inputs(s) for s in ('val','test')}
    pos = {}
    for v in views:
        s = v['key'][6:]
        ids = view_ids(v)
        a = data[s]
        pos[s,v['view']] = ids[a['trusted'][ids] & a['physical'][ids] & (a['y'][ids]==1)]
    positives = {s:np.concatenate([v for (k,_),v in pos.items() if s==k]) for s in data}
    rr = rows(P/'control_five_seed42_20261107/frozen_role_assignments.csv')
    roles = {s:{k:np.array([int(r['row']) for r in rr if r['key']==f'trans_{s}' and r['role_class']==k],
                          dtype=np.int64) for k in ('trigger','payload','payload_select')} for s in data}
    by_view, by_endpoint, summary, endpoint_summary = [], [], [], []
    with np.load(prior/'PANEL.npz') as panel:
        for arm in ('G0','high','low'):
            path = BASE/'NC_scores.npz' if arm=='G0' else OUT/arm/'NC_s42_scores.npz'
            if not path.exists() and os.getenv('NATIVE_ALLOW_PARTIAL') == '1':
                continue
            with np.load(path) as z:
                for s,a in data.items():
                    assert np.array_equal(z[f'y_{s}'],a['y']) and np.array_equal(z[f'trust_{s}'],a['trusted'])
                for point in ('best','last'):
                    score = {s:z[f'{s}_{point}'] for s in data}
                    for policy,s,cal in [('val95','val','val'),('val95','test','val'),('test95','test','test')]:
                        p = score[cal][positives[cal]]
                        cut = np.sort(p)[-int(np.ceil(.95*len(p)))]
                        current = []
                        for v in views:
                            if v['key'] != f'trans_{s}':
                                continue
                            view = v['view']
                            hard = panel[view]
                            p = pos[s,view]
                            ids = view_ids(v)
                            ids = ids[data[s]['trusted'][ids]&data[s]['physical'][ids]]
                            y = data[s]['y'][ids]
                            r = dict(arm=arm,point=point,split=s,policy=policy,source=v['source'],
                                     view=view,recipe=v['recipe'],threshold=float(cut),pos=len(p),
                                     tp=int((score[s][p]>=cut).sum()),neg=len(hard),
                                     fp=int((score[s][hard]>=cut).sum()),
                                     ap=float(average_precision_score(y,score[s][ids])) if np.unique(y).size==2 else '')
                            for k,ids in roles[s].items():
                                q = np.intersect1d(ids,p)
                                r[k+'_n'],r[k+'_hits'] = len(q),int((score[s][q]>=cut).sum())
                            current.append(r)
                        by_view.extend(current)
                        for recipe in ('all',*sorted({r['recipe'] for r in current})):
                            items = [r for r in current if recipe=='all' or r['recipe']==recipe]
                            rates = defaultdict(list)
                            for r in items:
                                if r['neg']:
                                    rates[r['source']].append(r['fp']/r['neg'])
                            summary.append(dict(arm=arm,point=point,split=s,policy=policy,recipe=recipe,
                                                recall=sum(r['tp'] for r in items)/sum(r['pos'] for r in items),
                                                fpr=mean(map(mean,rates.values())) if rates else '',
                                                sources=len(rates),negative=sum(r['neg'] for r in items),
                                                **{k:sum(r[k] for r in items) for k in items[0]
                                                   if k.endswith(('_n','_hits'))}))
                    for (view,kind), group in endpoints.items():
                        by_endpoint.append(dict(arm=arm,point=point,view=view,kind=kind,
                                                recipe=view.rsplit('__ys_',1)[-1],
                                                **endpoint_metrics(group,score['test'])))
    groups = defaultdict(list)
    for r in by_endpoint:
        groups[r['arm'],r['point'],r['kind'],'all'].append(r)
        groups[r['arm'],r['point'],r['kind'],r['recipe']].append(r)
    for (arm,point,kind,recipe), items in groups.items():
        def source_mean(metric):
            per_source = defaultdict(list)
            for r in items:
                if r[metric] is not None:
                    per_source[r['view'].rsplit('__ys_',1)[0]].append(r[metric])
            return mean(map(mean,per_source.values())) if per_source else ''
        endpoint_summary.append(dict(arm=arm,point=point,kind=kind,recipe=recipe,
                                     **{k:source_mean(k)
                                        for k in ('recall_512','gates_512','allpos_fp','allpos_unknown','allpos_gates')}))
    previous = {(r['point'],r['policy'],r['recipe']):r for r in rows(prior/'SUMMARY.csv') if r['arm']=='NC'}
    for r in summary:
        if r['arm']=='G0' and r['split']=='test':
            ref = previous[r['point'],r['policy'],r['recipe']]
            assert abs(r['fpr']-float(ref['hard_fpr'])) < 1e-12 and r['recall']==float(ref['test_recall'])
    suffix = '_PARTIAL.csv' if len({r['arm'] for r in summary}) < 3 else '.csv'
    for name, records in [('NODE_BY_VIEW',by_view),('NODE_SUMMARY',summary),
                          ('ENDPOINT_BY_VIEW',by_endpoint),('ENDPOINT_SUMMARY',endpoint_summary)]:
        write(name+suffix,records)


if __name__=='__main__':
    main()
