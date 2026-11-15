"""Evaluate seed42 with frozen native and endpoint panels."""
import importlib.util
import sys
from collections import defaultdict
from statistics import mean

from run_swap import ASSETS, BASE, OUT, P, digest, read, rows, t
from build import csv_out

import numpy as np
import torch
from sklearn.metrics import average_precision_score

sys.path.insert(0,str(P/'native_hard_fpr_20261113'))
from freeze import DICT, inputs, view_ids

sys.path.insert(0,str(P/'c2_endpoint_replay_20261112'))
from replay import endpoint_metrics


def average_source(records, key):
    grouped = defaultdict(list)
    for r in records:
        value = r[key]
        if value is not None:
            grouped[r['source']].append(value)
    return mean(map(mean,grouped.values())) if grouped else None


def rate(items, hits, total):
    n = sum(r[total] for r in items)
    return sum(r[hits] for r in items)/n if n else None


def validation_controls(model, cut):
    norm = np.load(ASSETS.parent/'control_boundary_v3_20261104/normalization.npz')
    by_view = defaultdict(list)
    for r in rows(ASSETS/'VAL_NEGATIVE_POOL.csv'):
        assert r['optimizer_eligible']=='0' and r['split']=='val'
        by_view[r['view']].append(r)
    total = 0
    for view, group in by_view.items():
        path = ASSETS/'graphs'/f'{view}.npz'
        assert digest(path) == group[0]['graph_sha']
        with np.load(path) as g:
            x = g['x39']
            x[:,25:] = np.clip((x[:,25:] - norm['mean'][25:])/norm['std'][25:],-10,10)
            ii = [int(r['row']) for r in group]
            assert [g['physical_names'][i] for i in ii]==[r['node'] for r in group]
            xt = torch.tensor(x,device='cuda')
            edge = torch.tensor(g['edge_index'],device='cuda')
        with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):
            logits = model(xt,edge).float()
        total += int(((logits[ii,1]-logits[ii,0]) >= cut).sum())
    return total


def main():
    spec = importlib.util.spec_from_file_location('live_control_endpoint_panel',
        P/'lcone_endpoint_overlap_20261112/audit.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _, endpoints = module.load()
    prior = P/'native_hard_fpr_20261113'
    assert digest(prior/'PANEL.npz') == read(prior/'FROZEN.json')['panel']
    views = [v for v in rows(DICT) if v['kind']=='trojan' and v['key'] in ('trans_val','trans_test')]
    lookup = {v['view']:v for v in views}
    data = {s:inputs(s) for s in ('val','test')}
    positives = {}
    for v in views:
        ids = view_ids(v)
        d = data[v['key'][6:]]
        positives[v['view']] = ids[d['trusted'][ids] & d['physical'][ids] & (d['y'][ids]==1)]
    role_names = ('trigger','payload','payload_select')
    rr = rows(P/'control_five_seed42_20261107/frozen_role_assignments.csv')
    roles = {k:np.array([int(r['row']) for r in rr if r['key']=='trans_test' and r['role_class']==k],
                       dtype=np.int64) for k in role_names}
    model = t.Model().cuda().eval()
    node_rows, endpoint_rows, summary, ep_summary = [], [], [], []
    with np.load(prior/'PANEL.npz') as panel:
        arms = ('historical',) if '--preflight' in sys.argv else ('historical','base','swap')
        for arm in arms:
            if arm=='historical':
                score_path = BASE/'NC_scores.npz'
            else:
                score_path = OUT/arm/'NC_s42_scores.npz'
            with np.load(score_path) as z:
                for s in data:
                    assert np.array_equal(z[f'y_{s}'],data[s]['y']) and np.array_equal(z[f'trust_{s}'],data[s]['trusted'])
                for point in ('best','last'):
                    score = {s:z[f'{s}_{point}'] for s in data}
                    for cal in ('val','test'):
                        p = np.concatenate([positives[v['view']] for v in views if v['key']==f'trans_{cal}'])
                        cut = float(np.sort(score[cal][p])[-int(np.ceil(.95*len(p)))])
                        current = []
                        for v in views:
                            if v['key']!='trans_test':
                                continue
                            view = v['view']
                            pos = positives[view]
                            ids = view_ids(v)
                            d = data['test']
                            ids = ids[d['trusted'][ids] & d['physical'][ids] & (d['y'][ids]>=0)]
                            pred = score['test']
                            r = dict(arm=arm,point=point,calibration=cal,view=view,source=v['source'],
                                recipe=v['recipe'],cut=cut,pos=len(pos),hits=int((pred[pos]>=cut).sum()),
                                ap=float(average_precision_score(d['y'][ids],pred[ids]))
                                if np.unique(d['y'][ids]).size==2 else None)
                            for subset, suffix in [('native','__native'),('hard','')]:
                                neg = panel[view+suffix]
                                assert (d['y'][neg]==0).all() and np.isin(neg,ids).all()
                                hits = int((pred[neg]>=cut).sum())
                                r[subset+'_n'],r[subset+'_fp'] = len(neg),hits
                                r[subset+'_fpr'] = hits/len(neg) if len(neg) else None
                            for role in role_names:
                                ii = np.intersect1d(pos,roles[role])
                                r[role+'_n'],r[role+'_hits'] = len(ii),int((pred[ii]>=cut).sum())
                            current.append(r)
                        node_rows.extend(current)
                        val_control_fp = None
                        if cal=='val':
                            ck = BASE/f'NC_{point}.pt' if arm=='historical' else OUT/arm/f'NC_s42_{point}.pt'
                            model.load_state_dict(torch.load(ck,map_location='cuda',weights_only=True),strict=True)
                            val_control_fp = validation_controls(model,cut)
                        for recipe in ('all',*sorted({r['recipe'] for r in current})):
                            items = [r for r in current if recipe=='all' or r['recipe']==recipe]
                            summary.append(dict(arm=arm,point=point,calibration=cal,recipe=recipe,cut=cut,
                                calibration_recall=float((score[cal][p]>=cut).mean()),
                                test_recall=rate(items,'hits','pos'), test_pos=sum(r['pos'] for r in items),
                                ap=average_source(items,'ap'),
                                **{k+'_fpr':average_source(items,k+'_fpr') for k in ('native','hard')},
                                **{k+'_fp':sum(r[k+'_fp'] for r in items) for k in ('native','hard')},
                                **{k+'_n':sum(r[k+'_n'] for r in items) for k in ('native','hard',*role_names)},
                                **{k+'_recall':rate(items,k+'_hits',k+'_n') for k in role_names},
                                val_control_fp=val_control_fp))
                    for (view,kind), group in endpoints.items():
                        v = lookup[view]
                        endpoint_rows.append(dict(arm=arm,point=point,view=view,source=v['source'],
                            recipe=v['recipe'],kind=kind,**endpoint_metrics(group,score['test'])))
    groups = defaultdict(list)
    for r in endpoint_rows:
        for recipe in ('all',r['recipe']):
            groups[r['arm'],r['point'],r['kind'],recipe].append(r)
    for (arm,point,kind,recipe), items in groups.items():
        ep_summary.append(dict(arm=arm,point=point,kind=kind,recipe=recipe,
            positive=sum(r['positive'] for r in items),
            **{k:average_source(items,k) for k in ('recall_512','gates_512','allpos_fp','allpos_unknown','allpos_gates')}))
    for tag, records in [('NODE_BY_VIEW',node_rows),('NODE_SUMMARY',summary),
                         ('ENDPOINT_BY_VIEW',endpoint_rows),('ENDPOINT_SUMMARY',ep_summary)]:
        prefix = 'PREFLIGHT_' if '--preflight' in sys.argv else ''
        csv_out(OUT/f'{prefix}{tag}.csv',records)
    for r in summary:
        if r['recipe']=='all':
            print({k:r[k] for k in ('arm','point','calibration','test_recall','native_fpr','hard_fpr',
                 'trigger_recall','payload_recall','payload_select_recall','val_control_fp')},flush=True)
    for r in ep_summary:
        if r['recipe']=='all':
            print(r,flush=True)


if __name__=='__main__':
    main()
