"""Compute offline bounds for exact gate matching in the frozen G0 slots."""
from collections import Counter, defaultdict

import networkx as nx
import numpy as np

from build import ROOT, csv_out, nl
from run_swap import ASSETS, OUT, digest, read, rows, t, write_json


def solve(occurrences, groups, cap, budget=None):
    graph = nx.DiGraph()
    graph.add_nodes_from(('start','end'))
    for (step, donor), (gate, _) in occurrences.items():
        s,d = ('step',step),('donor',donor)
        graph.add_edge('start',s,capacity=1)
        graph.add_edge(s,d,capacity=1)
        graph.add_edge(d,('gate',gate),capacity=1)
    for gate, candidates in groups.items():
        for i in range(cap):
            lane = ('lane',gate,i)
            graph.add_edge(('gate',gate),lane,capacity=len(candidates),weight=i)
            graph.add_edge(lane,'end',capacity=len(candidates))
    if budget is None:
        result = nx.maximum_flow_value(graph,'start','end',flow_func=nx.algorithms.flow.dinitz)
        assert nx.minimum_cut_value(graph,'start','end',flow_func=nx.algorithms.flow.preflow_push)==result
        return result
    graph.nodes['start']['demand'] = -budget
    graph.nodes['end']['demand'] = budget
    _, flow = nx.network_simplex(graph)
    picks = defaultdict(list)
    for (step, donor), (gate, slot) in occurrences.items():
        if flow['start'][('step',step)] and flow['step',step]['donor',donor]:
            picks[gate].append((step,donor,slot))
    assert sum(map(len,picks.values())) == budget
    return picks


def main():
    loader = t.FiveGroupLoader(verify_hashes=False)
    assert digest(OUT/'SCHEDULE.npz') == read(OUT/'PREFLIGHT.json')['schedule_sha']
    ds = loader.arrays('orig','train')
    names = (ASSETS.parent/'round32_20261029/orig_names/node_names_orig.txt').read_text(encoding='utf-8').splitlines()
    folds = ROOT/'generate_trans/folds/hosts_bt31'
    lib = nl.load_library(folds/'verilog_lib.v')
    order = read(folds/'gatelookup_recommended.json')['simplified_gate_type_order']
    simple = np.asarray(order)[ds['x39'][:,:25].argmax(axis=1)]
    cands = rows(ASSETS/'TRAIN_NEGATIVE_POOL.csv')
    hosts = sorted({r['host'] for r in cands})
    bindings = {r['view']:r for r in read(ASSETS/'MANIFEST.json')}
    donor = {}
    for v in loader.feature_contract['shared_inputs']['orig_train']['views']:
        host = v['view'].split('__')[0]
        if host not in hosts or '__inj' not in v['view']:
            continue
        n = nl.parse_netlist(folds/'orig'/f"{v['view']}.v",lib)
        cells = {c.name.lstrip('\\'):c.gate for c in n.insts}
        for i,k in enumerate(range(v['start'],v['physical_stop']),v['old_start']):
            if ds['physical'][k] and ds['trusted'][k] and ds['y'][k]==0:
                donor[k] = (host,cells[names[i].strip().lstrip('\\')],str(simple[k]))
    g0 = np.load(OUT/'SCHEDULE.npz')['base']
    actual = []
    for step in range(len(g0)):
        q = loader.step('orig','G0',step)
        assert np.array_equal(q.indices,g0[step])
        actual.extend((step,int(d),slot) for slot,d in enumerate(q.common_negative,len(q.positive)) if d in donor)
    summaries, detail, candidate_report, witnesses = [], [], [], []
    for mode,index in [('cell',1),('simple',2)]:
        for cap in (5,11):
            groups = {h:defaultdict(list) for h in hosts}
            for r in cands:
                with np.load(ASSETS/'graphs'/f"{r['view']}.npz") as g:
                    k = int(r['row'])
                    assert g['physical_names'][k] == r['node'] and k in g['region_rows']
                    kind = bindings[r['view']]['region'][r['node']] if index==1 else order[g['x39'][k,:25].argmax()]
                groups[r['host']][kind].append(r)
            edges = {h:{} for h in hosts}
            for step,d,slot in actual:
                host,kind = donor[d][0],donor[d][index]
                if kind in groups[host]:
                    edges[host][step,d] = kind,slot
            maxima = {h:solve(edges[h],groups[h],cap) for h in hosts}
            equal = min(maxima.values())
            for h in hosts:
                picks = solve(edges[h],groups[h],cap,equal)
                for kind, items in groups[h].items():
                    relevant = [k for k,v in edges[h].items() if v[0]==kind]
                    matched = picks[kind]
                    counts = Counter()
                    for i,(step,d,slot) in enumerate(sorted(matched)):
                        c = items[i%len(items)]
                        counts[c['view'],c['node']] += 1
                        witnesses.append(dict(mode=mode,cap=cap,host=h,gate=kind,step=step+1,
                            donor=d,slot=slot,view=c['view'],node=c['node']))
                        assert g0[step,slot]==d and donor[d][0]==h and donor[d][index]==kind
                    assert max(counts.values(),default=0)<=cap
                    detail.append(dict(mode=mode,cap=cap,host=h,gate=kind,candidates=len(items),
                        donors=len({d for _,d in relevant}),steps=len({s for s,_ in relevant}),
                        covered=len(counts),gap=len(items)-len(counts),assigned=len(matched)))
                    for c in items:
                        candidate_report.append(dict(mode=mode,cap=cap,host=h,gate=kind,
                            view=c['view'],node=c['node'],exposure=counts[c['view'],c['node']]))
                assert len({s for pairs in picks.values() for s,_,_ in pairs})==equal
                assert len({d for pairs in picks.values() for _,d,_ in pairs})==equal
            subset = [r for r in candidate_report if r['mode']==mode and r['cap']==cap]
            summaries.append(dict(mode=mode,cap=cap,max_per_host=maxima,equal_per_host=equal,
                total=2*equal,covered=sum(r['exposure']>0 for r in subset)))
    csv_out(OUT/'STRICT_GATE_COVERAGE.csv',detail)
    csv_out(OUT/'STRICT_CANDIDATES.csv',candidate_report)
    csv_out(OUT/'STRICT_MATCH_WITNESS.csv',witnesses)
    write_json(OUT/'STRICT_MATCH_SUMMARY.json',summaries)
    print(summaries)


if __name__=='__main__':
    main()
