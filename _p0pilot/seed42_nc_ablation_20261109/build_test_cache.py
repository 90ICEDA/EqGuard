"""Build the test-split D/PO cone cache with the frozen cone rules (no training use)."""
import collections
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = ROOT / '_p0pilot/seed42_nc_ablation_20261109'
sys.path.insert(0, str(ROOT / '_p0pilot/seed42_supervised_prep_20261109'))
import Signed_common as S
import cone_builder as B

VMAP = ROOT / 'generate_trans/folds/hosts_bt31/data/derived_v2/bitwise_alias_20261029_v2/virtual_node_map.jsonl'


def main():
    vmap = {}
    for line in VMAP.read_text(encoding='utf-8').splitlines():
        r = json.loads(line); vmap[(r['view'], r['name'])] = int(r['global_node'])
    c, arr, names, views = S.load_snapshot('test')
    cache, per_view = [], []
    for view, layout in sorted(views.items()):
        net = S.F / 'trans' / (view + '.v')
        if not net.exists():
            per_view.append(dict(view=view, error='netlist_missing')); continue
        b = B.build(net); vr = S.view_rows(views, names, view)
        lo = layout['start']; hi = lo + (layout['old_stop'] - layout['old_start'])
        local = []
        for cone in b['cones']:
            phys, aux = [], []
            for m in cone['members']:
                r = vr.get(m['cell'])
                if r is not None and lo <= r < hi:
                    phys.append(r)
                elif (view, m['cell']) in vmap:
                    aux.append(vmap[(view, m['cell'])])
            phys = sorted(set(phys)); aux = sorted(set(aux))
            ys = [(int(arr['y'][r]), bool(arr['trusted'][r])) for r in phys]
            pos = any(y == 1 and t for y, t in ys)
            neg = (not pos) and bool(ys) and all(y == 0 and t for y, t in ys)
            lab = 1 if pos else (0 if neg else -1)
            local.append(dict(view=view, split='test', cone_id=cone['cone_id'], kind=cone['kind'],
                              endpoint=cone['endpoint'], driver=cone['driver'], label=lab,
                              n_phys=len(phys), n_aux=len(aux),
                              phys_rows='|'.join(str(x) for x in phys),
                              aux_globals='|'.join(str(x) for x in aux)))
        cache.extend(local)
        per_view.append(dict(view=view, split='test', cones=len(local),
                             pos=sum(1 for x in local if x['label'] == 1),
                             neg=sum(1 for x in local if x['label'] == 0),
                             unknown=sum(1 for x in local if x['label'] == -1),
                             digest=hashlib.sha256(json.dumps(sorted(
                                 (x['cone_id'], x['phys_rows']) for x in local)).encode()).hexdigest()))
    S.table(OUT / 'CONE_CACHE_TEST.csv', cache)
    S.table(OUT / 'CONE_VIEW_STATS_TEST.csv', per_view)
    loaded = {r['view'] + '|' + r['cone_id']: r['phys_rows'] for r in S.rows(OUT / 'CONE_CACHE_TEST.csv')}
    bad = []
    for v in per_view:
        rows = sorted((k.split('|', 1)[1], val) for k, val in loaded.items() if k.startswith(v['view'] + '|'))
        if hashlib.sha256(json.dumps(rows).encode()).hexdigest() != v['digest']:
            bad.append(v['view'])
    tot = collections.Counter()
    for x in cache:
        tot[x['kind'] + '|' + str(x['label'])] += 1
    S.write_json(OUT / 'TEST_CACHE_VERIFIED.json', dict(passed=not bad, views=len(per_view), cones=len(cache),
                                                        counts=dict(tot), bad_views=bad[:5],
                                                        note='test cones for offline evaluation only; never used for training'))
    print(json.dumps(dict(passed=not bad, views=len(per_view), cones=len(cache), counts=dict(tot)), ensure_ascii=False))


if __name__ == '__main__':
    main()
