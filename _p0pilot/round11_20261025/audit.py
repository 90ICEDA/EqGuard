"""Cumulative source-bound audit, independent replay, blockers and pair registry."""
import ast
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'_p0pilot/round10_20261025'))
import native as N
spec=importlib.util.spec_from_file_location('r10_independent_replay',ROOT/'_p0pilot/round10_20261025/audit.py')
R=importlib.util.module_from_spec(spec);spec.loader.exec_module(R)
sys.path.insert(0,str(ROOT/'_p0pilot/round9_20261025'))
from boundary_repr import COLS
from prepare import drivers
OLD=N.OUT;OUT=OLD.parent/'sat_pair_round11'


def snapshot(view):
    for root in [OLD,OUT]:
        folder=root/'structures'/view
        if (folder/'source.json').exists():
            p=json.loads((folder/'source.json').read_text())
            assert p['source_sha']==N.sha(N.WORK/'trans'/(view+'.v')) and p['raw_sha']==N.sha(folder/'raw.json')
            return next(iter(json.loads((folder/'raw.json').read_text())['modules'].values()))
    raise ValueError('missing source snapshot')


def main():
    rows=pd.read_csv(OUT/'queries_batch3.csv',dtype={'pattern':str})
    rows['batch_id']=rows.batch_id.fillna(1).astype(int)
    assert len(rows)<=576 and not rows.duplicated(['folder','query_id']).any()
    disk_logs=list(OUT.rglob('*.query.log'))
    assert len(disk_logs)==len(rows), 'Every executed query, including recovered batch, must be counted exactly once'
    provenance=json.loads((OLD/'provenance.json').read_text())
    assert N.sha(Path(N.__file__))==provenance['source_code_sha']['native.py']
    for q in rows.itertuples():
        f=ROOT/q.folder
        assert N.sha(f/'model.v')==q.model_sha and N.sha(f/'run.log')==q.log_sha
        assert hashlib.sha256((f/'run.ys').read_text().encode()).hexdigest()==q.script_sha
        command=f'sat {q.args} -timeout 5 -show-inputs -show-outputs -dump_json "{N.P0.wsl(f/(str(int(q.query_id))+".model.json"))}"'
        sat_lines=[ln for ln in (f/'run.ys').read_text().splitlines() if ln.startswith('sat ')]
        assert sat_lines[int(q.query_id)]==command
        if q.status=='refuted':assert (ROOT/q.witness).exists()
    plans={};outcomes=[];tables=[];registries={};reused=[]
    for phase in [1,2,3]:
        suffix='' if phase==1 else f'_batch{phase}'
        p=json.loads((OUT/f'plan{suffix}.json').read_text());expected=p.pop('plan_sha256')
        assert hashlib.sha256(json.dumps(p,ensure_ascii=False,sort_keys=True).encode()).hexdigest()==expected
        plans[phase]=p
        for x in pd.read_csv(OUT/f'outcomes{suffix}.csv').to_dict('records'):
            x['batch_id']=phase;outcomes.append(x)
        for x in json.loads((OUT/f'aligned_tables{suffix}.json').read_text()):x['batch_id']=phase;tables.append(x)
        registries[phase]=pd.read_csv(OUT/f'proof_registry{suffix}.csv')
        f=OUT/f'reused_evidence{suffix}.csv'
        if f.stat().st_size>5:
            for x in pd.read_csv(f).to_dict('records'):x['batch_id']=phase;reused.append(x)
    assert len(outcomes)==24 and len({x['relation_id'] for x in outcomes})==24
    validated=[x for x in outcomes if x['status']=='paired_validated'];replays=[];proofs=[];payload=[];attachments=[]
    lookup={(x['batch_id'],x['pair_index'],x['side']):x for x in tables}
    context=json.loads((OUT/'aligned_context.json').read_text())
    for x in outcomes:
        phase,i=x['batch_id'],int(x['pair_index']);item=plans[phase]['selected'][i]
        q=rows[(rows.batch_id==phase)&(rows.pair_index==i)&(rows.kind=='boundary_equivalence')&(rows.status=='refuted')]
        if not q.empty:
            q=q.iloc[0];source,partner=snapshot(item['source_view']),snapshot(item['partner'])
            env=next(s['data'][0] for s in json.loads((ROOT/q.witness).read_text())['signal'] if s['name']=='env')
            j=int(q.pattern);a=R.replay(source,env);b=R.replay(partner,env)
            sa=source['netnames'][item['source_nets'][j]]['bits'][0];sb=partner['netnames'][q.partner_net]['bits'][0]
            assert a[sa] is not None and b[sb] is not None and a[sa]!=b[sb]
            replays.append(dict(batch_id=phase,pair_index=i,kind='rejected_mapping',slot=j,passed=True))
        if x['status']!='paired_validated':continue
        mapped=ast.literal_eval(x['mapped_nets'])
        a=lookup[(phase,i,'source')];b=lookup[(phase,i,'partner')]
        assert a['truth']==b['truth'] and a['features']==b['features'] and a['inputs']==b['inputs']
        assert x['old_context_migration_equal']
        for side,view,nets in [('source',item['source_view'],item['source_nets']),('partner',item['partner'],mapped)]:
            m=snapshot(view)
            q=rows[(rows.batch_id==phase)&(rows.pair_index==i)&(rows.kind=='aligned_'+side)&(rows.status=='refuted')].iloc[0]
            env=next(s['data'][0] for s in json.loads((ROOT/q.witness).read_text())['signal'] if s['name']=='env')
            values=R.replay(m,env);bits=[m['netnames'][n]['bits'][0] for n in nets]
            assert ''.join(str(values[b]) for b in bits[:4])==q.pattern and values[bits[4]]==1-int(q.prove)
            replays.append(dict(batch_id=phase,pair_index=i,kind='table_'+side,passed=True))
            for j,(n,bit) in enumerate(zip(nets,bits)):
                ds=drivers(m,bit);pi=[f'{pn}[{k}]' for pn,p in m['ports'].items() if p['direction']=='input' for k,b in enumerate(p['bits']) if b==bit]
                attachments.append(dict(batch_id=phase,pair_index=i,side=side,view=view,slot=j,net=n,bit=bit,
                    driver=ds[0][0] if len(ds)==1 else '',pin=ds[0][1] if len(ds)==1 else '',PI_anchor=';'.join(pi)))
        reg=registries[phase]
        for j in range(5):
            good=reg[(reg.pair_index==i)&(reg.slot==j)&(reg.status=='proved')&(reg.partner_net==mapped[j])]
            assert len(good)>=1
            q=good.iloc[-1];f=ROOT/q.folder
            assert 'no model found: SUCCESS' in (f/f'{int(q.query_id)}.query.log').read_text()
            proofs.append(dict(batch_id=phase,pair_index=i,relation_id=x['relation_id'],slot=j,
                source_view=item['source_view'],partner_view=item['partner'],source_net=item['source_nets'][j],partner_net=mapped[j],
                proof_folder=q.folder,query_id=int(q.query_id),proof_origin=q.origin,status='proved',training_pair_allowed=False))
        payload.append(dict(pair_key=f'r11b{phase}p{i}',relation_id=x['relation_id'],role=x['role'],
            source_view=item['source_view'],partner_view=item['partner'],source_nets=item['source_nets'],partner_nets=mapped,
            source_sha=N.sha(N.WORK/'trans'/(item['source_view']+'.v')),partner_sha=N.sha(N.WORK/'trans'/(item['partner']+'.v')),
            context_id=context['context_id'],complete_truth_equal=True,feature_max_abs_diff=0.,
            old_context_boundary_table_equal=True,fresh_PO_D_equivalence=x['global_equivalence'],training_pair_allowed=False))
    pd.DataFrame(replays).to_csv(OUT/'independent_replays.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(proofs).to_csv(OUT/'validated_signal_pairs.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(outcomes).to_csv(OUT/'all_outcomes.csv',index=False,encoding='utf-8-sig')
    # Map exactly the cells/PI anchors, no fabricated drivers for primary inputs.
    fids=json.loads((N.WORK/'data/for_train/metadata_trans.json').read_text())['file_ids']
    wanted={(x['view'],x['driver']) for x in attachments if x['driver']};names={n for v,n in wanted};hits={}
    with (N.WORK/'data/processed/node_names_trans.txt').open(encoding='utf-8') as f:
        for i,line in enumerate(f):
            n=line.strip().lstrip('\\')
            if n in names and (fids[i],n) in wanted:
                assert (fids[i],n) not in hits;hits[(fids[i],n)]=i
    for x in attachments:x['node_index']=hits.get((x['view'],x['driver']),-1)
    pd.DataFrame(attachments).to_csv(OUT/'boundary_attachments.csv',index=False,encoding='utf-8-sig')
    # Every old status is preserved except the 24 pending candidates examined here.
    oldcov=pd.read_csv(OLD/'pair_coverage_40.csv');byid={x['relation_id']:x for x in outcomes};coverage=[];blockers=[]
    for old in oldcov.to_dict('records'):
        rid=old['relation_id'];x=byid.get(rid);status=x['status'] if x else old['status']
        if x and status=='boundary_not_proved':
            item=plans[x['batch_id']]['selected'][int(x['pair_index'])];j=int(x['failed_slot']);signal=item['source_nets'][j]
            status='temporary_alias_correspondence_unproved' if signal.startswith('_') else 'boundary_correspondence_unproved'
            blockers.append(dict(relation_id=rid,role=old['role'],category=status,failed_slot=j,source_net=signal,
                tried=item['alternatives'][j],partner=item['partner'],note='mapping not proved, not evidence of feature instability'))
        elif status not in ('paired_validated',):
            blockers.append(dict(relation_id=rid,role=old['role'],category=status,note='retain missing boundary/alias/state issue separately'))
        coverage.append(dict(relation_id=rid,role=old['role'],status=status,updated_round=11 if x else 10))
    pd.DataFrame(coverage).to_csv(OUT/'pair_coverage_40.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(blockers).to_csv(OUT/'blocking_issues.csv',index=False,encoding='utf-8-sig')
    oldpayload=json.loads((OLD/'validated_pairs.json').read_text());combined=oldpayload+payload
    assert len({x['relation_id'] for x in combined})==len(combined)
    (OUT/'validated_pairs_new.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'validated_pairs_cumulative.json').write_text(json.dumps(combined,ensure_ascii=False,indent=2),encoding='utf-8')
    fa=np.array([[lookup[(x['batch_id'],int(x['pair_index']),'source')]['features'][c] for c in COLS] for x in validated],np.float32)
    fb=np.array([[lookup[(x['batch_id'],int(x['pair_index']),'partner')]['features'][c] for c in COLS] for x in validated],np.float32)
    assert np.array_equal(fa,fb) and np.isfinite(fa).all() and fa.min()>=0 and fa.max()<=1
    np.savez_compressed(OUT/'paired_features_new.npz',source=fa,partner=fb)
    review=rows[rows.kind=='review'];assert (review.status==review.original_status).all()
    summary=dict(examined_candidates=24,batches=3,new_validated=len(payload),new_validated_by_role=pd.Series([x['role'] for x in payload]).value_counts().to_dict(),
        cumulative_validated=len(combined),cumulative_by_role=pd.Series([x['role'] for x in combined]).value_counts().to_dict(),
        coverage_status=pd.Series([x['status'] for x in coverage]).value_counts().to_dict(),new_sat_queries=len(rows),
        status_counts=rows.status.value_counts().to_dict(),reviews=len(review),review_agree=len(review),
        independent_replays=len(replays),new_signal_proofs=len(proofs),reused_reference_count=len(reused),
        reused_unique_proofs=len({(x['folder'],x['query_id']) for x in reused}),
        feature_max_abs_diff=0.,new_distinct_feature_profiles=len(np.unique(fa,axis=0)),
        source_migration_agree=sum(bool(x['old_context_migration_equal']) for x in validated),
        graph_nodes_mapped=sum(x['node_index']>=0 for x in attachments),PI_anchor_records=sum(bool(x['PI_anchor']) for x in attachments),
        failed_mapping_relations=len([x for x in outcomes if x['status']=='boundary_not_proved']),
        recovered_query_records=int(rows.get('recovered_from_immutable_log',pd.Series(False,index=rows.index)).fillna(False).sum()),
        training_runs=0,test_evaluated=False,source_relations_added=0)
    (OUT/'audit_manifest.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':main()
