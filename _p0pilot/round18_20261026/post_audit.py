"""Independent saved-evidence/score audit, no new training or SAT."""
import collections
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import average_precision_score,roc_auc_score

ROOT=Path(__file__).resolve().parents[2]
T=ROOT/'10.15/06_统一评测协议/N4_三向泛化/tables/sat_small_round18'
RUNS=ROOT/'results_sat_small_r18'
sys.path.insert(0,str(ROOT/'phase2/ys'))
import native_boundary_extract as N
from sat_boundary_semantics import parse_query_results, classify, summarize


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    rows=json.loads((T/'records.json').read_text());snaps=json.loads((T/'snapshots.json').read_text())
    modules={s['view']:next(iter(json.loads((ROOT/s['folder']/'raw.json').read_text())['modules'].values())) for s in snaps}
    dependencies={v:N.dependency_index(m)[1] for v,m in modules.items()}
    certificates=0
    for r in rows:
        if r['status']!='eligible':continue
        cut=set(r['cut_bits']);todo=[r['target_bit']];seen=set()
        assert r['target_bit'] not in cut and 1<=len(cut)<=4
        while todo:
            b=todo.pop()
            if b in cut or b in seen:continue
            seen.add(b)
            assert b in dependencies[r['view']],(r['cell'],b)
            todo += dependencies[r['view']][b]
        certificates+=1
    batches=0;queries=0;wall=0.
    for p in sorted((T/'queries').rglob('results.json')):
        d=json.loads(p.read_text());log=(p.parent/'run.log').read_text();ss=parse_query_results(log)
        assert ss==[q['status'] for q in d['queries']]
        script=(p.parent/'run.ys').read_text();cmds=[x for x in script.splitlines() if x.startswith('sat ')]
        assert len(cmds)==len(d['queries'])
        for line,q in zip(cmds,d['queries']):
            assert line=='sat '+q['args'] or line.startswith('sat '+q['args']+' -show-inputs ')
        grouped=collections.defaultdict(list)
        for r in rows:
            if r.get('evidence')==str(p.relative_to(ROOT)):grouped[r['evidence_ordinal']].append(r)
        chunk=[grouped[o][0] for o in sorted(grouped)]
        assert N.model(modules[p.parent.parent.name],chunk)==(p.parent/'model.v').read_text()
        for ordinal,tab in d['tables'].items():
            qs=[q for q in d['queries'] if q['ordinal']==int(ordinal)];t={}
            for pat in {q['pattern'] for q in qs}:
                st={q['prove']:q['status'] for q in qs if q['pattern']==pat};t[pat]=classify(st[1],st[0])
            f,i=summarize(t,len(next(iter(t))))
            assert f==tab['features'] and i==tab['inputs']
        batches+=1;queries+=len(ss);wall+=d['wall_s']
    real=np.load(T/'real.npy');perm=np.load(T/'permuted_stratified.npy')
    gate=json.loads((T/'pretrain_gate.json').read_text())
    # This file was frozen before the runs; never edit it to correct display counts.
    run=json.loads((RUNS/'results.json').read_text())
    assert run['protocol']['gate_sha']==sha(T/'pretrain_gate.json')
    assert all(run['protocol']['feature_hashes'][a]==sha(T/f) for a,f in [('real','real.npy'),('zero','zero.npy'),('permuted','permuted_stratified.npy')])
    corrected={}
    for s in ('train','val','test'):
        ix=[r['local_node'] for r in rows if r['split']==s and real[r['local_node'],18]]
        corrected[s]=dict(unique_covered_profiles=len(np.unique(real[ix,:18],axis=0)),covered=len(ix))
    per_local={r['local_node']:r for r in rows}
    mapping=json.loads((T/'permutation_stratified.json').read_text())
    for pair in mapping:
        a,b=per_local[pair['destination']],per_local[pair['source']]
        assert (a['split'],a['target_role'],a['driver_type'],a['k'])==(b['split'],b['target_role'],b['driver_type'],b['k'])
        assert np.array_equal(perm[a['local_node'],:18],real[b['local_node'],:18])
    checks=[]
    for r in run['results']:
        folder=RUNS/f'{r["arm"]}_seed{r["seed"]}'
        val=np.load(folder/'val_predictions.npz');test=np.load(folder/'test_predictions.npz')
        for label,y,p in [('val_best',val['labels'],val['best']),('test',test['labels'],test['probability'])]:
            assert np.isfinite(p).all() and np.all((p>=0)&(p<=1))
            assert abs(average_precision_score(y,p)-r[label]['AP'])<1e-12
            assert abs(roc_auc_score(y,p)-r[label]['ROC_AUC'])<1e-12
        assert (folder/'test_predictions.npz').stat().st_mtime >= (RUNS/'validation_selection_complete.json').stat().st_mtime
        checks.append(dict(arm=r['arm'],seed=r['seed'],metrics_verified=True))
    info=dict(complete_cut_certificates=certificates,batches=batches,actual_sat_queries=queries,sat_process_wall_s=wall,
              models_regenerated=batches,score_checks=checks,corrected_covered_profile_counts=corrected,
              profile_count_note='Original gate counted one missing all-zero profile too; corrected counts exclude missing; gate still passes unchanged.',
              all_permutation_strata_verified=True,test_after_all_selection=True,
              query_evidence_scope='complete boundaries in native free physical-Q combinational context; no reset/reachability proof',
              code_hashes={str(p.relative_to(ROOT)):sha(p) for p in [ROOT/'phase2/ys/native_boundary_extract.py',ROOT/'phase2/ys/sat_boundary_semantics.py',*sorted((ROOT/'_p0pilot/round18_20261026').glob('*.py'))]})
    (T/'post_audit.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in info.items() if k not in ('code_hashes','score_checks')},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
