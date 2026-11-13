"""v3.1 object-level coverage: candidates (lineage) minus attempted (log); no reliance on old unchecked field."""
import collections
import csv
import json

import Signed_common as S

OUT = S.HERE
V1 = S.ROOT / '_p0pilot/control_signed_carrier_20261109'


def main():
    sel = {int(r['rank']): r for r in S.rows(V1 / 'SELECTION.csv')}
    lineage = S.rows(S.ROOT / '_p0pilot/control_role_pattern_20261107/NODE_LINEAGE.csv')
    attempted = collections.defaultdict(set)
    for r in S.rows(OUT / 'ATTEMPT_LOG.csv'):
        attempted[int(r['rank'])].add((r['view'], r['node']))
    rels = S.rows(OUT / 'RELATIONS_V31.csv')
    accepted = {int(r['relation_id'].split('_')[1].replace('EXT', '')) for r in rels
                if r['relation_id'].startswith('V2_EXT')}
    rows = []
    for rank in sorted(attempted):
        s = sel[rank]
        cand = {(d['view'], d['node_name']) for d in lineage
                if d['key'].startswith('trans') and d['source'] == s['source'] and s['gate'] in d['parents'].split('|')}
        att = attempted[rank]
        un = cand - att
        if rank in accepted:
            stop = 'accepted_early' if un else 'accepted_at_end'
        else:
            stop = 'cap_truncated' if un else 'exhausted'
        rows.append(dict(rank=rank, split=s['split'], source=s['source'], gate=s['gate'],
                         candidates=len(cand), attempted=len(att), unchecked=len(un),
                         accepted=int(rank in accepted), stop_reason=stop,
                         unchecked_views='|'.join(sorted({v for v, _ in un}))))
    summary = []
    for split in ('train', 'val'):
        rr = [r for r in rows if r['split'] == split]
        summary.append(dict(split=split, objects=len(rr), candidates=sum(r['candidates'] for r in rr),
                            attempted=sum(r['attempted'] for r in rr), unchecked=sum(r['unchecked'] for r in rr),
                            accepted_objects=sum(r['accepted'] for r in rr),
                            accepted_early=sum(r['stop_reason'] == 'accepted_early' for r in rr),
                            cap_truncated=sum(r['stop_reason'] == 'cap_truncated' for r in rr),
                            exhausted=sum(r['stop_reason'] == 'exhausted' for r in rr)))
    S.table(OUT / 'PER_OBJECT_COVERAGE_V31.csv', rows)
    S.write_json(OUT / 'PER_OBJECT_SUMMARY_V31.json', dict(rows=rows, summary=summary,
                                                           note='candidates from lineage; attempted from log; unchecked = set difference'))
    print(json.dumps(summary, ensure_ascii=False))
    assert sum(r['unchecked'] for r in rows if r['split'] == 'train') == 1
    assert sum(r['unchecked'] for r in rows if r['split'] == 'val') == 4


if __name__ == '__main__':
    main()
