"""Evaluate Task 1 checkpoints on paired keep views using frozen endpoint evidence."""
import argparse
import csv
import importlib.util
import json
import math
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import average_precision_score

from audit_task2_nokeep_20261113 import P, ROOT, CONFIRM, inspect_log, local, read, rows, sha

OUT = P / 'task2_nokeep_audit_20261113'
RUN = P / 'seed42_nc_ablation_20261109'
SEEDS = (42, 1, 2)
NORM = P / 'control_boundary_v3_20261104/normalization.npz'
CAL = P / 'seed42_nc_eval_v3_20261109/EVAL_V3_ALL.json'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def dump(path, data):
    with path.open('x', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False)


def write_csv(path, data):
    with path.open('x', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(data[0]))
        w.writeheader()
        w.writerows(data)


def endpoint_eval(margin, graph, entries, kind):
    group = {}
    for e in entries:
        if not e['rankable'] or e['kind'] != kind:
            continue
        i = e['packed_index']
        members = graph['members'][graph['ptr'][i]:graph['ptr'][i+1]]
        assert len(members) and graph['physical'][members].all()
        assert e['endpoint'] not in group
        group[e['endpoint']] = (e['status'], set(members.tolist()), float(margin[members].max()))
    order = sorted(group, key=lambda n: (-group[n][2], n))
    support = Counter(g[0] for g in group.values())
    positives = [n for n in order if group[n][0]=='positive']
    assert positives and support['negative']
    known = [group[n] for n in order if group[n][0]!='unknown']
    known_ap = average_precision_score([a[0]=='positive' for a in known], [a[2] for a in known])
    covered, budget = set(), Counter()
    for n in order:
        label, members, _ = group[n]
        updated = covered | members
        if len(updated)>512:
            break
        covered = updated
        budget[label] += 1
    cutoff = group[positives[-1]][2]
    at_recall = [group[n] for n in order if group[n][2]>=cutoff]
    counts = Counter(a[0] for a in at_recall)
    assert counts['positive']==len(positives)
    return dict(positive=len(positives), negative=support['negative'], unknown=support['unknown'], cone_ap=known_ap,
                top1=sum(group[n][0]=='positive' for n in order[:1])/len(positives),
                top5=sum(group[n][0]=='positive' for n in order[:5])/len(positives),
                top10=sum(group[n][0]=='positive' for n in order[:10])/len(positives),
                recall512=budget['positive']/len(positives), gates512=len(covered),
                fp512=budget['negative'], unknown512=budget['unknown'], equal_fp=counts['negative'],
                equal_unknown=counts['unknown'], equal_gates=len(set().union(*(a[1] for a in at_recall))))


def validation_threshold(seed, arm, point, evaluation):
    suffix = '' if seed==42 else f'_s{seed}'
    with np.load(RUN / f'{arm}{suffix}_scores.npz') as saved:
        physical = np.load(P / 'control_boundary_v3_20261104/inputs/trans_val/physical.npy')
        positive = (saved['y_val']==1) & saved['trust_val'].astype(bool) & physical.astype(bool)
        values = np.sort(saved[f'val_{point}'][positive])[::-1]
    cutoff = float(values[math.ceil(.95*len(values))-1])
    record = evaluation[f'{arm}_s{seed}_{point}']['equal_recall']['A_val_transfer']['0.95']
    assert cutoff == record['threshold']
    return cutoff


def evaluate(label, assets, manifest):
    model_type = module('task2_model', P / 'control_best200_20261104/evaluate.py').Model
    model = model_type().cuda().eval().requires_grad_(False)
    with np.load(NORM) as n:
        mean, std = n['mean'][25:], n['std'][25:]
    assert (std>0).all()
    graphs = {}
    known = []
    for r in manifest:
        f = assets / r['view']
        graph_file, meta_file = f / 'GRAPH_ENDPOINTS.npz', f / 'ENDPOINTS.json'
        assert sha(graph_file)==r['graph_sha256'] and sha(meta_file)==r['endpoint_sha256']
        with np.load(graph_file) as d:
            graph = {k:d[k] for k in d.files}
        assert graph['x39'].shape[1]==39 and np.isfinite(graph['x39']).all()
        meta = read(meta_file)
        assert len(graph['ptr'])-1==sum(e['rankable'] for e in meta)
        known.append({(e['kind'],e['endpoint'],e['status']) for e in meta if e['rankable'] and e['status']!='unknown'})
        x = graph['x39'].copy()
        x[:,25:] = np.clip((x[:,25:]-mean)/std,-10,10)
        graphs[r['view']] = graph, meta, torch.as_tensor(x,device='cuda'), torch.as_tensor(graph['edge_index'],device='cuda')
    shared = set.intersection(*known)
    assert all({x for x in s if x[2]=='positive'}=={x for x in shared if x[2]=='positive'} for s in known)
    if label=='s38584':
        full_meta = {v:data[1] for v,data in graphs.items()}
        for v, (graph, meta, x, edge) in graphs.items():
            matched = [dict(e,status='unknown') if e['rankable'] and (e['kind'],e['endpoint'],e['status']) not in shared else e for e in meta]
            graphs[v] = graph,matched,x,edge
    else:
        assert all(s==shared for s in known)
    evaluation = read(CAL)
    prior = P / 'lcone_injdelta_confirmation_20261112'
    prior_contract = read(prior / 'CONTRACT.json')
    old = {(r['view'],int(r['seed']),r['setting']):r for r in rows(prior / 'BY_VIEW.csv')
           if r['policy']=='endpoint' and r['arm']=='A'}
    results, sensitivity, margins, hashes = [], [], {}, {}
    forwards, reused = 0, 0
    for seed in SEEDS:
        for arm in ('N','NC'):
            for point in ('best','last'):
                suffix = '' if seed==42 else f'_s{seed}'
                ckpt = RUN / f'{arm}{suffix}_{point}.pt'
                key = f'{arm}_s{seed}_{point}'
                hashes[key] = sha(ckpt)
                threshold = validation_threshold(seed,arm,point,evaluation)
                use_old = label=='s38417' and arm=='N' and point=='best'
                if use_old:
                    assert hashes[key] == prior_contract['checkpoints'][str(seed)][f'{RUN.name}\\{ckpt.name}']
                    assert prior_contract['normalization_sha256']==sha(NORM)
                else:
                    model.load_state_dict(torch.load(ckpt,map_location='cpu',weights_only=True),strict=True)
                for view, (graph, meta, x, edge) in graphs.items():
                    if use_old:
                        with np.load(prior / f'{view}_s{seed}_SCORES.npz') as d:
                            margin = d['margin']
                        reused += 1
                    else:
                        with torch.inference_mode(), torch.autocast('cuda',dtype=torch.bfloat16):
                            logits = model(x,edge).float()
                        margin = (logits[:,1]-logits[:,0]).cpu().numpy()
                        forwards += 1
                    assert len(margin)==len(graph['physical']) and np.isfinite(margin).all()
                    margins[f'{key}__{view}'] = margin
                    physical_scores = margin[graph['physical']]
                    alarm = int((physical_scores>=threshold).any())
                    for kind in ('D','PO'):
                        r = endpoint_eval(margin,graph,meta,kind)
                        if use_old and kind=='D':
                            for setting,cols in [('gates_512',('recall512','gates512','fp512','unknown512')),
                                                 ('recall_100',(None,'equal_gates','equal_fp','equal_unknown'))]:
                                a = old[view,seed,setting]
                                assert all(r[k]==float(a[n]) for k,n in zip(cols,('recall','gates','negative','unknown')) if k)
                        results.append(dict(view=view,recipe=view.rsplit('__ys_',1)[1],keep=view.split('__')[2],
                                            seed=seed,arm=arm,point=point,kind=kind,**r, alarm_threshold=threshold,
                                            graph_alarm=alarm, alarm_nodes=int((physical_scores>=threshold).sum()),
                                            graph_max=float(physical_scores.max())))
                        if label=='s38584':
                            full = endpoint_eval(margin,graph,full_meta[view],kind)
                            assert all(r[k]==full[k] for k in ('top1','top5','top10','recall512','gates512','equal_gates'))
                            sensitivity.append(dict(view=view,seed=seed,arm=arm,point=point,kind=kind,**full))
    assert len(results)==96
    write_csv(OUT / f'{label}_N_NC_BY_SEED.csv',results)
    if sensitivity:
        write_csv(OUT / f'{label}_N_NC_VIEW_NATIVE_GT.csv',sensitivity)
    with (OUT / f'{label}_N_NC_SCORES.npz').open('xb') as f:
        np.savez_compressed(f,**margins)
    aggregate = []
    grouped = defaultdict(list)
    for r in results:
        grouped[tuple(r[k] for k in ('recipe','keep','kind','point','arm'))].append(r)
    metrics = ('cone_ap','top1','top5','top10','recall512','gates512','fp512','unknown512','equal_fp','equal_unknown',
               'equal_gates','graph_alarm','alarm_nodes')
    for key, items in sorted(grouped.items()):
        assert {r['seed'] for r in items}==set(SEEDS)
        aggregate.append(dict(zip(('recipe','keep','kind','point','arm'),key),
                              **{k:st.mean(r[k] for r in items) for k in metrics}))
    write_csv(OUT / f'{label}_N_NC_MEANS.csv',aggregate)
    dump(OUT / f'{label}_N_NC_PROTOCOL.json',dict(checkpoints=hashes,norm=sha(NORM),calibration=sha(CAL),
         shared_gt=dict(Counter(f'{k}|{s}' for k,_,s in shared)),
         reused_score_sets=reused,new_forward_sets=forwards,optimizer_steps=0,sat_cec_calls=0,labels_modified=False))
    print(label, 'evaluated', len(results), 'rows', forwards, 'forwards', flush=True)


def bind_s38584():
    # Build only the graph and replay frozen vectors, without searching for a witness.
    b = module('task2_graph_builder', CONFIRM / 'build.py')
    a = sys.modules['audit']
    s = b.S
    source = 's38584t100__injdelta_d1_s42'
    plain_evidence_path = P / 'lcone_endpoint_frozen_20261112/EVIDENCE.json'
    saved = defaultdict(dict)
    for e in read(plain_evidence_path)['endpoints']:
        if e['view'].rsplit('__ys_',1)[0]==source and e['status'] in ('positive','negative'):
            assert e['split']=='test' and e['cache_exact']
            saved[e['view']][tuple(e['cone_id'].split(':',1))] = e
    clean = ROOT / 'generate_trans/hosts/s38584t100/base/s38584t100_clean.v'
    original_plain = s.F / 'orig' / f'{source}.v'
    provenance, = [r for r in read(clean.parent.parent / 'provenance.json') if r['view']==source]
    cec = {Path(r['log']).stem:r for r in rows(P / 'heldout_composition_20261110/CEC_STAGE3B.csv') if r['view']==source}
    inventory = [r for r in rows(OUT / 'PANEL40.csv') if r['source']==source]
    assert len(inventory)==len(cec)==4
    lib = b.V.load_library(s.F / 'verilog_lib.v')
    mapping = {r['full_gate_name']:r['simplified_gate_type'] for r in read(s.F / 'gate_full_to_simplified_mapping.json')}
    gate_order = read(s.F / 'gatelookup_recommended.json')['simplified_gate_type_order']
    assets = OUT / 's38584_graphs'
    assets.mkdir(exist_ok=True)
    reports, checks = [], []
    for r in inventory:
        target = local(r['path'])
        log = local(cec[target.stem]['log'])
        orig, actual, _ = inspect_log(log)
        assert target==actual and sha(target)==r['target_sha256'] and sha(log)==r['log_sha256']
        plain = s.F / 'trans' / f"{source}__ys_{r['recipe']}.v"
        clean_g, orig_g, target_g, plain_orig_g, plain_g = [a.endpoints(p) for p in (clean,orig,target,original_plain,plain)]
        inserted, aliases, missing = a.bind_lineage(provenance,clean_g,orig_g)
        _, plain_aliases, _ = a.bind_lineage(provenance,clean_g,plain_orig_g)
        state, _, _ = a.binding(clean_g,orig_g,target_g,aliases)
        plain_state, _, _ = a.binding(clean_g,plain_orig_g,plain_g,plain_aliases)
        expr = a.Expressions()
        evaluate_roots = [a.construct(g,expr,state) for g in (clean_g,orig_g,target_g)]
        evaluate_plain = [a.construct(g,expr,plain_state) for g in (clean_g,plain_orig_g,plain_g)]
        raw = target_g[0]
        physical = [n for n in raw['cells'] if n not in set(raw['virtual_names'])]
        net, parsed, x, names, indices = b.graph(target,physical,lib,mapping,gate_order)
        ends = [('D',n,dict(pins)['D']) for n,(typ,pins) in net['pins'].items() if 'DFF' in typ and 'D' in dict(pins)]
        ends += [('PO',p,p) for p in sorted(target_g[2])]
        old = saved[plain.stem]
        expected = {k for k,e in old.items() if e['status']=='positive'}
        meta, ptr, members, proven = [], [0], [], set()
        for kind, name, signal in ends:
            key = kind,name
            entry = dict(kind=kind,endpoint=name,status='unknown',rankable=False)
            meta.append(entry)
            cells, issues = a.structural_cone(target_g,signal)
            owners = net['drivers'].get(net['find'](signal),set())
            phys = sorted(indices[g] for g in cells if indices[g]<len(physical))
            if len(owners)!=1 or issues or not phys:
                continue
            driver, = owners
            assert driver in cells
            entry.update(rankable=True,driver_row=indices[driver],packed_index=len(ptr)-1)
            members.extend(phys)
            ptr.append(len(members))
            try:
                if kind=='D':
                    if name not in state:
                        continue
                    nets = [dict(g[0]['pins'][name][1])['D'] for g in (clean_g,orig_g,target_g)]
                else:
                    if not all(name in g[2] for g in (clean_g,orig_g,target_g)):
                        continue
                    nets = [name]*3
                assert nets[-1]==signal
                evaluated = [ev(n) for ev,n in zip(evaluate_roots,nets)]
                assert evaluated[-1][1]==cells
                roots = [e[0] for e in evaluated]
                if key in expected:
                    evidence = old[key]
                    assignment = evidence['witness']['assignment']
                    variables = set().union(*(expr.inputs(z) for z in roots))
                    assert set(assignment) >= variables and not missing
                    assert inserted.intersection(evaluated[1][1])
                    if kind=='D':
                        assert name in plain_state
                        nets_plain = [dict(g[0]['pins'][name][1])['D'] for g in (clean_g,plain_orig_g,plain_g)]
                    else:
                        assert all(name in g[2] for g in (clean_g,plain_orig_g,plain_g))
                        nets_plain = [name]*3
                    roots_plain = [ev(n)[0] for ev,n in zip(evaluate_plain,nets_plain)]
                    truth = expr.evaluator(assignment,1)
                    assert [truth(z) for z in roots_plain]==evidence['witness']['clean_orig_trans']
                    value = [truth(z) for z in roots]
                    assert value==evidence['witness']['clean_orig_trans'] and value[0]!=value[1]==value[2]
                    entry['status'] = 'positive'
                    proven.add(key)
                    checks.append(dict(view=target.stem,kind=kind,endpoint=name,clean_net=nets[0],source_net=nets[1],
                                       target_net=signal,driver=driver,variables=len(variables),vector_inputs=len(assignment),
                                       outcome='|'.join(map(str,value)),source_lineage='|'.join(sorted(inserted.intersection(evaluated[1][1])))))
                elif len(set(roots))==1:
                    entry['status'] = 'negative'
                elif key in old and old[key]['status']=='negative':
                    if kind=='D':
                        if name not in plain_state:
                            continue
                        plain_nets = [dict(g[0]['pins'][name][1])['D'] for g in (clean_g,plain_orig_g,plain_g)]
                    else:
                        if not all(name in g[2] for g in (clean_g,plain_orig_g,plain_g)):
                            continue
                        plain_nets = [name]*3
                    if roots == [ev(n)[0] for ev,n in zip(evaluate_plain,plain_nets)]:
                        entry['status'] = 'negative'
            except (KeyError, ValueError, RecursionError):
                if key in expected:
                    raise
        assert proven==expected and Counter(k for k,_ in proven)=={'D':5,'PO':1}
        support = Counter(f"{e['kind']}|{e['status']}" for e in meta if e['rankable'])
        assert support['D|negative'] and support['PO|negative']
        folder = assets / target.stem
        folder.mkdir()
        graph_path, endpoint_path = folder / 'GRAPH_ENDPOINTS.npz', folder / 'ENDPOINTS.json'
        with graph_path.open('xb') as f:
            np.savez_compressed(f,x39=x,edge_index=parsed['edge_index'],names=np.array(names),
                                physical=np.arange(len(names))<len(physical),members=np.array(members),ptr=np.array(ptr))
        dump(endpoint_path,meta)
        reports.append(dict(view=target.stem,source=source,counts=dict(support),rankable=len(ptr)-1,
                       graph_sha256=sha(graph_path),endpoint_sha256=sha(endpoint_path),target_sha256=sha(target),
                       log_sha256=sha(log),plain_sha256=sha(plain),old_evidence_sha256=sha(plain_evidence_path)))
        print(target.stem, support, flush=True)
        expr.inputs.cache_clear()
    write_csv(OUT / 's38584_WITNESS_REPLAY.csv',checks)
    dump(OUT / 's38584_GRAPH_REPORT.json',dict(views=reports,solver_calls=0,labels_modified=False))


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action',choices=('s38417','bind_s38584','s38584'))
    action = parser.parse_args().action
    if action=='s38417':
        evaluate(action,CONFIRM,read(CONFIRM / 'GRAPH_REPORT.json')['views'])
    elif action=='bind_s38584':
        bind_s38584()
    else:
        evaluate(action,OUT / 's38584_graphs',read(OUT / 's38584_GRAPH_REPORT.json')['views'])
