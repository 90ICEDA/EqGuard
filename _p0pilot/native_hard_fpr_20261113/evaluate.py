"""Evaluate frozen margins on the preselected native hard-negative panel."""
from statistics import mean

from freeze import OUT, P, digest, inputs, np, read, rows, view_ids, write


def threshold(scores, target):
    return float(np.sort(scores)[-int(np.ceil(target * len(scores)))])


def main():
    frozen = read(OUT / 'FROZEN.json')
    assert digest(OUT / 'PANEL.npz') == frozen['panel']
    by_view = rows(OUT / 'COVERAGE.csv')
    data = {s: inputs(s) for s in ('val', 'test')}
    arrays = {s: {k: data[s][k] for k in ('y', 'trusted', 'physical')} for s in data}
    roles = rows(P / 'control_five_seed42_20261107/frozen_role_assignments.csv')
    role_ids = {k: np.array([int(r['row']) for r in roles if r['key'] == 'trans_test' and r['role_class']==k],
                            dtype=np.int64) for k in ('trigger','payload','payload_select')}
    from freeze import DICT
    layouts = {(v['key'][6:], v['view']): v for v in rows(DICT)
               if v['kind'] == 'trojan' and v['key'] in ('trans_val','trans_test')}
    pos = {}
    for (split, name), v in layouts.items():
        d = arrays[split]
        ids = view_ids(v)
        pos[split, name] = ids[d['trusted'][ids] & d['physical'][ids] & (d['y'][ids]==1)]
    test_pos = np.concatenate([ids for (s, _), ids in pos.items() if s=='test'])
    val_pos = np.concatenate([ids for (s, _), ids in pos.items() if s=='val'])
    out, totals = [], []
    with np.load(OUT / 'PANEL.npz') as panel:
        for arm in ('N','NC','N_GM','NC_GM'):
            path = (P / f'seed42_nc_ablation_20261109/{arm}_scores.npz' if '_' not in arm else
                    P / f"cone_control_alarm_20261113/{arm}/{arm.split('_')[0]}_s42_scores.npz")
            with np.load(path) as z:
                for s in data:
                    assert np.array_equal(z[f'y_{s}'], data[s]['y'])
                    assert np.array_equal(z[f'trust_{s}'], data[s]['trusted'])
                for point in ('best','last'):
                    test, val = z[f'test_{point}'], z[f'val_{point}']
                    for policy, sample, target in [('val95',val[val_pos],.95),('test95',test[test_pos],.95),
                                                   ('test80',test[test_pos],.80)]:
                        cut = threshold(sample, target)
                        subset = []
                        for v in by_view:
                            if v['split'] != 'test':
                                continue
                            view = v['view']
                            hard, native = panel[view], panel[view+'__native']
                            pp = pos['test', view]
                            r = dict(arm=arm, point=point, policy=policy, source=v['source'],
                                     recipe=v['recipe'], view=view, cut=cut,
                                     pos=len(pp), tp=int((test[pp]>=cut).sum()))
                            for name, ids in [('hard',hard),('native',native)]:
                                r[f'{name}_n'] = len(ids)
                                r[f'{name}_fp'] = int((test[ids]>=cut).sum())
                                r[f'{name}_ahead_best_pos'] = int((test[ids]>test[pp].max()).sum()) if len(pp) else ''
                            for role, members in role_ids.items():
                                ii = np.intersect1d(pp, members)
                                r[f'{role}_n'] = len(ii)
                                r[f'{role}_tp'] = int((test[ii]>=cut).sum())
                            subset.append(r)
                        out.extend(subset)
                        for recipe in ('all', *sorted({r['recipe'] for r in subset})):
                            rr = [r for r in subset if recipe=='all' or r['recipe']==recipe]
                            row = dict(arm=arm, point=point, policy=policy, recipe=recipe,
                                       views=len(rr), test_recall=sum(r['tp'] for r in rr)/sum(r['pos'] for r in rr))
                            for name in ('hard','native'):
                                groups = {}
                                ss = [r for r in rr if r[f'{name}_n']]
                                for r in ss:
                                    groups.setdefault(r['source'], []).append(r[f'{name}_fp']/r[f'{name}_n'])
                                row[f'{name}_fpr'] = mean(mean(v) for v in groups.values()) if groups else ''
                                row[f'{name}_n'] = sum(r[f'{name}_n'] for r in ss)
                                aa = [r[f'{name}_ahead_best_pos'] for r in ss if r[f'{name}_ahead_best_pos']!='']
                                row[f'{name}_ahead'] = mean(aa) if aa else ''
                            for role in role_ids:
                                row[f'{role}_hits'] = sum(r[f'{role}_tp'] for r in rr)
                                row[f'{role}_n'] = sum(r[f'{role}_n'] for r in rr)
                            totals.append(row)
    write('BY_VIEW.csv', out)
    write('SUMMARY.csv', totals)


if __name__ == '__main__':
    main()
