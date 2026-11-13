"""Build compact read-only endpoint-cone caches on real train/val views and verify export->reload.

Compact schema (one row per cone):
  view, split, cone_id, kind, endpoint, driver, label, n_members, member_rows ('r1|r2|...')
Checks:
  - every non-virtual member maps to a 39v3 row inside the view's [start, start+len);
  - labels: 1 = contains trusted positive; 0 = only trusted negatives; -1 = unknown;
  - empty / direct-PI / direct-Q / singleton / overlap reported separately;
  - reload CSV and require per-view member-row sets to equal the in-memory sets.
No model calls, no test split.
"""
import collections
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = ROOT / '_p0pilot/endpoint_cone_build_20261109'
sys.path.insert(0, str(OUT))
import Signed_common as S
import cone_builder as B


def main():
    snaps = {sp: S.load_snapshot(sp) for sp in ('train', 'val')}
    cache_rows, per_view = [], []
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
            missing = out_of_view = virtual = 0
            cone_rows, cone_members = [], {}
            for cone in b['cones']:
                mrows = []
                for m in cone['members']:
                    if m['cell'].startswith('V2_ASSIGN_'):
                        virtual += 1
                        continue
                    r = vr.get(m['cell'])
                    if r is None:
                        missing += 1
                        continue
                    if not (lo <= r < hi):
                        out_of_view += 1
                        continue
                    mrows.append(r)
                ys = [(int(arr['y'][r]), bool(arr['trusted'][r])) for r in mrows]
                pos = any(y == 1 and t for y, t in ys)
                neg_only = (not pos) and bool(ys) and all(y == 0 and t for y, t in ys)
                lab = 1 if pos else (0 if neg_only else -1)
                cone_members[cone['cone_id']] = mrows
                cone_rows.append(dict(cone_id=cone['cone_id'], kind=cone['kind'], label=lab,
                                      members=len(mrows), trusted=sum(t for _, t in ys), flag=cone.get('flag', '')))
                cache_rows.append(dict(view=view, split=split, cone_id=cone['cone_id'], kind=cone['kind'],
                                       endpoint=cone['endpoint'], driver=cone['driver'], label=lab,
                                       n_members=len(mrows), member_rows='|'.join(str(x) for x in sorted(set(mrows)))))
            inv = collections.defaultdict(list)
            for cr in cone_rows:
                for r in set(cone_members.get(cr['cone_id'], [])):
                    inv[(cr['kind'], r)].append(cr['cone_id'])
            pairs = sum(len(set(v)) * (len(set(v)) - 1) // 2 for v in inv.values())
            pos = sum(1 for x in cone_rows if x['label'] == 1)
            neg = sum(1 for x in cone_rows if x['label'] == 0)
            unk = sum(1 for x in cone_rows if x['label'] == -1)
            single = sum(1 for x in cone_rows if x['members'] == 1)
            empty = sum(1 for x in cone_rows if x['members'] == 0)
            trainable = sum(1 for x in cone_rows if x['label'] in (0, 1) and x['members'] >= 2)
            digest = hashlib.sha256(json.dumps(sorted(
                (r['cone_id'], r['member_rows']) for r in cache_rows if r['view'] == view)).encode()).hexdigest()
            per_view.append(dict(view=view, split=split, cones=len(cone_rows),
                                 members=sum(x['members'] for x in cone_rows),
                                 missing=missing, out_of_view=out_of_view, virtual=virtual,
                                 pos=pos, neg=neg, unknown=unk, singleton=single, empty=empty,
                                 overlap_pairs=pairs, trainable=trainable, member_digest=digest))
    S.table(OUT / 'CONE_CACHE.csv', cache_rows)
    S.table(OUT / 'CONE_VIEW_STATS.csv', per_view)
    loaded = {r['view'] + '|' + r['cone_id']: r['member_rows'] for r in S.rows(OUT / 'CONE_CACHE.csv')}
    bad = []
    for v in per_view:
        rows = sorted((k.split('|', 1)[1], val) for k, val in loaded.items() if k.startswith(v['view'] + '|'))
        digest = hashlib.sha256(json.dumps(rows).encode()).hexdigest()
        if digest != v.get('member_digest'):
            bad.append(v['view'])
    totals = dict(views=len(per_view), cones=sum(v.get('cones', 0) for v in per_view),
                  members=sum(v.get('members', 0) for v in per_view),
                  missing=sum(v.get('missing', 0) for v in per_view),
                  out_of_view=sum(v.get('out_of_view', 0) for v in per_view),
                  virtual=sum(v.get('virtual', 0) for v in per_view),
                  pos=sum(v.get('pos', 0) for v in per_view), neg=sum(v.get('neg', 0) for v in per_view),
                  unknown=sum(v.get('unknown', 0) for v in per_view),
                  singleton=sum(v.get('singleton', 0) for v in per_view),
                  empty=sum(v.get('empty', 0) for v in per_view),
                  trainable=sum(v.get('trainable', 0) for v in per_view),
                  overlap_pairs=sum(v.get('overlap_pairs', 0) for v in per_view),
                  split_views={sp: sum(1 for v in per_view if v['split'] == sp) for sp in ('train', 'val')})
    S.write_json(OUT / 'CONE_LOAD_VERIFIED.json', dict(passed=not bad, bad_views=bad[:10], totals=totals,
                                                       note='compact cache reloaded; per-view member-row sets must match; no test split'))
    print(json.dumps(dict(passed=not bad, totals=totals), ensure_ascii=False))


if __name__ == '__main__':
    main()
