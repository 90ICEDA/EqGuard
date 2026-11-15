"""Offline decomposition of threshold, ranking, and the shared graph context."""
import importlib.util
import sys
from collections import Counter

import numpy as np

from build import csv_out
from run_swap import ASSETS, BASE, OUT, P, digest, read, rows, write_json

sys.path.insert(0, str(P/'native_hard_fpr_20261113'))
from freeze import DICT, inputs, view_ids

sys.path.insert(0, str(P/'c2_endpoint_replay_20261112'))
from replay import endpoint_metrics


def cutoff(scores):
    return float(np.sort(scores)[-int(np.ceil(.95*len(scores)))])


def inspect(group, score):
    values = {k:float(score[mem].max()) for k, (_,mem) in group.items()}
    queue = sorted(group, key=lambda k:(-values[k],k))
    seen, hit, first = set(), set(), None
    stats = {}
    for rank,k in enumerate(queue,1):
        label, mem = group[k]
        own = set(mem)
        new = own-seen
        if first is None and len(seen)+len(new)>512:
            first = (k,label,rank,len(seen),len(new),len(own))
        if first is None and label=='positive':
            hit.add(k)
        if label=='positive':
            winners = tuple(map(int, mem[score[mem]==values[k]]))
            block_winners = set()
            if first:
                block_members = group[first[0]][1]
                block_winners = set(block_members[score[block_members]==values[first[0]]])
            stats[k] = dict(hit=int(k in hit),rank=rank,score=values[k],prefix_gates=len(seen),
                            new_gates=len(new),own_gates=len(own),winners='|'.join(map(str,winners)),
                            first_block=first[0] if first else '',block_label=first[1] if first else '',
                            block_rank=first[2] if first else '',block_prefix=first[3] if first else '',
                            block_new=first[4] if first else '',block_size=first[5] if first else '',
                            shared_block_winner=int(bool(set(winners) & block_winners)))
        seen.update(own)
    if stats:
        assert len(hit)/len(stats)==endpoint_metrics(group,score)['recall_512']
    return stats


def main():
    prior = P/'native_hard_fpr_20261113'
    assert digest(prior/'PANEL.npz') == read(prior/'FROZEN.json')['panel']
    spec = importlib.util.spec_from_file_location('live_control_diag_endpoint',
        P/'lcone_endpoint_overlap_20261112/audit.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _,panel = module.load()
    views = {v['view']:v for v in rows(DICT) if v['kind']=='trojan' and v['key'] in ('trans_val','trans_test')}
    data = {s:inputs(s) for s in ('val','test')}
    pos = {}
    for v in views.values():
        ids = view_ids(v)
        d = data[v['key'][6:]]
        pos[v['view']] = ids[d['trusted'][ids] & d['physical'][ids] & (d['y'][ids]==1)]
    pp = {s:np.concatenate([pos[v['view']] for v in views.values() if v['key']==f'trans_{s}'])
          for s in data}
    paths = {'historical':BASE/'NC_scores.npz', **{a:OUT/a/'NC_s42_scores.npz' for a in ('base','swap')}}
    packs = {a:np.load(p) for a,p in paths.items()}
    node_rows, end_rows, cuts = [], [], []
    with np.load(prior/'PANEL.npz') as n:
        for point in ('best','last'):
            scores = {a:{s:z[f'{s}_{point}'] for s in data} for a,z in packs.items()}
            cut = {a:{s:cutoff(sc[s][pp[s]]) for s in data} for a,sc in scores.items()}
            for a,sc in scores.items():
                cuts.append(dict(point=point,arm=a,val_cut=cut[a]['val'],test_cut=cut[a]['test'],
                    test_hits_val=int((sc['test'][pp['test']]>=cut[a]['val']).sum()),
                    test_hits_test=int((sc['test'][pp['test']]>=cut[a]['test']).sum())))
            for left,right in (('historical','base'),('base','swap')):
                for view,v in views.items():
                    if v['key']!='trans_test':
                        continue
                    l,r = scores[left]['test'],scores[right]['test']
                    for name,ids in [('native',n[view+'__native']),('hard',n[view]),('positive',pos[view])]:
                        a,b,c,d = (int((sc[ids]>=th).sum()) for sc,th in
                            [(l,cut[left]['val']),(l,cut[right]['val']),
                             (r,cut[left]['val']),(r,cut[right]['val'])])
                        et_l = int((l[ids]>=cut[left]['test']).sum())
                        et_r = int((r[ids]>=cut[right]['test']).sum())
                        node_rows.append(dict(point=point,left=left,right=right,source=v['source'],
                            recipe=v['recipe'],view=view,subset=name,n=len(ids),left_val=a,right_val=d,
                            right_at_left_val=c,left_at_right_val=b,threshold_only_sym=(b-a+d-c)/2,
                            score_only_sym=(c-a+d-b)/2,left_test=et_l,right_test=et_r,
                            delta_val=d-a,delta_test=et_r-et_l))
                    dgroup = panel.get((view,'D'))
                    if not dgroup:
                        continue
                    aa,bb = inspect(dgroup,l),inspect(dgroup,r)
                    assert aa.keys()==bb.keys()
                    for cid in aa:
                        u,w = aa[cid],bb[cid]
                        end_rows.append(dict(point=point,left=left,right=right,view=view,
                            source=v['source'],recipe=v['recipe'],cone_id=cid,delta_hit=w['hit']-u['hit'],
                            **{f'left_{k}':val for k,val in u.items()},
                            **{f'right_{k}':val for k,val in w.items()}))
    for z in packs.values():
        z.close()
    csv_out(OUT/'DIAG_THRESHOLDS.csv',cuts)
    csv_out(OUT/'DIAG_BY_SOURCE_RECIPE.csv',node_rows)
    csv_out(OUT/'DIAG_POS_D.csv',end_rows)
    swaps = rows(OUT/'SWAPS.csv')
    exact = [r for r in swaps if r['same_gate']=='1']
    key = lambda r:(r['host'],r['view'],r['node'])
    matched = Counter(map(key,exact))
    all_nodes = set(map(key,swaps))
    write_json(OUT/'DIAG_MATCHING.json',dict(exact_slots=len(exact),
        by_host=dict(Counter(r['host'] for r in exact)),exact_nodes=len(matched),
        exact_nodes_by_host=dict(Counter(k[0] for k in matched)),
        zero_existing_match=[list(k) for k in sorted(all_nodes-matched.keys())],
        existing_exact_exposure_hist=dict(Counter(matched.values()))))


if __name__=='__main__':
    main()
