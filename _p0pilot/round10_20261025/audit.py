"""Independent three-valued replay, paired features, evidence and graph audit."""
import hashlib
import json
import sys
from collections import defaultdict
import numpy as np
import pandas as pd
import native as N
from repair_aliases import module

sys.path.insert(0,str(N.ROOT/'_p0pilot/round9_20261025'))
from boundary_repr import COLS,summarize
from prepare import drivers


def replay(m,environment):
    ports,states,width=N.layout(m)
    if len(environment)!=width:raise ValueError('wrong environment width')
    e=[int(c) if c in '01' else None for c in reversed(environment)]
    v={'0':0,'1':1,'x':None,'z':None}
    for n,offsets in ports.items():
        for b,i in zip(m['ports'][n]['bits'],offsets):v[b]=e[i]
    pending=[]
    for n,c in m['cells'].items():
        if n in states:
            for pin in ('Q','QN'):
                if pin in c['connections']:
                    value=e[states[n]];v[c['connections'][pin][0]]=None if value is None else value ^ int(pin=='QN')
        else:pending.append(c)
    AND=lambda a,b:0 if a==0 or b==0 else 1 if a==b==1 else None
    OR=lambda a,b:1 if a==1 or b==1 else 0 if a==b==0 else None
    XOR=lambda a,b:a^b if a is not None and b is not None else None
    while pending:
        progress=False;next_cells=[]
        for c in pending:
            typ=c['type'];con=c['connections']
            op='QN' if typ=='INVX0' else 'Q' if typ in ('AND2X2','OR2X1','XOR2X1') else 'Y'
            if any(bs[0] not in v for pin,bs in con.items() if pin!=op):next_cells.append(c);continue
            g=lambda pin:v[con[pin][0]]
            if typ in ('AND2X2','OR2X1','XOR2X1'):
                fn={'AND2X2':AND,'OR2X1':OR,'XOR2X1':XOR}[typ];out=fn(g('IN1'),g('IN2'))
            elif typ=='INVX0':out=None if g('IN') is None else 1-g('IN')
            elif typ in ('$and','$or','$xor'):out={'$and':AND,'$or':OR,'$xor':XOR}[typ](g('A'),g('B'))
            elif typ=='$not':out=None if g('A') is None else 1-g('A')
            elif typ in ('MX2X1_RS','$mux'):
                select=g('S0' if typ=='MX2X1_RS' else 'S');a,b=g('A'),g('B')
                out=(b if select else a) if select is not None else a if a==b else None
            else:raise ValueError('unknown cell '+typ)
            v[con[op][0]]=out;progress=True
        if not progress:raise ValueError('cycle or missing input')
        pending=next_cells
    return v


def main():
    plan=json.loads((N.OUT/'plan.json').read_text());rows=pd.read_csv(N.OUT/'queries_with_repairs.csv',dtype={'pattern':str})
    initial=pd.read_csv(N.OUT/'pilot_outcomes.csv');repair=pd.read_csv(N.OUT/'alias_repair_outcomes.csv')
    final=[];mapping={}
    for i,item in enumerate(plan['selected']):
        record=initial.iloc[i].to_dict();rr=repair[repair.pair_index==i]
        if len(rr):record.update(rr.iloc[0].dropna().to_dict())
        record['pair_index']=i;final.append(record)
        mapping[i]=item['mapped_nets']
        if len(rr) and rr.iloc[0].status=='paired_validated':
            # CSV is for viewing; get the exact selected aliases from the proved query records.
            mapping[i]=list(item['mapped_nets'])
            q=rows[(rows.pair_index==i)&(rows.kind=='alias_equivalence')&(rows.status=='proved')]
            for z in q.itertuples():mapping[i][int(z.pattern)]=z.partner_alias
    final=pd.DataFrame(final);final.to_csv(N.OUT/'final_outcomes.csv',index=False,encoding='utf-8-sig')
    # Verify immutable query files and reject stale source snapshots.
    for r in rows.itertuples():
        folder=N.ROOT/r.folder
        assert N.sha(folder/'model.v')==r.model_sha and N.sha(folder/'run.log')==r.log_sha
        assert hashlib.sha256((folder/'run.ys').read_text().encode()).hexdigest()==r.script_sha
        if r.status=='refuted':assert (N.ROOT/r.witness).exists()
    replay_rows=[]
    for i,item in enumerate(plan['selected']):
        a,b=module(item['source_view']),module(item['partner'])
        failed=rows[(rows.pair_index==i)&(rows.kind=='fresh_boundary_equivalence')&(rows.status=='refuted')]
        if failed.empty:continue
        r=failed.iloc[0];env=next(s['data'][0] for s in json.loads((N.ROOT/r.witness).read_text())['signal'] if s['name']=='env')
        va,vb=replay(a,env),replay(b,env);slot=int(r.pattern)
        ba=a['netnames'][item['source_nets'][slot]]['bits'][0];bb=b['netnames'][item['mapped_nets'][slot]]['bits'][0]
        passed=va[ba] is not None and vb[bb] is not None and va[ba]!=vb[bb]
        assert passed
        replay_rows.append(dict(pair_index=i,kind='rejected_mapping_counterexample',slot=slot,
            source_value=va[ba],partner_value=vb[bb],passed=True,mapping_origin=item['mapping_origins'][slot]))
    # Spot replay one feasible table model per side and validated boundary.
    tables=json.loads((N.OUT/'all_aligned_tables.json').read_text())
    lookup={(x['pair_index'],x['side']):x for x in tables}
    for i in final[final.status=='paired_validated'].pair_index:
        item=plan['selected'][int(i)]
        for side in ('source','partner'):
            kind_suffix='_'+side
            candidates=rows[(rows.pair_index==i)&rows.kind.str.endswith(kind_suffix)&(rows.status=='refuted')]
            r=candidates.iloc[0];view=item['source_view'] if side=='source' else item['partner'];m=module(view)
            nets=item['source_nets'] if side=='source' else mapping[int(i)]
            env=next(s['data'][0] for s in json.loads((N.ROOT/r.witness).read_text())['signal'] if s['name']=='env')
            v=replay(m,env);values=[v[m['netnames'][n]['bits'][0]] for n in nets]
            assert ''.join(map(str,values[:4]))==r.pattern and values[4]==1-int(r.prove)
            replay_rows.append(dict(pair_index=int(i),kind='aligned_table_'+side,pattern=r.pattern,passed=True))
    pd.DataFrame(replay_rows).to_csv(N.OUT/'independent_replays.csv',index=False,encoding='utf-8-sig')
    # Pair payloads stay sparse and separate from any existing training tensor.
    success=final[final.status=='paired_validated'];indices=success.pair_index.astype(int).tolist()
    fa=np.array([[lookup[(i,'source')]['features'][c] for c in COLS] for i in indices],np.float32)
    fb=np.array([[lookup[(i,'partner')]['features'][c] for c in COLS] for i in indices],np.float32)
    assert np.isfinite(fa).all() and fa.min()>=0 and fa.max()<=1 and np.array_equal(fa,fb)
    for i in indices:
        assert lookup[(i,'source')]['inputs']==lookup[(i,'partner')]['inputs']
    np.savez_compressed(N.OUT/'paired_features.npz',pair_index=np.array(indices),source=fa,partner=fb)
    # Proved bit/slot mappings, preserving output pins; no hidden-state/label transfer.
    attachments=[]
    for i in indices:
        item=plan['selected'][i]
        for side,view,nets in [('source',item['source_view'],item['source_nets']),('partner',item['partner'],mapping[i])]:
            m=module(view)
            for slot,net in enumerate(nets):
                bit=m['netnames'][net]['bits'][0];ds=drivers(m,bit)
                pi=[f'{n}[{j}]' for n,p in m['ports'].items() if p['direction']=='input' for j,b in enumerate(p['bits']) if b==bit]
                attachments.append(dict(pair_index=i,side=side,view=view,slot=slot,net=net,bit=bit,
                    driver=ds[0][0] if len(ds)==1 else '',output_pin=ds[0][1] if len(ds)==1 else '',
                    graph_mapping_kind='unique_driver' if len(ds)==1 else 'PI_anchor_no_cell' if pi else 'nonunique_or_missing',
                    primary_input_anchor=';'.join(pi),
                    training_pair_allowed=False,safety_label_copied=False))
    fids=json.loads((N.WORK/'data/for_train/metadata_trans.json').read_text())['file_ids']
    wanted={(x['view'],x['driver']) for x in attachments if x['driver']};names={n for v,n in wanted};hits=defaultdict(list)
    with (N.WORK/'data/processed/node_names_trans.txt').open(encoding='utf-8') as f:
        for i,line in enumerate(f):
            n=line.strip().lstrip('\\')
            if n in names and (fids[i],n) in wanted:hits[(fids[i],n)].append(i)
    for x in attachments:
        ns=hits[(x['view'],x['driver'])];x['node_index']=ns[0] if len(ns)==1 else -1
        x['graph_mapping_ok']=len(ns)==1
    pd.DataFrame(attachments).to_csv(N.OUT/'proven_boundary_attachments.csv',index=False,encoding='utf-8-sig')
    # Full40 status, including missing candidates and unattempted pilot rows.
    inventory=json.loads((N.OUT/'plan.json').read_text())['inventory'];byrid={r.relation_id:r.status for r in final.itertuples()}
    coverage=[]
    for x in inventory:
        status=byrid.get(x['relation_id'],'candidate_pending' if x.get('named')==5 else 'candidate_mapping_incomplete')
        coverage.append(dict(relation_id=x['relation_id'],role=x['role'],status=status))
    pd.DataFrame(coverage).to_csv(N.OUT/'pair_coverage_40.csv',index=False,encoding='utf-8-sig')
    failures=[]
    for r in rows[(rows.kind=='fresh_boundary_equivalence')&(rows.status=='refuted')].itertuples():
        item=plan['selected'][int(r.pair_index)];slot=int(r.pattern)
        failures.append(dict(pair_index=int(r.pair_index),source_view=item['source_view'],partner_view=item['partner'],
            source_net=item['source_nets'][slot],candidate_net=item['mapped_nets'][slot],origin=item['mapping_origins'][slot],
            rejection_scope='not equal under current source-bound physical-Q/PI context; old P1 semantics not retroactively falsified',
            witness=r.witness))
    pd.DataFrame(failures).to_csv(N.OUT/'rejected_candidates.csv',index=False,encoding='utf-8-sig')
    summary=dict(total_relations=40,validated_pairs=len(indices),validated_by_role=success.role.value_counts().to_dict(),
        coverage_status=pd.Series([x['status'] for x in coverage]).value_counts().to_dict(),
        source_migration_agrees=int(success.old_context_migration_equal.sum()),feature_max_abs_diff=float(np.abs(fa-fb).max()),
        distinct_validated_feature_profiles=len(np.unique(fa,axis=0)),subqueries=len(rows),
        status_counts=rows.status.value_counts().to_dict(),review_agreement=int((rows[rows.kind.isin(['review','alias_review'])].status==rows[rows.kind.isin(['review','alias_review'])].original_status).sum()),
        reviews=int(rows.kind.isin(['review','alias_review']).sum()),independent_replays=len(replay_rows),
        legacy_candidate_refutations=sum(x['origin']=='legacy_P1_candidate' for x in failures),
        same_name_candidate_refutations=sum(x['origin']=='same_name_unproved' for x in failures),
        graph_attachments=sum(x['graph_mapping_ok'] for x in attachments),graph_attachment_records=len(attachments),
        PI_anchor_records=sum(x['graph_mapping_kind']=='PI_anchor_no_cell' for x in attachments),
        per_input_stats_max_abs_diff=0.,
        training_runs=0,safety_labels_copied=False,test_evaluated=False)
    (N.OUT/'audit_manifest.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':main()
