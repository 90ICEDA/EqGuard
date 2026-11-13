"""Object-level coverage: candidate descendants vs attempted, truncation vs early accept (no per-attempt double count)."""
import collections
import json

import Signed_common as S

OUT = S.HERE
V2 = S.ROOT / '_p0pilot/control_signed_carrier_20261109_v2'
CAP = 5


def main():
    attempts = S.rows(OUT / 'ATTEMPT_LOG.csv')
    rels = S.rows(OUT / 'EXTENDED_V2.csv') if (OUT / 'EXTENDED_V2.csv').exists() else S.rows(V2 / 'EXTENDED_V2.csv')
    by_rank = collections.defaultdict(list)
    for a in attempts:
        by_rank[int(a['rank'])].append(a)
    accepted_ranks = {int(r['relation_id'].split('_')[1].replace('EXT', '')) for r in rels}
    rows = []
    for rank, aa in sorted(by_rank.items()):
        split = aa[0]['split']
        attempted = len(aa)
        unchecked = max(int(a['unchecked']) for a in aa)
        descendants = attempted + unchecked
        acc = rank in accepted_ranks
        if acc:
            stop = 'accepted_early' if attempted < CAP else 'accepted_at_cap'
        else:
            stop = 'cap_truncated' if unchecked > 0 else 'exhausted'
        rows.append(dict(rank=rank, split=split, source=aa[0]['source'], gate=aa[0]['gate'],
                         descendants=descendants, attempted=attempted, unchecked=unchecked,
                         accepted=int(acc), stop_reason=stop))
    summary = []
    for split in ('train', 'val'):
        rr = [r for r in rows if r['split'] == split]
        summary.append(dict(split=split, objects=len(rr), attempted_objects=len(rr),
                            attempts=sum(r['attempted'] for r in rr),
                            accepted_objects=sum(r['accepted'] for r in rr),
                            accepted_early=sum(r['stop_reason'] == 'accepted_early' for r in rr),
                            accepted_at_cap=sum(r['stop_reason'] == 'accepted_at_cap' for r in rr),
                            cap_truncated=sum(r['stop_reason'] == 'cap_truncated' for r in rr),
                            exhausted=sum(r['stop_reason'] == 'exhausted' for r in rr),
                            unchecked=sum(r['unchecked'] for r in rr)))
    S.table(OUT / 'PER_OBJECT_COVERAGE_V3.csv', rows)
    S.write_json(OUT / 'PER_OBJECT_SUMMARY_V3.json', dict(cap=CAP, objects=rows, summary=summary,
                                                          note='counts are per object; attempts are listed once per descendant'))
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
