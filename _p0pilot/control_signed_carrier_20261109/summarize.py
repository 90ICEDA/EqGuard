"""Coverage summary for the signed-carrier round (read-only)."""
import collections

import Signed_common as S

OUT = S.HERE


def main():
    sel = S.rows(OUT / 'SELECTION.csv')
    rel = S.rows(OUT / 'EXTENDED_RELATIONS.csv')
    unres = S.rows(OUT / 'EXTENSION_UNRESOLVED.csv')
    checked = S.rows(OUT / 'EXTENSION_CHECKED.csv')
    by_obj = {(s['source'], s['gate']): s for s in sel}
    rows = []
    for split in ('train', 'val'):
        objs = [s for s in sel if s['split'] == split]
        rels = [r for r in rel if r['split'] == split]
        uns = [u for u in unres if u['split'] == split]
        rows.append(dict(
            split=split, objects=len(objs), independent_sources=len({s['source'] for s in objs}),
            flows=len({c['views'] for c in checked if c['split'] == split}),
            checked=len([c for c in checked if c['split'] == split]),
            signed=len(rels), signed_plus=sum(r['polarity'] == '+1' for r in rels),
            signed_minus=sum(r['polarity'] == '-1' for r in rels),
            live=sum(r['host_usage'] == 'active' for r in rels), dead=sum(r['host_usage'] == 'dead' for r in rels),
            unresolved=len(uns),
            boundary_unaligned=sum('boundary_not_aligned' in u['reason'] for u in uns),
            no_descendant=sum(u['reason'] == 'no_descendant' for u in uns)))
    total = dict(split='total', objects=sum(r['objects'] for r in rows),
                 independent_sources=len({s['source'] for s in sel}), flows=len({c['views'] for c in checked}),
                 checked=sum(r['checked'] for r in rows), signed=sum(r['signed'] for r in rows),
                 signed_plus=sum(r['signed_plus'] for r in rows), signed_minus=sum(r['signed_minus'] for r in rows),
                 live=sum(r['live'] for r in rows), dead=sum(r['dead'] for r in rows),
                 unresolved=sum(r['unresolved'] for r in rows),
                 boundary_unaligned=sum(r['boundary_unaligned'] for r in rows),
                 no_descendant=sum(r['no_descendant'] for r in rows))
    S.table(OUT / 'COVERAGE_SUMMARY.csv', rows + [total])
    print(rows + [total])


if __name__ == '__main__':
    main()
