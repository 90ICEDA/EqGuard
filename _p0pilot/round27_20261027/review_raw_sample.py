"""Deterministic first/middle/last evidence checks per historical view."""
import json
import sys
from pathlib import Path
import k4_runtime as R

sys.path.insert(0,str(R.ROOT/'phase2/ys'))
from sat_boundary_semantics import parse_query_results


def main():
    names=['sat_s15850_round22','sat_k4_rs232_round23','sat_k6_rs232_round23',
           'sat_k8_rs232_round24','sat_k8_s15850_round25','sat_k6_s15850_round26']
    report=dict(scope='Deterministic sampled raw logs; not an exhaustive raw-log audit',
                errors=[],panels={},new_sat_queries=0)
    for name in names:
        panel=R.TABLES/name;sampled=0;queries=0;details=[]
        source_by_view={i['view']:i for i in R.read_plan(panel/'plan.json')['views']}
        for folder in sorted((panel/'views').iterdir()):
            if not folder.is_dir():continue
            files=sorted((folder/'queries').rglob('results.json'))
            if not files:continue
            selected=sorted({0,len(files)//2,len(files)-1})
            snapshots=json.loads((folder/'snapshots.json').read_text())
            raw_by_sha={s['raw_sha']:R.ROOT/s['folder']/'raw.json' for s in snapshots}
            for i in selected:
                path=files[i];saved=json.loads(path.read_text());qs=saved['queries']
                try:
                    item=source_by_view[folder.name]
                    assert R.sha(R.ROOT/item['source'])==saved['source_sha']==item['source_sha']
                    assert saved['raw_sha'] in raw_by_sha
                    assert R.sha(raw_by_sha[saved['raw_sha']])==saved['raw_sha']
                    assert R.sha(path.parent/'model.v')==saved['model_sha']
                    script=(path.parent/'run.ys').read_text(encoding='utf-8')
                    import hashlib
                    assert hashlib.sha256(script.encode()).hexdigest()==saved['script_sha']
                    assert R.sha(path.parent/'run.log')==saved['log_sha']
                    statuses=R.complete_statuses((path.parent/'run.log').read_text(encoding='utf-8',errors='replace'),len(qs),parse_query_results)
                    assert statuses==[q['status'] for q in qs]
                    sampled+=1;queries+=len(qs)
                except Exception as e:
                    report['errors'].append(dict(path=str(path.relative_to(R.ROOT)),error=repr(e)))
                details.append(str(path.relative_to(R.ROOT)))
        report['panels'][name]=dict(sampled_batches=sampled,sampled_queries=queries,paths=details)
    out=R.fresh_dir(Path(__file__).parent/'result_reviews','raw_sample')
    R.write_new(out/'raw_sample.json',report)
    print(json.dumps(dict(output=str(out),errors=report['errors'],
        panels={k:{a:b for a,b in v.items() if a!='paths'} for k,v in report['panels'].items()}),ensure_ascii=False))
    if report['errors']:raise SystemExit(1)


if __name__=='__main__':main()
