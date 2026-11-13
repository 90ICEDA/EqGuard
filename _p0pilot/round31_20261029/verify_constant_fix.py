"""Offline only: regenerate available validation cones; never invoke a solver."""
import collections
import hashlib
import importlib.util
import itertools
import json
import re
import sys
from datetime import datetime
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'_p0pilot/round27_20261027'),str(ROOT/'phase2/ys')]
import k4_fast_support as F
import k4_runtime as R
import native_boundary_extract as N

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(name,obj):(HERE/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')

def main():
    spec=importlib.util.spec_from_file_location('old',HERE/'k4_fast_support.before.py')
    old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    lines=['wire b2,b3,b4,b5,b6;', 'assign b2=env[0];',
           "assign b3=b2&1'b0;", "assign b4=b2|1'b1;",
           "assign b5=b2?1'b0:1'b1;", 'assign b6=b2^b2;']
    compiled=F.compile_logic(lines)
    assert compiled[1]=={2:(),3:(2,),4:(2,),5:(2,),6:(2,2)}
    assert old.compile_logic(lines)[1][3]==(2,0)
    for bit,expected in [(3,[0,0]),(4,[1,1]),(5,[1,0]),(6,[0,0])]:
        rec=[dict(target_bit=bit,cut_bits=[2])]
        code=F.pruned_model(compiled,1,rec,N.bitref)
        assert 'wire b2,b'+str(bit)+';' in code
        for value,want in enumerate(expected):
            # Independent exhaustive interpretation of the tiny regression circuit.
            got={3:value&0,4:value|1,5:0 if value else 1,6:value^value}[bit]
            assert got==want
    try:F.pruned_model(compiled,1,[dict(target_bit=99,cut_bits=[2])],N.bitref)
    except ValueError as e:assert str(e)=='Undriven required bit 99'
    else:raise AssertionError('Real undriven signal must still fail closed')

    panel=R.TABLES/'sat_k4_validation_round29'
    with np.load(panel/'base_inputs.npz') as z:gids,vi=z['global_ids'],z['view_index']
    wanted=set(map(int,gids));names={}
    with (ROOT/'generate_trans/folds/hosts_bt31/data/processed/node_names_trans.txt').open(encoding='utf-8') as f:
        for i,line in enumerate(f):
            if i in wanted:names[i]=line.strip().lstrip('\\')
            if len(names)==len(wanted):break
    reports=[];baseline={};nmodels=0;nbatches=0
    for j,item in enumerate(R.read_plan(panel/'plan.json')['views']):
        folder=panel/'views'/item['view']
        raws=list((folder/'structures'/item['view']).glob('attempt_*/raw.json'))
        if not raws:continue
        raw=raws[0];binding=json.loads((raw.parent/'binding.json').read_text())
        assert sha(raw)==binding['raw_sha'] and R.sha(ROOT/item['source'])==binding['source_sha']==item['source_sha']
        m=next(iter(json.loads(raw.read_text())['modules'].values()))
        logic,width=N.logic(m);comp=F.compile_logic(logic);oldcomp=old.compile_logic(logic)
        drivers,deps=R.dependency_index_fast(m);outs=collections.defaultdict(list)
        for bit,(cell,pin) in drivers.items():outs[cell].append(bit)
        tasks={}
        for g in gids[vi==j]:
            name=names[int(g)];c=m['cells'].get(name)
            if c is None:continue
            target=N.scalar(c['connections']['D']) if 'DFF' in c['type'].upper() else outs[name][0]
            cut,_,status=N.choose_cut(target,deps,**item.get('cut_rule_filter',{})) if item.get('cut_rule_filter') else N.choose_cut(target,deps,4,4)
            if status=='eligible':tasks.setdefault((target,tuple(cut)),dict(target_bit=target,cut_bits=cut))
        tasks=list(tasks.values());affected=[];checked=0
        for start in range(0,len(tasks),32):
            chunk=tasks[start:start+32];code=F.pruned_model(comp,width,chunk,N.bitref);nbatches+=1
            try:oldcode=old.pruned_model(oldcomp,width,chunk,N.bitref)
            except ValueError as e:
                assert str(e) in ('Undriven required bit 0','Undriven required bit 1');affected.append(start)
            else:assert oldcode==code
            for result in (folder/'queries'/item['view']/f'{start:05d}').glob('attempt_*/results.json'):
                before=sha(result);saved=json.loads(result.read_text())
                model=result.parent/'model.v';log=result.parent/'run.log'
                assert sha(model)==saved['model_sha'] and sha(log)==saved['log_sha']
                expected=code if saved.get('model_variant')=='cone_pruned_v1' else F.model_from_logic(logic,width,chunk,N.bitref)
                assert model.read_bytes()==expected.encode()
                baseline[str(result.relative_to(ROOT))]=before
                checked+=1;nmodels+=1
        row=dict(view=item['view'],tasks=len(tasks),batches=(len(tasks)+31)//32,
                 old_failure_batches=len(affected),first_old_failure=affected[0] if affected else None,
                 existing_models_identical=checked)
        reports.append(row);print(json.dumps(row),flush=True)
    assert any(r['old_failure_batches'] for r in reports)
    assert all(sha(ROOT/p)==h for p,h in baseline.items())
    dump('evidence_baseline.json',baseline)
    dump('verification.json',dict(time=datetime.now().astimezone().isoformat(),passed=True,
        solver_calls=0,training_runs=0,views=len(reports),generated_batches=nbatches,
        existing_models_identical=nmodels,evidence_unchanged=True,views_detail=reports,
        old_sha=sha(HERE/'k4_fast_support.before.py'),new_sha=sha(Path(F.__file__)),
        scope='All available bound validation raw snapshots; remaining snapshots not yet prepared.'))
    print('OFFLINE PASS',len(reports),nbatches,nmodels,flush=True)

if __name__=='__main__':main()
