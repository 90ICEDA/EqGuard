"""Repair only local alias candidates in the eight already-frozen pairs.

No new targets, simulation search, labels, or whole-netlist SAT sweeping.
Candidate alternatives and budget are written before the additional queries.
"""
import hashlib
import itertools
import json
import sys
from datetime import datetime
import numpy as np
import pandas as pd
import native as N
from run_pilot import table_wrapper,truth

sys.path.insert(0,str(N.ROOT/'_p0pilot/round9_20261025'))
from boundary_repr import COLS,parse_table,summarize,canonical


def module(view):
    folder=N.OUT/'structures'/view
    provenance=json.loads((folder/'source.json').read_text())
    assert provenance['source_sha']==N.sha(N.WORK/'trans'/(view+'.v'))
    assert provenance['raw_sha']==N.sha(folder/'raw.json')
    return next(iter(json.loads((folder/'raw.json').read_text())['modules'].values()))


def main():
    plan=json.loads((N.OUT/'plan.json').read_text());previous=pd.read_csv(N.OUT/'queries.csv',dtype={'pattern':str})
    N.ROWS=previous.to_dict('records')
    old_outcomes=pd.read_csv(N.OUT/'pilot_outcomes.csv')
    proposals=[]
    for i,item in enumerate(plan['selected']):
        if old_outcomes.iloc[i].status!='boundary_not_proved':continue
        proof=previous[(previous.pair_index==i)&(previous.kind=='fresh_boundary_equivalence')]
        failed=[int(r.pattern) for r in proof.itertuples() if r.status!='proved']
        a,b=module(item['source_view']),module(item['partner'])
        alternatives={}
        for j in failed:
            net=item['source_nets'][j];bits=a['netnames'].get(net,a['ports'].get(net,{})).get('bits')
            names=[n for n,info in a['netnames'].items() if info['bits']==bits and n in b['netnames']
                   and n!=item['mapped_nets'][j] and len(bits)==1]
            names.sort(key=lambda n:(n!=net,hashlib.sha256(('r10alias|'+n).encode()).hexdigest()))
            alternatives[str(j)]=names[:2]
        proposals.append(dict(pair_index=i,role=item['role'],failed_slots=failed,alternatives=alternatives,
            can_attempt=all(alternatives[str(j)] for j in failed)))
    proposals.sort(key=lambda x:(x['role']!='val',len(x['failed_slots']),x['pair_index']))
    repair_plan=dict(created=datetime.now().astimezone().isoformat(),proposals=proposals,
        rule='source-snapshot same-bit aliases present in frozen partner; same original alias first, then fixed hash; <=2 alternatives/failed slot',
        max_alias_queries=24,max_additional_tables=4,overall_query_cap=576,source_relations_unchanged=True)
    (N.OUT/'alias_repair_plan.json').write_text(json.dumps(repair_plan,ensure_ascii=False,indent=2),encoding='utf-8')
    results=[];new_tables=[];alias_used=0;paired=0;review_candidates=[]
    originals={r.relation_id:r for rd,folder in [('r5','sat_nonlocal_round5'),('r6','sat_expand_round6'),('r7','sat_repair_round7')]
        for r in pd.read_csv(N.OUT.parent/folder/f'{rd}_nonlocal_relations.csv').itertuples()}
    for proposal in proposals:
        i=proposal['pair_index'];item=plan['selected'][i]
        base=dict(pair_index=i,relation_id=item['relation_id'],role=item['role'],source_view=item['source_view'],partner_view=item['partner'])
        if not proposal['can_attempt']:
            results.append(dict(**base,status='local_alias_unavailable'));continue
        if paired>=4 or alias_used>=24:
            results.append(dict(**base,status='repair_budget_not_attempted'));continue
        a,b=module(item['source_view']),module(item['partner'])
        mapped=list(item['mapped_nets']);success=True
        for j in proposal['failed_slots']:
            accepted=False
            for attempt,name in enumerate(proposal['alternatives'][str(j)]):
                if alias_used>=24:break
                trial=list(mapped);trial[j]=name
                ca,sa=N.emit(a,'left_design',item['source_nets']);cb,sb=N.emit(b,'right_design',trial)
                code=ca+'\n'+cb+f'''\nmodule check(input [{sa['width']-1}:0] env,output mismatch);
wire [4:0] a,b;wire [{len(sa['obs'])-1}:0] oa,ob;
left_design l(env,a,oa);right_design r(env,b,ob);assign mismatch=a[{j}]^b[{j}];endmodule
'''
                row=N.run(N.OUT/'alias_repairs'/str(i)/f'slot{j}_try{attempt}',code,[dict(pair_index=i,kind='alias_equivalence',pattern=str(j),prove=0,
                    source_alias=item['source_nets'][j],partner_alias=name,args='-prove mismatch 0')])[0]
                alias_used+=1
                if row['status']=='proved':
                    mapped=trial;accepted=True;review_candidates.append(row);break
            if not accepted:success=False;break
        if not success:
            results.append(dict(**base,status='alias_not_proved'));continue
        if len(N.ROWS)+64+len(review_candidates)>576:
            results.append(dict(**base,status='table_budget_not_attempted'));continue
        ca,sa=N.emit(a,'left_design',item['source_nets']);cb,sb=N.emit(b,'right_design',mapped)
        measured=[]
        for label,code,name,spec in [('source',ca,'left_design',sa),('partner',cb,'right_design',sb)]:
            qs=[dict(pair_index=i,kind='repair_aligned_'+label,pattern=p,prove=v,
                args=f"-set pattern 4'b{''.join(reversed(p))} -set premise 1 -prove target {v}")
                for p in map(''.join,itertools.product('01',repeat=4)) for v in (1,0)]
            rows=N.run(N.OUT/'alias_repairs'/str(i)/label,table_wrapper(code,name,spec),qs)
            t=truth(rows);measured.append(t);desc,per=summarize(t,4)
            new_tables.append(dict(pair_index=i,side=label,view=item['source_view'] if label=='source' else item['partner'],
                relation_id=item['relation_id'],context_id=json.loads((N.OUT/'aligned_context.json').read_text())['context_id'],
                truth=t,features=desc,inputs=per,source_sha=N.sha(N.WORK/'trans'/((item['source_view'] if label=='source' else item['partner'])+'.v'))))
        fa=summarize(measured[0],4)[0];fb=summarize(measured[1],4)[0]
        results.append(dict(**base,status='paired_validated' if measured[0]==measured[1] else 'paired_table_mismatch',
            old_context_migration_equal=measured[0]==parse_table(originals[item['relation_id']].truth_table,4),
            identical_named_order_truth=measured[0]==measured[1],feature_max_abs_diff=max(abs(fa[c]-fb[c]) for c in COLS),
            repaired_mapping=mapped,canonical_equal=canonical(measured[0],4)['signature']==canonical(measured[1],4)['signature']))
        paired+=1
    reviews=[]
    for j,q in enumerate(review_candidates):
        row=N.run(N.OUT/'alias_reviews'/str(j),(N.ROOT/q['folder']/'model.v').read_text(),[
            dict(pair_index=q['pair_index'],kind='alias_review',pattern=q['pattern'],prove=0,args=q['args'],original_status=q['status'])])[0]
        reviews.append(row)
    pd.DataFrame(N.ROWS).to_csv(N.OUT/'queries_with_repairs.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(results).to_csv(N.OUT/'alias_repair_outcomes.csv',index=False,encoding='utf-8-sig')
    old_tables=json.loads((N.OUT/'aligned_tables.json').read_text())
    (N.OUT/'all_aligned_tables.json').write_text(json.dumps(old_tables+new_tables,ensure_ascii=False,indent=2),encoding='utf-8')
    summary=dict(alias_queries=alias_used,additional_paired_tables=paired,outcomes=pd.Series([r['status'] for r in results]).value_counts().to_dict(),
        review_queries=len(reviews),review_agree=sum(r['status']==r['original_status'] for r in reviews),
        total_subqueries=len(N.ROWS),overall_cap=576,training_runs=0)
    (N.OUT/'alias_repair_manifest.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':main()
