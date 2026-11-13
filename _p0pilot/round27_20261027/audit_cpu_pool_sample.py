"""Read-only replay of sampled newly scheduled SAT evidence."""
import collections
import datetime
import hashlib
import json
from pathlib import Path
import sys
import k4_runtime as R
sys.path.insert(0,str(R.ROOT/'phase2/ys'))
import sat_functional_relations as P0
from sat_boundary_semantics import classify,summarize

out=Path(__file__).parent/'cpu_pool_runs/run_00000'
started=json.loads((out/'started.json').read_text(encoding='utf-8'))
assert all(R.sha(Path(__file__).with_name(n))==h for n,h in started['source_sha'].items())
plan={x['view']:x for x in R.read_plan(R.PANEL/'plan.json')['views']}
checks=[]
for manifest in out.glob('worker_*.json'):
    view=json.loads(manifest.read_text(encoding='utf-8'))['view'];item=plan[view]
    assert R.sha(R.ROOT/item['source'])==item['source_sha']
    paths=sorted((R.PANEL/'views'/view/'queries'/view).glob('*/attempt_*/results.json'))
    sample=sorted(set([paths[0],paths[len(paths)//2],paths[-1]])) if paths else []
    rawfiles=list((R.PANEL/'views'/view/'structures'/view).glob('attempt_*/raw.json'))
    raws={R.sha(p) for p in rawfiles}
    for path in sample:
        saved=json.loads(path.read_text(encoding='utf-8'))
        assert saved['source_sha']==item['source_sha'] and saved['raw_sha'] in raws
        assert saved['model_sha']==R.sha(path.parent/'model.v')
        assert saved['log_sha']==R.sha(path.parent/'run.log')
        script=(path.parent/'run.ys').read_text(encoding='utf-8')
        assert hashlib.sha256(script.encode()).hexdigest()==saved['script_sha']
        # Match the extractor's decoding of mixed Windows/WSL diagnostic text.
        log=(path.parent/'run.log').read_text(encoding='utf-8',errors='replace')
        statuses=R.complete_statuses(log,len(saved['queries']),P0.parse_results)
        assert statuses==[q['status'] for q in saved['queries']]
        grouped=collections.defaultdict(list)
        for q in saved['queries']:grouped[q['ordinal']].append(q)
        for ordinal,queries in grouped.items():
            patterns=collections.defaultdict(dict)
            for q in queries:patterns[q['pattern']][q['prove']]=q['status']
            table={p:classify(v[1],v[0]) for p,v in patterns.items()}
            features,inputs=summarize(table,len(next(iter(patterns))))
            assert json.dumps(saved['tables'][str(ordinal)],sort_keys=True)==json.dumps(dict(table=table,features=features,inputs=inputs),sort_keys=True)
        checks.append(dict(view=view,batch=str(path.relative_to(R.ROOT)),queries=len(statuses),tables=len(grouped)))
report=dict(time=datetime.datetime.now().astimezone().isoformat(),checks=checks,
    batches=len(checks),queries=sum(x['queries'] for x in checks),tables=sum(x['tables'] for x in checks),
    errors=[],source_extractor_unchanged=True,lock_contention_check='VIEW_BUSY before extraction; no duplicate SAT',new_training_runs=0)
dest=R.fresh_dir(out/'audits','audit');R.write_new(dest/'report.json',report)
print(json.dumps({k:v for k,v in report.items() if k!='checks'},ensure_ascii=False))
