"""Rebuild the endpoint-cone cache with explicit physical / auxiliary / missing member classes.

Fixes:
  - `__v2_assign_*` cells are auxiliary graph rows (virtual_node_map.jsonl, global ids appended after originals);
    they are NOT missing and have NO supervision label (contract: masks false, never negative).
  - structural members and MIL supervision members are stored separately;
  - cone labels come only from physical members (trusted positive/negative); no physical member -> unknown;
  - never drop members to manufacture a negative cone.
"""
import collections
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = ROOT / '_p0pilot/seed42_supervised_prep_20261109'
sys.path.insert(0, str(OUT))
import Signed_common as S
import cone_builder as B

VMAP = ROOT / 'generate_trans/folds/hosts_bt31/data/derived_v2/bitwise_alias_20261029_v2/virtual_node_map.jsonl'


def main():
    vmap = {}
    for line in VMAP.read_text(encoding='utf-8').splitlines():
        r = json.loads(line)
        vmap[(r['view'], r['name'])] = int(r['global_node'])
    snaps = {sp: S.load_snapshot(sp) for sp in ('train', 'val')}
    cache, per_view, budget = [], [], collections.Counter()
    for split in ('train', 'val'):
        c, arr, names, views = snaps[split]
        for view, layout in sorted(views.items()):
            net = S.F / 'trans' / (view + '.v')
            if not net.exists():
                per_view.append(dict(view=view, split=split, error='netlist_missing'))
                continue
            b = B.build(net)
            vr = S.view_rows(views, names, view)
            lo = layout['start']
            hi = lo + (layout['old_stop'] - layout['old_start'])
            phys_all, aux_all, missing = set(), set(), 0
            cone_rows, local = {}, []
            for cone in b['cones']:
                phys, aux = [], []
                for m in cone['members']:
                    nm = m['cell']
                    r = vr.get(nm)
                    if r is not None and lo <= r < hi:
                        phys.append(r)
                    elif (view, nm) in vmap:
                        aux.append(vmap[(view, nm)])
                    elif r is not None:
                        missing += 1
                    else:
                        missing += 1
                phys = sorted(set(phys)); aux = sorted(set(aux))
                ys = [(int(arr['y'][r]), bool(arr['trusted'][r])) for r in phys]
                pos = any(y == 1 and t for y, t in ys)
                neg_only = (not pos) and bool(ys) and all(y == 0 and t for y, t in ys)
                lab = 1 if pos else (0 if neg_only else -1)
                cone_rows[cone['cone_id']] = phys
                local.append(dict(view=view, split=split, cone_id=cone['cone_id'], kind=cone['kind'],
                                  endpoint=cone['endpoint'], driver=cone['driver'], label=lab,
                                  n_phys=len(phys), n_aux=len(aux), n_missing=len([1 for m in cone['members']
                                                                                   if m['cell'] not in vr and (view, m['cell']) not in vmap]),
                                  phys_rows='|'.join(str(x) for x in phys),
                                  aux_globals='|'.join(str(x) for x in aux)))
                phys_all.update(phys); aux_all.update(aux)
            inv = collections.defaultdict(list)
            for cid, rows in cone_rows.items():
                for r in set(rows):
                    inv[r].append(cid)
            pairs = sum(len(set(v)) * (len(set(v)) - 1) // 2 for v in inv.values())
            cache.extend(local)
            pos = sum(1 for x in local if x['label'] == 1)
            neg = sum(1 for x in local if x['label'] == 0)
            unk = sum(1 for x in local if x['label'] == -1)
            empty = sum(1 for x in local if x['n_phys'] == 0)
            single = sum(1 for x in local if x['n_phys'] == 1)
            trainable = sum(1 for x in local if x['label'] in (0, 1) and x['n_phys'] >= 2)
            digest = hashlib.sha256(json.dumps(sorted(
                (x['cone_id'], x['phys_rows']) for x in local)).encode()).hexdigest()
            per_view.append(dict(view=view, split=split, cones=len(cone_rows), phys_members=len(phys_all),
                                 aux_members=len(aux_all), missing=missing, pos=pos, neg=neg, unknown=unk,
                                 empty=empty, singleton=single, trainable=trainable, overlap_pairs=pairs,
                                 member_digest=digest))
    S.table(OUT / 'CONE_CACHE_V2.csv', cache)
    S.table(OUT / 'CONE_VIEW_STATS_V2.csv', per_view)
    # budget by split x kind (physical supervised members >=2)
    for split in ('train', 'val'):
        for kind in ('D', 'SI', 'PO'):
            rows = [x for x in cache if x['split'] == split and x['kind'] == kind]
            budget[f'{split}|{kind}|cones'] += len(rows)
            budget[f'{split}|{kind}|pos'] += sum(1 for x in rows if x['label'] == 1)
            budget[f'{split}|{kind}|neg'] += sum(1 for x in rows if x['label'] == 0)
            budget[f'{split}|{kind}|unknown'] += sum(1 for x in rows if x['label'] == -1)
            budget[f'{split}|{kind}|trainable_ge2'] += sum(1 for x in rows if x['label'] in (0, 1) and x['n_phys'] >= 2)
            budget[f'{split}|{kind}|phys_exposure'] += sum(x['n_phys'] for x in rows if x['label'] in (0, 1) and x['n_phys'] >= 2)
            budget[f'{split}|{kind}|aux_exposure'] += sum(x['n_aux'] for x in rows if x['label'] in (0, 1) and x['n_phys'] >= 2)
    S.write_json(OUT / 'BUDGET_V2.json', dict(budget=dict(budget)))
    # reload check
    loaded = {r['view'] + '|' + r['cone_id']: r['phys_rows'] for r in S.rows(OUT / 'CONE_CACHE_V2.csv')}
    bad = []
    for v in per_view:
        rows = sorted((k.split('|', 1)[1], val) for k, val in loaded.items() if k.startswith(v['view'] + '|'))
        if hashlib.sha256(json.dumps(rows).encode()).hexdigest() != v.get('member_digest'):
            bad.append(v['view'])
    S.write_json(OUT / 'CACHE_V2_VERIFIED.json', dict(passed=not bad, bad_views=bad[:5],
                                                      note='reload from CONE_CACHE_V2.csv; physical member rows per cone must match'))
    print(json.dumps(dict(passed=not bad, views=len(per_view),
                          cones=sum(v.get('cones', 0) for v in per_view),
                          phys=sum(v.get('phys_members', 0) for v in per_view),
                          aux=sum(v.get('aux_members', 0) for v in per_view),
                          missing=sum(v.get('missing', 0) for v in per_view),
                          pos=sum(v.get('pos', 0) for v in per_view),
                          neg=sum(v.get('neg', 0) for v in per_view),
                          unknown=sum(v.get('unknown', 0) for v in per_view)), ensure_ascii=False))


if __name__ == '__main__':
    main()
