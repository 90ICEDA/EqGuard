"""Independent recount of v2 coverage from raw files (must match COVERAGE_V2.csv)."""
import collections
import json

import Signed_common as S

OUT = S.HERE
V1 = S.ROOT / '_p0pilot/control_signed_carrier_20261109'


def main():
    sel = S.rows(V1 / 'SELECTION.csv')
    attempts = S.rows(OUT / 'ATTEMPT_LOG.csv')
    rels = S.rows(OUT / 'EXTENDED_V2.csv')
    cov = {r['split']: r for r in S.rows(OUT / 'COVERAGE_V2.csv')}
    rows = []
    for split in ('train', 'val'):
        objs = [s for s in sel if s['split'] == split]
        retried = {a['rank'] for a in attempts if a['split'] == split}
        accepted = {a['rank'] for a in attempts if a['split'] == split and a['result'].startswith('accepted')}
        rel = [r for r in rels if r['split'] == split]
        rec = dict(split=split, candidates=len(objs), retried_objects=len(retried),
                   accepted_objects=len(accepted), relations=len(rel),
                   flows_attempted=len({a['view'][len(a['source']) + 2:] for a in attempts
                                        if a['split'] == split and a['view']}),
                   flows_accepted=len({r['implementation_flow'] for r in rel}),
                   plus=sum(r['polarity'] == '+1' for r in rel), minus=sum(r['polarity'] == '-1' for r in rel),
                   live=sum(r['host_usage'] == 'active' for r in rel), dead=sum(r['host_usage'] == 'dead' for r in rel),
                   attempts=len([a for a in attempts if a['split'] == split]),
                   unaligned=len([a for a in attempts if a['split'] == split and a['result'] == 'boundary_not_aligned']),
                   mismatch=len([a for a in attempts if a['split'] == split and a['result'] == 'function_mismatch']),
                   unchecked_descendants=sum(int(a['unchecked']) for a in attempts if a['split'] == split))
        for k, v in rec.items():
            if k in cov[split] and k != 'split':
                assert str(v) == cov[split][k], (split, k, v, cov[split][k])
        rows.append(rec)
    total = cov['total']
    for k in ('candidates', 'retried_objects', 'accepted_objects', 'relations', 'attempts'):
        assert str(sum(r[k] for r in rows)) == total[k], (k, total[k])
    out = dict(passed=True, rows=rows, checks='per-split fields equal COVERAGE_V2; totals equal')
    S.write_json(OUT / 'COVERAGE_CHECK.json', out)
    print(json.dumps(out, ensure_ascii=False))


if __name__ == '__main__':
    main()
