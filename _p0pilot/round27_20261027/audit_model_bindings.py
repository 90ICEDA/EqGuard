"""Regenerate native models in memory from frozen coordinates, without SAT."""
import collections
import json
import sys
import time
from pathlib import Path
import numpy as np
import k4_runtime as R
from k4_fast_support import compile_logic, model_from_logic, pruned_model

sys.path.insert(0, str(R.ROOT/'phase2/ys'))
import native_boundary_extract as N


def main():
    with np.load(R.PANEL/'base_inputs.npz') as z:
        gids,vi=z['global_ids'],z['view_index']
    selected=[];needed=set();idmap={}
    for j,item in enumerate(R.read_plan(R.PANEL/'plan.json')['views']):
        folder=R.PANEL/'views'/item['view']
        batches=list((folder/'queries'/item['view']).rglob('results.json'))
        if batches:
            ids=gids[vi==j];idmap[item['view']]=ids;needed.update(map(int,ids))
            selected.append((item,batches))
    names={}
    path=R.ROOT/'generate_trans/folds/hosts_bt31/data/processed/node_names_trans.txt'
    with path.open(encoding='utf-8') as f:
        for i,line in enumerate(f):
            if i in needed:names[i]=line.strip().lstrip('\\')
            if len(names)==len(needed):break
    report=dict(views=0,regenerated_models=0,errors=[],dependency_timings=[],solver_calls=0)
    for item,batches in selected:
        first=json.loads(batches[0].read_text());v=item['view']
        folder=R.PANEL/'views'/v/'structures'/v
        candidates=[folder/'raw.json']+list(folder.glob('attempt_*/raw.json'))
        for rnd in (10,11,12):
            candidates.append(R.TABLES/f'sat_pair_round{rnd}'/'structures'/v/'raw.json')
        raw=next((p for p in candidates if p.exists() and R.sha(p)==first['raw_sha']),None)
        if raw is None:
            report['errors'].append([v,'missing matching raw']);continue
        m=next(iter(json.loads(raw.read_text())['modules'].values()));logic_lines,logic_width=N.logic(m);compiled_logic=compile_logic(logic_lines)
        t=time.perf_counter();old=N.dependency_index(m);old_s=time.perf_counter()-t
        t=time.perf_counter();drivers,deps=R.dependency_index_fast(m);new_s=time.perf_counter()-t
        if old!=(drivers,deps):raise ValueError('Optimized dependency index differs')
        report['dependency_timings'].append(dict(view=v,original_s=old_s,optimized_s=new_s))
        outs=collections.defaultdict(list)
        for bit,(owner,pin) in drivers.items():outs[owner].append(bit)
        unique={}
        for g in idmap[v]:
            cell=m['cells'][names[int(g)]]
            target=N.scalar(cell['connections']['D']) if 'DFF' in cell['type'].upper() else outs[names[int(g)]][0]
            cut,_,status=N.choose_cut(target,deps,4,4)
            if status=='eligible':
                unique.setdefault((target,tuple(cut)),dict(target_bit=target,cut_bits=cut))
        tasks=list(unique.values())
        for p in batches:
            start=int(p.parent.name if p.parent.name.isdigit() else p.parent.parent.name)
            saved=json.loads(p.read_text());variant=saved.get('model_variant','full_legacy')
            if variant=='full_legacy':code=model_from_logic(logic_lines,logic_width,tasks[start:start+32],N.bitref)
            elif variant=='cone_pruned_v1':code=pruned_model(compiled_logic,logic_width,tasks[start:start+32],N.bitref)
            else:raise ValueError('Unrecognized model variant: '+str(variant))
            if code.encode()!=(p.parent/'model.v').read_bytes():
                report['errors'].append([str(p),'model mismatch'])
            else:report['regenerated_models']+=1
        report['views']+=1
    out=R.fresh_dir(Path(__file__).parent/'repair_audits','model_audit')
    R.write_new(out/'models.json',report)
    print(json.dumps({k:v for k,v in report.items() if k!='dependency_timings'}))
    print(out)
    if report['errors']:raise SystemExit(1)


if __name__=='__main__':main()
