"""Pre-training gate; native equivalence, counterexample replay, fair permutation."""
import collections
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
T=ROOT/'10.15/06_统一评测协议/N4_三向泛化/tables/sat_small_round18'
sys.path.insert(0,str(ROOT/'phase2/ys'))
import native_boundary_extract as N
sys.path.insert(0,str(ROOT/'_p0pilot/round10_20261025'))
import native as OLD
spec=importlib.util.spec_from_file_location('independent_native_replay',ROOT/'_p0pilot/round10_20261025/audit.py')
R=importlib.util.module_from_spec(spec);spec.loader.exec_module(R)


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    rows=json.loads((T/'records.json').read_text());snaps=json.loads((T/'snapshots.json').read_text())
    modules={};matched=[];replays=[]
    for s in snaps:
        f=ROOT/s['folder'];assert sha(f/'raw.json')==s['raw_sha'];m=next(iter(json.loads((f/'raw.json').read_text())['modules'].values()));modules[s['view']]=m
        name=next(n for n,v in m['netnames'].items() if len(v['bits'])==1)
        old,spec=OLD.emit(m,'impl',[name]*5)
        old_assigns=old.splitlines()[1:old.splitlines().index(next(line for line in old.splitlines() if line.startswith('assign sigs=')))]
        lines,width=N.logic(m);assert lines==old_assigns and width==spec['width'];matched.append(s['view'])
    qcount=0;status_counts=collections.Counter();ordinals=collections.defaultdict(set)
    for p in sorted((T/'queries').rglob('results.json')):
        data=json.loads(p.read_text());assert sha(p.parent/'model.v')==data['model_sha'];assert sha(p.parent/'run.log')==data['log_sha']
        assert hashlib.sha256((p.parent/'run.ys').read_text().encode()).hexdigest()==data['script_sha']
        qcount+=len(data['queries']);status_counts.update(q['status'] for q in data['queries'])
        for q in data['queries']:
            witness=p.parent/(str(q['query_id'])+'.model.json')
            if not witness.exists() or q['ordinal'] in ordinals[p.parent.parent.name]:continue
            env=next(x['data'][0] for x in json.loads(witness.read_text())['signal'] if x['name']=='env')
            rel=str(p.relative_to(ROOT));r=next(r for r in rows if r.get('evidence')==rel and r.get('evidence_ordinal')==q['ordinal'])
            values=R.replay(modules[r['view']],env)
            assert ''.join(str(values[b]) for b in r['cut_bits'])==q['pattern']
            assert values[r['target_bit']]==1-q['prove']
            replays.append(dict(view=r['view'],ordinal=q['ordinal'],role=r['target_role'],passed=True,witness=str(witness.relative_to(ROOT))))
            ordinals[r['view']].add(q['ordinal'])
    assert len(replays)==24 and not (status_counts['unknown'] or status_counts['error'])
    real=np.load(T/'real.npy');zero=np.load(T/'zero.npy');perm=real.copy()
    groups=collections.defaultdict(list)
    for r in rows:
        if real[r['local_node'],18]:groups[(r['split'],r['target_role'],r['driver_type'],r['k'])].append(r['local_node'])
    rng=np.random.default_rng(20261026);mapping=[]
    for key,ix in groups.items():
        order=rng.permutation(len(ix));src=np.asarray(ix)[order]
        if len(ix)>1 and np.array_equal(src,ix):src=np.roll(src,1)
        perm[ix,:18]=real[src,:18]
        mapping += [dict(destination=int(d),source=int(s),stratum=list(key)) for d,s in zip(ix,src)]
    assert np.array_equal(real[:,0],perm[:,0]) and np.array_equal(real[:,18],perm[:,18])
    assert np.all(zero[:,:18]==0) and np.array_equal(zero[:,18],real[:,18])
    stats={}
    for split in ('train','val','test'):
        rr=[r for r in rows if r['split']==split];ids=[r['local_node'] for r in rr];covered=int(real[ids,18].sum())
        changed=int(np.any(real[ids,:18]!=perm[ids,:18],axis=1).sum())
        stats[split]=dict(nodes=len(ids),covered=covered,coverage=covered/len(ids),permutation_changed=changed,changed_fraction=changed/covered,
                          unique_profiles=len(np.unique(real[ids,:18],axis=0)),
                          nonlocal_nodes=sum(r.get('nonlocal_cut',0) for r in rr))
    gate=all(stats[s]['coverage']>=.8 and stats[s]['unique_profiles']>=10 and stats[s]['changed_fraction']>=.3 for s in ('train','val'))
    np.save(T/'permuted_stratified.npy',perm)
    (T/'permutation_stratified.json').write_text(json.dumps(mapping,indent=2))
    info=dict(gate_passed=gate,gate_scope='engineering coverage/diversity, not predictive gain',stats=stats,
              actual_sat_queries=qcount,query_status=dict(status_counts),native_models_exactly_matched=len(matched),independent_witness_replays=replays,
              amendment='Before training/label use: permutation now also preserves gate type and cut size; original permutation retained but not trained.',
              training_features=dict(real=sha(T/'real.npy'),zero=sha(T/'zero.npy'),permuted=sha(T/'permuted_stratified.npy')),
              trainable_schema='39 base + 18 bounded + covered; cut k and gate type preserved under permutation',test_labels_read=False)
    (T/'pretrain_gate.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in info.items() if k!='independent_witness_replays'},ensure_ascii=False,indent=2))
    if not gate:raise RuntimeError('Information gate not passed; do not train')


if __name__=='__main__':main()
