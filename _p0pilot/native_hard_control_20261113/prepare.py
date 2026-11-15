"""Check score robustness and match high/low recipients to identical slots."""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from types import SimpleNamespace

from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import maximum_bipartite_matching

OUT = Path(__file__).resolve().parent
P = OUT.parent
OLD = P / 'native_hard_swap_20261113'
sys.path.insert(0, str(OLD))
from audit import BASE, FiveGroupLoader, Model, candidates, digest, inputs, norm, np, read, rows, torch


def replay(loader):
    scores = {}
    graph = loader.torch_graph('trans', 'train', 'cuda')
    for point in ('best', 'last'):
        model = Model().cuda()
        model.load_state_dict(torch.load(BASE/f'NC_{point}.pt', weights_only=True, map_location='cuda'))
        model.eval()
        for precision in ('bf16','fp32'):
            with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16, enabled=precision=='bf16'):
                logits = model(graph['x'],graph['edge']).float()
                scores[point,precision] = (logits[:,1]-logits[:,0]).cpu().numpy()
        assert all(p.grad is None for p in model.parameters())
    return scores


def main():
    import csv
    torch.set_num_threads(2)
    loader = FiveGroupLoader()
    with np.load(OLD/'STEP_SCHEDULE.npz') as z, np.load(OLD/'TRAIN_NC_SCORES.npz') as s:
        base, orig, former = z['g0_trans'],z['orig_shared'],z['native_trans']
        saved = {p:s[p] for p in ('best','last')}
    data = inputs('train')
    exp = np.bincount(base[:,829:].ravel(), minlength=len(data['y']))
    _, _, sets, norm_stats = candidates(loader,data,saved,exp)
    from freeze import DICT, view_ids
    views = {int(v['view_id']):v for v in rows(DICT) if v['key']=='trans_train' and v['kind']=='trojan'}
    predictions = replay(loader)
    all_scores = {**predictions, **{(p,'saved'):s for p,s in saved.items()}}
    cutoff = {}
    for vi,v in views.items():
        ids = view_ids(v)
        pos = ids[data['trusted'][ids] & (data['y'][ids]==1)]
        if len(pos):
            cutoff[vi] = {k: np.sort(s[pos])[-int(np.ceil(.95*len(pos)))] for k,s in all_scores.items()}
    margins, low_ok = {}, {}
    by_view = defaultdict(list)
    occ = defaultdict(list)
    ledger = rows(OLD/'STEP_SWAPS.csv')
    for r in ledger:
        i, vi, step, donor = [int(r[k]) for k in ('row','vi','step','donor')]
        j, = np.flatnonzero(base[step-1]==donor)
        assert former[step-1,j]==i and 829<=j<829+8192
        occ[i].append((step-1,j))
        if len(occ[i])==1:
            by_view[vi].append((i,int(r['stratum'])))
            margins[i] = [float(s[i]-cutoff[vi][k]) for k,s in all_scores.items()]
    high, low, matched, robust = base.copy(),base.copy(),[],set()
    for vi, rr in sorted(by_view.items()):
        ids, stratum, hard, *_ = sets[vi]
        stable_low = np.logical_and.reduce([s[ids] < cutoff[vi][k]-.05 for k,s in all_scores.items()])
        low_ids = ids[stable_low & (exp[ids]<=5)]
        low_strata = stratum[stable_low & (exp[ids]<=5)]
        choices, pair_ids, eligible = [], [], []
        for i, st in rr:
            if min(margins[i]) <= .05:
                continue
            robust.add(i)
            visits = [t for t,_ in occ[i]]
            pool = np.flatnonzero((low_strata==st) & (exp[low_ids]==exp[i]))
            pool = pool[~np.isin(low_ids[pool],base[visits])]
            dd = np.sqrt(np.mean((norm(data,low_ids[pool],norm_stats)-norm(data,[i],norm_stats))**2,axis=1))
            ordered = np.lexsort((low_ids[pool],dd))
            jj = [int(pool[j]) for j in ordered if dd[j]<=2]
            pair_ids.extend(jj)
            choices.extend([len(eligible)]*len(jj))
            eligible.append(i)
        if not choices:
            continue
        graph = csr_matrix((np.ones(len(choices)),(choices,pair_ids)),shape=(len(eligible),len(low_ids)))
        assignment = maximum_bipartite_matching(graph,perm_type='column')
        for i,j in zip(eligible,assignment):
            if j<0:
                continue
            ctl = int(low_ids[j])
            assert exp[i]==exp[ctl]
            for t,k in occ[i]:
                high[t,k],low[t,k] = i,ctl
            matched.append(dict(high=i,low=ctl,view=views[vi]['view'],source=views[vi]['source'],
                                recipe=views[vi]['recipe'],old_exposure=int(exp[i]),added=len(occ[i]),
                                min_high_margin=min(margins[i]),low_max_margin=max(
                                    float(s[ctl]-cutoff[vi][k]) for k,s in all_scores.items())))
    assert len({r['low'] for r in matched})==len(matched)
    assert np.array_equal(high!=base,low!=base)
    for mat in (high,low):
        assert np.array_equal(mat[:,:829],base[:,:829])
        assert np.array_equal(mat[:,9021:],base[:,9021:])
        for a,b in zip(mat,base):
            assert len(np.unique(a))==len(a)
            assert (data['trusted'][a]&data['physical'][a]).all()
            assert np.array_equal(data['y'][a],data['y'][b])
    hist = [np.bincount(m[:,829:].ravel(),minlength=len(exp)) for m in (high,low)]
    assert np.array_equal(np.sort(hist[0]),np.sort(hist[1])) and max(map(np.max,hist))<=128
    with (OUT/'MATCHED.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(matched[0])); w.writeheader(); w.writerows(matched)
    np.savez_compressed(OUT/'SCHEDULE.npz',g0=base,high=high,low=low,orig=orig)
    changes = np.count_nonzero(high!=base,axis=1)
    summary=dict(original_nodes=len(occ),robust_nodes=len(robust),
                 robust_slots=sum(len(occ[i]) for i in robust),matched_nodes=len(matched),
                 sign_flip_nodes=sum(min(m)<=0 for m in margins.values()),
                 matched_slots=int(changes.sum()),active_steps=int((changes>0).sum()),
                 source_count=len({r['source'] for r in matched}),
                 by_recipe=dict(Counter(r['recipe'] for r in matched)),
                 margin_guard=.05, unique_negative=int((hist[0]>0).sum()),
                 schedule_sha=digest(OUT/'SCHEDULE.npz'))
    (OUT/'GATE.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(summary,flush=True)


if __name__=='__main__':
    main()
