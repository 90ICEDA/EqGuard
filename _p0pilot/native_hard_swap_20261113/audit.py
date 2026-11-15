"""Mine training-only native hard negatives and verify a one-for-one G0 swap."""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

OUT = Path(__file__).resolve().parent
P = OUT.parent
BASE = P / 'seed42_nc_ablation_20261109'
sys.path.insert(0, str(P / 'native_hard_fpr_20261113'))
from freeze import DICT, cKDTree, digest, inputs, key, norm, np, read, rows, view_ids
sys.path.insert(0, str(BASE))
from train_pair import FiveGroupLoader, Model, torch


def write(name, records):
    import csv
    with (OUT / name).open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def infer(loader):
    scores = {}
    with np.load(BASE / 'NC_scores.npz') as saved:
        for point in ('best', 'last'):
            path = BASE / f'NC_{point}.pt'
            sha = digest(path)
            model = Model().cuda()
            model.load_state_dict(torch.load(path, weights_only=True, map_location='cuda'))
            model.eval()
            for split in ('val', 'train'):
                g = loader.torch_graph('trans', split, 'cuda')
                with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
                    logits = model(g['x'], g['edge']).float()
                    m = (logits[:, 1] - logits[:, 0]).cpu().numpy()
                assert np.isfinite(m).all()
                if split == 'val':
                    ref = saved[f'val_{point}']
                    error = float(np.max(np.abs(m-ref)))
                    assert error <= .035, error
                    print('validation replay', point, error, flush=True)
                else:
                    scores[point] = m
                del g, logits
            assert digest(path) == sha and all(p.grad is None for p in model.parameters())
    return scores


def budget(loader, data):
    steps, common, original = [], [], []
    log = read(BASE / 'RESULTS_PAIR.json')['NC']['history']
    import hashlib
    history = {r['step']: r['idx_sha'] for r in log if 'idx_sha' in r}
    historical = {(r['domain'], int(r['update'])): r['index_sha']
                  for r in rows(P / 'control_five_seed42_20261107/integrated_indices_ledger.csv')
                  if r['arm'] == 'G0'}
    for step in range(200):
        a = loader.step('trans', 'G0', step)
        b = loader.step('orig', 'G0', step)
        for domain, s in [('trans', a), ('orig', b)]:
            sha = hashlib.sha256(s.indices.tobytes()).hexdigest()
            assert sha == historical[domain, step+1]
            if domain == 'trans' and step+1 in history:
                assert sha == history[step+1]
        steps.append(a.indices)
        common.append(a.common_negative)
        original.append(b.indices)
    steps, common, original = map(np.stack, (steps, common, original))
    pos_n = steps.shape[1]-8336
    assert pos_n == 829 and original.shape == (200, 136+8296)
    assert np.all(steps[:, :pos_n] == steps[0, :pos_n])
    assert (data['y'][steps[:, :pos_n]] == 1).all()
    assert (data['y'][steps[:, pos_n:]] == 0).all()
    exp = np.bincount(steps[:, pos_n:].ravel(), minlength=len(data['y']))
    return steps, common, original, pos_n, exp


def candidates(loader, data, scores, exp):
    views = [v for v in rows(DICT) if v['key']=='trans_train' and v['kind']=='trojan']
    panel = read(P / 'native_hard_fpr_20261113/FROZEN.json')
    cutoff = panel['cutoff']
    hp = P / 'control_overall_contract_20261105/trojan_host_trans_train.npz'
    with np.load(hp) as z:
        ids, vids = z['rows'][z['eligible']], z['view_id'][z['eligible']]
    assert len(np.unique(ids)) == len(ids)
    assert (data['physical'][ids] & data['trusted'][ids] & (data['y'][ids]==0)).all()
    stats = loader.normalization['mean'][25:], loader.normalization['std'][25:]
    templates = defaultdict(list)
    pos, native = {}, {}
    for v in views:
        vi = int(v['view_id'])
        native[vi] = ids[vids==vi]
        assert np.isin(native[vi], view_ids(v)).all()
        vv = view_ids(v)
        pp = vv[data['trusted'][vv] & data['physical'][vv] & (data['y'][vv]==1)]
        pos[vi] = pp
        kk = key(v, data, pp)
        for k in np.unique(kk):
            templates[v['recipe'], int(k)].append(pp[kk==k])
    trees = {k: cKDTree(norm(data, np.concatenate(v), stats)) for k,v in templates.items()}
    output, populations, donor_sets = [], [], {}
    for v in views:
        vi = int(v['view_id'])
        ii, pp = native[vi], pos[vi]
        kk = key(v, data, ii)
        dd = np.full(len(ii), np.inf)
        for k in np.unique(kk):
            t = trees.get((v['recipe'], int(k)))
            if t is not None:
                m = kk == k
                dd[m] = t.query(norm(data, ii[m], stats))[0]/np.sqrt(14)
        hard = dd <= cutoff.get(v['recipe'], -1)
        b, l = scores['best'], scores['last']
        b95 = np.sort(b[pp])[-int(np.ceil(.95*len(pp)))] if len(pp) else np.inf
        l95 = np.sort(l[pp])[-int(np.ceil(.95*len(pp)))] if len(pp) else np.inf
        bmax = b[pp].max() if len(pp) else np.inf
        lmax = l[pp].max() if len(pp) else np.inf
        stable = hard & (b[ii]>b95) & (l[ii]>l95)
        ahead = hard & (b[ii]>bmax) & (l[ii]>lmax)
        populations.append(dict(view=v['view'], source=v['source'], recipe=v['recipe'], positives=len(pp),
                                native=len(ii), hard=int(hard.sum()), stable=int(stable.sum()),
                                zero=int((stable & (exp[ii]==0)).sum()),
                                low=int((stable & (exp[ii]>0) & (exp[ii]<=5)).sum()),
                                ahead_best_both=int(ahead.sum()), ahead_best_zero=int((ahead & (exp[ii]==0)).sum())))
        donor_sets[vi] = (ii, kk, hard, b95, l95)
        for j in np.flatnonzero(stable):
            i = int(ii[j])
            output.append(dict(row=i, vi=vi, view=v['view'], source=v['source'], recipe=v['recipe'],
                               stratum=int(kk[j]), distance=float(dd[j]), exposure=int(exp[i]),
                               margin_advantage=float(min(b[i]-b95,l[i]-l95)), ahead_best_both=int(ahead[j])))
    return output, populations, donor_sets, stats


def propose(data, scores, pool, donor_sets, stats, steps, common, original, pos_n, exp):
    # Whole-exposure swaps from the 8192 common slots. Each selected source gets at most two pairs.
    common_exp = np.bincount(common.ravel(), minlength=len(exp))
    b, l = scores['best'], scores['last']
    groups = defaultdict(list)
    for row in pool:
        if row['exposure']==0:
            groups[row['source']].append(row)
    options = {s: sorted(r, key=lambda x: (-x['ahead_best_both'], -x['margin_advantage'], x['row']))
               for s,r in groups.items()}
    pairs, used, incoming = [], set(), set()
    for quota in (1,2):
        for source, rr in sorted(options.items()):
            if sum(p['source']==source for p in pairs) >= quota:
                continue
            for r in rr:
                i = r['row']
                if i in incoming:
                    continue
                ids, kk, hard, b95, l95 = donor_sets[r['vi']]
                ok = ((kk==r['stratum']) & ~hard & (exp[ids]==common_exp[ids]) & (exp[ids]>0)
                      & (exp[ids]<=24) & (b[ids]<b95) & (l[ids]<l95))
                eligible = np.array([d for d in ids[ok] if d not in used], dtype=np.int64)
                if not len(eligible):
                    continue
                d = np.sqrt(np.mean((norm(data, eligible, stats)-norm(data, [i], stats))**2, axis=1))
                j = np.lexsort((eligible, d))[0]
                donor = int(eligible[j])
                if d[j]>2:
                    continue
                pairs.append(dict(**r, donor=donor, replacement_exposure=int(exp[donor]), donor_rms=float(d[j])))
                used.add(donor)
                incoming.add(i)
                break
    assert pairs and not used & incoming
    new = steps.copy()
    replacement = {p['donor']: p['row'] for p in pairs}
    lookup = np.arange(len(exp), dtype=np.int64)
    for donor, recipient in replacement.items():
        lookup[donor] = recipient
    new[:, pos_n:pos_n+8192] = lookup[common]
    for a, z in zip(steps, new):
        assert len(np.unique(z)) == len(z)
        assert (data['trusted'][z] & data['physical'][z]).all()
        assert np.array_equal(data['y'][a], data['y'][z])
    ne = np.bincount(new[:,pos_n:].ravel(), minlength=len(exp))
    assert np.array_equal(np.sort(ne), np.sort(exp)) and ne.max() == exp.max()
    assert np.array_equal(new[:, :pos_n], steps[:, :pos_n])
    assert np.array_equal(new[:, pos_n+8192:], steps[:, pos_n+8192:])
    count = np.count_nonzero(new!=steps, axis=1)
    assert count.sum() == sum(r['replacement_exposure'] for r in pairs)
    np.savez_compressed(OUT / 'SCHEDULE.npz', g0_trans=steps, native_trans=new, orig_shared=original)
    return pairs, dict(pairs=len(pairs), exposures=int(count.sum()), nonzero_steps=int((count>0).sum()),
                       step_min=int(count.min()), step_max=int(count.max()))


def main():
    torch.set_num_threads(2)
    assert 'ginvenv_gpu' in sys.executable and torch.cuda.is_available()
    loader = FiveGroupLoader()
    data = inputs('train')
    steps, common, original, pos_n, exp = budget(loader, data)
    scores = infer(loader)
    np.savez_compressed(OUT / 'TRAIN_NC_SCORES.npz', **scores)
    mined, populations, donor_sets, stats = candidates(loader, data, scores, exp)
    write('CANDIDATES.csv', mined)
    write('BY_VIEW.csv', populations)
    sums = defaultdict(Counter)
    for r in populations:
        for k in [(r['source'],r['recipe']),('all',r['recipe']),('all','all')]:
            sums[k].update({s:r[s] for s in ('native','hard','stable','zero','low','ahead_best_both','ahead_best_zero')})
    write('BY_SOURCE_RECIPE.csv',[dict(source=s, recipe=r, **v) for (s,r),v in sorted(sums.items())])
    pairs, info = propose(data, scores, mined, donor_sets, stats, steps, common, original, pos_n, exp)
    write('SWAPS.csv', pairs)
    info.update(original_positive=136, original_negative=8296, trans_positive=829, trans_negative=8336,
                unchanged_lcone=True, schedule_sha=digest(OUT / 'SCHEDULE.npz'),
                score_sha=digest(OUT / 'TRAIN_NC_SCORES.npz'),
                checkpoints={s:digest(BASE / f'NC_{s}.pt') for s in ('best','last')})
    (OUT / 'AUDIT.json').write_text(json.dumps(info, indent=2), encoding='utf-8')
    print(sums['all','all'], info, flush=True)


if __name__ == '__main__':
    main()
