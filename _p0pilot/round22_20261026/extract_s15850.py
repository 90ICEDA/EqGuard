"""s15850 ys_abc all-cell native extraction; no labels are inspected."""
import collections
import hashlib
import itertools
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import torch

ROOT=Path(__file__).resolve().parents[2]
T=Path(os.environ.get('SAT_T', str(ROOT/'10.15/06_统一评测协议/N4_三向泛化/tables/sat_s15850_round22')))
TABLES=T.parent
sys.path.insert(0,str(ROOT/'phase2/ys'))
import sat_functional_relations as P0
import native_boundary_extract as N
from sat_boundary_semantics import classify, summarize, COLS


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def raw_snapshot(item):
    for rnd in (10,11,12):
        folder=TABLES/f'sat_pair_round{rnd}'/'structures'/item['view']
        if (folder/'source.json').exists():
            info=json.loads((folder/'source.json').read_text())
            if info['source_sha']==item['source_sha'] and info['raw_sha']==sha(folder/'raw.json'):
                return next(iter(json.loads((folder/'raw.json').read_text())['modules'].values())),folder
    folder=T/'structures'/item['view'];folder.mkdir(parents=True,exist_ok=True)
    raw=folder/'raw.json'
    if raw.exists():
        info=json.loads((folder/'binding.json').read_text())
        assert info['source_sha']==item['source_sha'] and info['raw_sha']==sha(raw)
    else:
        src=ROOT/item['source'];top=P0.module_name(src)
        script=f'read_verilog "{P0.wsl(src)}"\nhierarchy -top {top}\nflatten\nproc -noopt\nwrite_json "{P0.wsl(raw)}"\n'
        log=P0.run_yosys(script,folder/'prepare.log',timeout=180)
        if 'ERROR:' in log: raise RuntimeError(log[-500:])
        (folder/'binding.json').write_text(json.dumps(dict(source_sha=item['source_sha'],raw_sha=sha(raw)),indent=2))
    return next(iter(json.loads(raw.read_text())['modules'].values())),folder


def write(p,x): p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')


def main():
    plan=json.loads((T/'plan.json').read_text());h=plan.pop('plan_sha')
    assert hashlib.sha256(json.dumps(plan,sort_keys=True).encode()).hexdigest()==h
    P=ROOT/'generate_trans/folds/hosts_bt31/data/processed'
    BASE=ROOT/'10.15/06_统一评测协议/N4_三向泛化/tables/sat_s15850_round22/base_inputs.npz'
    BASE_PLAN=ROOT/'10.15/06_统一评测协议/N4_三向泛化/tables/sat_s15850_round22/plan.json'
    names=(P/'node_names_trans.txt').read_text(encoding='utf-8').splitlines()
    selected={x['view']:x for x in plan['views']}
    view_order={r['view']:i for i,r in enumerate(plan['views'])}
    if BASE.exists():
        # Use the frozen 30k-node base; avoids loading the 3.2M-node graph and
        # makes a single-view run memory-feasible alongside other work.
        z=np.load(BASE)
        base_plan=json.loads(BASE_PLAN.read_text(encoding='utf-8'))
        base_names=[r['view'] for r in base_plan['views']]
        base_ids=z['global_ids'];base_vi=z['view_index'];base_x=z['x'];base_edges=z['edge_index']
        mask=np.array([base_names[int(v)] in selected for v in base_vi])
        ids=base_ids[mask]
        view_by_global={int(g):base_names[int(v)] for g,v in zip(base_ids,base_vi)}
        local={int(n):i for i,n in enumerate(ids)}
        if not (T/'base_inputs.npz').exists():
            base_positions=np.flatnonzero(mask)
            pos={int(p):i for i,p in enumerate(base_positions)}
            keep=np.array([int(a) in pos and int(b) in pos
                           for a,b in zip(base_edges[0],base_edges[1])],bool)
            edges=np.array([[pos[int(a)],pos[int(b)]] for a,b in zip(base_edges[0,keep],base_edges[1,keep])],np.int64)
            vi=np.array([view_order[view_by_global[int(g)]] for g in ids],np.int64)
            assert np.all(vi[edges[0]]==vi[edges[1]])
            np.savez_compressed(T/'base_inputs.npz',global_ids=ids,x=base_x[mask],
                                edge_index=edges,view_index=vi)
    else:
        g=torch.load(P/'trans_graph.pt',map_location='cpu',weights_only=False,mmap=True)
        ids=np.array([i for i,v in enumerate(g.file_ids) if v in selected],dtype=np.int64)
        view_by_global={int(n):g.file_ids[int(n)] for n in ids}
        local={int(n):i for i,n in enumerate(ids)}
        if not (T/'base_inputs.npz').exists():
            reverse=np.full(g.num_nodes,-1,np.int64);reverse[ids]=np.arange(len(ids))
            ei=g.edge_index.numpy();keep=(reverse[ei[0]]>=0)&(reverse[ei[1]]>=0)
            edges=reverse[ei[:,keep]]
            vi=np.array([view_order[g.file_ids[n]] for n in ids],np.int64)
            assert np.all(vi[edges[0]]==vi[edges[1]])
            np.savez_compressed(T/'base_inputs.npz',global_ids=ids,x=g.x[torch.from_numpy(ids)].numpy(),edge_index=edges,view_index=vi)
    records=[];snapshot_info=[]
    for item in plan['views']:
        assert sha(ROOT/item['source'])==item['source_sha']
        m,folder=raw_snapshot(item);N.logic(m);drivers,deps=N.dependency_index(m)
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
                    outs=[(pin,b) for b,(cn,pin) in drivers.items() if cn==cell]
                    if len(outs)!=1:raise ValueError('Ambiguous cell output')
                    r['target_pin'],root=outs[0];r['target_role']='comb_output'
                cut,meta,status=N.choose_cut(root,deps,**plan['cut_rule_filter']) if 'cut_rule_filter' in plan else N.choose_cut(root,deps,4,4)
                r.update(target_bit=root,cut_bits=cut,k=len(cut),status=status,**meta)
            rows.append(r);records.append(r)
        snapshot_info.append(dict(view=item['view'],folder=str(folder.relative_to(ROOT)),raw_sha=sha(folder/'raw.json'),source_sha=item['source_sha'],cells=len(m['cells']),graph_nodes=len(rows)))
        eligible=[r for r in rows if r['status']=='eligible']
        unique={}
        for r in eligible:
            key=(r['target_bit'],tuple(r['cut_bits']))
            unique.setdefault(key,[]).append(r)
        tasks=[v[0] for v in unique.values()]
        by_key={k:v for k,v in unique.items()}
        print(f"[VIEW] {item['view']} nodes={len(rows)} eligible={len(eligible)} unique_queries={len(tasks)}",flush=True)
        for batch_start in range(0,len(tasks),32):
            chunk=tasks[batch_start:batch_start+32]
            batch=T/'queries'/item['view']/f'{batch_start:05d}';batch.mkdir(parents=True,exist_ok=True)
            result_file=batch/'results.json'
            code=N.model(m,chunk)
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
            if result_file.exists():
                saved=json.loads(result_file.read_text());assert saved['model_sha']==hashlib.sha256(code.encode()).hexdigest()
                assert saved['script_sha']==hashlib.sha256(script.encode()).hexdigest();assert sha(batch/'run.log')==saved['log_sha']
                measured=saved['tables']
            else:
                if (batch/'run.log').exists():raise RuntimeError('Unconsolidated evidence: audit rather than overwrite')
                (batch/'model.v').write_text(code,encoding='utf-8',newline='\n')
                t=time.perf_counter();log=P0.run_yosys(script,batch/'run.log',timeout=600)
                statuses=P0.parse_results(log)
                if len(statuses)!=len(qs): raise RuntimeError('Incomplete batch: preserve logs')
                measured={}
                for row,s in zip(qs,statuses):row['status']=s
                for i,r in enumerate(chunk):
                    rr=[q for q in qs if q['ordinal']==batch_start+i];tab={}
                    for pat in map(''.join,itertools.product('01',repeat=r['k'])):
                        ss={q['prove']:q['status'] for q in rr if q['pattern']==pat};tab[pat]=classify(ss[1],ss[0])
                    features,inputs=summarize(tab,r['k'])
                    measured[str(batch_start+i)]=dict(table=tab,features=features,inputs=inputs)
                saved=dict(model_sha=sha(batch/'model.v'),script_sha=hashlib.sha256(script.encode()).hexdigest(),log_sha=sha(batch/'run.log'),source_sha=item['source_sha'],raw_sha=sha(folder/'raw.json'),wall_s=time.perf_counter()-t,queries=qs,tables=measured)
                write(result_file,saved)
            for i,r in enumerate(chunk):
                result=measured[str(batch_start+i)]
                for dest in by_key[(r['target_bit'],tuple(r['cut_bits']))]:
                    dest.update(**result,evidence=str(result_file.relative_to(ROOT)),evidence_ordinal=batch_start+i)
            print(f"[BATCH] {batch_start+len(chunk)}/{len(tasks)} queries={len(qs)}",flush=True)
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
        stats[split]=dict(nodes=len(rr),queried=sum(r['status']=='eligible' for r in rr),covered=len(covered),coverage=(len(covered)/len(rr) if rr else 0.0),forced_evidence=len(forced),influence_evidence=len(influenced),nonlocal_nodes=len(nonlocal_rows),unique_profiles=(len(np.unique(real[idx,:18],axis=0)) if len(idx) else 0),same_type_multiple_profiles=sum(len(v)>1 for v in signatures.values()),permutation_changed_nodes=int(np.any(real[idx,:18]!=perm[idx,:18],axis=1).sum()) if len(idx) else 0,excluded=dict(collections.Counter(r['status'] for r in rr if r['status']!='eligible')))
    batches=list((T/'queries').rglob('results.json'));nq=sum(len(json.loads(p.read_text())['queries']) for p in batches)
    gate=all(stats[s]['coverage']>=0.8 and stats[s]['unique_profiles']>=10 and stats[s]['permutation_changed_nodes']>=stats[s]['covered']*0.3 and stats[s]['same_type_multiple_profiles']>0 for s in ('train','val'))
    info=dict(splits=stats,actual_sat_queries=nq,gate_passed=gate,gate_scope='engineering information/coverage gate, not predictive gain',columns=COLS+['covered'],test_labels_read=False,base_sha=sha(T/'base_inputs.npz'),feature_sha={a:sha(T/(a+'.npy')) for a in ('real','permuted','zero')})
    write(T/'coverage.json',info);print(json.dumps(info,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':main()
