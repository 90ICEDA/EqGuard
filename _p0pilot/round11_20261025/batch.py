"""Next eight of the existing 24 candidates. No new relation/source search.

Reuse only source-bound native-context proofs. Old P1 remains a locator.
Aliases are source-snapshot same-bit names in the already-fixed partner.
"""
import hashlib
import itertools
import json
import sys
from datetime import datetime
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'_p0pilot/round10_20261025'))
import native as N
from run_pilot import truth,table_wrapper
sys.path.insert(0,str(ROOT/'_p0pilot/round9_20261025'))
from boundary_repr import COLS,parse_table,summarize

OLD=N.OUT
OUT=OLD.parent/'sat_pair_round11'
N.OUT=OUT
OUT.mkdir(parents=True,exist_ok=True)
_native_run=N.run


def checked_run(folder,code,queries):
    """Recover only identical already-executed queries; never overwrite/re-solve."""
    if not (folder/'run.log').exists():return _native_run(folder,code,queries)
    assert (folder/'model.v').read_text()==code
    commands=[f'read_verilog "{N.P0.wsl(folder/"model.v")}"','hierarchy -top check','proc','flatten','opt_clean']
    for i,q in enumerate(queries):
        commands += [f'log Q{i:04d}',f'sat {q["args"]} -timeout 5 -show-inputs -show-outputs -dump_json "{N.P0.wsl(folder/(str(i)+".model.json"))}"']
    assert (folder/'run.ys').read_text()=='\n'.join(commands)+'\n'
    blocks={};current=None
    for line in (folder/'run.log').read_text().splitlines():
        if line.startswith('Q') and len(line)==5 and line[1:].isdigit():current=int(line[1:]);blocks[current]=[]
        elif current is not None:blocks[current].append(line)
    result=[]
    for i,q in enumerate(queries):
        text=(folder/f'{i}.query.log').read_text()
        assert text.splitlines()[0]==q['args']
        assert text.split('\n',1)[1]=='\n'.join(blocks[i])
        status='proved' if 'no model found: SUCCESS' in text else 'refuted' if 'model found: FAIL' in text else 'unknown'
        assert 'ERROR:' not in (folder/'run.log').read_text()
        row=dict(**q,status=status,timeout='TIMEOUT' in text,query_id=i,folder=str(folder.relative_to(ROOT)),
            model_sha=N.sha(folder/'model.v'),script_sha=hashlib.sha256((folder/'run.ys').read_text().encode()).hexdigest(),
            log_sha=N.sha(folder/'run.log'),witness=str((folder/f'{i}.model.json').relative_to(ROOT)) if (folder/f'{i}.model.json').exists() else '',
            recovered_from_immutable_log=True)
        N.ROWS.append(row);result.append(row)
    return result


N.run=checked_run


def h(x):return hashlib.sha256(('r11|'+x).encode()).hexdigest()


def load(view):
    if view in N.MODULES:return N.MODULES[view]
    for root in [OLD,OUT]:
        p=root/'structures'/view
        if (p/'source.json').exists():
            info=json.loads((p/'source.json').read_text())
            assert info['source_sha']==N.sha(N.WORK/'trans'/(view+'.v')) and info['raw_sha']==N.sha(p/'raw.json')
            m=next(iter(json.loads((p/'raw.json').read_text())['modules'].values()))
            N.MODULES[view]=m;return m
    return N.load(view)


def at(m,name):return m['netnames'].get(name,m['ports'].get(name,{}))['bits'][0]


def eq_code(ca,sa,cb):
    return ca+'\n'+cb+f'''\nmodule check(input [{sa['width']-1}:0] env,output [4:0] delta,output observation_diff);
wire [4:0] a,b;wire [{len(sa['obs'])-1}:0] oa,ob;
left_design l(env,a,oa);right_design r(env,b,ob);assign delta=a^b;assign observation_diff=|(oa^ob);endmodule
'''


def main():
    phase=int(sys.argv[1]) if len(sys.argv)>1 else 1
    suffix='' if phase==1 else f'_batch{phase}'
    if (OUT/f'queries{suffix}.csv').exists():raise RuntimeError('Use a fresh batch; existing results are immutable')
    if phase>1:
        previous='' if phase==2 else f'_batch{phase-1}'
        N.ROWS=pd.read_csv(OUT/f'queries{previous}.csv',dtype={'pattern':str}).to_dict('records')
        for q in N.ROWS:q.setdefault('batch_id',1)
    prior_count=len(N.ROWS)
    previous_plan=json.loads((OLD/'plan.json').read_text());saved=previous_plan.pop('plan_sha256')
    assert hashlib.sha256(json.dumps(previous_plan,sort_keys=True,ensure_ascii=False).encode()).hexdigest()==saved
    pending=set(pd.read_csv(OLD/'pair_coverage_40.csv').query("status=='candidate_pending'").relation_id)
    pool=[x for x in previous_plan['inventory'] if x['relation_id'] in pending]
    for earlier in range(1,phase):
        oldsuffix='' if earlier==1 else f'_batch{earlier}'
        used={x['relation_id'] for x in json.loads((OUT/f'plan{oldsuffix}.json').read_text())['selected']}
        pool=[x for x in pool if x['relation_id'] not in used]
    selected=[x for x in pool if x['role']=='val']
    # Cover three training hosts first, then a distinct reused source view.
    train=sorted([x for x in pool if x['role']=='train'],key=lambda x:(-x['variant_equal'],-x['legacy'],h(x['relation_id'])))
    seen_hosts=set();seen_views=set()
    quota=8-len(selected)
    for diversity in ['host','view','any']:
        for x in train:
            if sum(t['role']=='train' for t in selected)>=quota:break
            host=x['source_view'].split('__')[0]
            if x in selected or (diversity!='any' and x['source_view'] in seen_views) or (diversity=='host' and host in seen_hosts):continue
            selected.append(x);seen_hosts.add(host);seen_views.add(x['source_view'])
    selected.sort(key=lambda x:(x['role']!='val',h(x['relation_id'])))
    context=json.loads((OLD/'aligned_context.json').read_text())
    proof_cache={};global_cache={};reused=[];source_reuse=[]
    oldq=pd.read_csv(OLD/'queries_with_repairs.csv',dtype={'pattern':str})
    # Validate cached proof files before accepting their statuses, including negative examples.
    for r in oldq[oldq.kind.isin(['fresh_boundary_equivalence','fresh_PO_D_equivalence','alias_equivalence'])].itertuples():
        item=previous_plan['selected'][int(r.pair_index)]
        a,b=load(item['source_view']),load(item['partner'])
        folder=ROOT/r.folder
        assert N.sha(folder/'model.v')==r.model_sha and N.sha(folder/'run.log')==r.log_sha
        ref=dict(status=r.status,folder=r.folder,query_id=int(r.query_id),origin='round10_source_bound_native')
        key=(item['source_view'],item['partner'])
        if r.kind=='fresh_PO_D_equivalence':global_cache[key]=ref;continue
        j=int(r.pattern)
        dst=r.partner_alias if r.kind=='alias_equivalence' else item['mapped_nets'][j]
        proof_cache[key+(at(a,item['source_nets'][j]),at(b,dst))]=ref
    for earlier in range(1,phase):
        oldsuffix='' if earlier==1 else f'_batch{earlier}'
        items=json.loads((OUT/f'plan{oldsuffix}.json').read_text())['selected']
        for r in pd.read_csv(OUT/f'proof_registry{oldsuffix}.csv').itertuples():
            item=items[int(r.pair_index)];a,b=load(item['source_view']),load(item['partner'])
            proof_cache[(item['source_view'],item['partner'],at(a,r.source_net),at(b,r.partner_net))]=dict(
                status=r.status,folder=r.folder,query_id=int(r.query_id),origin='round11_prior_batch_source_bound')
    prepared=[]
    for item in selected:
        a,b=load(item['source_view']),load(item['partner'])
        alternatives=[]
        for source,old_candidate in zip(item['source_nets'],item['mapped_nets']):
            source_bit=at(a,source)
            aliases={n for n,z in a['netnames'].items() if z['bits']==[source_bit] and n in b['netnames']}
            candidates=aliases|{old_candidate}
            ranked=[]
            for name in candidates:
                if name not in b['netnames']:continue
                ref=proof_cache.get((item['source_view'],item['partner'],source_bit,at(b,name)))
                if ref and ref['status']=='refuted':continue
                rank=(not(ref and ref['status']=='proved'),name!=source,name not in aliases,h(name))
                ranked.append((rank,name))
            alternatives.append([name for rank,name in sorted(ranked)][:2])
        prepared.append(dict(**item,alternatives=alternatives))
        for view in (item['source_view'],item['partner']):
            p=OLD/'structures'/view
            current=p if (p/'source.json').exists() else OUT/'structures'/view
            source_reuse.append(dict(view=view,snapshot=str(current.relative_to(ROOT)),reused=(current==p),
                source_sha=N.sha(N.WORK/'trans'/(view+'.v')),raw_sha=N.sha(current/'raw.json')))
    plan=dict(created=datetime.now().astimezone().isoformat(),selected=prepared,remaining_input_count=len(pool),
        context=context,prior_plan_sha=saved,
        selection='all four pending val; training host diversity then distinct views, variant/P1 locator coverage and fixed hash',
        alternatives='source same-bit aliases in fixed partner or previous candidate; no broad search; <=2 per slot',
        budget=dict(new_sat_queries=576,max_review=16,wall_s=1800),training_runs=0)
    plan['plan_sha256']=hashlib.sha256(json.dumps(plan,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    plan['batch_id']=phase;plan['queries_before_batch']=prior_count
    plan.pop('plan_sha256');plan['plan_sha256']=hashlib.sha256(json.dumps(plan,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    plan_path=OUT/f'plan{suffix}.json'
    if plan_path.exists():
        prior_plan=json.loads(plan_path.read_text())
        assert prior_plan['selected']==plan['selected'] and prior_plan.get('queries_before_batch',0)==prior_count
        plan=prior_plan  # retain the actual pre-query timestamp/hash
    else:plan_path.write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
    pd.DataFrame(source_reuse).drop_duplicates('view').to_csv(OUT/f'source_snapshots{suffix}.csv',index=False,encoding='utf-8-sig')
    (OUT/'aligned_context.json').write_text(json.dumps(context,indent=2),encoding='utf-8')
    originals={r.relation_id:r for rd,folder in [('r5','sat_nonlocal_round5'),('r6','sat_expand_round6'),('r7','sat_repair_round7')]
        for r in pd.read_csv(OLD.parent/folder/f'{rd}_nonlocal_relations.csv').itertuples()}
    outcomes=[];tables=[];proofs=[];review=[]
    pair_root=OUT/('pairs' if phase==1 else f'pairs_batch{phase}')
    for i,item in enumerate(prepared):
        a,b=load(item['source_view']),load(item['partner'])
        base=dict(pair_index=i,relation_id=item['relation_id'],role=item['role'],source_view=item['source_view'],partner_view=item['partner'])
        if len(N.ROWS)+22>576:
            outcomes.append(dict(**base,status='query_budget_not_attempted'));continue
        mapped=[xs[0] if xs else None for xs in item['alternatives']]
        if any(n is None for n in mapped):outcomes.append(dict(**base,status='local_alias_unavailable'));continue
        try:
            ca,sa=N.emit(a,'left_design',item['source_nets']);cb,sb=N.emit(b,'right_design',mapped)
            if (sa['ports'],sa['states'],sa['obs'])!=(sb['ports'],sb['states'],sb['obs']):
                outcomes.append(dict(**base,status='state_or_interface_mismatch'));continue
        except (ValueError,KeyError) as e:outcomes.append(dict(**base,status='model_error',reason=str(e)));continue
        success=True
        for j in range(5):
            accepted=False
            for attempt,name in enumerate(item['alternatives'][j]):
                mapped[j]=name
                cache_key=(item['source_view'],item['partner'],at(a,item['source_nets'][j]),at(b,name))
                ref=proof_cache.get(cache_key)
                if ref and ref['status']=='proved':
                    reused.append(dict(pair_index=i,slot=j,source=item['source_nets'][j],partner=name,**ref));accepted=True
                else:
                    cb,sb=N.emit(b,'right_design',mapped)
                    q=N.run(pair_root/str(i)/f'slot{j}_try{attempt}',eq_code(ca,sa,cb),[
                        dict(pair_index=i,kind='boundary_equivalence',pattern=str(j),prove=0,partner_net=name,args=f'-prove delta[{j}] 0')])[0]
                    ref=dict(status=q['status'],folder=q['folder'],query_id=q['query_id'],origin='round11_fresh')
                    proof_cache[cache_key]=ref
                    if q['status']=='proved':accepted=True;review.append(q)
                proofs.append(dict(pair_index=i,slot=j,source_net=item['source_nets'][j],partner_net=name,**ref))
                if accepted:break
            if not accepted:success=False;break
        if not success:outcomes.append(dict(**base,status='boundary_not_proved',failed_slot=j));continue
        cb,sb=N.emit(b,'right_design',mapped)
        ref=global_cache.get((item['source_view'],item['partner']))
        if not ref or ref['status']!='proved':
            q=N.run(pair_root/str(i)/'PO_D',eq_code(ca,sa,cb),[
                dict(pair_index=i,kind='PO_D_equivalence',pattern='all',prove=0,args='-prove observation_diff 0')])[0]
            ref=dict(status=q['status'],folder=q['folder'],query_id=q['query_id'],origin='round11_fresh')
        else:reused.append(dict(pair_index=i,slot='all_PO_D',**ref))
        if len(N.ROWS)+64+16>576:
            outcomes.append(dict(**base,status='proof_valid_table_budget_pending',mapped_nets=mapped));continue
        measured=[]
        for side,code,name,spec,view in [('source',ca,'left_design',sa,item['source_view']),('partner',cb,'right_design',sb,item['partner'])]:
            qs=[dict(pair_index=i,kind='aligned_'+side,pattern=p,prove=v,
                args=f"-set pattern 4'b{''.join(reversed(p))} -set premise 1 -prove target {v}")
                for p in map(''.join,itertools.product('01',repeat=4)) for v in (1,0)]
            rr=N.run(pair_root/str(i)/side,table_wrapper(code,name,spec),qs)
            t=truth(rr);measured.append(t);desc,inp=summarize(t,4)
            tables.append(dict(pair_index=i,side=side,view=view,relation_id=item['relation_id'],context_id=context['context_id'],
                truth=t,features=desc,inputs=inp,source_sha=N.sha(N.WORK/'trans'/(view+'.v'))))
        fa,ia=summarize(measured[0],4);fb,ib=summarize(measured[1],4)
        good=measured[0]==measured[1] and not any(f=='unknown' for f,v in measured[0].values())
        outcomes.append(dict(**base,status='paired_validated' if good else 'table_mismatch_or_unknown',mapped_nets=mapped,
            global_equivalence=ref['status'],old_context_migration_equal=measured[0]==parse_table(originals[item['relation_id']].truth_table,4),
            feature_max_abs_diff=max(abs(fa[c]-fb[c]) for c in COLS),input_stats_equal=ia==ib))
        print(json.dumps(outcomes[-1],ensure_ascii=False),flush=True)
    # Persist completed work before reviews so a directory error cannot lose the ledger.
    for q in N.ROWS[prior_count:]:q['batch_id']=phase
    pd.DataFrame(N.ROWS).to_csv(OUT/f'checkpoint_queries{suffix}.csv',index=False,encoding='utf-8-sig')
    # Spread reviews over new proofs, not merely the first relation.
    picked=[]
    for review_pass in (0,1):
        for i in range(len(prepared)):
            options=[q for q in review if q['pair_index']==i]
            if len(options)>review_pass:picked.append(options[review_pass])
    for i,q in enumerate(picked[:16]):
        if len(N.ROWS)>=576:break
        N.run(OUT/('reviews' if phase==1 else f'reviews_batch{phase}')/str(i),(ROOT/q['folder']/'model.v').read_text(),[
            dict(pair_index=q['pair_index'],kind='review',pattern=q['pattern'],prove=0,args=q['args'],original_status=q['status'])])
    for q in N.ROWS[prior_count:]:q['batch_id']=phase
    pd.DataFrame(N.ROWS).to_csv(OUT/f'queries{suffix}.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(outcomes).to_csv(OUT/f'outcomes{suffix}.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(proofs).to_csv(OUT/f'proof_registry{suffix}.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(reused).to_csv(OUT/f'reused_evidence{suffix}.csv',index=False,encoding='utf-8-sig')
    (OUT/f'aligned_tables{suffix}.json').write_text(json.dumps(tables,ensure_ascii=False,indent=2),encoding='utf-8')
    summary=dict(selected=len(prepared),outcomes=pd.Series([x['status'] for x in outcomes]).value_counts().to_dict(),
        new_sat_queries=len(N.ROWS)-prior_count,cumulative_new_sat_queries=len(N.ROWS),budget=576,reused_proofs=len(reused),training_runs=0)
    (OUT/f'manifest{suffix}.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':main()
