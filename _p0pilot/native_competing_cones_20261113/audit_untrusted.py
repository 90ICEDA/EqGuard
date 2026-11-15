"""Read-only lineage audit of the frozen queue's untrusted peak nodes."""
from collections import defaultdict, Counter
from audit_winners import OUT, P, csv_rows, load, read, write, np, digest

ROOT = OUT.parents[1]
F = ROOT/'generate_trans/folds/hosts_bt31'
FT = F/'data/for_train'
V = P/'control_boundary_v3_20261104'


def clean(s):
    return s.strip().lstrip('\\')


def main():
    views, groups = load()
    winners = [r for r in csv_rows(OUT/'WINNERS.csv') if r['trusted']=='0']
    selected = {r['view'] for r in winners}
    contract = read(V/'input_contract.json')['shared_inputs']
    orig = {r['view']:r for r in contract['orig_train']['views']}
    names = (P/'round32_20261029/orig_names/node_names_orig.txt').read_text(encoding='utf8').splitlines()
    provenance = defaultdict(set)
    sources = {r['source'] for r in winners}
    for p in (ROOT/'generate_trans').glob('hosts*/*/provenance.json'):
        for r in read(p):
            if r.get('view') in sources and r.get('kind')=='trojan' and r.get('new_gates'):
                provenance[r['view']].add(tuple(sorted(map(clean,r['new_gates']))))
    source_nodes, inserted = {}, {}
    for s in sources:
        o = orig[s]
        source_nodes[s] = {clean(names[i]):i for i in range(o['old_start'],o['old_stop'])}
        good = [set(a) for a in provenance[s] if set(a)<=source_nodes[s].keys()]
        assert len(good)==1
        inserted[s] = good[0]
    labels = read(FT/'class_map_orig.json')
    transported = read(FT/'class_map_trans_transported.json')
    mask = np.load(FT/'trust_trans.npy',mmap_mode='r')
    node_rows = {int(r['node']):r for r in winners}
    def global_row(n,r):
        v=views[r['view']]
        return int(v['old_start'])+n-int(v['start'])
    target = {global_row(n,r):n for n,r in node_rows.items()}
    parents = defaultdict(set)
    for a,b in read(FT/'alignment.json'):
        if b in target:
            parents[target[b]].add(a)
    raw = {}
    for view in selected:
        r = views[view]
        mapping = read(F/'mappings'/f'{view}.json')
        assert mapping['src_view']==r['source'] and mapping['rw_view']==view
        rev = defaultdict(set)
        for par, tt in mapping['node_alignment'].items():
            for child in tt:
                rev[clean(child)].add(clean(par))
        raw[view] = rev
    relations = P/'control_signed_carrier_20261109_v3_1'
    manifest=read(relations/'VERIFIED_V31.json')
    assert manifest['passed']
    for f in ('RELATIONS_V31.csv','REGION_MEMBERS_V31.csv'):
        assert digest(relations/f)==manifest['files'][f]
    accepted = {r['relation_id']:r for r in csv_rows(relations/'RELATIONS_V31.csv')
                if r['accepted_or_unresolved']=='accepted' and r['split']=='train'}
    carrier=defaultdict(list)
    for rid,r in accepted.items():
        for n in r['target_rows'].split('|'):
            if n and int(n) in node_rows:
                a=node_rows[int(n)]
                assert (a['source'],a['recipe'])==(r['source_object'],r['implementation_flow'])
                assert a['name'] in r['target_driver_cells'].split('|')
                assert digest(F/'trans'/f"{a['view']}.v")==r['target_sha']
                carrier[int(n)].append(rid)
    member=defaultdict(list)
    for r in csv_rows(relations/'REGION_MEMBERS_V31.csv'):
        ref=accepted.get(r['relation_id'])
        if not ref:
            continue
        for n,a in node_rows.items():
            if (a['source'],a['recipe'],a['name'])==(ref['source_object'],ref['implementation_flow'],r['cell']):
                assert digest(F/'trans'/f"{a['view']}.v")==ref['target_sha']
                member[n].append(r['relation_id'])
    docs = ROOT/'10.15/00_说明'
    archival = {}
    for view in selected:
        path = docs/f'SAT_ALL_{view}.json'
        if path.is_file():
            z = read(path)
            assert z['view']==view
            archival[view] = ({clean(r['gate']):r['region'] for r in z['labels']},
                              {clean(r['trans_node']):r['status'] for r in z['results']})
    historic = {}
    for file in ('BOUNDARY_LABELS_20261112.csv','ORIG_BOUNDARY_LABELS_20261112.csv','STRICT_LABELS_20261112.csv'):
        historic[file] = {(r['view'],clean(r['gate'])):r['label']
                          for r in csv_rows(docs/file) if r['view'] in selected}
    info={}
    for n,r in sorted(node_rows.items()):
        v,s,name=r['view'],r['source'],r['name']
        gid=global_row(n,r)
        raw_par=raw[v][name]
        same=name in source_nodes[s]
        resolved={a for a in raw_par if a in source_nodes[s]}
        family=resolved|({name} if same else set())
        t={a for a in family if a in inserted[s] or labels.get(str(source_nodes[s][a]))==1}
        h=family-t
        if h and t:
            lineage='mixed_host_trojan'
        elif t:
            lineage='trojan_parent'
        elif h:
            lineage='host_parent'
        elif raw_par:
            lineage='raw_parent_unbound'
        else:
            lineage='no_parent_mapping'
        info[n]=dict(global_id=gid,transport_mask=int(mask[gid]),transport_label=transported.get(str(gid),''),
                     alignment_parents='|'.join(map(str,sorted(parents[n]))),
                     lineage=lineage,host_parents='|'.join(sorted(h)),trojan_parents='|'.join(sorted(t)),
                     unresolved_parents='|'.join(sorted(raw_par-resolved)),identity_name=int(same),
                     carrier='|'.join(carrier[n]),region_only='|'.join(member[n]),
                     archived_region=archival.get(v,({},{}))[0].get(name,''),
                     archived_node_result=archival.get(v,({},{}))[1].get(name,''),
                     boundary_label=historic['BOUNDARY_LABELS_20261112.csv'].get((v,name),''),
                     orig_boundary_label=historic['ORIG_BOUNDARY_LABELS_20261112.csv'].get((v,name),''),
                     strict_label=historic['STRICT_LABELS_20261112.csv'].get((v,name),''))
        assert bool(mask[gid]) == (str(gid) in transported) == bool(parents[n])
    detail=[]
    for r in winners:
        n=int(r['node'])
        detail.append(dict(**r,**info[n]))
    # A non-fitting predecessor is the actual stopping cone in the frozen trace.
    stop={(r['view'],r['kind'],r['point'],r['competitor']) for r in csv_rows(OUT/'COMPETITORS.csv')
          if r['reached_or_blocker']=='1' and r['before_stop']=='0'}
    for r in detail:
        r['first_blocker']=int(tuple(r[k] for k in ('view','kind','point','cone')) in stop)
    write('UNTRUSTED_LINEAGE.csv',detail)
    groups_out=defaultdict(list)
    for r in detail:
        groups_out[r['source'],r['recipe']].append(r)
    summary=[]
    for (s,rec), rr in sorted(groups_out.items()):
        uniq={r['node']:r for r in rr}
        summary.append(dict(source=s,recipe=rec,nodes=len(uniq),
                            blocker_nodes=len({r['node'] for r in rr if r['first_blocker']}),
                            **{k:sum(r['lineage']==k for r in uniq.values()) for k in
                               ('no_parent_mapping','raw_parent_unbound','mixed_host_trojan','trojan_parent','host_parent')},
                            carrier=sum(bool(r['carrier']) for r in uniq.values())))
    write('UNTRUSTED_BY_SOURCE_RECIPE.csv',summary)
    assert len(info)==81
    print(Counter(r['lineage'] for r in info.values()))
    print('transported',sum(r['transport_mask'] for r in info.values()),
          'alignment',sum(bool(r['alignment_parents']) for r in info.values()),
          'carrier',sum(bool(r['carrier']) for r in info.values()))
    for k in ('archived_region','archived_node_result','boundary_label','orig_boundary_label','strict_label'):
        print(k,Counter(r[k] for r in info.values()))
    for r in summary:
        print(r)


if __name__=='__main__':
    main()
