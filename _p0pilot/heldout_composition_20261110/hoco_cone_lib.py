"""Production cone functions for hoco: build store, match per source/label, guards."""
import csv
from pathlib import Path
import numpy as np

R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = R / '_p0pilot/heldout_composition_20261110'
PREP = R / '_p0pilot/seed42_supervised_prep_20261109'


def load_group(tag):
    g = np.load(OUT / f'hoco_{tag}.npz')
    return dict(o2n=g['old2new'], trusted=g['trusted'], physical=g['physical'], y=g['y'])


def build_store(tag, cache=None):
    g = load_group(tag)
    rows = cache if cache is not None else list(csv.DictReader((PREP / 'CONE_CACHE_V2.csv').open(encoding='utf-8-sig', newline='')))
    store = {}
    for r in rows:
        if r['split'] != 'train' or r['kind'] != 'D' or int(r['label']) < 0 or int(r['n_phys']) < 2:
            continue
        old = np.array([int(x) for x in r['phys_rows'].split('|') if x], np.int64)
        loc = g['o2n'][old]
        loc = loc[loc >= 0]
        loc = loc[g['trusted'][loc] & g['physical'][loc]]
        if len(loc) >= 2:
            store[(r['view'], r['cone_id'])] = (int(r['label']), loc, r['view'].split('__ys_')[0])
    return store


def match(sa, sb, srcs):
    def grp(st):
        d = {}
        for (v, cid), (l, m, s) in st.items():
            d.setdefault((s, l), []).append((v, cid, l, m))
        return d
    ga, gb = grp(sa), grp(sb)
    selA, selB, per = [], [], []
    for s in srcs:
        for l in (1, 0):
            a = sorted(ga.get((s, l), []), key=lambda x: (x[0], x[1]))
            b = sorted(gb.get((s, l), []), key=lambda x: (x[0], x[1]))
            n = min(len(a), len(b))
            per.append(dict(source=s, label=l, cand_A=len(a), cand_B=len(b), matched=n))
            selA += a[:n]; selB += b[:n]
    return selA, selB, per


def negative_guard(ids, g):
    ids = np.asarray(ids, np.int64)
    if bool((g['y'][ids] == 1).any()):
        raise ValueError('positive node in negative pool')
    if not bool(g['trusted'][ids].all() and g['physical'][ids].all()):
        raise ValueError('ineligible node (not trusted+physical)')
    return True


def duplicate_guard(ids):
    ids = np.asarray(ids)
    if len(np.unique(ids)) != len(ids):
        raise ValueError('duplicate indices')
    return True


def insufficient_guard(pool, n):
    if len(pool) < n:
        raise ValueError(f'insufficient pool: {len(pool)} < {n}')
    return True


def cross_recipe_check(store):
    byid = {}
    for (v, cid), (l, m, s) in store.items():
        byid.setdefault(cid, []).append((v, tuple(sorted(m.tolist()))))
    for cid, items in byid.items():
        views = {x[0] for x in items}
        if len(views) >= 2:
            memsets = {x[1] for x in items}
            return dict(cone_id=cid, views=sorted(views), distinct_members=len(memsets) >= 2,
                        members_differ=len(memsets) > 1, n=len(items))
    return dict(cone_id=None, views=[], distinct_members=False, members_differ=False, n=0)
