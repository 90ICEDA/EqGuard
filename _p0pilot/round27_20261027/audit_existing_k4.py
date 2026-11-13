"""Read-only existing SAT evidence audit; writes only a new audit report."""
import collections
import hashlib
import json
import sys
from pathlib import Path
import k4_runtime as R

sys.path.insert(0, str(R.ROOT/'phase2/ys'))
from sat_boundary_semantics import classify, summarize, parse_query_results


def main():
    report = dict(successful_batches=0, reusable_queries=0, recoverable_orphans=[],
                  failed_or_incomplete_logs=[], errors=[], verified_views=[], pending_views=[],
                  preserved_files=0, changed_or_missing_originals=[], solver_calls=0)
    root=Path(__file__).parent
    before=json.loads((root/'evidence_before_repair.json').read_text())
    for relative, info in before.items():
        p=R.PANEL/relative
        if not p.exists() or R.sha(p)!=info['sha256']:
            report['changed_or_missing_originals'].append(relative)
        else:report['preserved_files']+=1
    for p in sorted((R.PANEL/'views').rglob('results.json')):
        try:
            saved=json.loads(p.read_text())
            script=(p.parent/'run.ys').read_text(encoding='utf-8')
            code=(p.parent/'model.v').read_text(encoding='utf-8')
            qs=saved['queries']
            found=R.find_bound_batch(p.parent,code,script,saved['source_sha'],
                                    saved['raw_sha'],len(qs),parse_query_results)
            if found is None or found[0]!=p.parent:raise ValueError('Batch binding rejected')
            if [q['query_id'] for q in qs]!=list(range(len(qs))):raise ValueError('Query IDs')
            by_ord=collections.defaultdict(list)
            for q in qs:by_ord[q['ordinal']].append(q)
            for ordinal, rows in by_ord.items():
                by_pat=collections.defaultdict(dict)
                for q in rows:
                    if q['prove'] in by_pat[q['pattern']]:raise ValueError('Duplicate prove')
                    by_pat[q['pattern']][q['prove']]=q['status']
                table={pat:classify(pair[1],pair[0]) for pat,pair in by_pat.items()}
                features,inputs=summarize(table,len(next(iter(table))))
                measured=dict(table=table,features=features,inputs=inputs)
                if json.dumps(measured,sort_keys=True)!=json.dumps(saved['tables'][str(ordinal)],sort_keys=True):
                    raise ValueError('Replayed table/summary mismatch')
            report['successful_batches']+=1;report['reusable_queries']+=len(qs)
        except Exception as e:report['errors'].append(dict(path=str(p),error=repr(e)))
    for p in sorted((R.PANEL/'views').rglob('run.log')):
        if (p.parent/'results.json').exists():continue
        try:
            script=(p.parent/'run.ys').read_text(encoding='utf-8')
            count=sum(line.startswith('sat ') for line in script.splitlines())
            if not count:raise ValueError('No SAT commands')
            R.complete_statuses(p.read_text(encoding='utf-8',errors='replace'),count,parse_query_results)
            report['recoverable_orphans'].append(dict(path=str(p.relative_to(R.ROOT)),queries=count,
                note='Only recover on exact regenerated source/model/script binding during resume'))
        except Exception as e:
            report['failed_or_incomplete_logs'].append(dict(path=str(p.relative_to(R.ROOT)),error=str(e)))
    for item in R.read_plan(R.PANEL/'plan.json')['views']:
        ok,detail=R.validate_complete(R.PANEL/'views'/item['view'])
        report['verified_views' if ok else 'pending_views'].append(dict(view=item['view'],detail=detail))
    out=R.fresh_dir(root/'repair_audits','audit')
    R.write_new(out/'audit.json',report)
    print(json.dumps({k:(len(v) if isinstance(v,list) else v) for k,v in report.items()},ensure_ascii=False))
    print(out)
    if report['errors'] or report['changed_or_missing_originals']:raise SystemExit(1)


if __name__=='__main__':main()
