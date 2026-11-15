"""Independently replay the saved supervision schedule against the loader."""
from collections import Counter

import numpy as np

from run_swap import ASSETS, BASE, OUT, P, digest, read, rows, t, write_json


def main():
    pre = read(OUT/'PREFLIGHT.json')
    assert digest(OUT/'SCHEDULE.npz') == pre['schedule_sha']
    loader = t.FiveGroupLoader(verify_hashes=False)
    bindings = rows(ASSETS/'TRAIN_NEGATIVE_POOL.csv')
    n = len(loader.arrays('orig')['y'])
    current = n
    pool, host_by_view = {}, {}
    for view in sorted({r['view'] for r in bindings}):
        with np.load(ASSETS/'graphs'/f'{view}.npz') as g:
            for r in bindings:
                if r['view'] == view:
                    row = int(r['row'])
                    assert g['physical_names'][row] == r['node']
                    pool[current + row] = (r['host'],view,r['node'])
            host_by_view[view] = current, current+len(g['x39'])
            current += len(g['x39'])
    ledger = {(int(r['step'])-1,int(r['slot'])):r for r in rows(OUT/'SWAPS.csv')}
    train = loader.arrays('orig')
    view_host = {}
    for view in loader.feature_contract['shared_inputs']['orig_train']['views']:
        for i in range(view['start'],view['physical_stop']):
            view_host[i] = view['view'].split('__')[0]
    exposures, host_counts = Counter(), Counter()
    donors, seen_slots = set(), set()
    with np.load(OUT/'SCHEDULE.npz') as z:
        for step in range(200):
            a = loader.step('orig','G0',step)
            b = loader.step('trans','G0',step)
            base, swap = z['base'][step], z['swap'][step]
            assert np.array_equal(base,a.indices) and np.array_equal(z['trans'][step],b.indices)
            assert (train['y'][base[:len(a.positive)]] == 1).all()
            assert (train['y'][base[len(a.positive):]] == 0).all()
            assert np.unique(swap).size == len(swap) == len(base)
            hosts = set()
            for slot in np.flatnonzero(base!=swap):
                r = ledger[step,slot]
                old,new = int(base[slot]),int(swap[slot])
                host,view,node = pool[new]
                assert len(a.positive)<=slot<len(a.positive)+len(a.common_negative)
                assert host==view_host[old]==r['host'] and view==r['view'] and node==r['node']
                assert old==int(r['donor']) and new==int(r['row'])
                assert train['trusted'][old] and train['physical'][old] and train['y'][old]==0
                assert host not in hosts and old not in donors
                hosts.add(host)
                donors.add(old)
                seen_slots.add((step,slot))
                exposures[new] += 1
                host_counts[host] += 1
    assert set(ledger) == seen_slots and set(exposures) == set(pool)
    assert len(donors)==220 and dict(host_counts)==pre['host_exposure']
    report = dict(steps=200, donor_count=len(donors), candidates=len(exposures),
        max_node_exposure=max(exposures.values()), host_counts=host_counts,
        trans_unchanged=True, orig_positives_unchanged=True, val_or_test_rows_consumed=0,
        init_sha=digest(P/'control_v3_eligible_20261104/init_s42.pt'),
        cone_code_sha=digest(BASE/'cone_loss.py'), schedule_sha=pre['schedule_sha'])
    write_json(OUT/'INDEPENDENT_AUDIT.json',report)
    print(report,flush=True)


if __name__=='__main__':
    main()
