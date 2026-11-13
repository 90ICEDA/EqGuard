"""Existing-evidence-only transfer audit. No SAT or model code is imported."""
import hashlib
import json
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from boundary_repr import COLS, canonical, comparison_gate, context_key, parse_table, summarize

ROOT=Path(__file__).resolve().parents[2]
TABLES=ROOT/'10.15/06_统一评测协议/N4_三向泛化/tables'
OUT=TABLES/'sat_boundary_round9'
R8=TABLES/'sat_cases_round8'
WORK=ROOT/'generate_trans/folds/hosts_bt31'


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, rows):
    pd.DataFrame(rows).to_csv(OUT/name,index=False,encoding='utf-8-sig')


def drivers(module, bit):
    # Unresolved library cells in raw JSON lack port_directions. Only these
    # explicitly checked schemas are accepted; unknown cell types fail closed.
    schemas={'AND2X2':{'Q'},'OR2X1':{'Q'},'XOR2X1':{'Q'},'INVX0':{'QN'},
             'MX2X1_RS':{'Y'},'SDFFSRX1_RS':{'Q','QN'},'SDFFX1':{'Q','QN'},
             '$and':{'Y'},'$mux':{'Y'}}
    result=[]
    for name,cell in module['cells'].items():
        dirs=cell.get('port_directions',{})
        outs={p for p,d in dirs.items() if d=='output'} if dirs else schemas.get(cell['type'])
        if outs is None:
            raise ValueError('Unknown library output schema: '+cell['type'])
        result += [(name,p) for p,bs in cell['connections'].items() if p in outs and bit in bs]
    return result


def region_cells(module, target, boundary):
    cells=set();seen=set();pending=[target];escapes=set()
    for bit in pending:
        if bit in seen or bit in boundary or not isinstance(bit,int):
            continue
        seen.add(bit)
        ds=drivers(module,bit)
        if len(ds)!=1:
            escapes.add(bit);continue
        name,pin=ds[0];cell=module['cells'][name]
        if 'DFF' in cell['type'].upper():
            escapes.add(bit);continue
        cells.add(name)
        # These accepted combinational types have exactly one output pin.
        pending.extend(b for p,bs in cell['connections'].items() if p!=pin for b in bs if isinstance(b,int))
    return sorted(cells),sorted(escapes)


def environment_region(module, target):
    """Existing fixed-root fanin cone, stopped at named PI/physical Q state.

    QN is an explicitly complemented physical Q anchor. Do not infer matches
    between internal cells, or enumerate a large boundary truth table.
    """
    pi={b:f'PI:{n}[{i}]' for n,p in module['ports'].items() if p['direction']=='input'
        for i,b in enumerate(p['bits']) if isinstance(b,int)}
    pending=[target];seen=set();cells=set();leaves=[];errors=[]
    for bit in pending:
        if not isinstance(bit,int) or bit in seen:
            continue
        seen.add(bit)
        if bit in pi:
            leaves.append(dict(bit=bit,anchor=pi[bit],phase=0));continue
        ds=drivers(module,bit)
        if len(ds)!=1:
            errors.append(bit);continue
        name,pin=ds[0];cell=module['cells'][name]
        if 'DFF' in cell['type'].upper():
            if pin not in ('Q','QN'):raise ValueError('Unsupported state output')
            leaves.append(dict(bit=bit,anchor='Q:'+name,phase=int(pin=='QN')));continue
        cells.add(name)
        pending.extend(b for p,bs in cell['connections'].items() if p!=pin for b in bs if isinstance(b,int))
    return dict(cells=sorted(cells),leaves=leaves,unresolved=errors)


def main():
    start=time.perf_counter();OUT.mkdir(parents=True,exist_ok=True)
    input_files=[R8/n for n in ['queries.csv','sources.csv','signal_correspondence.csv','functional_relations.csv','boundary_queries.csv']]
    plan=dict(created=datetime.now().astimezone().isoformat(),new_sat_queries=0,training_runs=0,
              scope='offline role-aware boundary representation, proven-pair transfer, existing 40 blind records',
              inputs={str(p.relative_to(ROOT)):sha(p) for p in input_files})
    (OUT/'plan.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')
    cases, blind, annotations, pair_rows, checks = [], [], [], [], []
    modules={}
    case_context=dict(model='native_combinational_physical_Q_boundary_v1',
        constraints={'sys_rst_l':1,'test_mode':0,'test_se':0},reachability='not_proved',
        intervention='fixed_functional_boundary_not_global_wire',input_roles=['selector','data_A','data_B'])
    case_context_id=context_key(case_context)
    src=pd.read_csv(R8/'sources.csv');truth=pd.read_csv(R8/'functional_relations.csv',dtype={'pattern':str})
    proof=pd.read_csv(R8/'queries.csv',dtype={'pattern':str})
    vectors={};features={};participant_specs=[];regions={};environment_regions={}
    for row in src.itertuples():
        source=ROOT/row.source;raw=R8/row.view/'raw.json'
        assert sha(source)==row.source_sha and sha(raw)==row.raw_sha
        mod=next(iter(json.loads(raw.read_text())['modules'].values()));modules[row.view]=mod
        prefix='TrojanA' if row.source_instance=='injalpha' else 'TrojanE'
        names=[prefix+'HJ.S0',prefix+'HJ.A',prefix+'HJ.B',prefix+'HJ.Y']
        bits=[mod['netnames'][n]['bits'][0] for n in names]
        region,escapes=region_cells(mod,bits[-1],set(bits[:3]))
        regions[row.view]=dict(cells=region,escape_bits=escapes,closed=not escapes)
        assert mod['netnames']['rec_readyH']['bits']==[bits[-1]]
        subset=truth[truth.view==row.view]
        text=';'.join(f'{r.pattern}:feasible:{r.forced}' for r in subset.itertuples())
        table=parse_table(text,3);desc,per=summarize(table,3);can=canonical(table,3)
        vectors[row.view]=[desc[c] for c in COLS];features[row.view]=(desc,per)
        cases.append(dict(boundary_id=row.view+'|HJ',view=row.view,instance=row.source_instance,
            scope='privileged_mechanism_only',context_id=case_context_id,source_sha=row.source_sha,
            raw_sha=row.raw_sha,role_bindings=dict(zip(['selector','data_A','data_B','target'],names)),
            target_equals_PO=True,canonical_signature=can['signature'],canonical_orders=can['orders'],
            signature_is_equivalence_proof=False,features=desc,
            training_eligible=False,reason='mechanism-selected cases; no label-blind extraction qualification'))
        for i,(name,bit) in enumerate(zip(names,bits)):
            environment_regions[(row.view,['selector','data_A','data_B','target'][i])]=environment_region(mod,bit)
            ds=drivers(mod,bit)
            participant_specs.append(dict(view=row.view,source_sha=row.source_sha,role=['selector','data_A','data_B','target'][i],
                net=name,bit=bit,drivers=ds,driver=ds[0][0] if len(ds)==1 else '',pin=ds[0][1] if len(ds)==1 else '',
                source_instance=row.source_instance,slot=i))
    # Proof-backed signal pairs, target/PO aliases deduplicated as one signal.
    for inst in ['injalpha','injepsilon']:
        a=f'rs232t1000__{inst}_d1_s42__ys_id';b=f'rs232t1000__{inst}_d1_s42__ys_abc'
        for i,role in enumerate(['selector','data_A','data_B','target']):
            q=proof[(proof.view==inst)&(proof.kind=='cross_signal_equivalence')&(proof.pattern==str(i))]
            assert len(q)==1 and q.iloc[0].status=='proved'
            audit=q.iloc[0];folder=ROOT/audit.folder
            assert sha(folder/'model.v')==audit.model_sha and sha(folder/'run.log')==audit.log_sha
            canonical_match=cases[src.view.tolist().index(a)]['canonical_signature']==cases[src.view.tolist().index(b)]['canonical_signature']
            actual_diff=float(np.max(np.abs(np.asarray(vectors[a])-np.asarray(vectors[b]))))
            role_diff=(0. if i==3 else max(abs(features[a][1][i][c]-features[b][1][i][c])
                       for c in ['pair_coverage','change_fraction','influence_valid']))
            pair_rows.append(dict(instance=inst,role=role,view_a=a,view_b=b,polarity='equal_proved',
                query_id=int(audit.query_id),evidence_folder=audit.folder,canonical_equal=canonical_match,
                descriptor_max_abs_diff=actual_diff,input_stats_max_abs_diff=role_diff,
                **comparison_gate(case_context_id,case_context_id,True,False),
                scope='bit_and_boundary_role; not automatic cell embedding correspondence'))
    # Retain global-wire intervention as a nontransferable diagnostic, never a feature.
    wire=proof[proof.kind=='equal_context_blocking']
    wire_rows=[dict(view=r.view,control=r.pattern,status=r.status,
                    scope='global_physical_wire',transfer_feature_allowed=False) for r in wire.itertuples()]
    save('excluded_wire_intervention.csv',wire_rows)

    contexts={case_context_id:case_context}
    node_frames=[]
    for rd,folder in [('r5','sat_nonlocal_round5'),('r6','sat_expand_round6'),('r7','sat_repair_round7')]:
        base=TABLES/folder
        rr=pd.read_csv(base/f'{rd}_nonlocal_relations.csv')
        qq=pd.read_csv(base/f'{rd}_nonlocal_queries.csv',dtype={'pattern':str})
        nn=pd.read_csv(base/f'{rd}_nodes.csv');node_frames.append(nn)
        version={'r5':'r5.1','r6':'r6.1','r7':'r7.1'}[rd]
        for row in rr.itertuples():
            source=WORK/'trans'/row.design
            cache=json.loads((base/'cache'/f'{Path(row.design).stem}.json').read_text())
            group=qq[qq.relation_id==row.relation_id]
            k=len(row.cut_nets.split(';'));verified=0;cellmap=None
            for q in group.itertuples():
                entry=cache[q.query_key];meta=json.loads((base/entry['query_dir']/'meta.json').read_text())
                assert meta['source_sha']==sha(source) and meta['status']==q.status
                assert meta['pattern']==q.pattern and meta['prove']==q.prove and meta['seq']==1
                payload=dict(design=meta['source_sha'],cellmap=meta['cellmap_sha'],script=version,
                             cut=meta['cut'],cut_bits=meta['cut_bits'],target=meta['target'],
                             pattern=meta['pattern'],prove=meta['prove'],timeout=meta['timeout'],seq=meta['seq'])
                assert hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()==q.query_key
                assert meta['cut']==row.cut_nets.split(';')
                assert meta['cut_bits']==list(map(int,row.cut_bits.split(';'))) and meta['target']==row.target
                cellmap=meta['cellmap_sha'];verified+=1
            assert verified==2*2**k
            table=parse_table(row.truth_table,k)
            # Rebuild truth from explicit (pattern,prove), never CSV position.
            pair_state={('proved','proved'):('infeasible','not_applicable'),('proved','refuted'):('feasible','1'),
                        ('refuted','proved'):('feasible','0'),('refuted','refuted'):('feasible','undecided')}
            for pat,values in table.items():
                st=group[group.pattern==pat].set_index('prove').status.to_dict()
                assert values==pair_state[(st[1],st[0])]
            context=dict(model='seq1_arbitrary_init_legacy_cellmap',cellmap_sha=cellmap,
                         constraints={},reachability='not_proved',input_roles='generic_cut_inputs')
            ctx=context_key(context);contexts[ctx]=context
            desc,per=summarize(table,k);can=canonical(table,k)
            blind.append(dict(relation_id=row.relation_id,view=Path(row.design).stem,source_sha=sha(source),
                context_id=ctx,k=k,signature=can['signature'],signature_sha=can['signature_sha'],
                unique_canonical_order=can['unique_order'],canonical_order_count=len(can['orders']),
                canonical_slot_candidates=can['slot_candidates'],features=desc,
                verified_queries=verified,signal_equivalence_proved=False,
                transfer_validated=False,training_eligible=False))
            # Only the proven target signal's driver, not every receiving FF.
            selected=nn[(nn.relation_id==row.relation_id)&(nn.name==row.driver)]
            for n in selected.itertuples():
                annotations.append(dict(relation_id=row.relation_id,node_index=int(n.node_index),view=n.view,
                    driver=n.name,role='endpoint_driver',input_index=-1,context_id=ctx,values=[desc[c] for c in COLS],source_sha=sha(source)))
            # Input annotations carry ONLY their own comparison statistics, not target descriptors.
            part=pd.read_csv(TABLES/'sat_repair_round7/input_participants.csv')
            part=part[(part.relation_id==row.relation_id)&(part.mapping_status=='mapped')]
            for p in part.itertuples():
                inp=per[int(p.input_index)]
                if not inp['influence_valid']:
                    continue  # unknown comparison support is not new functional coverage
                annotations.append(dict(relation_id=row.relation_id,node_index=int(p.node_index),view=p.view,
                    driver=p.driver,role='input_driver',input_index=int(p.input_index),context_id=ctx,
                    values=[inp['pair_coverage'],inp['change_fraction'],inp['influence_valid']],source_sha=sha(source)))
            checks.append(dict(relation_id=row.relation_id,verified_queries=verified,explicit_binding=True,source_sha_ok=True))
    # Sparse, role-separated annotations; deterministic mean over unique relation/role records.
    ids=sorted({x['node_index'] for x in annotations});idpos={n:i for i,n in enumerate(ids)}
    columns=['endpoint_'+c for c in COLS]+['endpoint_record_valid','input_pair_coverage',
        'input_change_fraction','input_influence_valid','input_record_valid']
    arr=np.zeros((len(ids),len(columns)),np.float32)
    bucket=defaultdict(dict)
    for x in annotations:
        bucket[(x['node_index'],x['role'])][(x['relation_id'],x['input_index'])]=x['values']
    for (n,role),values in bucket.items():
        v=np.mean(list(values.values()),axis=0)
        if role=='endpoint_driver':arr[idpos[n],:len(COLS)]=v;arr[idpos[n],len(COLS)]=1
        else:arr[idpos[n],len(COLS)+1:len(COLS)+4]=v;arr[idpos[n],-1]=1
    assert np.isfinite(arr).all() and arr.min()>=0 and arr.max()<=1
    np.savez_compressed(OUT/'blind_annotations_sparse.npz',node_index=np.asarray(ids,dtype=np.int64),features=arr)
    np.savez_compressed(OUT/'case_descriptors.npz',view=np.asarray(list(vectors)),features=np.asarray(list(vectors.values()),np.float32))
    (OUT/'boundary_records.json').write_text(json.dumps(cases+blind,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'contexts.json').write_text(json.dumps(contexts,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'feature_schema.json').write_text(json.dumps(dict(relation_columns=COLS,node_columns=columns,
        aggregation='mean per role over unique (relation,input-index); input and endpoint channels separate; no last-input overwrite',
        canonical_signature_numeric_feature=False,training_loader_compatible=False,role_valid_masks=True,
        context_compatibility='compare only equal explicit context identifiers',
        comparison_semantics='forced-pattern comparisons; not shared-environment causal intervention',
        inference_limits='same descriptor is not a signal proof; same bit is not a cell embedding or safety-label proof',
        excluded_fields=['global_wire_fault','Trojan_name','label','covered_proxy','ordinal_signature']),indent=2),encoding='utf-8')
    save('proven_boundary_pairs.csv',pair_rows);save('case_participants.csv',participant_specs)
    save('evidence_binding_audit.csv',checks)
    # Map proven case roles to graph cells, preserving output pins and bit identity.
    fids=json.loads((WORK/'data/for_train/metadata_trans.json').read_text())['file_ids']
    splits=json.loads((WORK/'views.json').read_text())
    fold_of={v:r for r in ('train','val') for v in splits[r+'_views']}
    wanted={(x['view'],x['driver']) for x in participant_specs if x['driver']}
    wanted.update((v,n) for v,r in regions.items() for n in r['cells'])
    wanted.update((v,n) for (v,role),r in environment_regions.items() for n in r['cells'])
    wanted_names={x[1] for x in wanted};hits=defaultdict(list)
    expected_nodes=defaultdict(set)
    for x in annotations:
        assert fids[x['node_index']]==x['view']
        expected_nodes[x['node_index']].add(x['driver'].lstrip('\\'))
    verified_nodes=set()
    with (WORK/'data/processed/node_names_trans.txt').open(encoding='utf-8') as stream:
        for i,line in enumerate(stream):
            n=line.strip().lstrip('\\')
            if i in expected_nodes:
                assert expected_nodes[i]=={n}
                verified_nodes.add(i)
            if n in wanted_names and (fids[i],n) in wanted:hits[(fids[i],n)].append(i)
    assert len(verified_nodes)==len(ids)
    mapped=[]
    for x in participant_specs:
        ids_for=hits[(x['view'],x['driver'])]
        mapped.append(dict(view=x['view'],role=x['role'],bit=x['bit'],driver=x['driver'],output_pin=x['pin'],
            node_index=ids_for[0] if len(ids_for)==1 else -1,
            mapping_status='mapped' if len(ids_for)==1 else 'ambiguous_or_missing',
            fold_role=fold_of.get(x['view'],'not_eligible'),training_pair_allowed=False))
    save('case_graph_attachments.csv',mapped)
    case_node_pairs=[]
    for pair in pair_rows:
        left=next(x for x in mapped if x['view']==pair['view_a'] and x['role']==pair['role'])
        right=next(x for x in mapped if x['view']==pair['view_b'] and x['role']==pair['role'])
        case_node_pairs.append(dict(instance=pair['instance'],role=pair['role'],node_a=left['node_index'],
            node_b=right['node_index'],output_pin_a=left['output_pin'],output_pin_b=right['output_pin'],
            mapping_ok=left['node_index']>=0 and right['node_index']>=0,
            bit_equivalence_proved=True,cell_embedding_equivalence_proved=False,training_pair_allowed=False))
    save('mapped_role_pairs.csv',case_node_pairs)
    members=[]
    for view,r in regions.items():
        for cell in r['cells']:
            ns=hits[(view,cell)]
            members.append(dict(view=view,cell=cell,cell_type=modules[view]['cells'][cell]['type'],
                node_index=ns[0] if len(ns)==1 else -1,mapping_ok=len(ns)==1,
                safety_label='not_inferred_from_equivalence'))
    save('region_membership.csv',members)
    region_pairs=[]
    for inst in ['injalpha','injepsilon']:
        a=f'rs232t1000__{inst}_d1_s42__ys_id';b=f'rs232t1000__{inst}_d1_s42__ys_abc'
        region_pairs.append(dict(instance=inst,view_a=a,view_b=b,cells_a=len(regions[a]['cells']),
            cells_b=len(regions[b]['cells']),closed_a=regions[a]['closed'],closed_b=regions[b]['closed'],
            boundary_role_proofs=4,truth_profiles_equal=True,internal_cell_pairs_inferred=0,
            training_pair_allowed=False,scope='proved functional boundary; cell embedding or safety correspondence not inferred'))
    save('region_boundary_pairs.csv',region_pairs)
    expanded_pairs=[];expanded_members=[];expanded_leaves=[]
    for (view,role),r in environment_regions.items():
        for name in r['cells']:
            ns=hits[(view,name)]
            expanded_members.append(dict(view=view,role=role,cell=name,cell_type=modules[view]['cells'][name]['type'],
                node_index=ns[0] if len(ns)==1 else -1,annotation='region_membership_only_no_feature_or_label_copy'))
        for leaf in r['leaves']:
            expanded_leaves.append(dict(view=view,role=role,**leaf))
    for pair in pair_rows:
        a=environment_regions[(pair['view_a'],pair['role'])]
        b=environment_regions[(pair['view_b'],pair['role'])]
        anchors=sorted({x['anchor'] for x in a['leaves']+b['leaves']})
        expanded_pairs.append(dict(instance=pair['instance'],role=pair['role'],
            view_a=pair['view_a'],view_b=pair['view_b'],cells_a=len(a['cells']),cells_b=len(b['cells']),
            shared_anchor_union=anchors,boundary_variables=len(anchors),
            resolved_a=not a['unresolved'],resolved_b=not b['unresolved'],
            root_equivalence_proved=True,evidence_folder=pair['evidence_folder'],query_id=pair['query_id'],
            nontrivial_rewrite=len(a['cells'])>1 and len(b['cells'])>1,
            differing_cell_counts=len(a['cells'])!=len(b['cells']),
            compact_full_truth_feature_available=False,training_pair_allowed=False,
            internal_node_correspondence_inferred=False))
    save('expanded_region_pairs.csv',expanded_pairs)
    save('expanded_region_membership.csv',expanded_members)
    save('expanded_region_anchors.csv',expanded_leaves)
    (OUT/'expanded_region_records.json').write_text(json.dumps(dict(
        proof_context='shared named physical Q + same PI, unrestricted combinational state boundary',
        proof_source='round8 existing cross_signal_equivalence, not new SAT',
        pairs=expanded_pairs,
        regions=[dict(view=v,role=role,source_sha=next(x['source_sha'] for x in participant_specs if x['view']==v),
                      raw_sha=sha(R8/v/'raw.json'),**r) for (v,role),r in environment_regions.items()],
        training_pair_allowed=False,full_truth_enumerated=False),ensure_ascii=False,indent=2),encoding='utf-8')
    # Do not advertise a preserved one-cell mux as a successful 1:N rewrite test.
    preserved_single_cell=sum(p['cells_a']==p['cells_b']==1 for p in region_pairs)
    driver_rows=[]
    original_types={r.relation_id:str(r.driver_type) for rd,folder in
        [('r5','sat_nonlocal_round5'),('r6','sat_expand_round6'),('r7','sat_repair_round7')]
        for r in pd.read_csv(TABLES/folder/f'{rd}_nonlocal_relations.csv').itertuples()}
    for (typ,k,ctx),g in pd.DataFrame([dict(driver_type=original_types[x['relation_id']],k=x['k'],
        context_id=x['context_id'],profile=tuple(x['features'].values())) for x in blind]).groupby(['driver_type','k','context_id']):
        driver_rows.append(dict(driver_type=typ,k=k,context_id=ctx,relations=len(g),
                               distinct_profiles=g.profile.nunique()))
    save('driver_conditioned_information.csv',driver_rows)
    # No solver-based cross-implementation pairs exist among the 40 frozen blind records.
    groups=pd.DataFrame(blind).assign(instance=lambda d:d.view.str.split('__').str[0]+'|'+d.view.str.split('__').str[1])
    potential=groups.groupby('instance').view.nunique()
    summary=dict(case_boundaries=len(cases),proven_role_pairs=len(pair_rows),
        transferred_role_pairs=sum(r['descriptor_max_abs_diff']==0 and r['input_stats_max_abs_diff']==0 for r in pair_rows),
        unique_case_feature_profiles=len({tuple(v) for v in vectors.values()}),
        blind_relations=len(blind),verified_blind_queries=sum(r['verified_queries'] for r in blind),
        blind_unique_feature_profiles=len({tuple(r['features'].values()) for r in blind}),
        ambiguous_canonical_orders=sum(not r['unique_canonical_order'] for r in blind),
        blind_sources_with_multiple_implementations=int((potential>1).sum()),
        blind_transfer_validated=0,training_consistency_pairs=0,
        case_participant_mapping=sum(x['mapping_status']=='mapped' for x in mapped),
        case_mapped_role_pairs=sum(x['mapping_ok'] for x in case_node_pairs),
        region_boundary_pairs=region_pairs,
        preserved_single_cell_region_pairs=preserved_single_cell,
        proven_expanded_region_pairs=len(expanded_pairs),
        nontrivial_rewritten_region_pairs=sum(x['nontrivial_rewrite'] for x in expanded_pairs),
        different_cell_count_region_pairs=sum(x['differing_cell_counts'] for x in expanded_pairs),
        expanded_region_mapping_failures=sum(x['node_index']<0 for x in expanded_members),
        current_graph_node_bindings_verified=len(verified_nodes),
        multi_relation_driver_groups_with_varied_profiles=sum(x['relations']>1 and x['distinct_profiles']>1 for x in driver_rows),
        sparse_annotation_nodes=len(ids),endpoint_annotation_nodes=sum(role=='endpoint_driver' for n,role in bucket),
        input_annotation_nodes=sum(role=='input_driver' for n,role in bucket),
        case_blind_context_compatible=comparison_gate(case_context_id,blind[0]['context_id'])['descriptor_comparable'],
        sat_queries=0,training_runs=0,test_evaluated=False,elapsed_s=round(time.perf_counter()-start,2))
    (OUT/'manifest.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':main()
