"""s15850 ys_abc all-cell native extraction; no labels are inspected."""
import collections
import hashlib
import itertools
import json
import os
import sys
import shutil
import time
from pathlib import Path

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
T=Path(os.environ.get('SAT_T', str(ROOT/'10.15/06_统一评测协议/N4_三向泛化/tables/sat_k4_alltrain_round27')))
TABLES=ROOT/'10.15/06_统一评测协议/N4_三向泛化/tables'
sys.path.insert(0,str(ROOT/'phase2/ys'))
import sat_functional_relations as P0
import native_boundary_extract as N
from sat_boundary_semantics import classify, summarize, COLS
from k4_fast_support import compile_logic, model_from_logic, pruned_model
from k4_runtime import (sha, checked_yosys, fresh_dir, find_bound_batch,
                        complete_statuses, load_view_inputs, read_plan, dependency_index_fast, view_base_path)


def raw_snapshot(item):
    candidates=[]
    for rnd in (10,11,12):
        candidates.append(TABLES/f'sat_pair_round{rnd}'/'structures'/item['view'])
    root=T/'structures'/item['view']
    candidates += [root]+sorted(root.glob('attempt_*'))
    for folder in candidates:
        raw=folder/'raw.json'
        for binding in ('source.json','binding.json'):
            if raw.exists() and (folder/binding).exists():
                info=json.loads((folder/binding).read_text())
                if info['source_sha']==item['source_sha'] and info['raw_sha']==sha(raw):
                    return next(iter(json.loads(raw.read_text())['modules'].values())),folder
    folder=fresh_dir(root)
    raw=folder/'raw.json';src=ROOT/item['source'];top=P0.module_name(src)
    script=f'read_verilog "{P0.wsl(src)}"\nhierarchy -top {top}\nflatten\nproc -noopt\nwrite_json "{P0.wsl(raw)}"\n'
    checked_yosys(script,folder/'prepare.log',timeout=180)
    if not raw.exists():raise RuntimeError(f'Yosys produced no raw snapshot: {folder}')
    module=next(iter(json.loads(raw.read_text())['modules'].values()))
    write(folder/'binding.json',dict(source_sha=item['source_sha'],raw_sha=sha(raw)))
    return module,folder


def write(p,x): p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')


def main():
    plan=read_plan(T/'plan.json')
    ids,view_by_global,local,names=load_view_inputs(T)
    # Preserve partial derived artifacts before regenerating them; never touch query logs.
    old=[T/n for n in ('records.json','snapshots.json','real.npy','zero.npy','permuted.npy','permutation.json','coverage.json')]
    old += list(T.glob('*.records.json'))
    if any(p.exists() for p in old):
        backup=fresh_dir(T/'derived_backups','backup')
        for p in old:
            if p.exists():shutil.copy2(p,backup/p.name)
    records=[];snapshot_info=[]
    for item in plan['views']:
        assert sha(ROOT/item['source'])==item['source_sha']
        m,folder=raw_snapshot(item)
        raw_file=folder/'raw.json';raw_digest=sha(raw_file)
        raw_stamp=(raw_file.stat().st_size,raw_file.stat().st_mtime_ns)
        logic_lines,logic_width=N.logic(m);compiled_logic=compile_logic(logic_lines)
        drivers,deps=dependency_index_fast(m)
        outputs_by_cell=collections.defaultdict(list)
        for bit,(owner,pin) in drivers.items():outputs_by_cell[owner].append((pin,bit))
        rows=[]
        for n in ids:
            if view_by_global[int(n)]!=item['view']:continue
            cell=names[n].strip().lstrip('\\')
            c=m['cells'].get(cell)
            r=dict(global_node=int(n),local_node=local[int(n)],cell=cell,view=item['view'],split=item['split'],family=item['family'])
            if c is None:r['status']='graph_cell_missing'
            else:
                r['driver_type']=c['type']
                if 'DFF' in c['type'].upper():
                    root=N.scalar(c['connections']['D']);r['target_role']='DFF_data_D';r['target_pin']='D'
                else:
                    outs=outputs_by_cell[cell]
                    if len(outs)!=1:raise ValueError('Ambiguous cell output')
                    r['target_pin'],root=outs[0];r['target_role']='comb_output'
                cut,meta,status=N.choose_cut(root,deps,**plan['cut_rule_filter']) if 'cut_rule_filter' in plan else N.choose_cut(root,deps,4,4)
                r.update(target_bit=root,cut_bits=cut,k=len(cut),status=status,**meta)
            rows.append(r);records.append(r)
        snapshot_info.append(dict(view=item['view'],folder=str(folder.relative_to(ROOT)),raw_sha=raw_digest,source_sha=item['source_sha'],cells=len(m['cells']),graph_nodes=len(rows)))
        eligible=[r for r in rows if r['status']=='eligible']
        unique={}
        for r in eligible:
            key=(r['target_bit'],tuple(r['cut_bits']))
            unique.setdefault(key,[]).append(r)
        tasks=[v[0] for v in unique.values()]
        by_key={k:v for k,v in unique.items()}
        print(f"[VIEW] {item['view']} nodes={len(rows)} eligible={len(eligible)} unique_queries={len(tasks)}",flush=True)
        for batch_start in range(0,len(tasks),32):
            stop=os.environ.get('SAT_K4_STOP_FILE')
            if (stop and Path(stop).exists()) or shutil.disk_usage(ROOT).free < 4*2**30:
                raise RuntimeError('Stopped at batch boundary; committed evidence retained')
            chunk=tasks[batch_start:batch_start+32]
            batch=T/'queries'/item['view']/f'{batch_start:05d}';batch.mkdir(parents=True,exist_ok=True)
            result_file=batch/'results.json'
            if (raw_file.stat().st_size,raw_file.stat().st_mtime_ns)!=raw_stamp:
                raise RuntimeError('Raw snapshot changed during extraction')
            full_code=model_from_logic(logic_lines,logic_width,chunk,N.bitref)
            code=full_code
            qs=[]
            cmds=[f'read_verilog "{P0.wsl(batch/"model.v")}"','hierarchy -top check','proc','flatten','opt_clean']
            for i,r in enumerate(chunk):
                for pat in map(''.join,itertools.product('01',repeat=r['k'])):
                    for prove in (1,0):
                        qid=len(qs);binary=pat[::-1].rjust(4,'0')
                        args=f"-set pattern 4'b{binary} -set premise[{i}] 1 -prove target[{i}] {prove} -timeout 3"
                        witness=''
                        # Three predetermined ordinal cells/view get counterexample dumps.
                        if batch_start+i in (0,len(tasks)//2,len(tasks)-1):
                            witness=f' -show-inputs -show-outputs -dump_json "{P0.wsl(batch/f"{qid}.model.json")}"'
                        cmds += [f'log SATQ{qid:06d}',f'sat {args}{witness}']
                        qs.append(dict(query_id=qid,ordinal=batch_start+i,pattern=pat,prove=prove,args=args))
            script='\n'.join(cmds)+'\n'
            found=find_bound_batch(batch,full_code,script,item['source_sha'],raw_digest,len(qs),P0.parse_results)
            model_variant='full_legacy'
            if found is None and os.environ.get('SAT_K4_DISABLE_COI','0')!='1':
                code=pruned_model(compiled_logic,logic_width,chunk,N.bitref)
                model_variant='cone_pruned_v1'
                found=find_bound_batch(batch,code,script,item['source_sha'],raw_digest,len(qs),P0.parse_results)
            reused=False
            if found:
                batch,saved,statuses,script=found
                result_file=batch/'results.json'
                reused=True
            else:
                original=batch
                batch=fresh_dir(original)
                script=script.replace(P0.wsl(original),P0.wsl(batch))
                result_file=batch/'results.json'
                with (batch/'model.v').open('x',encoding='utf-8',newline='\n') as f:f.write(code)
                t=time.perf_counter()
                log=checked_yosys(script,batch/'run.log',timeout=600)
                statuses=complete_statuses(log,len(qs),P0.parse_results)
                saved=None
            measured={}
            for row,status in zip(qs,statuses):row['status']=status
            for i,r in enumerate(chunk):
                rr=[q for q in qs if q['ordinal']==batch_start+i];tab={}
                for pat in map(''.join,itertools.product('01',repeat=r['k'])):
                    ss={q['prove']:q['status'] for q in rr if q['pattern']==pat}
                    tab[pat]=classify(ss[1],ss[0])
                features,inputs=summarize(tab,r['k'])
                measured[str(batch_start+i)]=dict(table=tab,features=features,inputs=inputs)
            if saved is not None:
                # Replay interpretation, not SAT; refuse stale/corrupt derived data.
                assert json.dumps(saved['tables'],sort_keys=True)==json.dumps(measured,sort_keys=True)
            else:
                saved=dict(model_sha=sha(batch/'model.v'),script_sha=hashlib.sha256(script.encode()).hexdigest(),
                    log_sha=sha(batch/'run.log'),source_sha=item['source_sha'],raw_sha=raw_digest,model_variant=model_variant,
                    wall_s=0.0 if reused else time.perf_counter()-t,queries=qs,tables=measured,
                    recovered_without_solving=reused)
                write(result_file,saved)
            print(f"[EVIDENCE] {'reused' if reused else 'solved'} {result_file}",flush=True)
            for i,r in enumerate(chunk):
                result=measured[str(batch_start+i)]
                for dest in by_key[(r['target_bit'],tuple(r['cut_bits']))]:
                    dest.update(**result,evidence=str(result_file.relative_to(ROOT)),evidence_ordinal=batch_start+i)
            print(f"[BATCH] {batch_start+len(chunk)}/{len(tasks)} queries={len(qs)}",flush=True)
        if sha(raw_file)!=raw_digest:
            raise RuntimeError('Raw snapshot digest changed; refuse derived completion')
        write(T/(item['view']+'.records.json'),rows)
    write(T/'records.json',records);write(T/'snapshots.json',snapshot_info)
    real=np.zeros((len(ids),19),np.float32)
    for r in records:
        if r['status']=='eligible' and r['features']['has_unknown']==0:
            real[r['local_node'],:18]=[r['features'][c] for c in COLS];real[r['local_node'],18]=1
    perm=real.copy();rng=np.random.default_rng(20261026);permutation=[]
    for split in ('train','val','test'):
        for role in ('comb_output','DFF_data_D'):
            rr=[r for r in records if r['status']=='eligible' and r['split']==split and r['target_role']==role and real[r['local_node'],18]]
            ix=np.array([r['local_node'] for r in rr],dtype=np.int64);order=rng.permutation(len(ix)).astype(np.int64)
            if len(ix)>1 and np.array_equal(order,np.arange(len(ix))):order=np.roll(order,1)
            perm[ix,:18]=real[ix[order],:18]
            for dst,src in zip(ix,ix[order]):permutation.append(dict(destination=int(dst),source=int(src),split=split,role=role))
    zero=np.zeros_like(real);zero[:,18]=real[:,18]
    for name,arr in [('real',real),('permuted',perm),('zero',zero)]:np.save(T/(name+'.npy'),arr)
    write(T/'permutation.json',permutation)
    stats={}
    for split in ('train','val','test'):
        rr=[r for r in records if r['split']==split];idx=np.array([r['local_node'] for r in rr]);covered=[r for r in rr if real[r['local_node'],18]]
        forced=[r for r in covered if r['features']['forced_fraction']>0];influenced=[r for r in covered if r['features']['change_on_comparable']>0]
        nonlocal_rows=[r for r in covered if r['nonlocal_cut']]
        signatures=collections.defaultdict(set)
        for r in covered:signatures[(r['driver_type'],r['target_role'])].add(tuple(r['features'].values()))
        stats[split]=dict(nodes=len(rr),queried=sum(r['status']=='eligible' for r in rr),covered=len(covered),coverage=(len(covered)/len(rr) if rr else 0.0),forced_evidence=len(forced),influence_evidence=len(influenced),nonlocal_nodes=len(nonlocal_rows),unique_profiles=(len(np.unique(real[[r['local_node'] for r in covered],:18],axis=0)) if covered else 0),same_type_multiple_profiles=sum(len(v)>1 for v in signatures.values()),permutation_changed_nodes=int(np.any(real[idx,:18]!=perm[idx,:18],axis=1).sum()) if len(idx) else 0,excluded=dict(collections.Counter(r['status'] for r in rr if r['status']!='eligible')))
    batches={r['evidence'] for r in records if 'evidence' in r};nq=sum(len(json.loads((ROOT/p).read_text())['queries']) for p in batches)
    gate=all(stats[s]['coverage']>=0.8 and stats[s]['unique_profiles']>=10 and stats[s]['permutation_changed_nodes']>=stats[s]['covered']*0.3 and stats[s]['same_type_multiple_profiles']>0 for s in ('train','val','test') if stats[s]['nodes']>0)
    info=dict(splits=stats,actual_sat_queries=nq,gate_passed=gate,gate_scope='nonempty splits only; engineering information/coverage gate, not predictive gain', repair_version='20261028', model_generation='full_legacy_or_cone_pruned_v1', extractor_sha=sha(Path(__file__)), support_sha=sha(Path(__file__).with_name('k4_fast_support.py')), permutation_scope='split+target_role only; diagnostic, not training-ready',columns=COLS+['covered'],test_labels_read=False,base_file=view_base_path(T).name,base_sha=sha(view_base_path(T)),feature_sha={a:sha(T/(a+'.npy')) for a in ('real','permuted','zero')})
    write(T/'coverage.json',info);print(json.dumps(info,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':main()
